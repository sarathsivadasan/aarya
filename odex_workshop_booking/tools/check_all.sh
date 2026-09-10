#!/bin/sh
# Pre-deploy validation. Run from the module root: sh tools/check_all.sh
# Each check corresponds to a bug that actually reached production in this
# module, so the suite only grows when something slips through.
set -e
echo "1. python syntax"      && python3 -m py_compile $(find . -name '*.py')
echo "2. undefined names"    && python3 tools/check_scope.py
echo "3. model references"   && python3 tools/check_models.py
echo "4. xml well-formed"    && python3 - <<'PY'
import glob, sys
from xml.etree import ElementTree as ET
bad = 0
for f in glob.glob('**/*.xml', recursive=True):
    try:
        ET.parse(f)
    except Exception as e:
        bad = 1
        print('  FAIL', f, e)
sys.exit(bad)
PY
echo "5. manifest files"     && python3 - <<'PY'
import ast, os, sys
m = ast.literal_eval(open('__manifest__.py').read())
missing = [f for f in m['data'] if not os.path.exists(f)]
if missing:
    print('  missing:', missing); sys.exit(1)
PY
echo "ALL CHECKS PASSED"
