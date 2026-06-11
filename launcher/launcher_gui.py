"""
Launcher GUI for CosRnD Application

PyQt6-based GUI for installation wizard and update management.
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFileDialog, QMessageBox,
    QStackedWidget, QLineEdit, QTextEdit, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from launcher.config_manager import ConfigManager
from launcher.installer import Installer, InstallationError
from launcher.updater import Updater, UpdateError
from launcher.process_manager import ProcessManager


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
        title = QLabel("CosRnD 설치 마법사에 오신 것을 환영합니다")
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
            "CosRnD를 설치할 위치를 선택하세요.\n"
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
        title = QLabel("CosRnD 설치 중")
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
        title = QLabel("설치 완료!")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.message_label = QLabel(
            "CosRnD가 성공적으로 설치되었습니다.\n\n"
            "'완료' 버튼을 클릭하여 설치 프로그램을 종료하세요."
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(self.message_label)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_success(self, success: bool, message: str):
        """Set completion status"""
        if success:
            self.message_label.setText(
                f"{message}\n\n"
                "'완료' 버튼을 클릭하여 설치 프로그램을 종료하세요."
            )
        else:
            self.message_label.setText(
                f"설치 실패:\n{message}\n\n"
                "다시 시도하거나 지원팀에 문의하세요."
            )


class InstallationWizard(QMainWindow):
    """Installation wizard main window"""
    
    def __init__(self, config_manager: ConfigManager, version: str):
        super().__init__()
        self.config_manager = config_manager
        self.version = version
        self.installer = Installer()
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("CosRnD 설치 마법사")
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
        """Go to next page or start installation"""
        current = self.pages.currentIndex()
        
        if current == 0:  # Welcome -> Path selection
            self.pages.setCurrentIndex(1)
        elif current == 1:  # Path selection -> Installation
            self.start_installation()
        elif current == 3:  # Completion -> Close
            self.close()
        
        self.update_buttons()
    
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
        self.setWindowTitle("CosRnD 업데이트 중")
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
        self.setWindowTitle("화장품 연구소 관리 시스템 런처")
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
        title = QLabel("CosRnD 런처")
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
            
            app_path = install_path / "bin" / "화장품연구관리_v1.0.3.exe"
            if not app_path.exists():
                app_path = install_path / "bin" / "main.exe"
            
            if not app_path.exists():
                QMessageBox.critical(
                    self,
                    "오류",
                    f"다음 위치에서 애플리케이션을 찾을 수 없습니다:\n{install_path / 'bin' / '화장품연구관리_v1.0.3.exe'}"
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


def run_launcher_gui(config_manager: ConfigManager, version: str):
    """
    Run launcher GUI application.
    
    Args:
        config_manager: ConfigManager instance
        version: Application version
    """
    app = QApplication(sys.argv)
    app.setApplicationName("CosRnD 런처")
    
    # Check if already installed
    if config_manager.exists():
        window = LauncherMainWindow(config_manager)
    else:
        window = InstallationWizard(config_manager, version)
    
    window.show()
    sys.exit(app.exec())
