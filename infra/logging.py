# infra/logging.py
"""
Minimal logging infrastructure for HSP Metadata Wizard.
Logs only key events: worker start/finish/errors, startup info.
"""
from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path


def get_logger(name: str = "HSPMetaWizard") -> logging.Logger:
    """
    Get or create a logger with rotating file handler.
    
    Args:
        name: Logger name (default: HSPMetaWizard)
        
    Returns:
        Configured logger instance
        
    Log location:
        %LOCALAPPDATA%/HSPMetaWizard/logs/hspmeta_YYYY-MM.log
    """
    logger = logging.getLogger(name)
    
    # Only configure once
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Create log directory
    log_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "HSPMetaWizard" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Monthly log file naming
    log_file = log_dir / f"hspmeta_{datetime.now().strftime('%Y-%m')}.log"
    
    # Rotating handler: 5MB max, keep 3 backups
    handler = RotatingFileHandler(
        log_file, 
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    
    # Simple format: timestamp level message
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


def log_startup(exiftool_path: str, pikepdf_available: bool):
    """
    Log application startup information.
    
    Args:
        exiftool_path: Path to ExifTool executable
        pikepdf_available: Whether pikepdf module is available
    """
    logger = get_logger()
    logger.info("=" * 60)
    logger.info("HSP Metadata Wizard started")
    logger.info(f"ExifTool: {exiftool_path}")
    logger.info(f"pikepdf available: {pikepdf_available}")


def log_worker_event(worker_type: str, event: str, details: str = ""):
    """
    Log worker lifecycle events.
    
    Args:
        worker_type: Type of worker (Loader/Writer/Undo)
        event: Event type (started/finished/error/cancelled)
        details: Additional details (file counts, error messages)
    """
    logger = get_logger()
    if details:
        logger.info(f"{worker_type} {event}: {details}")
    else:
        logger.info(f"{worker_type} {event}")