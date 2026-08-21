import sys
import ast

files_to_check = [
    "modules/translation.py",
    "modules/document_management.py"
]

for filepath in files_to_check:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        print(f"OK: {filepath}")
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {filepath}:")
        print(f"  Line {e.lineno}: {e.msg}")
        print(f"  {e.text}")
    except Exception as e:
        print(f"ERROR reading {filepath}: {e}")
