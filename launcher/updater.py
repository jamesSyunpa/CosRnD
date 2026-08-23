"""
Updater Module for CosRnD Launcher

Handles automatic updates with download, verification, backup, and rollback.
"""

import os
import json
import hashlib
import logging
import shutil
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple
from datetime import datetime
import tempfile


logger = logging.getLogger(__name__)


class UpdateError(Exception):
    """Raised when update fails"""
    pass


class Updater:
    """Handles application updates"""
    
    # Network timeouts
    DOWNLOAD_TIMEOUT = 300  # 5 minutes
    CHECK_TIMEOUT = 10  # 10 seconds
    
    # Retry configuration
    MAX_RETRIES = 3
    
    def __init__(self, config_manager):
        """
        Initialize updater.
        
        Args:
            config_manager: ConfigManager instance
        """
        self.config_manager = config_manager
    
    def check_for_updates(self, update_server_url: str) -> Optional[Dict[str, Any]]:
        """
        Check if updates are available.
        
        Args:
            update_server_url: URL or local file path to check for updates (latest.json)
            
        Returns:
            Update info dictionary if update available, None otherwise
            
        Raises:
            UpdateError: If check fails
        """
        if not update_server_url:
            logger.info("No update server configured")
            return None
        
        logger.info(f"Checking for updates from: {update_server_url}")
        
        try:
            # Check if local path (Windows network share or local drive)
            if not (update_server_url.startswith("http://") or update_server_url.startswith("https://")):
                manifest_path = Path(update_server_url)
                if manifest_path.exists():
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        latest_info = json.load(f)
                else:
                    raise UpdateError(f"Local update server path not found: {update_server_url}")
            else:
                # Download latest.json via HTTP
                req = urllib.request.Request(update_server_url, headers={"User-Agent": "CosRnD-Launcher"})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=self.CHECK_TIMEOUT, context=ctx) as resp:
                    if resp.status == 200:
                        latest_info = json.loads(resp.read().decode('utf-8'))
                    else:
                        raise UpdateError(f"HTTP error {resp.status}")
            
            # Compare versions
            current_version = self.config_manager.get_version()
            latest_version = latest_info.get("version")
            
            logger.info(f"Current version: {current_version}, Latest version: {latest_version}")
            
            if current_version != latest_version:
                logger.info("Update available")
                return latest_info
            else:
                logger.info("Application is up to date")
                return None
                
        except Exception as e:
            raise UpdateError(f"Failed to check for updates: {e}")
    
    def download_update(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """
        Download/copy update file.
        
        Args:
            download_url: URL or local file path to download/copy from
            dest_path: Destination file path
            progress_callback: Optional callback(bytes_downloaded, total_bytes)
            
        Returns:
            Path to downloaded file
            
        Raises:
            UpdateError: If download/copy fails
        """
        logger.info(f"Downloading/copying update from: {download_url}")
        
        # Check if local file or network share path
        if not (download_url.startswith("http://") or download_url.startswith("https://")):
            try:
                src_path = Path(download_url)
                if not src_path.exists():
                    raise UpdateError(f"Source update file not found: {download_url}")
                
                total_size = src_path.stat().st_size
                downloaded = 0
                
                with open(src_path, 'rb') as fsrc, open(dest_path, 'wb') as fdst:
                    while True:
                        chunk = fsrc.read(65536) # Read in 64kb chunks
                        if not chunk:
                            break
                        fdst.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size:
                            progress_callback(downloaded, total_size)
                            
                logger.info(f"Local update file copy completed: {dest_path}")
                return dest_path
            except Exception as e:
                raise UpdateError(f"Failed to copy local update file: {e}")
        
        # HTTP download logic via urllib
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(download_url, headers={"User-Agent": "CosRnD-Launcher"})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                with urllib.request.urlopen(req, timeout=self.DOWNLOAD_TIMEOUT, context=ctx) as resp:
                    total_size = int(resp.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(dest_path, 'wb') as f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size:
                                progress_callback(downloaded, total_size)
                    
                    logger.info(f"Download completed: {dest_path}")
                    return dest_path
                    
            except Exception as e:
                logger.warning(f"Download attempt {attempt} failed: {e}")
                if attempt == self.MAX_RETRIES:
                    raise UpdateError(f"Failed to download update after {self.MAX_RETRIES} attempts: {e}")
                continue
        
        raise UpdateError("Download failed")
    
    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        """
        Calculate SHA256 checksum of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of SHA256 hash
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """
        Verify file checksum.
        
        Args:
            file_path: Path to file
            expected_checksum: Expected SHA256 checksum
            
        Returns:
            True if checksum matches
        """
        actual_checksum = self.calculate_checksum(file_path)
        matches = actual_checksum.lower() == expected_checksum.lower()
        
        if matches:
            logger.info("Checksum verification passed")
        else:
            logger.error(
                f"Checksum mismatch! Expected: {expected_checksum}, "
                f"Actual: {actual_checksum}"
            )
        
        return matches
    
    def create_backup(self, install_path: Path, version: str) -> Path:
        """
        Create backup of current installation.
        
        Args:
            install_path: Installation directory
            version: Current version for backup naming
            
        Returns:
            Path to backup directory
            
        Raises:
            UpdateError: If backup creation fails
        """
        try:
            backup_dir = install_path / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Create version-specific backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{version}_{timestamp}"
            backup_path = backup_dir / backup_name
            
            # Backup bin directory
            bin_dir = install_path / "bin"
            if bin_dir.exists():
                shutil.copytree(bin_dir, backup_path)
                logger.info(f"Created backup: {backup_path}")
                return backup_path
            else:
                raise UpdateError("bin directory not found")
                
        except Exception as e:
            raise UpdateError(f"Failed to create backup: {e}")
    
    def restore_backup(self, install_path: Path, backup_path: Path) -> None:
        """
        Restore from backup.
        
        Args:
            install_path: Installation directory
            backup_path: Backup directory to restore from
            
        Raises:
            UpdateError: If restore fails
        """
        try:
            logger.info(f"Restoring from backup: {backup_path}")
            
            bin_dir = install_path / "bin"
            
            # Remove current bin directory
            if bin_dir.exists():
                shutil.rmtree(bin_dir)
            
            # Restore from backup
            shutil.copytree(backup_path, bin_dir)
            
            logger.info("Backup restored successfully")
        except Exception as e:
            raise UpdateError(f"Failed to restore backup: {e}")
    
    def extract_update(self, archive_path: Path, dest_dir: Path) -> None:
        """
        Extract update archive.
        
        Args:
            archive_path: Path to update archive
            dest_dir: Destination directory
            
        Raises:
            UpdateError: If extraction fails
        """
        try:
            import zipfile
            
            logger.info(f"Extracting update to: {dest_dir}")
            
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
            
            logger.info("Update extracted successfully")
        except Exception as e:
            raise UpdateError(f"Failed to extract update: {e}")
    
    def apply_update(
        self,
        update_path: Path,
        install_path: Path,
        new_version: str
    ) -> None:
        """
        Apply update by replacing files atomically.
        
        Args:
            update_path: Path to extracted update files
            install_path: Installation directory
            new_version: New version number
            
        Raises:
            UpdateError: If update application fails
        """
        try:
            logger.info("Applying update...")
            
            bin_dir = install_path / "bin"
            
            # Copy new files over old ones
            for item in update_path.iterdir():
                dest_item = bin_dir / item.name
                
                if item.is_file():
                    # Atomic file replacement
                    temp_name = dest_item.with_suffix('.new')
                    shutil.copy2(item, temp_name)
                    temp_name.replace(dest_item)
                    logger.info(f"Updated file: {item.name}")
                elif item.is_dir():
                    # Replace directory
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(item, dest_item)
                    logger.info(f"Updated directory: {item.name}")
            
            # Update version in config
            self.config_manager.update_version(new_version)
            
            logger.info("Update applied successfully")
        except Exception as e:
            raise UpdateError(f"Failed to apply update: {e}")
    
    def perform_update(
        self,
        update_info: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> bool:
        """
        Perform complete update process.
        
        Args:
            update_info: Update information from latest.json
            progress_callback: Optional callback(stage, current, total)
            
        Returns:
            True if update was successful
        """
        install_path = self.config_manager.get_install_path()
        if not install_path:
            raise UpdateError("Installation path not found in configuration")
        
        current_version = self.config_manager.get_version()
        new_version = update_info.get("version")
        download_url = update_info.get("download_url")
        checksum = update_info.get("checksum")
        
        if not all([new_version, download_url, checksum]):
            raise UpdateError("Invalid update information")
        
        backup_path = None
        temp_dir = None
        
        try:
            # Create backup
            if progress_callback:
                progress_callback("backup", 0, 100)
            backup_path = self.create_backup(install_path, current_version)
            
            # Download update
            if progress_callback:
                progress_callback("download", 0, 100)
            
            temp_dir = Path(tempfile.mkdtemp())
            download_path = temp_dir / "update.zip"
            
            def download_progress(downloaded, total):
                if progress_callback and total > 0:
                    percent = int((downloaded / total) * 100)
                    progress_callback("download", percent, 100)
            
            self.download_update(download_url, download_path, download_progress)
            
            # Verify checksum
            if progress_callback:
                progress_callback("verify", 0, 100)
            
            if not self.verify_checksum(download_path, checksum):
                raise UpdateError("Checksum verification failed")
            
            if progress_callback:
                progress_callback("verify", 100, 100)
            
            # Extract update
            if progress_callback:
                progress_callback("extract", 0, 100)
            
            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir()
            self.extract_update(download_path, extract_dir)
            
            if progress_callback:
                progress_callback("extract", 100, 100)
            
            # Apply update
            if progress_callback:
                progress_callback("apply", 0, 100)
            
            self.apply_update(extract_dir, install_path, new_version)
            
            if progress_callback:
                progress_callback("apply", 100, 100)
            
            logger.info(f"Update to version {new_version} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            
            # Attempt rollback
            if backup_path and backup_path.exists():
                logger.info("Attempting to rollback...")
                try:
                    self.restore_backup(install_path, backup_path)
                    logger.info("Rollback successful")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
            
            raise UpdateError(f"Update failed: {e}")
        
        finally:
            # Cleanup temporary files
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
