import py_compile
import sys
import traceback

try:
    py_compile.compile('modules/document_management.py', doraise=True)
    with open('syntax_error.txt', 'w', encoding='utf-8') as f:
        f.write("OK")
except Exception:
    with open('syntax_error.txt', 'w', encoding='utf-8') as f:
        traceback.print_exc(file=f)
