"""
Build script to create app.zip bundle for embedding in launcher

This script packages the main application into a zip file that will be
embedded in the launcher executable.
"""

import zipfile
import shutil
from pathlib import Path


def create_app_bundle():
    """Create app.zip bundle from main application"""
    print("Creating app.zip bundle...")
    
    project_root = Path(__file__).parent
    dist_folder = project_root / "dist"
    
    # Find the main executable (CoRQD_vXX.exe)
    main_exe = None
    # Wait a short while for the exe to appear (avoid race with pyinstaller finishing)
    import time
    for _ in range(15):
        matches = list(dist_folder.glob("CoRQD_*.exe")) if dist_folder.exists() else []
        if matches:
            main_exe = matches[0]
            break
        time.sleep(1)
    
    if not main_exe or not main_exe.exists():
        print("ERROR: Main application executable not found in dist/")
        print("Please build the main application first using: pyinstaller build.spec")
        return 1
    
    print(f"Found main executable: {main_exe.name}")
    
    # Create app.zip in PROJECT ROOT (safer than dist/)
    bundle_path = project_root / "app.zip"
    
    # Remove old bundle if exists
    if bundle_path.exists():
        bundle_path.unlink()
    
    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add main executable and rename to main.exe
        zipf.write(main_exe, "main.exe")
        print(f"  Added: {main_exe.name} as main.exe")
        
        # Add VERSION file
        version_file = project_root / "VERSION"
        if version_file.exists():
            zipf.write(version_file, "VERSION")
            print(f"  Added: VERSION")
        
        # Add Icon.ico
        icon_file = project_root / "Icon.ico"
        if icon_file.exists():
            zipf.write(icon_file, "Icon.ico")
            print(f"  Added: Icon.ico")
        
        # Add data folder if exists
        data_folder = project_root / "data"
        if data_folder.exists():
            for file in data_folder.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(project_root)
                    zipf.write(file, arcname)
                    print(f"  Added: {arcname}")
        
        # Add assets folder if exists
        assets_folder = project_root / "assets"
        if assets_folder.exists():
            for file in assets_folder.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(project_root)
                    zipf.write(file, arcname)
                    print(f"  Added: {arcname}")
    
    bundle_size = bundle_path.stat().st_size / (1024 * 1024)
    print(f"\n✓ Created app.zip ({bundle_size:.2f} MB)")
    print(f"  Location: {bundle_path}")
    
    return 0


if __name__ == "__main__":
    exit(create_app_bundle())
