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
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. VERSION 확인
    ver_file = os.path.join(current_dir, "VERSION")
    version = "v65.0.1"
    if os.path.exists(ver_file):
        with open(ver_file, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                version = v if v.startswith("v") else f"v{v}"
                
    print(f"=== CosRQD {version} Setup Package Build Starting ===")
    dist_dir = os.path.join(current_dir, "dist")
    
    # 2. Build main application
    main_spec = os.path.join(current_dir, "build_scripts", f"화장품연구관리_{version}.spec")
    if not os.path.exists(main_spec):
        # 없으면 1.0.3 또는 기본 spec fallback
        main_spec = os.path.join(current_dir, "build_scripts", "setup_installer.spec")
        
    run_pyinstaller(main_spec)
    
    app_folder = os.path.join(dist_dir, f"화장품연구관리_{version}")
    if not os.path.exists(app_folder):
        print(f"[Error] Built folder not found: {app_folder}")
        return
        
    # 복사: 빌드 폴더 내에 VERSION 및 config.ini 파일 포함
    if os.path.exists(ver_file):
        print(f"[Processing] Copying VERSION to {app_folder}")
        shutil.copy2(ver_file, os.path.join(app_folder, "VERSION"))

    cfg_file = os.path.join(current_dir, "config.ini")
    if os.path.exists(cfg_file):
        print(f"[Processing] Copying config.ini to {app_folder}")
        shutil.copy2(cfg_file, os.path.join(app_folder, "config.ini"))

    # 3. Compress the built app folder to app.zip
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
    
    # 4. Build Setup_CosRQD_{version}.exe
    setup_spec = os.path.join(current_dir, "build_scripts", "setup_installer.spec")
    run_pyinstaller(setup_spec)
    
    setup_exe = os.path.join(dist_dir, f"Setup_CosRQD_{version}.exe")
    if not os.path.exists(setup_exe):
        alt_exe = os.path.join(dist_dir, f"Setup_화장품연구관리_{version}.exe")
        if os.path.exists(alt_exe):
            setup_exe = alt_exe
        else:
            print(f"[Error] Setup exe not found: {setup_exe}")
            return
        
    # 5. Copy to final release directory
    release_dir = os.path.join(current_dir, "CosRQD_Release")
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir, exist_ok=True)
    
    # Copy Setup_CosRQD_{version}.exe
    dest_setup = os.path.join(release_dir, f"Setup_CosRQD_{version}.exe")
    shutil.copy2(setup_exe, dest_setup)

    # 6. 배포용 Setup_CosRQD_{version}.zip 생성
    dest_zip = os.path.join(release_dir, f"Setup_CosRQD_{version}.zip")
    shutil.copy2(zip_path, dest_zip)

    # 네이버 카페 50MB 제한 대비 40MB 분할 파일 자동 생성
    chunk_size = 40 * 1024 * 1024  # 40MB
    with open(dest_zip, 'rb') as f:
        part_num = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk: break
            part_name = f"{dest_zip}.{part_num:03d}"
            with open(part_name, 'wb') as pf:
                pf.write(chunk)
            print(f"[Success] 네이버 카페 첨부용 분할 파일 생성: {os.path.basename(part_name)} ({len(chunk)/(1024*1024):.2f} MB)")
            part_num += 1
    
    print("\n=======================================================")
    print(f"[Success] Release packaging successful!")
    print(f"1. Setup Installer (실행 설치용): {dest_setup}")
    print(f"2. Setup ZIP Package (깃허브/클라우드용): {dest_zip}")
    print(f"3. Cafe Split Files (카페 분할 첨부용):")
    print(f"   • {os.path.basename(dest_zip)}.001")
    print(f"   • {os.path.basename(dest_zip)}.002")
    print("=======================================================")

if __name__ == "__main__":
    main()
