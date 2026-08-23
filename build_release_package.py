import os
import zipfile
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def run_pyinstaller(spec_path):
    print(f"[Build] PyInstaller starting for: {spec_path}")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", spec_path]
    print("Command:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[Build] PyInstaller finished for: {spec_path}")

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. VERSION 및 설정 확인
    ver_file = os.path.join(current_dir, "VERSION")
    cfg_file = os.path.join(current_dir, "config.ini")
    icon_file = os.path.join(current_dir, "Icon.ico")
    version = "v65.0.2"
    if os.path.exists(ver_file):
        with open(ver_file, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                version = v if v.startswith("v") else f"v{v}"
                
    print(f"=== CosRQD {version} Setup Package Build Starting ===")
    dist_dir = os.path.join(current_dir, "dist")
    
    # 2. Build main application (One-file CosRQD.exe 우선)
    main_spec = os.path.join(current_dir, "build_scripts", f"CosRQD_{version}.spec")
    if not os.path.exists(main_spec):
        main_spec = os.path.join(current_dir, "build_scripts", f"화장품연구관리_{version}.spec")
    if not os.path.exists(main_spec):
        main_spec = os.path.join(current_dir, "build_scripts", "setup_installer.spec")
        
    run_pyinstaller(main_spec)
    
    # 3. Create app.zip bundle for installer
    zip_path = os.path.join(dist_dir, "app.zip")
    print(f"[Processing] Packaging {zip_path}...")
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    cosrqd_single_exe = os.path.join(dist_dir, "CosRQD.exe")
    app_folder = os.path.join(dist_dir, f"화장품연구관리_{version}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
        if os.path.exists(cosrqd_single_exe):
            # One-file 모드: CosRQD.exe 단일 파일 및 필수 설정 파일만 zip에 포함
            print(f"[Processing] Adding single executable: {cosrqd_single_exe}")
            zip_ref.write(cosrqd_single_exe, "CosRQD.exe")
            if os.path.exists(ver_file):
                zip_ref.write(ver_file, "VERSION")
            if os.path.exists(cfg_file):
                zip_ref.write(cfg_file, "config.ini")
            icon_file = os.path.join(current_dir, "Icon.ico")
            if os.path.exists(icon_file):
                zip_ref.write(icon_file, "Icon.ico")
        elif os.path.exists(app_folder):
            # Onedir 모드
            if os.path.exists(ver_file):
                shutil.copy2(ver_file, os.path.join(app_folder, "VERSION"))
            if os.path.exists(cfg_file):
                shutil.copy2(cfg_file, os.path.join(app_folder, "config.ini"))
            for root, dirs, files in os.walk(app_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, app_folder)
                    zip_ref.write(file_path, arcname)
        else:
            print(f"[Error] No built artifacts found in {dist_dir}")
            return
                
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

    # 6. 배포용 Setup_CosRQD_{version}.zip 생성 (설치 마법사 Setup.exe를 ZIP으로 패키징)
    dest_zip = os.path.join(release_dir, f"Setup_CosRQD_{version}.zip")
    if os.path.exists(dest_zip):
        os.remove(dest_zip)
    with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(dest_setup, f"Setup_CosRQD_{version}.exe")
    print(f"[Success] 인스톨러 ZIP 패키징 완료: {dest_zip}")

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
    print(f"   - {os.path.basename(dest_zip)}.001")
    print(f"   - {os.path.basename(dest_zip)}.002")
    print("=======================================================")

if __name__ == "__main__":
    main()
