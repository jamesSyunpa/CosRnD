"""
Launcher GUI for CosRnD Application

PyQt6-based GUI for installation wizard and update management.
"""

import os
import sys
import shutil
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFileDialog, QMessageBox,
    QStackedWidget, QLineEdit, QTextEdit, QDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

try:
    from launcher.config_manager import ConfigManager
    from launcher.installer import Installer, InstallationError
    from launcher.updater import Updater, UpdateError
    from launcher.process_manager import ProcessManager
except ImportError:
    from config_manager import ConfigManager
    from installer import Installer, InstallationError
    from updater import Updater, UpdateError
    from process_manager import ProcessManager


logger = logging.getLogger(__name__)


class InstallWorker(QThread):
    """Worker thread for installation"""
    
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, installer, install_path, version, update_server):
        super().__init__()
        self.installer = installer
        self.install_path = install_path
        self.version = version
        self.update_server = update_server
    
    def run(self):
        try:
            def progress_callback(current, total, filename):
                self.progress.emit(current, total, f"{filename} 설치 중...")
            
            self.installer.install(
                self.install_path,
                self.version,
                self.update_server,
                progress_callback
            )
            
            self.finished.emit(True, "설치가 성공적으로 완료되었습니다!")
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.finished.emit(False, str(e))


class UpdateWorker(QThread):
    """Worker thread for updates"""
    
    progress = pyqtSignal(str, int, int)  # stage, current, total
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, updater, update_info):
        super().__init__()
        self.updater = updater
        self.update_info = update_info
    
    def run(self):
        try:
            def progress_callback(stage, current, total):
                self.progress.emit(stage, current, total)
            
            self.updater.perform_update(self.update_info, progress_callback)
            self.finished.emit(True, "업데이트가 성공적으로 완료되었습니다!")
        except Exception as e:
            logger.error(f"Update failed: {e}")
            self.finished.emit(False, str(e))


