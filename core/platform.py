# core/platform.py
"""
Platform-specific file operations.
Consolidates Windows-specific code for cleaner metadata.py.
"""
from __future__ import annotations

import os
import time
import stat
from typing import Tuple

if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    
    _MoveFileExW = ctypes.windll.kernel32.MoveFileExW
    _MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    _MoveFileExW.restype = wintypes.BOOL
    
    MOVEFILE_REPLACE_EXISTING = 0x1
    MOVEFILE_COPY_ALLOWED = 0x2
    MOVEFILE_WRITE_THROUGH = 0x8
    FILE_ATTRIBUTE_NORMAL = 0x80
    
    _SetFileAttributesW = ctypes.windll.kernel32.SetFileAttributesW
    _SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    _SetFileAttributesW.restype = wintypes.BOOL


def clear_readonly(path: str) -> None:
    """Clear read-only attribute on Windows."""
    if not os.path.exists(path):
        return
        
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass
        
    if os.name == "nt":
        try:
            _SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL)
        except Exception:
            pass


def robust_replace(src: str, dst: str, attempts: int = 10) -> Tuple[bool, str]:
    """
    Platform-aware file replacement with retry logic.
    Returns (success, error_message).
    """
    if os.name != "nt":
        # Simple replace on non-Windows
        try:
            os.replace(src, dst)
            return True, ""
        except Exception as e:
            return False, str(e)
    
    # Windows: clear read-only and retry with MoveFileEx
    clear_readonly(dst)
    delay = 0.05
    last_err = ""
    
    for i in range(attempts):
        try:
            flags = MOVEFILE_REPLACE_EXISTING | MOVEFILE_COPY_ALLOWED | MOVEFILE_WRITE_THROUGH
            if _MoveFileExW(src, dst, flags):
                return True, ""
            last_err = "MoveFileExW failed (sharing violation or lock)"
        except Exception as e:
            last_err = str(e)
        time.sleep(min(delay, 0.5))
        delay *= 1.5
    
    return False, (last_err or "Access denied while replacing file")


def fsync_path(path: str) -> None:
    """Best-effort file sync to disk."""
    try:
        with open(path, 'rb+') as f:
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass
        
    # Also sync directory
    try:
        dir_fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        pass