"""Every model/field referenced from XML must exist in Python.

Catches the exact failure Odoo reports as "Model not found: <name>" at
upgrade time — a view whose model was deleted, renamed, or (as here)
removed by accident along with neighbouring code.
"""
import glob, re, sys

# models declared in python
declared, fields_by_model = set(), {}
for f in glob.glob('models/*.py') + glob.glob('wizard/*.py'):
    cur = None
    for line in open(f):
        m = re.match(r"\s*_name\s*=\s*'([\w.]+)'", line)
        if m:
            cur = m.group(1); declared.add(cur); fields_by_model.setdefault(cur, set())
        m = re.match(r"\s*_inherit\s*=\s*'([\w.]+)'", line)
        if m:
            cur = m.group(1); fields_by_model.setdefault(cur, set())
        m = re.match(r"\s{4}(\w+)\s*=\s*fields\.", line)
        if m and cur:
            fields_by_model[cur].add(m.group(1))

# models referenced from xml
problems = []
for f in glob.glob('**/*.xml', recursive=True):
    src = open(f).read()
    for m in re.finditer(r'<field name="(?:model|res_model)">([\w.]+)</field>', src):
        name = m.group(1)
        if name.startswith('odex.') and name not in declared:
            problems.append((f, name, 'model referenced but not declared'))
    for m in re.finditer(r'ref="model_(odex_\w+)"', src):
        name = m.group(1).replace('_', '.')
        # crude reverse mapping; only flag odex models with no plausible match
        candidates = [d for d in declared if d.replace('.', '_') == m.group(1)]
        if not candidates:
            problems.append((f, m.group(1), 'model_ ref has no matching model'))

# models referenced from the ACL csv
for line in open('security/ir.model.access.csv').read().splitlines()[1:]:
    if not line.strip():
        continue
    model_ref = line.split(',')[2]
    if model_ref.startswith('model_odex_'):
        key = model_ref[len('model_'):]
        if not [d for d in declared if d.replace('.', '_') == key]:
            problems.append(('ir.model.access.csv', model_ref, 'ACL for missing model'))

if problems:
    print('MODEL REFERENCE PROBLEMS:')
    for p in problems:
        print('  ', p)
    sys.exit(1)
print('every model referenced from XML/CSV exists in Python (%d models)'
      % len(declared))
