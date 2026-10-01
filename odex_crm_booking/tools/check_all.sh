#!/usr/bin/env bash
# Static checks - run before every deploy (pip install libsass pyflakes).
set -e
cd "$(dirname "$0")/.."
echo "[py]   compile";  python3 -m py_compile $(find . -name '*.py' -not -path './tools/*')
echo "[py]   pyflakes"; python3 -m pyflakes $(find . -name '*.py' -not -path './tools/*' -not -name '__init__.py')
echo "[xml]  well-formed / no '--' in comments"
for f in $(find . -name '*.xml'); do
  python3 -c "import sys,lxml.etree as e; e.parse(sys.argv[1])" "$f"
  python3 - "$f" <<'PY'
import re,sys
for c in re.findall(r'<!--(.*?)-->', open(sys.argv[1]).read(), re.S):
    assert '--' not in c, sys.argv[1] + ': -- inside comment'
PY
done
echo "[scss] compile"; python3 -c "import sass,glob;[sass.compile(filename=f) for f in glob.glob('static/src/**/*.scss',recursive=True)]"
echo "[manifest] data files exist"
python3 - <<'PY'
import ast,os
m=ast.literal_eval(open('__manifest__.py').read())
for f in m['data']: assert os.path.exists(f), f
for b in m.get('assets',{}).values():
    for f in b: assert os.path.exists(f.split('/',1)[1]), f
PY
echo "ALL CHECKS PASSED"
