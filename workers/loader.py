# workers/loader.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Dict, Iterable, Tuple, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from infra.logging import log_worker_event 

from core.metadata import MetadataHandler
from core.rules import validate_filename


@dataclass
class FileRecord:
    filepath: str
    filename: str
    in_subfolder: bool
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    is_protected: bool = False
    is_corrupted: bool = False
    error_message: str = ""
    filename_warning: str = ""


class LoaderWorker(QThread):
    """Scans a folder recursively for PDFs, reads metadata, computes warnings, and streams results."""
    progress = pyqtSignal(int, int)            # current, total discovered PDFs
    status = pyqtSignal(str)                   # short status lines for the UI console
    file_found = pyqtSignal(dict)              # emits a dict per file (for table row)
    scan_complete = pyqtSignal(list)           # emits full list on completion
    error = pyqtSignal(str)                    # fatal errors
    subfolder_warning = pyqtSignal(list)       # list of subfolder relative paths (for the once-per-scan warning)

    def __init__(self, root_folder: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.root = os.path.abspath(root_folder)
        self._stop = False
        self._results: List[Dict] = []

    def stop(self):
        self._stop = True

    # ---- internal helpers ----
    def _iter_pdfs(self) -> Iterable[Tuple[str, str, bool]]:
        root_len = len(self.root.rstrip("\\/")) + 1
        for dirpath, _dirs, files in os.walk(self.root):
            for name in files:
                if name.lower().endswith(".pdf"):
                    full = os.path.join(dirpath, name)
                    rel = full[root_len:] if full.startswith(self.root) else name
                    in_sub = os.path.sep in rel
                    yield full, name, in_sub

    def _safe_validate_filename(self, filename: str) -> str:
        try:
            return validate_filename(filename) or ""
        except Exception:
            return ""

    def run(self):
        # Discover first so we know the total
        try:
            discovered = list(self._iter_pdfs())
        except Exception as e:
            log_worker_event("Loader", "error", str(e))
            self.error.emit(f"Scan failed: {e}")
            return

        total = len(discovered)
        log_worker_event("Loader", "started", f"{total} PDFs in {self.root}") 
        self.progress.emit(0, total)
        self.status.emit(f"Scanning… found {total} PDF(s).")

        # Compute subfolder list once (relative paths)
        subfolders = sorted(
            {os.path.dirname(p[len(self.root)+1:]) for (p, _n, _s) in discovered
             if p.startswith(self.root) and os.path.dirname(p[len(self.root)+1:])}
        )
        if subfolders:
            self.subfolder_warning.emit(subfolders)

        # Use MetadataHandler for read; fail fast if exiftool not found
        try:
            handler = MetadataHandler()
        except FileNotFoundError as e:
            self.error.emit(str(e))
            return

        results: List[Dict] = []
        done = 0
        for path, name, in_sub in discovered:
            if self._stop:
                self.status.emit("Scan cancelled.")
                self.scan_complete.emit(results)
                return

            md = handler.read_metadata(path)
            warn = self._safe_validate_filename(name)

            rec = FileRecord(
                filepath=path,
                filename=name,
                in_subfolder=in_sub,
                title=md.title,
                author=md.author,
                subject=md.subject,
                keywords=md.keywords,
                is_protected=md.is_protected,
                is_corrupted=md.is_corrupted,
                error_message=md.error_message,
                filename_warning=warn
            )

            row = {
                "filepath": rec.filepath,
                "filename": rec.filename,
                "in_subfolder": rec.in_subfolder,
                "title": rec.title,
                "author": rec.author,
                "subject": rec.subject,
                "keywords": rec.keywords,
                "is_protected": rec.is_protected,
                "is_corrupted": rec.is_corrupted,
                "error_message": rec.error_message,
                "filename_warning": rec.filename_warning,
            }
            results.append(row)
            self.file_found.emit(row)

            done += 1
            self.progress.emit(done, total)

        log_worker_event("Loader", "finished", f"{len(results)} files loaded") 
        self.status.emit("Scan complete.") 
        self.scan_complete.emit(results) 

class LoaderManager(QObject):
    """
    Thin manager façade used by the UI.
    Starts/stops the LoaderWorker and provides post-scan statistics and filters.
    """
    progress = pyqtSignal(int, int)
    status = pyqtSignal(str)
    file_found = pyqtSignal(dict)
    scan_complete = pyqtSignal(list)
    error = pyqtSignal(str)
    subfolder_warning = pyqtSignal(list)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._worker: Optional[LoaderWorker] = None
        self.loaded_files: List[Dict] = []

        # cache last computed stats
        self._stats = {"total": 0, "warnings": 0, "protected": 0}

    def start_loading(self, folder: str):
        self.stop_loading()
        self.loaded_files = []
        self._worker = LoaderWorker(folder)
        # connect pass-through signals
        self._worker.progress.connect(self.progress)
        self._worker.status.connect(self.status)
        self._worker.file_found.connect(self._on_file_found)
        self._worker.scan_complete.connect(self._on_scan_complete)
        self._worker.error.connect(self.error)
        self._worker.subfolder_warning.connect(self.subfolder_warning)
        self._worker.start()
        self.status.emit(f"Scanning folder: {folder}")

    def stop_loading(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self._worker = None

    def is_loading(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    # ---- signal handlers ----
    def _on_file_found(self, row: Dict):
        self.loaded_files.append(row)
        self.file_found.emit(row)

    def _on_scan_complete(self, rows: List[Dict]):
        self.loaded_files = rows
        self._recompute_stats()
        self.scan_complete.emit(rows)

    # ---- public helpers used by UI ----
    def get_statistics(self) -> Dict[str, int]:
        if not self.loaded_files:
            return {"total": 0, "warnings": 0, "protected": 0}
        return dict(self._stats)

    def _recompute_stats(self):
        total = len(self.loaded_files)
        warnings = sum(1 for r in self.loaded_files if r.get("filename_warning"))
        protected = sum(1 for r in self.loaded_files if r.get("is_protected"))
        self._stats = {"total": total, "warnings": warnings, "protected": protected}

    def get_files_by_status(self, status: str) -> List[Dict]:
        if status == "protected":
            return [r for r in self.loaded_files if r.get("is_protected")]
        if status == "warning":
            return [r for r in self.loaded_files if r.get("filename_warning")]
        if status == "error":
            return [r for r in self.loaded_files if r.get("is_corrupted") or r.get("error_message")]
            # kept for compatibility with UI's optional group
        return []