class WelcomePage(QWidget):
    """Welcome page of installation wizard"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Welcome message
        title = QLabel("CosRQD 설치 마법사에 오신 것을 환영합니다")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        description = QLabel(
            "이 마법사가 설치 과정을 안내합니다.\n\n"
            "'다음' 버튼을 클릭하여 계속 진행하세요."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        
        self.setLayout(layout)


class PathSelectionPage(QWidget):
    """Installation path selection page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title = QLabel("설치 위치 선택")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        
        # Description
        description = QLabel(
            "CosRQD를 설치할 위치를 선택하세요.\n"
            "대부분의 사용자에게는 기본 위치를 권장합니다."
        )
        description.setWordWrap(True)
        
        # Path input
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(str(Installer.get_default_install_path()))
        self.path_input.setReadOnly(True)
        
        browse_btn = QPushButton("찾아보기...")
        browse_btn.clicked.connect(self.browse_path)
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(path_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def browse_path(self):
        """Open folder browser dialog"""
        path = QFileDialog.getExistingDirectory(
            self,
            "설치 디렉토리 선택",
            str(Path.home())
        )
        
        if path:
            self.path_input.setText(path)
    
    def get_install_path(self) -> Path:
        """Get selected installation path"""
        return Path(self.path_input.text())


class InstallationProgressPage(QWidget):
    """Installation progress page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title = QLabel("CosRQD 설치 중")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        
        # Status label
        self.status_label = QLabel("설치 준비 중...")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def update_progress(self, current: int, total: int, message: str):
        """Update progress display"""
        self.status_label.setText(message)
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)


class CompletionPage(QWidget):
    """Installation completion page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Success message
        title = QLabel("🎉 설치 완료!")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.message_label = QLabel(
            "CosRQD 시스템이 성공적으로 설치되었습니다.\n\n"
            "'완료' 버튼을 클릭하면 프로그램이 자동으로 실행됩니다."
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)

        self.launch_checkbox = QCheckBox("🚀 CosRQD 바로 실행 (권장)")
        self.launch_checkbox.setChecked(True)
        chk_font = QFont()
        chk_font.setPointSize(10)
        chk_font.setBold(True)
        self.launch_checkbox.setFont(chk_font)
        
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(self.message_label)
        
        chk_container = QHBoxLayout()
        chk_container.addStretch()
        chk_container.addWidget(self.launch_checkbox)
        chk_container.addStretch()
        layout.addLayout(chk_container)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def is_launch_checked(self) -> bool:
        """Check if launch checkbox is checked"""
        return self.launch_checkbox.isChecked()

    def set_success(self, success: bool, message: str):
        """Set completion status"""
        if success:
            self.message_label.setText(
                f"{message}\n\n"
                "'완료' 버튼을 클릭하면 프로그램이 즉시 실행됩니다."
            )
            self.launch_checkbox.setVisible(True)
        else:
            self.message_label.setText(
                f"설치 실패:\n{message}\n\n"
                "다시 시도하거나 지원팀에 문의하세요."
            )
            self.launch_checkbox.setVisible(False)


class InstallationWizard(QMainWindow):
    """Installation wizard main window"""
    
    def __init__(self, config_manager: ConfigManager, version: str):
        super().__init__()
        self.config_manager = config_manager
        self.version = version
        self.installer = Installer()
        self._is_launched = False
        
        self.init_ui()

    def closeEvent(self, event):
        """인스톨러 창 닫기 시 설치 완료 상태라면 프로그램 자동 실행 보장"""
        if not getattr(self, '_is_launched', False) and hasattr(self, 'pages') and self.pages.currentIndex() == 3:
            self.launch_application_and_close()
        event.accept()
    
    def init_ui(self):
        self.setWindowTitle("CosRQD 설치 마법사")
        self.setMinimumSize(600, 400)
        
        # Set Window Icon
        try:
            icon_path = Path(sys._MEIPASS if hasattr(sys, '_MEIPASS') else '').joinpath('Icon.ico')
            if not icon_path.exists():
                icon_path = Path(__file__).parent.parent / 'Icon.ico'
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.error(f"Failed to set wizard icon: {e}")
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Stacked widget for pages
        self.pages = QStackedWidget()
        
        self.welcome_page = WelcomePage()
        self.path_page = PathSelectionPage()
        self.progress_page = InstallationProgressPage()
        self.completion_page = CompletionPage()
        
        self.pages.addWidget(self.welcome_page)
        self.pages.addWidget(self.path_page)
        self.pages.addWidget(self.progress_page)
        self.pages.addWidget(self.completion_page)
        
        # Navigation buttons
        button_layout = QHBoxLayout()
        
        self.back_btn = QPushButton("< 이전")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        
        self.next_btn = QPushButton("다음 >")
        self.next_btn.clicked.connect(self.go_next)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.back_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.next_btn)
        
        layout.addWidget(self.pages)
        layout.addLayout(button_layout)
        
        central_widget.setLayout(layout)
    
    def go_back(self):
        """Go to previous page"""
        current = self.pages.currentIndex()
        if current > 0:
            self.pages.setCurrentIndex(current - 1)
            self.update_buttons()
    
    def go_next(self):
        """Go to next page or start installation or launch application"""
        current = self.pages.currentIndex()
        
        if current == 0:  # Welcome -> Path selection
            self.pages.setCurrentIndex(1)
        elif current == 1:  # Path selection -> Installation
            self.start_installation()
        elif current == 3:  # Completion -> Launch & Close
            self.launch_application_and_close()
        
        self.update_buttons()

    def launch_application_and_close(self):
        """완료 버튼 클릭 시 완전 독립 백그라운드 런처를 통해 최신 프로그램을 100% 확실하게 실행하고 인스톨러 종료"""
        if getattr(self, '_is_launched', False):
            return
        self._is_launched = True
        try:
            if hasattr(self, 'completion_page') and self.completion_page.is_launch_checked():
                install_path = self.path_page.get_install_path()
                bin_dir = install_path / "bin"
                
                # 1. 실행 대상 탐색 (설치된 최신 바이너리 및 바로가기)
                candidates = [
                    bin_dir / "CosRQD.exe",
                    bin_dir / "main.exe",
                    install_path / "CosRQD.exe",
                    install_path / "main.exe"
                ]
                for p in bin_dir.glob("*.exe"):
                    if not p.name.startswith("Setup_") and not p.name.startswith("Uninstall"):
                        candidates.append(p)
                
                target_file = None
                for c in candidates:
                    if c.exists():
                        target_file = c
                        break
                
                # 바탕화면 바로가기 탐색 (보조 후보)
                if not target_file and sys.platform.startswith('win'):
                    user_profile = Path(os.environ.get("USERPROFILE", ""))
                    desktop_paths = [
                        user_profile / "Desktop",
                        user_profile / "OneDrive" / "Desktop",
                        user_profile / "OneDrive" / "바탕 화면",
                        user_profile / "바탕 화면"
                    ]
                    for dp in desktop_paths:
                        if dp.exists():
                            for lnk_name in ["CosRQD.lnk", "CosRnD.lnk", "화장품연구관리.lnk"]:
                                lnk_candidate = dp / lnk_name
                                if lnk_candidate.exists():
                                    target_file = lnk_candidate
                                    break
                        if target_file:
                            break

                if target_file and target_file.exists():
                    target_str = str(target_file)
                    work_dir = str(bin_dir if bin_dir.exists() else install_path)
                    logger.info(f"Auto-launching target via standalone launcher: {target_str}")
                    
                    if sys.platform.startswith('win'):
                        # 환경변수 정화
                        import ctypes
                        for k in ['_MEIPASS', '_MEIPASS2', 'PYTHONPATH', 'PYTHONHOME', 'PYINSTALLER_STRICT_UNLOAD_MODE']:
                            try:
                                ctypes.windll.kernel32.SetEnvironmentVariableW(k, None)
                                os.environ.pop(k, None)
                            except Exception:
                                pass
                        
                        # [핵심] WScript.Shell VBScript 백그라운드 독립 런처 가동
                        # 인스톨러 프로세스가 완전히 종료된 후(0.5초 대기) Windows 쉘에서 부모 관계 없이 100% 안전 실행
                        import tempfile
                        vbs_content = (
                            'Set WshShell = CreateObject("WScript.Shell")\r\n'
                            f'WshShell.CurrentDirectory = "{work_dir}"\r\n'
                            'WScript.Sleep 500\r\n'
                            f'WshShell.Run """{target_str}""", 1, False\r\n'
                        )
                        temp_vbs = os.path.join(tempfile.gettempdir(), f"cosrqd_launch_{int(time.time())}.vbs")
                        try:
                            with open(temp_vbs, "w", encoding="ansi") as vf:
                                vf.write(vbs_content)
                            subprocess.Popen(["wscript.exe", temp_vbs], shell=False)
                        except Exception as vbs_err:
                            logger.warning(f"VBS launcher failed, fallback to explorer.exe: {vbs_err}")
                            # Fallback: Windows explorer.exe 직접 호출
                            subprocess.Popen(["explorer.exe", target_str], shell=False)
                    else:
                        subprocess.Popen([target_str], cwd=work_dir)
        except Exception as e:
            logger.error(f"Failed to auto-launch application: {e}")
        finally:
            import time
            time.sleep(0.2)
            self.close()
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
            import os as _os
            _os._exit(0)
    
    def update_buttons(self):
        """Update button states based on current page"""
        current = self.pages.currentIndex()
        
        self.back_btn.setEnabled(current > 0 and current < 2)
        
        if current == 3:  # Completion page
            self.next_btn.setText("완료")
            self.cancel_btn.setEnabled(False)
        elif current == 2:  # Installing
            self.next_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
        else:
            self.next_btn.setText("다음 >")
            self.next_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
    
    def start_installation(self):
        """Start installation process"""
        self.pages.setCurrentIndex(2)
        self.update_buttons()
        
        install_path = self.path_page.get_install_path()
        
        # Start installation in worker thread
        self.install_worker = InstallWorker(
            self.installer,
            install_path,
            self.version,
            ""  # Update server can be configured later
        )
        
        self.install_worker.progress.connect(self.progress_page.update_progress)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()
    
    def installation_finished(self, success: bool, message: str):
        """Handle installation completion"""
        if success:
            # Save configuration
            install_path = self.path_page.get_install_path()
            self.config_manager.config_dir = install_path
            self.config_manager.create_default_config(
                str(install_path),
                self.version
            )
        
        self.completion_page.set_success(success, message)
        self.pages.setCurrentIndex(3)
        self.update_buttons()


