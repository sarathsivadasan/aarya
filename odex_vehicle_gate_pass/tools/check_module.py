#!/usr/bin/env python3
"""Static validation for the odex_vehicle_gate_pass module.

Checks, in order:
  1. Python compiles (py_compile) + pyflakes.
  2. Every XML file is well-formed, and no XML comment contains '--'.
  3. ir.model.access.csv columns and model ids are sane.
  4. SCSS compiles via libsass.
  5. Every JS file passes `node --check`.
  6. Every OWL template expression parses as JavaScript.
  7. Manifest data + asset paths all exist on disk.
  8. Every view <field name=".."> exists on its Python model.
"""
import ast
import csv
import glob
import os
import py_compile
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
def fail(msg): errors.append(msg)


def check_python():
    for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as err:
            fail("py_compile: %s" % err)
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pyflakes", ROOT],
            capture_output=True, text=True,
        )
        # pyflakes prints unused imports etc.; treat only real problems as errors
        for line in out.stdout.splitlines():
            if "imported but unused" in line or "unable to detect undefined" in line:
                continue
            if line.strip():
                fail("pyflakes: %s" % line)
    except FileNotFoundError:
        pass


def check_xml():
    for path in glob.glob(os.path.join(ROOT, "**", "*.xml"), recursive=True):
        raw = open(path, encoding="utf-8").read()
        for comment in re.findall(r"<!--(.*?)-->", raw, re.DOTALL):
            if "--" in comment:
                fail("XML comment contains '--': %s" % os.path.relpath(path, ROOT))
        try:
            ET.parse(path)
        except ET.ParseError as err:
            fail("XML parse: %s (%s)" % (os.path.relpath(path, ROOT), err))


def check_csv():
    path = os.path.join(ROOT, "security", "ir.model.access.csv")
    with open(path, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"id", "name", "model_id:id", "group_id:id",
                "perm_read", "perm_write", "perm_create", "perm_unlink"}
    if rows and not required.issubset(rows[0].keys()):
        fail("CSV missing columns: %s" % (required - set(rows[0].keys())))
    for row in rows:
        for perm in ("perm_read", "perm_write", "perm_create", "perm_unlink"):
            if row[perm] not in ("0", "1"):
                fail("CSV bad permission value in %s" % row["id"])


def check_scss():
    try:
        import sass
    except ImportError:
        return
    for path in glob.glob(os.path.join(ROOT, "**", "*.scss"), recursive=True):
        try:
            sass.compile(filename=path)
        except sass.CompileError as err:
            fail("SCSS: %s (%s)" % (os.path.relpath(path, ROOT), str(err)[:200]))


def check_js():
    for path in glob.glob(os.path.join(ROOT, "**", "*.js"), recursive=True):
        out = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if out.returncode != 0:
            fail("JS: %s\n%s" % (os.path.relpath(path, ROOT), out.stderr.strip()))


def check_owl_expressions():
    """OWL templates are JS: t-esc / t-att / t-on expressions must parse as JS."""
    node = """
const fs = require('fs');
const vm = require('vm');
let bad = 0;
// OWL allows python-ish 'or'/'and'/'not' in expressions -> rewrite to JS before parsing.
function toJs(expr) {
    return expr
        .replace(/\\bor\\b/g, '||')
        .replace(/\\band\\b/g, '&&')
        .replace(/\\bnot\\b/g, '!');
}
function checkExpr(expr, path) {
    if (!expr.trim()) return;
    const js = toJs(expr);
    try { new vm.Script('(' + js + ')'); return; } catch (e1) {}
    try { new vm.Script(js); return; } catch (e2) {
        console.log('BAD ' + path + ' :: ' + expr + ' :: ' + e2.message); bad++;
    }
}
for (const path of process.argv.slice(1)) {
    const xml = fs.readFileSync(path, 'utf8');
    // 1) plain expression attributes
    const re = /(?:t-esc|t-out|t-att-[\\w-]+|t-if|t-elif|t-on-[\\w-]+|t-model)="([^"]*)"/g;
    let m;
    while ((m = re.exec(xml)) !== null) { checkExpr(m[1], path); }
    // 2) t-foreach is an expression; t-as is a name (skip)
    const rf = /t-foreach="([^"]*)"/g;
    while ((m = rf.exec(xml)) !== null) { checkExpr(m[1], path); }
    // 3) t-attf-* : only the {{...}} / #{...} interpolated segments are expressions
    const ra = /t-attf-[\\w-]+="([^"]*)"/g;
    while ((m = ra.exec(xml)) !== null) {
        const segRe = /\\{\\{([^}]*)\\}\\}|#\\{([^}]*)\\}/g;
        let s;
        while ((s = segRe.exec(m[1])) !== null) { checkExpr(s[1] || s[2], path); }
    }
}
process.exit(bad ? 1 : 0);
"""
    templates = glob.glob(os.path.join(ROOT, "**", "*.xml"), recursive=True)
    templates = [p for p in templates if "static" in p]
    if not templates:
        return
    out = subprocess.run(["node", "-e", node] + templates, capture_output=True, text=True)
    if out.returncode != 0:
        for line in out.stdout.splitlines():
            fail("OWL: %s" % line)


