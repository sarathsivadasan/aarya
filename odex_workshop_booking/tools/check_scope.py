import ast, glob, builtins, sys
BUILT = set(dir(builtins))

def collect_scope(fn):
    names = set()
    for sub in ast.walk(fn):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = sub.args
            for x in a.args + a.kwonlyargs + a.posonlyargs: names.add(x.arg)
            if a.vararg: names.add(a.vararg.arg)
            if a.kwarg: names.add(a.kwarg.arg)
            if not isinstance(sub, ast.Lambda): names.add(sub.name)
        if isinstance(sub, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            tgts = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
            for t in tgts:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name): names.add(x.id)
        if isinstance(sub, (ast.For, ast.AsyncFor, ast.comprehension)):
            for x in ast.walk(sub.target):
                if isinstance(x, ast.Name): names.add(x.id)
        if isinstance(sub, ast.ExceptHandler) and sub.name: names.add(sub.name)
        if isinstance(sub, ast.withitem) and sub.optional_vars:
            for x in ast.walk(sub.optional_vars):
                if isinstance(x, ast.Name): names.add(x.id)
        if isinstance(sub, (ast.Import, ast.ImportFrom)):
            for a2 in sub.names: names.add((a2.asname or a2.name).split('.')[0])
    return names

bad = []
for f in sorted(glob.glob('**/*.py', recursive=True)):
    tree = ast.parse(open(f).read())
    # true module scope: top-level only
    module_names = set()
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: module_names.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, (ast.ClassDef, ast.FunctionDef)): module_names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name): module_names.add(x.id)
    for cls in [c for c in tree.body if isinstance(c, ast.ClassDef)]:
        class_names = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}
        for a in cls.body:
            if isinstance(a, ast.Assign):
                for t in a.targets:
                    if isinstance(t, ast.Name): class_names.add(t.id)
        for fn in [m for m in cls.body if isinstance(m, ast.FunctionDef)]:
            local = collect_scope(fn)
            used = {n.id for n in ast.walk(fn)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            miss = {m for m in used - local - module_names - class_names - BUILT
                    if not m.startswith('__')}
            if miss: bad.append((f, cls.name, fn.name, sorted(miss)))
if bad:
    print('UNRESOLVED NAMES:')
    for b in bad: print(' ', b)
    sys.exit(1)
print('scope check clean — every method resolves all its names')