class UpdateDialog(QDialog):
    """Update notification and progress dialog"""
    
    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("업데이트 가능")
        self.setMinimumSize(500, 300)
        
        layout = QVBoxLayout()
        
        # Update info
        info_text = (
            f"새 버전을 사용할 수 있습니다!\n\n"
            f"현재 버전: {self.update_info.get('current_version', '알 수 없음')}\n"
            f"새 버전: {self.update_info.get('version', '알 수 없음')}\n\n"
            f"변경 사항:\n{self.update_info.get('changelog', '변경 사항이 없습니다')}"
        )
        
        info_label = QTextEdit()
        info_label.setPlainText(info_text)
        info_label.setReadOnly(True)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        update_btn = QPushButton("지금 업데이트")
        update_btn.clicked.connect(self.accept)
        
        later_btn = QPushButton("나중에")
        later_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(later_btn)
        button_layout.addWidget(update_btn)
        
        layout.addWidget(info_label)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)


class UpdateProgressDialog(QDialog):
    """Update progress dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("CosRQD 업데이트 중")
        self.setMinimumSize(400, 150)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        self.status_label = QLabel("업데이트 준비 중...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def update_progress(self, stage: str, current: int, total: int):
        """Update progress display"""
        stage_names = {
            "backup": "백업 생성 중...",
            "download": "업데이트 다운로드 중...",
            "verify": "다운로드 검증 중...",
            "extract": "파일 압축 해제 중...",
            "apply": "업데이트 적용 중..."
        }
        
        self.status_label.setText(stage_names.get(stage, f"{stage}..."))
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)


class LauncherMainWindow(QMainWindow):
    """Main launcher window (shown when app is already installed)"""
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.process_manager = ProcessManager()
        self.updater = Updater(config_manager)
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("CosRQD 화장품 연구소 관리 시스템 런처")
        self.setMinimumSize(400, 300)
        
        # Set Window Icon
        try:
            icon_path = Path(sys._MEIPASS if hasattr(sys, '_MEIPASS') else '').joinpath('Icon.ico')
            if not icon_path.exists():
                icon_path = Path(__file__).parent.parent / 'Icon.ico'
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.error(f"Failed to set launcher icon: {e}")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Title
        title = QLabel("CosRQD 런처")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Version info
        version = self.config_manager.get_version() or "알 수 없음"
        version_label = QLabel(f"현재 버전: {version}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Launch button
        launch_btn = QPushButton("애플리케이션 실행")
        launch_btn.setMinimumHeight(50)
        launch_btn.clicked.connect(self.launch_application)
        
        # Update button
        update_btn = QPushButton("업데이트 확인")
        update_btn.clicked.connect(self.check_updates)
        
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(version_label)
        layout.addWidget(launch_btn)
        layout.addWidget(update_btn)
        layout.addStretch()
        
        central_widget.setLayout(layout)
    
    def launch_application(self):
        """Launch the main application"""
        try:
            install_path = self.config_manager.get_install_path()
            if not install_path:
                QMessageBox.critical(self, "오류", "설치 경로를 찾을 수 없습니다!")
                return
            
            bin_dir = install_path / "bin"
            exe_candidates = list(bin_dir.glob("CosRQD*.exe")) + list(bin_dir.glob("화장품연구관리_*.exe")) + list(bin_dir.glob("CosRnD*.exe")) + [f for f in bin_dir.glob("*.exe") if not f.name.startswith("Setup_")] + [bin_dir / "main.exe"]
            app_path = next((c for c in exe_candidates if c.exists()), None)
            
            if not app_path:
                QMessageBox.critical(
                    self,
                    "오류",
                    f"다음 위치에서 애플리케이션 실행 파일을 찾을 수 없습니다:\n{bin_dir}"
                )
                return
            
            self.process_manager.start_application(app_path)
            QMessageBox.information(self, "성공", "애플리케이션이 성공적으로 실행되었습니다!")
            self.close()
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"애플리케이션 실행 실패:\n{e}")
    
    def check_updates(self):
        """Check for available updates"""
        try:
            update_server = self.config_manager.get_update_server()
            
            if not update_server:
                QMessageBox.information(
                    self,
                    "업데이트 서버 없음",
                    "업데이트 서버가 구성되지 않았습니다.\n"
                    "업데이트는 수동으로 설치해야 합니다."
                )
                return
            
            # Check for updates
            update_info = self.updater.check_for_updates(update_server)
            
            if update_info:
                # Add current version to update info
                update_info['current_version'] = self.config_manager.get_version()
                
                # Show update dialog
                dialog = UpdateDialog(update_info, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self.perform_update(update_info)
            else:
                QMessageBox.information(
                    self,
                    "업데이트 없음",
                    "최신 버전을 사용하고 있습니다!"
                )
            
            # Update last check time
            self.config_manager.update_last_check()
            
        except UpdateError as e:
            QMessageBox.critical(self, "업데이트 확인 실패", str(e))
    
    def perform_update(self, update_info: dict):
        """Perform update process"""
        # Terminate running application if needed
        if self.process_manager.is_app_running():
            reply = QMessageBox.question(
                self,
                "애플리케이션 종료",
                "업데이트를 위해 애플리케이션을 종료해야 합니다.\n"
                "계속하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
            
            if not self.process_manager.terminate_app():
                QMessageBox.critical(
                    self,
                    "오류",
                    "애플리케이션을 종료하지 못했습니다.\n"
                    "수동으로 종료한 후 다시 시도하세요."
                )
                return
        
        # Show progress dialog
        progress_dialog = UpdateProgressDialog(self)
        progress_dialog.show()
        
        # Start update worker
        self.update_worker = UpdateWorker(self.updater, update_info)
        self.update_worker.progress.connect(progress_dialog.update_progress)
        self.update_worker.finished.connect(
            lambda success, msg: self.update_finished(success, msg, progress_dialog)
        )
        self.update_worker.start()
    
    def update_finished(self, success: bool, message: str, progress_dialog: QDialog):
        """Handle update completion"""
        progress_dialog.close()
        
        if success:
            reply = QMessageBox.information(
                self,
                "업데이트 완료",
                f"{message}\n\n지금 애플리케이션을 실행하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.launch_application()
        else:
            QMessageBox.critical(self, "업데이트 실패", message)


class UninstallWorker(QThread):
    """Worker thread for background uninstallation"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, installer: Installer, install_path: Path, keep_user_data: bool):
        super().__init__()
        self.installer = installer
        self.install_path = install_path
        self.keep_user_data = keep_user_data
    
    def run(self):
        try:
            self.progress.emit(10, 100, "실행 중인 프로세스 정리 중...")
            import time
            time.sleep(0.3)
            
            self.progress.emit(30, 100, "프로그램 바이너리 및 설치 폴더 삭제 중...")
            success = self.installer.uninstall(self.install_path, keep_user_data=self.keep_user_data)
            time.sleep(0.3)
            
            self.progress.emit(80, 100, "바탕화면 바로가기 및 레지스트리 정리 중...")
            time.sleep(0.3)
            
            self.progress.emit(100, 100, "제거 작업 완료")
            if success:
                self.finished.emit(True, "CosRQD 프로그램이 컴퓨터에서 성공적으로 제거되었습니다.")
            else:
                self.finished.emit(False, "일부 파일을 제거하는 도중 오류가 발생했습니다.")
        except Exception as e:
            self.finished.emit(False, f"제거 중 오류 발생: {e}")


