#!/usr/bin/env python3
import ast
import sys
import os

def check_syntax(path):
    errors = []
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    try:
        ast.parse(content, filename=path)
    except SyntaxError as e:
        errors.append(f'{path}:{e.lineno}: {e.msg}')
    return errors

all_errors = []
count = 0
# Check all .py files in nanobot/
for root, dirs, files in os.walk('nanobot'):
    for file in files:
        if file.endswith('.py'):
            count += 1
            full_path = os.path.join(root, file)
            err = check_syntax(full_path)
            all_errors.extend(err)

print(f'Total .py files checked: {count}')
print(f'Found {len(all_errors)} syntax errors:')
for e in all_errors:
    print('  ', e)
