"""
Process Manager for CosRnD Launcher

Handles application process lifecycle: checking, termination, and launching.
"""

import os
import time
import subprocess
import psutil
from pathlib import Path
from typing import Optional, List
import logging


logger = logging.getLogger(__name__)


class ProcessManager:
    """Manages application process lifecycle"""
    
    def __init__(self, app_exe_name: str = "main.exe", app_name: str = "CosRQD"):
        """
        Initialize process manager.
        
        Args:
            app_exe_name: Name of the application executable
            app_name: Application name for window title matching
        """
        self.app_exe_name = app_exe_name
        self.app_name = app_name
    
    def find_app_processes(self) -> List[psutil.Process]:
        """
        Find all running instances of the application.
        
        Returns:
            List of Process objects for the application
        """
        processes = []
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    name = proc.info['name']
                    if name == self.app_exe_name or name == "main.exe" or name == "화장품연구관리_v1.0.exe":
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Error finding processes: {e}")
        
        return processes
    
    def is_app_running(self) -> bool:
        """
        Check if application is currently running.
        
        Returns:
            True if at least one instance is running
        """
        return len(self.find_app_processes()) > 0
    
    def request_graceful_shutdown(self) -> bool:
        """
        Request graceful shutdown of the application.
        
        Sends WM_CLOSE message to application windows.
        
        Returns:
            True if shutdown request was sent successfully
        """
        try:
            import win32gui
            import win32con
            
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self.app_name in title:
                        windows.append(hwnd)
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            for hwnd in windows:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                logger.info(f"Sent WM_CLOSE to window: {hwnd}")
            
            return len(windows) > 0
        except ImportError:
            logger.warning("pywin32 not available, cannot send graceful shutdown")
            return False
        except Exception as e:
            logger.error(f"Error requesting graceful shutdown: {e}")
            return False
    
    def wait_for_termination(self, timeout: int = 30) -> bool:
        """
        Wait for application to terminate.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if application terminated within timeout, False otherwise
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if not self.is_app_running():
                logger.info("Application terminated successfully")
                return True
            time.sleep(0.5)
        
        logger.warning(f"Application did not terminate within {timeout} seconds")
        return False
    
    def force_terminate(self) -> bool:
        """
        Force terminate all application processes.
        
        Returns:
            True if all processes were terminated
        """
        processes = self.find_app_processes()
        
        if not processes:
            return True
        
        for proc in processes:
            try:
                proc.terminate()
                logger.info(f"Terminated process: {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.error(f"Failed to terminate process {proc.pid}: {e}")
        
        # Wait a bit for termination
        time.sleep(2)
        
        # Force kill if still running
        for proc in processes:
            try:
                if proc.is_running():
                    proc.kill()
                    logger.warning(f"Force killed process: {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return not self.is_app_running()
    
    def terminate_app(self, timeout: int = 30, force: bool = False) -> bool:
        """
        Terminate the application gracefully if possible, forcefully if needed.
        
        Args:
            timeout: Maximum time to wait for graceful shutdown
            force: If True, skip graceful shutdown and force terminate
            
        Returns:
            True if application was terminated successfully
        """
        if not self.is_app_running():
            logger.info("Application is not running")
            return True
        
        if not force:
            # Try graceful shutdown first
            logger.info("Requesting graceful shutdown...")
            self.request_graceful_shutdown()
            
            if self.wait_for_termination(timeout):
                return True
            
            logger.warning("Graceful shutdown failed, will force terminate")
        
        # Force terminate
        return self.force_terminate()
    
    def start_application(self, app_path: Path, wait: bool = False) -> Optional[subprocess.Popen]:
        """
        Start the application.
        
        Args:
            app_path: Path to the application executable
            wait: If True, wait for process to complete
            
        Returns:
            Popen object if wait=False, None if wait=True
            
        Raises:
            FileNotFoundError: If executable doesn't exist
        """
        if not app_path.exists():
            raise FileNotFoundError(f"Application executable not found: {app_path}")
        
        logger.info(f"Starting application: {app_path}")
        
        try:
            # Start in the application directory
            cwd = app_path.parent
            
            if wait:
                subprocess.run([str(app_path)], cwd=cwd, check=True)
                return None
            else:
                process = subprocess.Popen(
                    [str(app_path)],
                    cwd=cwd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"Application started with PID: {process.pid}")
                return process
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            raise
    
    def restart_application(self, app_path: Path, timeout: int = 30) -> bool:
        """
        Restart the application.
        
        Args:
            app_path: Path to the application executable
            timeout: Timeout for termination
            
        Returns:
            True if restart was successful
        """
        logger.info("Restarting application...")
        
        if not self.terminate_app(timeout):
            logger.error("Failed to terminate application for restart")
            return False
        
        try:
            self.start_application(app_path, wait=False)
            return True
        except Exception as e:
            logger.error(f"Failed to start application after termination: {e}")
            return False
