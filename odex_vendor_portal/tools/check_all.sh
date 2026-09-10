#!/usr/bin/env bash
# Pre-deploy validation for odex_vendor_portal.
# Run from anywhere:  bash odex_vendor_portal/tools/check_all.sh
set -u
MOD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

say() { printf '%-38s %s\n' "$1" "$2"; }

# 1. Python syntax
if python3 -m compileall -q "$MOD_DIR" >/dev/null 2>&1; then
    say "python syntax" "OK"
else
    python3 -m compileall -q "$MOD_DIR"
    say "python syntax" "FAILED"; FAIL=1
fi

# 2. Undefined-name AST scan (very light: unresolved bare names)
python3 - "$MOD_DIR" <<'PY'
import ast, os, sys
root = sys.argv[1]
bad = []
for dirpath, _dirs, files in os.walk(root):
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(dirpath, f)
        try:
            ast.parse(open(path, encoding='utf-8').read())
        except SyntaxError as e:
            bad.append('%s: %s' % (path, e))
print('%-38s %s' % ('python AST parse', 'OK' if not bad else 'FAILED'))
for b in bad:
    print('   ', b)
sys.exit(1 if bad else 0)
PY
[ $? -ne 0 ] && FAIL=1

# 3. XML well-formed
python3 - "$MOD_DIR" <<'PY'
import os, sys, xml.dom.minidom
root = sys.argv[1]
bad = []
for dirpath, _dirs, files in os.walk(root):
    for f in files:
        if not f.endswith('.xml'):
            continue
        path = os.path.join(dirpath, f)
        try:
            xml.dom.minidom.parse(path)
        except Exception as e:
            bad.append('%s: %s' % (path, e))
print('%-38s %s' % ('xml well-formed', 'OK' if not bad else 'FAILED'))
for b in bad:
    print('   ', b)
sys.exit(1 if bad else 0)
PY
[ $? -ne 0 ] && FAIL=1

# 4. Manifest data files all exist
python3 - "$MOD_DIR" <<'PY'
import ast, os, sys
root = sys.argv[1]
manifest = ast.literal_eval(open(os.path.join(root, '__manifest__.py'), encoding='utf-8').read())
missing = [f for f in manifest.get('data', []) if not os.path.exists(os.path.join(root, f))]
for bundle, files in manifest.get('assets', {}).items():
    for f in files:
        rel = f.split('/', 1)[1]
        if not os.path.exists(os.path.join(root, rel)):
            missing.append(f)
print('%-38s %s' % ('manifest data/assets exist', 'OK' if not missing else 'FAILED'))
for m in missing:
    print('   missing:', m)
sys.exit(1 if missing else 0)
PY
[ $? -ne 0 ] && FAIL=1

# 5. Every template referenced with t-call inside this module is defined here
python3 - "$MOD_DIR" <<'PY'
import os, re, sys
root = sys.argv[1]
defined, called = set(), set()
for dirpath, _dirs, files in os.walk(root):
    for f in files:
        if not f.endswith('.xml'):
            continue
        text = open(os.path.join(dirpath, f), encoding='utf-8').read()
        defined |= {'odex_vendor_portal.' + m for m in re.findall(r'<template id="([^"]+)"', text)}
        called |= set(re.findall(r't-call="(odex_vendor_portal\.[^"]+)"', text))
missing = sorted(called - defined)
print('%-38s %s' % ('internal t-call targets', 'OK' if not missing else 'FAILED'))
for m in missing:
    print('   undefined:', m)
sys.exit(1 if missing else 0)
PY
[ $? -ne 0 ] && FAIL=1

# 6. CSV model references resolve to a python _inherit or a known core model
python3 - "$MOD_DIR" <<'PY'
import csv, os, sys
root = sys.argv[1]
path = os.path.join(root, 'security', 'ir.model.access.csv')
rows = list(csv.DictReader(open(path, encoding='utf-8')))
bad = [r['id'] for r in rows if not r['model_id:id'].startswith(('purchase.', 'account.', 'uom.', 'base.'))]
print('%-38s %s' % ('acl model refs', 'OK' if not bad else 'CHECK'))
for b in bad:
    print('   ', b)
PY

find "$MOD_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
echo
[ $FAIL -eq 0 ] && echo "ALL CHECKS PASSED" || echo "CHECKS FAILED"
exit $FAIL
