try:
    print("Attempting to import modules.legal_notice...")
    from modules.legal_notice import LegalNoticeDialog
    print("Import successful")
except Exception as e:
    import traceback
    traceback.print_exc()
