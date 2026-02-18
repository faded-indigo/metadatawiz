# infra/bundled.py
from __future__ import annotations

import os
import sys 
from pathlib import Path
from typing import Tuple

APP_NAME = "HSPMetaWizard"

def get_appdata_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or ""
    return Path(base) / APP_NAME

def get_sessions_dir() -> Path:
    p = get_appdata_root() / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p

def resource_path(rel: str) -> str:
    """
    Return absolute path to a resource for both dev and PyInstaller.
    Place app.ico and splash.png under the project 'resources' folder.
    """
    try:
        base = Path(getattr(sys, "_MEIPASS"))  # PyInstaller temp dir
    except Exception:
        base = Path(__file__).resolve().parents[1]  # project root
    return str(base / rel)

def get_logs_dir() -> Path:
    p = get_appdata_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_exiftool_path() -> str:
    """
    Resolve the path to the bundled ExifTool executable.
    Order:
      1) Next to the app (PyInstaller one-folder): ./tools/exiftool.exe
      2) Development tree: project_root/tools/exiftool.exe
    """
    # 1) Running beside the executable/frozen bundle
    try:
        base = Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
    except Exception:
        base = Path(__file__).resolve().parents[1]  # project root

    cand = base / "tools" / "exiftool.exe"
    if cand.exists():
        return str(cand)

    # 2) Fallback to project root guess
    dev = Path(__file__).resolve().parents[1] / "tools" / "exiftool.exe"
    return str(dev)