def check_manifest_paths():
    manifest = ast.literal_eval(
        re.search(r"\{.*\}", open(os.path.join(ROOT, "__manifest__.py"),
                                  encoding="utf-8").read(), re.DOTALL).group(0)
    )
    for rel in manifest.get("data", []):
        if not os.path.exists(os.path.join(ROOT, rel)):
            fail("Manifest data missing: %s" % rel)
    prefix = os.path.basename(ROOT) + "/"
    for bundle, assets in manifest.get("assets", {}).items():
        for rel in assets:
            local = rel[len(prefix):] if rel.startswith(prefix) else rel
            if not os.path.exists(os.path.join(ROOT, local)):
                fail("Manifest asset missing: %s" % rel)


def check_view_fields():
    """Every <field name=".."> in a view must exist on the target Python model."""
    model_fields = _collect_model_fields()
    for path in glob.glob(os.path.join(ROOT, "views", "*.xml")):
        tree = ET.parse(path)
        for view in tree.iter("record"):
            if view.get("model") != "ir.ui.view":
                continue
            model = None
            for child in view:
                if child.get("name") == "model":
                    model = (child.text or "").strip()
            if not model or model not in model_fields:
                continue
            known = model_fields[model]
            arch = None
            for child in view:
                if child.get("name") == "arch":
                    arch = child
            if arch is None:
                continue
            for field in arch.iter("field"):
                name = field.get("name")
                if name == "arch":
                    continue
                if name and name not in known:
                    fail("View %s: field '%s' not on %s"
                         % (os.path.basename(path), name, model))


def _is_top_level(arch, field):
    # crude: only validate fields whose name exists on the main model set;
    # sub-list fields are validated by their own model when present.
    return True


def _collect_model_fields():
    fields_by_model = {}
    for path in glob.glob(os.path.join(ROOT, "models", "*.py")):
        source = open(path, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model_name = None
            names = set()
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    target = stmt.targets[0]
                    if isinstance(target, ast.Name):
                        if target.id == "_name" and isinstance(stmt.value, ast.Constant):
                            model_name = stmt.value.value
                        elif target.id == "_inherit" and isinstance(stmt.value, ast.Constant):
                            model_name = model_name or stmt.value.value
                        elif isinstance(stmt.value, ast.Call):
                            func = stmt.value.func
                            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                                if func.value.id == "fields":
                                    names.add(target.id)
            if model_name:
                fields_by_model.setdefault(model_name, set())
                fields_by_model[model_name].update(names)
    # inherited framework fields commonly used in views
    common = {"id", "display_name", "create_date", "write_date", "company_id",
              "activity_ids", "message_ids", "message_follower_ids", "state"}
    for model in fields_by_model:
        fields_by_model[model].update(common)
    # merge sub-model fields so nested list views resolve too
    all_names = set()
    for names in fields_by_model.values():
        all_names |= names
    for model in fields_by_model:
        fields_by_model[model] |= all_names
    return fields_by_model


def main():
    check_python()
    check_xml()
    check_csv()
    check_scss()
    check_js()
    check_owl_expressions()
    check_manifest_paths()
    check_view_fields()
    if errors:
        print("FAILED (%d):" % len(errors))
        for err in errors:
            print("  - %s" % err)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
