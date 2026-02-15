"""
CosRnD Launcher Main Entry Point

This is the main launcher application that handles:
- First-time installation
- Application updates
- Process management
"""

import sys
import logging
from pathlib import Path

from launcher.config_manager import ConfigManager
from launcher.launcher_gui import run_launcher_gui


# Configure logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


def setup_logging():
    """Configure logging for the launcher"""
    # Log to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler('launcher.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def read_version() -> str:
    """
    Read application version from folder name or VERSION file.
    
    Priority:
    1. Folder name pattern (_vXX)
    2. VERSION file
    3. Default v1.0.0
    
    Returns:
        Version string
    """
    try:
        import re
        import os
        
        # 1순위: 폴더 이름에서 버전 추출 (예: CosRnD_v57 -> v57)
        current_dir = Path(__file__).parent
        folder_name = current_dir.name
        version_match = re.search(r'_v(\d+)', folder_name)
        if version_match:
            return f"v{version_match.group(1)}"
        
        # 2순위: VERSION 파일
        version_file = current_dir / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    
    return "v1.0.0"


def main():
    """Main entry point for launcher"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("CosRnD Launcher Starting")
    logger.info("=" * 60)
    
    try:
        # Read version
        version = read_version()
        logger.info(f"Application version: {version}")
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        
        # Check if this is first run or existing installation
        if config_manager.exists():
            logger.info("Existing installation detected")
            install_path = config_manager.get_install_path()
            logger.info(f"Installation path: {install_path}")
        else:
            logger.info("First run - installation required")
        
        # Run GUI
        run_launcher_gui(config_manager, version)
        
    except Exception as e:
        logger.exception(f"Fatal error in launcher: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
