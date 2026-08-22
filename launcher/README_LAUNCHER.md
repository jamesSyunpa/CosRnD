# CosRnD Launcher Documentation

## Overview

The CosRnD Launcher is an installer and updater system that manages the installation, configuration, and updates of the CosRnD application.

## Features

- **First-Time Installation**: Guided installation wizard with customizable installation path
- **Automatic Updates**: Check and install updates automatically from configured server
- **Process Management**: Gracefully handles application shutdown during updates
- **Backup & Rollback**: Automatic backup before updates with rollback on failure
- **Secure Downloads**: SHA256 checksum verification for all downloads

## Distribution Package Structure

When you build the distribution, you'll have the following structure:

```
CosRnD_Release/
├── launcher.exe          # The launcher/installer
├── main.exe             # The main application
├── VERSION              # Version file
├── Icon.ico             # Application icon
├── data/                # Data files (if any)
└── assets/              # Asset files (if any)
```

## Installation Process

### First-Time Installation

1. Extract the distribution package to any location (e.g., Downloads folder)
2. Run `launcher.exe`
3. Follow the installation wizard:
   - Welcome screen
   - Select installation location (default: `%LOCALAPPDATA%\CosRnD`)
   - Installation progress
   - Completion

### After Installation

The launcher creates the following directory structure:

```
%LOCALAPPDATA%\CosRnD/
├── bin/                 # Application binaries
│   ├── main.exe
│   ├── Icon.ico
│   ├── VERSION
│   ├── data/
│   └── assets/
├── backup/              # Backup folder for updates
├── logs/                # Log files
└── config.json          # Configuration file
```

### Configuration File

The `config.json` contains:

```json
{
  "install_path": "C:\\Users\\USERNAME\\AppData\\Local\\CosRnD",
  "version": "v55",
  "installed_at": "2025-12-19T11:27:24+09:00",
  "last_update_check": "2025-12-19T11:27:24+09:00",
  "update_server": ""
}
```

## Update Process

### Configuring Update Server

To enable automatic updates, you need to:

1. Host a `latest.json` file on a web server or GitHub releases
2. Update the `update_server` field in `config.json` to point to the URL

Example `latest.json`:

```json
{
  "version": "v56",
  "download_url": "https://example.com/CosRnD_v56.zip",
  "checksum": "abc123...",
  "changelog": "- New features\n- Bug fixes",
  "release_date": "2025-12-19"
}
```

### Update Workflow

1. User clicks "Check for Updates" in launcher
2. Launcher downloads and parses `latest.json`
3. If new version is available, shows update dialog with changelog
4. User approves update
5. Launcher:
   - Closes running application (if any)
   - Creates backup of current version
   - Downloads new version
   - Verifies checksum
   - Extracts update
   - Applies update atomically
   - Updates config.json with new version
6. User can launch updated application

### Update Rollback

If an update fails at any stage:
- The launcher automatically restores from the backup
- The application remains functional with the previous version
- User is notified of the failure

## Building the Launcher

### Prerequisites

Install required packages:

```bash
pip install PyQt6 psutil requests pywin32 pyinstaller
```

### Build Launcher

**Method 1: Unified Build (Recommended)**
```bash
# Build both launcher and main app together
pyinstaller build.spec
# Output: dist/CosRnD/ folder contains both executables
```

**Method 2: Separate Build**
```bash
# Build launcher only (if needed separately)
pyinstaller launcher_build.spec
```

> **Note**: The main `build.spec` file now builds both `launcher.exe` and the main application in one step.

### Create Distribution Package

**Automated (Recommended)**:
```bash
python build_distribution.py
```

This script:
1. Builds both executables using `build.spec`
2. Creates `CosRnD_Release/` folder with all files
3. Generates versioned ZIP archive

**Manual**:
After running `pyinstaller build.spec`:

1. Files are in `dist/CosRnD/` folder
2. Copy entire folder or selected files for distribution
3. Include VERSION, Icon.ico, data, and assets
4. Compress as ZIP

The `build_distribution.py` script already exists in your project and automates this process.

## Troubleshooting

### Installation Issues

**Problem**: "Insufficient disk space"
- **Solution**: Free up at least 500MB on the target drive

**Problem**: "Permission denied" during installation
- **Solution**: Don't install to Program Files; use the default location (%LOCALAPPDATA%)

### Update Issues

**Problem**: Update fails with "Application won't close"
- **Solution**: Manually close the application and try again

**Problem**: Update fails with "Checksum mismatch"
- **Solution**: The download may be corrupt; try again. Check if the server's latest.json has correct checksum

**Problem**: "No update server configured"
- **Solution**: Edit `config.json` and add update server URL

### Application Launch Issues

**Problem**: "Application not found"
- **Solution**: Verify that `bin/main.exe` exists in the installation directory

**Problem**: Application crashes after update
- **Solution**: The launcher creates backups in `backup/` folder. You can manually restore from there

## Advanced Configuration

### Custom Installation Path

Edit the launcher code to change the default path:

```python
# In launcher/installer.py
@staticmethod
def get_default_install_path() -> Path:
    return Path("C:/CustomPath/CosRnD")  # Your custom path
```

### Update Server Options

The update server can be:
- **GitHub Releases**: `https://github.com/user/repo/releases/latest/download/latest.json`
- **Custom Web Server**: `https://yourdomain.com/updates/latest.json`
- **Local Network**: `file:///\\server\share\updates\latest.json`

### Logging

Logs are stored in:
- Installation: `launcher.log` (current directory during install)
- After installation: `%LOCALAPPDATA%\CosRnD\logs\`

## Security Considerations

1. **HTTPS Required**: Always use HTTPS for update servers to prevent MITM attacks
2. **Checksum Verification**: Never skip checksum verification
3. **Code Signing**: Consider signing executables for production deployment
4. **Permissions**: The launcher requests minimal permissions by defaulting to user folders

## License

This launcher system is part of the CosRnD application.
