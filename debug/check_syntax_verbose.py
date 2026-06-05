import py_compile
try:
    py_compile.compile('modules/document_management.py', doraise=True)
    print("Syntax OK")
except Exception as e:
    print(f"SYNTAX ERROR: {e}")
