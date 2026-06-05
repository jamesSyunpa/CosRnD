import os
import zipfile
import shutil
import subprocess
import sys

def run_pyinstaller(spec_path):
    print(f"[Build] PyInstaller starting for: {spec_path}")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", spec_path]
    print("Command:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[Build] PyInstaller finished for: {spec_path}")

def main():
    print("=== CosRnD v1.0 Packaging Build Starting ===")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(current_dir, "dist")
    
    # 1. Build main application
    main_spec = os.path.join(current_dir, "build_scripts", "화장품연구관리_v1.0.spec")
    run_pyinstaller(main_spec)
    
    app_folder = os.path.join(dist_dir, "화장품연구관리_v1.0")
    if not os.path.exists(app_folder):
        print(f"[Error] Built folder not found: {app_folder}")
        return
        
    # 2. Compress the built app folder to app.zip
    zip_path = os.path.join(dist_dir, "app.zip")
    print(f"[Processing] Packaging {zip_path}...")
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
        for root, dirs, files in os.walk(app_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, app_folder)
                zip_ref.write(file_path, arcname)
                
    print(f"[Success] Compression complete: {zip_path}")
    
    # 3. Build Setup_화장품연구관리_v1.0.exe
    setup_spec = os.path.join(current_dir, "build_scripts", "setup_installer.spec")
    run_pyinstaller(setup_spec)
    
    setup_exe = os.path.join(dist_dir, "Setup_화장품연구관리_v1.0.exe")
    if not os.path.exists(setup_exe):
        print(f"[Error] Setup exe not found: {setup_exe}")
        return
        
    # 4. Copy to final release directory
    release_dir = os.path.join(current_dir, "CosRnD_Release")
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir, exist_ok=True)
    
    # Copy Setup_화장품연구관리_v1.0.exe
    dest_setup = os.path.join(release_dir, "Setup_화장품연구관리_v1.0.exe")
    shutil.copy2(setup_exe, dest_setup)
    
    print("\n=======================================================")
    print(f"[Success] Single setup packaging successful!")
    print(f"Final Setup File: {dest_setup}")
    print("=======================================================")

if __name__ == "__main__":
    main()
