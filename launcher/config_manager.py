"""
Configuration Manager for CosRnD Launcher

Handles reading, writing, and managing installation configuration.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import threading


class ConfigManager:
    """Manages launcher configuration stored in config.json"""
    
    CONFIG_FILENAME = "config.json"
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory where config.json is stored.
                       If None, uses %LOCALAPPDATA%/CosRnD
        """
        if config_dir is None:
            # Default to %LOCALAPPDATA%\CosRnD
            local_app_data = os.getenv('LOCALAPPDATA')
            config_dir = Path(local_app_data) / "CosRnD"
        
        self.config_dir = Path(config_dir)
        self.config_path = self.config_dir / self.CONFIG_FILENAME
        self._lock = threading.Lock()
        self._config: Optional[Dict[str, Any]] = None
    
    def exists(self) -> bool:
        """Check if configuration file exists"""
        return self.config_path.exists()
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid
        """
        with self._lock:
            if not self.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            return self._config.copy()
    
    def save(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
        """
        with self._lock:
            # Ensure directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_path = self.config_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                # Atomic rename
                temp_path.replace(self.config_path)
                self._config = config.copy()
            except Exception as e:
                # Clean up temp file if it exists
                if temp_path.exists():
                    temp_path.unlink()
                raise e
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if self._config is None:
            try:
                self.load()
            except FileNotFoundError:
                return default
        
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value and save.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        if self._config is None:
            try:
                self.load()
            except FileNotFoundError:
                self._config = {}
        
        self._config[key] = value
        self.save(self._config)
    
    def create_default_config(
        self,
        install_path: str,
        version: str,
        update_server: str = ""
    ) -> Dict[str, Any]:
        """
        Create default configuration.
        
        Args:
            install_path: Installation directory path
            version: Current application version
            update_server: Update server URL (optional)
            
        Returns:
            Default configuration dictionary
        """
        config = {
            "install_path": str(install_path),
            "version": version,
            "installed_at": datetime.now().isoformat(),
            "last_update_check": datetime.now().isoformat(),
            "update_server": update_server
        }
        
        self.save(config)
        return config
    
    def update_version(self, new_version: str) -> None:
        """
        Update version in configuration.
        
        Args:
            new_version: New version string
        """
        self.set("version", new_version)
    
    def update_last_check(self) -> None:
        """Update last update check timestamp"""
        self.set("last_update_check", datetime.now().isoformat())
    
    def get_install_path(self) -> Optional[Path]:
        """Get installation path from config"""
        path_str = self.get("install_path")
        return Path(path_str) if path_str else None
    
    def get_version(self) -> Optional[str]:
        """Get current version from config"""
        return self.get("version")
    
    def get_update_server(self) -> Optional[str]:
        """Get update server URL from config"""
        return self.get("update_server")
