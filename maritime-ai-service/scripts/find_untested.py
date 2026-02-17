"""Find source modules without unit test coverage."""
import os
import re

test_files = [f for f in os.listdir('tests/unit') if f.startswith('test_') and f.endswith('.py')]

tested_modules = set()
for tf in test_files:
    path = os.path.join('tests', 'unit', tf)
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        content = fh.read()
    for m in re.finditer(r'(?:from|import)\s+app\.[\w.]+\.(\w+)', content):
        tested_modules.add(m.group(1))

source_files = []
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
    for f in files:
        if f.endswith('.py') and f != '__init__.py':
            fp = os.path.join(root, f)
            with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = len(fh.readlines())
            if lines > 30:
                mod_name = f.replace('.py', '')
                if mod_name not in tested_modules:
                    source_files.append((fp.replace(os.sep, '/'), lines))

source_files.sort(key=lambda x: -x[1])
print(f'Untested modules with >30 lines ({len(source_files)}):')
for path, lines in source_files:
    print(f'  {lines:4d}  {path}')