class UninstallOptionsPage(QWidget):
    """Uninstallation option selection page"""
    
    def __init__(self, install_path: Path, version: str, parent=None):
        super().__init__(parent)
        self.install_path = install_path
        self.version = version
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title = QLabel("CosRQD 제거 마법사")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        
        # Description
        desc = QLabel(
            f"컴퓨터에서 CosRQD_v{self.version} (화장품연구개발 플랫폼)을(를) 제거합니다.\n"
            f"설치 위치: {self.install_path}\n\n"
            "제거 방식을 선택해 주세요:"
        )
        desc.setWordWrap(True)
        
        from PyQt6.QtWidgets import QRadioButton, QButtonGroup, QGroupBox
        
        self.group_box = QGroupBox("제거 옵션 선택")
        box_layout = QVBoxLayout()
        box_layout.setSpacing(12)
        
        self.radio_keep = QRadioButton("기본 제거 (권장)\n  • 프로그램 실행 파일, 바로가기, 레지스트리만 제거합니다.\n  • 사용자가 작성한 연구 데이터 및 백업 파일은 안전하게 보존됩니다.")
        self.radio_keep.setChecked(True)
        
        self.radio_full = QRadioButton("완전 제거 (모든 파일 및 폴더 영구 삭제)\n  • 프로그램 실행 파일, 바로가기, 레지스트리뿐만 아니라\n  • 백업(backup), 로그(logs), 설치 폴더 전체를 컴퓨터에서 흔적 없이 100% 삭제합니다.")
        
        box_layout.addWidget(self.radio_keep)
        box_layout.addWidget(self.radio_full)
        self.group_box.setLayout(box_layout)
        
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(self.group_box)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def should_keep_user_data(self) -> bool:
        return self.radio_keep.isChecked()


