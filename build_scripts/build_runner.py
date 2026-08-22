import argparse
import os
import subprocess
import sys


def find_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def run_pyinstaller_with_spec(spec_path):
    cmd = [sys.executable, "-m", "PyInstaller", spec_path]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def find_icon_file(root):
    # 우선순위: .ico → .png → .icns
    for ext in [".ico", ".png", ".icns"]:
        for fname in os.listdir(root):
            if fname.lower().endswith(ext):
                return os.path.join(root, fname)
    return None

def collect_datas(root):
    datas = []
    # 주요 폴더 및 파일 포함
    include_dirs = ["assets", "data", "database", "modules", "utils"]
    for d in include_dirs:
        dpath = os.path.join(root, d)
        if os.path.isdir(dpath):
            datas.append(f"{d}{os.sep}*;{d}")
    # 주요 설정 파일 포함
    for fname in ["config.ini", "config copy.ini", "VERSION"]:
        fpath = os.path.join(root, fname)
        if os.path.isfile(fpath):
            datas.append(f"{fname};.")
    return datas

def get_version_from_folder(root):
    """폴더 이름에서 버전 추출 (예: CosRnD_v58 -> v58)"""
    folder_name = os.path.basename(root)
    import re
    match = re.search(r'v(\d+)', folder_name, re.IGNORECASE)
    if match:
        return f"v{match.group(1)}"
    return "v1"


def run_pyinstaller_with_script(script_path, onefile=False, windowed=False, noconfirm=True, clean=False, add_data=None, icon=None, name=None):
    args = [sys.executable, "-m", "PyInstaller"]
    if noconfirm:
        args.append("--noconfirm")
    if onefile:
        args.append("--onefile")
    if windowed:
        args.append("--windowed")
    if clean:
        args.append("--clean")
    if name:
        args.extend(["--name", name])
    if add_data:
        for d in add_data:
            args.extend(["--add-data", d])
    if icon:
        args.extend(["--icon", icon])
    args.append(script_path)
    print("Running:", " ".join(args))
    subprocess.run(args, check=True)



def main():
    parser = argparse.ArgumentParser(description="Run PyInstaller build from a Python entrypoint.")
    parser.add_argument("--script", "-s", default="main.py", help="Entry script to build (default: main.py)")
    parser.add_argument("--onefile", action="store_true", help="Build onefile executable")
    parser.add_argument("--windowed", action="store_true", help="Build windowed (no console)")
    parser.add_argument("--clean", action="store_true", help="Pass --clean to PyInstaller")
    parser.add_argument("--name", "-n", default=None, help="Output executable name (default: 화장품연구관리_v{version})")

    args = parser.parse_args()
    root = find_project_root()
    script_path = os.path.join(root, args.script)

    if not os.path.exists(script_path):
        print(f"Error: script not found: {script_path}")
        sys.exit(2)

    # 자동 데이터/리소스/아이콘 포함
    datas = collect_datas(root)
    icon = find_icon_file(root)
    
    # 출력 파일명 결정 (기본값: 화장품연구관리_버전)
    output_name = args.name
    if not output_name:
        version = get_version_from_folder(root)
        output_name = f"화장품연구관리_{version}"
    
    print(f"Build output name: {output_name}")

    try:
        run_pyinstaller_with_script(
            script_path,
            onefile=args.onefile,
            windowed=args.windowed,
            noconfirm=True,
            clean=args.clean,
            add_data=datas,
            icon=icon,
            name=output_name
        )
    except subprocess.CalledProcessError as e:
        print("Build failed:", e)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
