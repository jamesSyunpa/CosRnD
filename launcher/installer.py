"""
Installer Module for CosRnD Launcher

Handles first-time installation of the application.
"""

import os
import sys
import shutil
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import psutil

if sys.platform.startswith('win'):
    import winreg
    import ctypes
    from ctypes import wintypes


logger = logging.getLogger(__name__)


class InstallationError(Exception):
    """Raised when installation fails"""
    pass


class Installer:
    """Handles application installation"""
    
    # Minimum required disk space in MB
    MIN_DISK_SPACE_MB = 500
    
    def __init__(self, source_dir: Optional[Path] = None):
        """
        Initialize installer.
        
        Args:
            source_dir: Directory containing files to install.
                       If None, uses current directory.
        """
        self.source_dir = source_dir or Path.cwd()
    
    @staticmethod
    def get_default_install_path() -> Path:
        r"""
        Get default installation path.
        
        Returns:
            Default installation directory (C:\CosRQD)
        """
        return Path("C:\\CosRQD")

    
    @staticmethod
    def validate_install_path(path: Path) -> bool:
        """
        Validate installation path.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is valid
            
        Raises:
            ValueError: If path is invalid
        """
        # Check if path is absolute
        if not path.is_absolute():
            raise ValueError("Installation path must be absolute")
        
        # Check if path contains invalid characters
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(f"Invalid installation path: {e}")
        
        return True
    
    def check_disk_space(self, install_path: Path) -> bool:
        """
        Check if there's enough disk space for installation.
        
        Args:
            install_path: Installation directory
            
        Returns:
            True if enough space is available
        """
        try:
            # Get disk usage for the drive
            usage = psutil.disk_usage(str(install_path.drive or install_path.anchor))
            free_space_mb = usage.free / (1024 * 1024)
            
            if free_space_mb < self.MIN_DISK_SPACE_MB:
                logger.error(
                    f"Insufficient disk space: {free_space_mb:.1f}MB available, "
                    f"{self.MIN_DISK_SPACE_MB}MB required"
                )
                return False
            
            logger.info(f"Disk space check passed: {free_space_mb:.1f}MB available")
            return True
        except Exception as e:
            logger.error(f"Failed to check disk space: {e}")
            return False
    
    def create_directory_structure(self, install_path: Path) -> None:
        """
        Create installation directory structure.
        
        Args:
            install_path: Base installation directory
            
        Raises:
            InstallationError: If directory creation fails
        """
        try:
            # Create main directories
            (install_path / "bin").mkdir(parents=True, exist_ok=True)
            (install_path / "backup").mkdir(parents=True, exist_ok=True)
            (install_path / "logs").mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created directory structure at: {install_path}")
        except Exception as e:
            raise InstallationError(f"Failed to create directory structure: {e}")
    
    def copy_application_files(
        self,
        install_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> None:
        """
        Extract application files from embedded bundle to installation directory.
        
        Args:
            install_path: Installation directory
            progress_callback: Optional callback function(current, total, filename)
            
        Raises:
            InstallationError: If file extraction fails
        """
        try:
            import zipfile
            import sys
            
            bin_dir = install_path / "bin"
            
            # Check if app.zip is embedded in the launcher
            # PyInstaller bundles resources in sys._MEIPASS when running as exe
            if hasattr(sys, '_MEIPASS'):
                # Running as packaged exe
                bundle_path = Path(sys._MEIPASS) / "app.zip"
            else:
                # Running from source - look for built app in dist folder
                bundle_path = self.source_dir / "dist" / "app.zip"
            
            if not bundle_path.exists():
                # Fallback to old method if bundle not found
                logger.warning(f"Embedded bundle not found at {bundle_path}, falling back to file copy")
                self._copy_from_source_dir(install_path, progress_callback)
                return
            
            logger.info(f"Extracting application from: {bundle_path}")
            
            # Extract the zip file
            with zipfile.ZipFile(bundle_path, 'r') as zip_ref:
                members = zip_ref.namelist()
                total_items = len(members)
                
                for idx, member in enumerate(members):
                    if progress_callback:
                        filename = Path(member).name
                        progress_callback(idx, total_items, filename)
                    
                    zip_ref.extract(member, bin_dir)
                    logger.info(f"Extracted: {member}")
            
            # 언인스톨러 전용 바이너리 (Uninstall.exe) 복사 배치
            try:
                current_exe = Path(sys.executable)
                if current_exe.exists() and current_exe.suffix.lower() == '.exe':
                    dest_uninstaller = bin_dir / "Uninstall.exe"
                    shutil.copy2(current_exe, dest_uninstaller)
                    logger.info(f"Copied uninstaller binary to {dest_uninstaller}")
            except Exception as copy_uninst_err:
                logger.warning(f"Failed to copy uninstaller executable: {copy_uninst_err}")
            
            if progress_callback:
                progress_callback(total_items, total_items, "완료")
            
            logger.info("Application files extracted successfully")
        except Exception as e:
            raise InstallationError(f"Failed to extract application files: {e}")
    
    def _copy_from_source_dir(
        self,
        install_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> None:
        """
        Fallback method: Copy files from source directory (for development).
        """
        bin_dir = install_path / "bin"
        
        # Files to copy
        files_to_copy = [
            "main.exe",
            "Icon.ico",
            "VERSION",
            "config.ini",
        ]
        
        # Add directories to copy if they exist
        dirs_to_copy = [
            "data",
            "assets",
        ]
        
        total_items = len(files_to_copy)
        current = 0
        
        # Copy files
        for filename in files_to_copy:
            source = self.source_dir / filename
            if source.exists():
                dest = bin_dir / filename
                logger.info(f"Copying {filename}...")
                
                if progress_callback:
                    progress_callback(current, total_items, filename)
                
                if source.is_file():
                    shutil.copy2(source, dest)
                
                current += 1
            else:
                logger.warning(f"Source file not found: {source}")
        
        # Copy directories
        for dirname in dirs_to_copy:
            source_dir = self.source_dir / dirname
            if source_dir.exists() and source_dir.is_dir():
                dest_dir = bin_dir / dirname
                logger.info(f"Copying directory {dirname}...")
                
                if progress_callback:
                    progress_callback(current, total_items, dirname)
                
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                shutil.copytree(source_dir, dest_dir)
        
        if progress_callback:
            progress_callback(total_items, total_items, "완료")
    
    def verify_installation(self, install_path: Path) -> bool:
        """
        Verify that installation completed successfully.
        
        Args:
            install_path: Installation directory
            
        Returns:
            True if installation is valid
        """
        try:
            # Check required files exist
            bin_dir = install_path / "bin"
            exe_candidates = list(bin_dir.glob("CosRQD*.exe")) + list(bin_dir.glob("화장품연구관리_*.exe")) + list(bin_dir.glob("CosRnD*.exe")) + [f for f in bin_dir.glob("*.exe") if not f.name.startswith("Setup_")] + [bin_dir / "main.exe"]
            main_exe = next((c for c in exe_candidates if c.exists()), None)
            
            if not main_exe:
                logger.error("Application executable not found in installation bin directory")
                return False
            
            # Check directory structure
            required_dirs = ["bin", "backup", "logs"]
            for dirname in required_dirs:
                if not (install_path / dirname).is_dir():
                    logger.error(f"Required directory not found: {dirname}")
                    return False
            
            logger.info("Installation verification passed")
            return True
        except Exception as e:
            logger.error(f"Installation verification failed: {e}")
            return False
    
    def install(
        self,
        install_path: Path,
        version: str,
        update_server: str = "",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Perform complete installation.
        
        Args:
            install_path: Installation directory
            version: Application version
            update_server: Update server URL
            progress_callback: Optional progress callback
            
        Returns:
            Installation configuration dictionary
            
        Raises:
            InstallationError: If installation fails
        """
        logger.info(f"Starting installation to: {install_path}")
        
        # Validate path
        self.validate_install_path(install_path)
        
        # Check disk space
        if not self.check_disk_space(install_path):
            raise InstallationError("Insufficient disk space for installation")
        
        # Create directory structure
        self.create_directory_structure(install_path)
        
        # Copy files
        self.copy_application_files(install_path, progress_callback)
        
        # Verify installation
        if not self.verify_installation(install_path):
            raise InstallationError("Installation verification failed")
        
        # 바탕화면 및 시작메뉴 단축아이콘 생성
        try:
            bin_dir = install_path / "bin"
            exe_candidates = list(bin_dir.glob("CosRQD*.exe")) + list(bin_dir.glob("화장품연구관리_*.exe")) + list(bin_dir.glob("CosRnD*.exe")) + [f for f in bin_dir.glob("*.exe") if not f.name.startswith("Setup_")] + [bin_dir / "main.exe"]
            target_exe = next((c for c in exe_candidates if c.exists()), bin_dir / "CosRQD.exe")
            
            icon_path = bin_dir / "Icon.ico"
            if not icon_path.exists():
                # 리소스에서 복사 시도
                import sys
                src_icon = Path(sys._MEIPASS if hasattr(sys, '_MEIPASS') else '').joinpath('Icon.ico')
                if not src_icon.exists():
                    src_icon = Path(__file__).parent.parent / 'Icon.ico'
                if src_icon.exists():
                    shutil.copy2(src_icon, icon_path)
            
            app_ver_name = f"CosRQD_{version}" if version else "CosRQD (화장품연구관리)"
            self.create_shortcuts(target_exe, app_ver_name, icon_path)
        except Exception as shortcut_err:
            logger.error(f"Failed to create shortcuts during installation: {shortcut_err}")

        logger.info("Installation completed successfully")
        
        # Return config data
        return {
            "install_path": str(install_path),
            "version": version,
            "update_server": update_server
        }
        
    def _get_all_shortcut_dirs(self) -> list:
        """Windows API, 레지스트리, 환경변수를 모두 조회하여 모든 바탕화면 및 시작메뉴 경로 목록을 반환"""
        dirs = set()
        
        # 1. Windows Shell API (SHGetFolderPathW)
        if sys.platform.startswith('win'):
            try:
                import ctypes
                from ctypes import wintypes
                for csidl in [0x0000, 0x0002, 0x0019, 0x0017]:  # Desktop, Programs, Common Desktop, Common Programs
                    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
                    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
                    if buf.value:
                        dirs.add(Path(buf.value))
            except Exception:
                pass

            # 2. 레지스트리 User Shell Folders
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                    for val_name in ["Desktop", "Programs", "Common Desktop", "Common Programs"]:
                        try:
                            val, _ = winreg.QueryValueEx(k, val_name)
                            expanded = os.path.expandvars(val)
                            if expanded:
                                dirs.add(Path(expanded))
                        except Exception:
                            pass
            except Exception:
                pass

        # 3. 환경변수 기반 기본 및 OneDrive 경로
        user_prof = os.environ.get("USERPROFILE", "")
        if user_prof:
            dirs.add(Path(user_prof) / "Desktop")
            dirs.add(Path(user_prof) / "OneDrive" / "Desktop")
            dirs.add(Path(user_prof) / "OneDrive" / "바탕 화면")
            dirs.add(Path(user_prof) / "OneDrive - 개인" / "Desktop")
            dirs.add(Path(user_prof) / "OneDrive - 개인" / "바탕 화면")
            
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            dirs.add(Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
            
        public_dir = os.environ.get("PUBLIC", "")
        if public_dir:
            dirs.add(Path(public_dir) / "Desktop")
            
        prog_data = os.environ.get("PROGRAMDATA", "")
        if prog_data:
            dirs.add(Path(prog_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

        return [d for d in dirs if d.exists()]

    def _create_single_shortcut(self, target_exe: Path, shortcut_path: Path, working_dir: Path, icon_path: Path) -> bool:
        """단일 바로가기 파일을 3중 안전망(win32com -> VBScript -> PowerShell)으로 생성"""
        # 1. win32com.client (가장 안정적이고 빠름)
        try:
            import win32com.client
            shell = win32com.client.Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = str(target_exe)
            shortcut.WorkingDirectory = str(working_dir)
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
            shortcut.save()
            if shortcut_path.exists():
                logger.info(f"[win32com] Shortcut created at {shortcut_path}")
                return True
        except Exception as com_err:
            logger.debug(f"win32com failed for {shortcut_path}: {com_err}")

        # 2. VBScript 임시 스크립트 실행
        try:
            import tempfile
            import subprocess
            vbs_content = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{str(shortcut_path)}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{str(target_exe)}"
oLink.WorkingDirectory = "{str(working_dir)}"
oLink.IconLocation = "{str(icon_path)}"
oLink.Save
'''
            with tempfile.NamedTemporaryFile(mode='w', suffix='.vbs', delete=False, encoding='cp949') as vbs_f:
                vbs_f.write(vbs_content)
                vbs_path = vbs_f.name
            try:
                subprocess.run(["cscript", "//nologo", vbs_path], capture_output=True, check=True)
                if shortcut_path.exists():
                    logger.info(f"[VBScript] Shortcut created at {shortcut_path}")
                    return True
            finally:
                try:
                    os.remove(vbs_path)
                except Exception:
                    pass
        except Exception as vbs_err:
            logger.debug(f"VBScript failed for {shortcut_path}: {vbs_err}")

        # 3. PowerShell 스크립트 파일 실행
        try:
            import tempfile
            import subprocess
            ps_content = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{str(shortcut_path)}")
$Shortcut.TargetPath = "{str(target_exe)}"
$Shortcut.WorkingDirectory = "{str(working_dir)}"
$Shortcut.IconLocation = "{str(icon_path)}"
$Shortcut.Save()
'''
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as ps_f:
                ps_f.write(ps_content)
                ps_path = ps_f.name
            try:
                subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path], capture_output=True, check=True)
                if shortcut_path.exists():
                    logger.info(f"[PowerShell] Shortcut created at {shortcut_path}")
                    return True
            finally:
                try:
                    os.remove(ps_path)
                except Exception:
                    pass
        except Exception as ps_err:
            logger.debug(f"PowerShell failed for {shortcut_path}: {ps_err}")

        return False

    def create_shortcuts(self, target_exe: Path, shortcut_name: str, icon_path: Path):
        """윈도우 바탕화면 및 시작메뉴에 단축 아이콘 정확히 1개씩 생성 및 제어판 앱 등록"""
        try:
            working_dir = target_exe.parent
            user_profile = Path(os.environ.get("USERPROFILE", ""))
            
            # 1. 활성 바탕화면 경로 단 1곳만 선택 (OneDrive 연동 바탕화면 최우선, 없으면 일반 Desktop)
            target_desktop = None
            onedrive_candidates = [
                user_profile / "OneDrive" / "바탕 화면",
                user_profile / "OneDrive" / "Desktop",
                user_profile / "OneDrive - Personal" / "바탕 화면",
                user_profile / "OneDrive - Personal" / "Desktop",
            ]
            for cand in onedrive_candidates:
                if cand.exists():
                    target_desktop = cand
                    break
            
            if not target_desktop:
                # Windows Shell API(CSIDL_DESKTOP=0x0000)로 실제 유효한 바탕화면 확인
                if sys.platform.startswith('win'):
                    try:
                        import ctypes
                        from ctypes import wintypes
                        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
                        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
                        if buf.value and Path(buf.value).exists():
                            target_desktop = Path(buf.value)
                    except Exception:
                        pass
                        
            if not target_desktop or not target_desktop.exists():
                target_desktop = user_profile / "Desktop"
                
            # 2. 시작메뉴 경로 1곳
            start_menu_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

            target_dirs = []
            if target_desktop and target_desktop.exists():
                target_dirs.append(target_desktop)
            if start_menu_dir and start_menu_dir.exists() and start_menu_dir not in target_dirs:
                target_dirs.append(start_menu_dir)

            success_count = 0
            for base_dir in target_dirs:
                shortcut_path = base_dir / f"{shortcut_name}.lnk"
                if self._create_single_shortcut(target_exe, shortcut_path, working_dir, icon_path):
                    success_count += 1
            
            logger.info(f"Successfully created {success_count} unique shortcuts (Desktop: {target_desktop}, StartMenu: {start_menu_dir})")
            
            # 윈도우 쉘 아이콘 캐시 새로고침
            if sys.platform.startswith('win'):
                try:
                    import ctypes
                    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
                except Exception:
                    pass

            # 윈도우 제어판 '앱 및 기능'(프로그램 추가/제거)에 등록
            self.register_in_windows_uninstall(target_exe, shortcut_name, icon_path)
            
        except Exception as e:
            logger.error(f"Failed to create shortcuts: {e}")

    def register_in_windows_uninstall(self, target_exe: Path, display_name: str, icon_path: Path):
        """윈도우 레지스트리에 언인스톨 정보를 등록하여 제어판의 설치된 앱 리스트에 노출시킵니다."""
        if not sys.platform.startswith('win'):
            return
        try:
            import winreg
            import ctypes
            
            is_admin = False
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                pass
            
            hkeys = [winreg.HKEY_CURRENT_USER]
            if is_admin:
                hkeys.append(winreg.HKEY_LOCAL_MACHINE)
            
            reg_paths = [
                r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CosRQD",
                r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\CosRQD"
            ]
            
            install_dir = target_exe.parent.parent
            uninst_exe = target_exe.parent / "Uninstall.exe"
            if not uninst_exe.exists():
                uninst_candidates = list(target_exe.parent.glob("Setup_*.exe"))
                uninst_exe = uninst_candidates[0] if uninst_candidates else target_exe
            uninstall_string = f'"{uninst_exe}" --uninstall'
            
            app_version_str = "65.0.3"
            try:
                ver_file = target_exe.parent / "VERSION"
                if not ver_file.exists():
                    ver_file = install_dir / "VERSION"
                if ver_file.exists():
                    app_version_str = ver_file.read_text(encoding='utf-8').strip().lstrip('v')
            except Exception:
                pass
            
            for hkey in hkeys:
                for reg_path in reg_paths:
                    for access_flag in [winreg.KEY_WRITE, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY, winreg.KEY_WRITE | winreg.KEY_WOW64_32KEY]:
                        try:
                            key = winreg.CreateKeyEx(hkey, reg_path, 0, access_flag)
                            
                            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, display_name)
                            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_string)
                            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_path))
                            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, app_version_str)
                            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Luckfortma")
                            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
                            winreg.SetValueEx(key, "URLInfoAbout", 0, winreg.REG_SZ, "https://cafe.naver.com/cosrqd")
                            winreg.SetValueEx(key, "HelpLink", 0, winreg.REG_SZ, "https://cafe.naver.com/cosrqd")
                            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 150000)
                            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
                            
                            winreg.CloseKey(key)
                            logger.info(f"Registered app in Windows Registry: {'HKLM' if hkey == winreg.HKEY_LOCAL_MACHINE else 'HKCU'} -> {reg_path}")
                        except PermissionError:
                            continue
                        except Exception as e:
                            logger.warning(f"Failed to write registry key {reg_path} on {hkey} with flag {access_flag}: {e}")
                        
            logger.info("Control Panel app list registration complete")
        except Exception as e:
            logger.error(f"Failed to register in Windows Registry: {e}")
    
    def uninstall(self, install_path: Path, keep_user_data: bool = True) -> bool:
        """
        Uninstall the application (files across all candidate install directories, shortcuts, and Windows registry).
        """
        try:
            logger.info(f"Uninstalling from: {install_path}")
            
            # 1. 실행 중인 프로세스 강제 종료 시도
            try:
                import subprocess
                for proc_name in ["CosRQD.exe", "CosRnD.exe", "main.exe", "화장품연구관리.exe", "Setup_CosRQD_v65.0.2.exe", "Setup_CosRQD_v65.0.1.exe"]:
                    subprocess.run(["taskkill", "/F", "/IM", proc_name, "/T"], capture_output=True)
            except Exception:
                pass
            
            # 2. 모든 설치 후보 디렉터리 탐색 및 bin 바이너리 폴더 전수 정리
            candidate_dirs = [install_path]
            for extra_path in [
                Path("C:/CosRQD"),
                Path("C:/CosRnD"),
                Path(os.environ.get("LOCALAPPDATA", "")) / "CosRQD",
                Path(os.environ.get("LOCALAPPDATA", "")) / "CosRnD",
                Path(os.environ.get("PROGRAMFILES", "")) / "CosRQD",
                Path(os.environ.get("PROGRAMFILES(X86)", "")) / "CosRQD"
            ]:
                if extra_path not in candidate_dirs:
                    candidate_dirs.append(extra_path)

            for target_dir in candidate_dirs:
                if target_dir.exists():
                    bin_dir = target_dir / "bin"
                    if bin_dir.exists():
                        # 파일 읽기전용 속성 해제 및 강제 삭제
                        try:
                            for root, dirs, files in os.walk(str(bin_dir), topdown=False):
                                for name in files:
                                    f_path = os.path.join(root, name)
                                    try:
                                        os.chmod(f_path, 0o777)
                                        os.remove(f_path)
                                    except Exception:
                                        pass
                                for name in dirs:
                                    d_path = os.path.join(root, name)
                                    try:
                                        os.rmdir(d_path)
                                    except Exception:
                                        pass
                            shutil.rmtree(bin_dir, ignore_errors=True)
                            logger.info(f"Removed application binaries from {bin_dir}")
                        except Exception as rm_err:
                            logger.warning(f"Failed to remove {bin_dir}: {rm_err}")
                    
                    # keep_user_data가 False이거나, 사용자 데이터 폴더가 없는 경우 폴더 자체 삭제
                    if not keep_user_data:
                        shutil.rmtree(target_dir, ignore_errors=True)
                        logger.info(f"Removed entire installation directory {target_dir}")
            
            # 3. 모든 바탕화면 및 시작메뉴에서 바로가기 완벽 삭제
            try:
                all_dirs = self._get_all_shortcut_dirs()
                target_patterns = ["*CosRQD*.lnk", "*CosRnD*.lnk", "*화장품연구관리*.lnk", "*화장품연구*.lnk", "*화장품*.lnk", "*Luckfortma*.lnk"]
                
                deleted_count = 0
                for d in all_dirs:
                    if d.exists():
                        for pat in target_patterns:
                            for lnk in d.glob(pat):
                                try:
                                    lnk.unlink()
                                    deleted_count += 1
                                    logger.info(f"Removed shortcut: {lnk}")
                                except Exception as del_err:
                                    logger.warning(f"Failed to delete {lnk}: {del_err}")
                logger.info(f"Total shortcuts deleted: {deleted_count}")
                
                # 윈도우 쉘 아이콘 캐시 새로고침
                if sys.platform.startswith('win'):
                    try:
                        import ctypes
                        # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0x0000
                        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Failed to remove shortcuts: {e}")
            
            # 4. Windows 레지스트리 Uninstall 키 완전 삭제
            if sys.platform.startswith('win'):
                try:
                    import subprocess
                    import winreg
                    
                    # 방법 1: reg delete 명령어로 OS 레벨에서 강제 삭제
                    for root_str in ["HKCU", "HKLM"]:
                        for sub_path in [
                            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                            r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
                        ]:
                            for app_name in ["CosRQD", "CosRnD"]:
                                try:
                                    full_reg = f"{root_str}\\{sub_path}\\{app_name}"
                                    subprocess.run(["reg", "delete", full_reg, "/f"], capture_output=True)
                                    logger.info(f"Deleted registry via reg delete: {full_reg}")
                                except Exception:
                                    pass
                    
                    # 방법 2: winreg.DeleteKeyEx 및 DeleteKey로 32/64비트 키 직접 삭제
                    for root_key in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                        for base_path in [
                            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                            r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
                        ]:
                            for app_name in ["CosRQD", "CosRnD"]:
                                for flag in [0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]:
                                    try:
                                        winreg.DeleteKeyEx(root_key, f"{base_path}\\{app_name}", flag, 0)
                                        logger.info(f"Deleted registry via DeleteKeyEx: {base_path}\\{app_name}")
                                    except Exception:
                                        try:
                                            winreg.DeleteKey(root_key, f"{base_path}\\{app_name}")
                                        except Exception:
                                            pass
                except Exception as e:
                    logger.warning(f"Failed to delete registry keys: {e}")
            
            logger.info("Uninstallation complete")
            return True
        except Exception as e:
            logger.error(f"Uninstallation failed: {e}")
            return False
