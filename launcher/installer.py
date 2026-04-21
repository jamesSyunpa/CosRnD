"""
Installer Module for CosRnD Launcher

Handles first-time installation of the application.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import psutil


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
        """
        Get default installation path.
        
        Returns:
            Default installation directory (%LOCALAPPDATA%/CosRnD)
        """
        return Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / "CosRnD"
    
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
            main_exe = bin_dir / "main.exe"
            
            if not main_exe.exists():
                logger.error("main.exe not found in installation")
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
        
        logger.info("Installation completed successfully")
        
        # Return config data
        return {
            "install_path": str(install_path),
            "version": version,
            "update_server": update_server
        }
    
    def uninstall(self, install_path: Path, keep_user_data: bool = True) -> bool:
        """
        Uninstall the application.
        
        Args:
            install_path: Installation directory
            keep_user_data: If True, preserve user data/config
            
        Returns:
            True if uninstallation was successful
        """
        try:
            logger.info(f"Uninstalling from: {install_path}")
            
            if not install_path.exists():
                logger.warning("Installation directory does not exist")
                return True
            
            if keep_user_data:
                # Remove only bin directory
                bin_dir = install_path / "bin"
                if bin_dir.exists():
                    shutil.rmtree(bin_dir)
                    logger.info("Removed application binaries")
            else:
                # Remove entire installation
                shutil.rmtree(install_path)
                logger.info("Removed entire installation directory")
            
            return True
        except Exception as e:
            logger.error(f"Uninstallation failed: {e}")
            return False
