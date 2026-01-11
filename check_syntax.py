#!/usr/bin/env python3
"""Check syntax of all Python files in the project."""
import py_compile
import glob
import sys

files = glob.glob('**/*.py', recursive=True)
errors = []

for filepath in sorted(files):
    if '.venv' in filepath or '__pycache__' in filepath:
        continue
    try:
        py_compile.compile(filepath, doraise=True)
        print(f'✓ {filepath}')
    except py_compile.PyCompileError as e:
        print(f'✗ {filepath}: {e}')
        errors.append(filepath)

if errors:
    print(f'\n❌ {len(errors)} files with syntax errors:')
    for f in errors:
        print(f'  - {f}')
    sys.exit(1)
else:
    print(f'\n✓ All {len(files)} files have valid syntax')
    sys.exit(0)