class UninstallCompletionPage(QWidget):
    """Uninstallation completion page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        self.title_label = QLabel("제거 완료!")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.message_label = QLabel(
            "CosRQD 프로그램이 컴퓨터에서 성공적으로 제거되었습니다.\n\n"
            "'완료' 버튼을 클릭하여 프로그램을 종료하세요."
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        
        layout.addStretch()
        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_success(self, success: bool, message: str):
        """Set completion status"""
        if success:
            self.title_label.setText("제거 완료!")
            self.message_label.setText(
                f"{message}\n\n"
                "'완료' 버튼을 클릭하여 프로그램을 종료하세요."
            )
        else:
            self.title_label.setText("제거 실패")
            self.message_label.setText(
                f"제거 도중 오류가 발생했습니다:\n{message}\n\n"
                "수동으로 폴더를 정리하거나 지원팀에 문의하세요."
            )


class UninstallationWizard(QMainWindow):
    """Dedicated wizard for application uninstallation (Reverse Install Wizard)"""
    
    def __init__(self, config_manager: ConfigManager, version: str, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.version = version
        self.installer = Installer()
        
        # 설치 경로 탐색
        self.install_path = None
        if config_manager.exists():
            self.install_path = config_manager.get_install_path()
        if not self.install_path or not self.install_path.exists():
            for cand in [Path("C:/CosRQD"), Path("C:/CosRnD"), Path(os.environ.get("LOCALAPPDATA", "")) / "CosRQD"]:
                if cand.exists():
                    self.install_path = cand
                    break
        if not self.install_path:
            self.install_path = Path("C:/CosRQD")
            
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("CosRQD 제거 마법사")
        self.setMinimumSize(580, 420)
        self.resize(580, 420)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Pages
        self.pages = QStackedWidget()
        
        self.options_page = UninstallOptionsPage(self.install_path, self.version)
        self.progress_page = InstallationProgressPage()
        # 프로그레스 페이지 타이틀 커스텀
        try:
            for child in self.progress_page.findChildren(QLabel):
                if "설치 중" in child.text():
                    child.setText("CosRQD 제거 중")
                    break
        except Exception:
            pass
            
        self.completion_page = UninstallCompletionPage()
        
        self.pages.addWidget(self.options_page)      # Index 0
        self.pages.addWidget(self.progress_page)     # Index 1
        self.pages.addWidget(self.completion_page)   # Index 2
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.close)
        
        self.action_btn = QPushButton("제거 시작 >")
        self.action_btn.setStyleSheet("background-color: #D32F2F; color: white; font-weight: bold;")
        self.action_btn.clicked.connect(self.handle_action)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.action_btn)
        
        layout.addWidget(self.pages)
        layout.addLayout(button_layout)
        
        central_widget.setLayout(layout)
    
    def handle_action(self):
        current = self.pages.currentIndex()
        if current == 0:  # 제거 시작
            keep_data = self.options_page.should_keep_user_data()
            self.pages.setCurrentIndex(1)
            self.cancel_btn.setEnabled(False)
            self.action_btn.setEnabled(False)
            
            # Start worker
            self.worker = UninstallWorker(self.installer, self.install_path, keep_data)
            self.worker.progress.connect(self.progress_page.update_progress)
            self.worker.finished.connect(self.uninstall_finished)
            self.worker.start()
        elif current == 2:  # 완료 후 종료
            self.close()
    
    def uninstall_finished(self, success: bool, message: str):
        self.completion_page.set_success(success, message)
        self.pages.setCurrentIndex(2)
        self.cancel_btn.setVisible(False)  # 완료 화면에서는 취소 버튼 숨김
        self.action_btn.setText("완료")
        self.action_btn.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        self.action_btn.setEnabled(True)
        self.action_btn.setEnabled(True)


def run_uninstaller_gui(config_manager: ConfigManager, version: str):
    """
    Run dedicated reverse uninstallation wizard.
    """
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    app.setApplicationName("CosRQD 제거")
    
    wizard = UninstallationWizard(config_manager, version)
    wizard.show()
    sys.exit(app.exec())


def run_launcher_gui(config_manager: ConfigManager, version: str):
    """
    Run launcher GUI application.
    
    Args:
        config_manager: ConfigManager instance
        version: Application version
    """
    app = QApplication(sys.argv)
    app.setApplicationName("CosRQD 런처")
    
    # Check if already installed
    if config_manager.exists():
        window = LauncherMainWindow(config_manager)
    else:
        window = InstallationWizard(config_manager, version)
    
    window.show()
    sys.exit(app.exec())
