# core/undo.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from core.metadata import MetadataHandler


@dataclass
class UndoBatch:
    """
    A single undo batch: list of (filepath, old_values, new_values).
    'old_values' are what we restore to; 'new_values' are informative only.
    """
    changes: List[Tuple[str, Dict[str, str], Dict[str, str]]]


class UndoManager:
    """Simple LIFO stack of UndoBatch objects."""
    def __init__(self):
        self._stack: List[UndoBatch] = []

    def push_batch(self, changes: List[Tuple[str, Dict[str, str], Dict[str, str]]]):
        if changes:
            self._stack.append(UndoBatch(changes=changes))

    def can_undo(self) -> bool:
        return len(self._stack) > 0

    def pop_last(self) -> UndoBatch | None:
        if not self._stack:
            return None
        return self._stack.pop()

    def clear(self):
        self._stack.clear()


class UndoWorker(QThread):
    """
    Background worker that restores metadata for the last batch.

    Emits:
      - progress(current:int, total:int)
      - file_progress(done:int, total:int, filename:str)
      - status(msg:str)
      - finished(stats:dict, failures:list[dict])
      - cancelled()
      - error(msg:str)
    """
    progress = pyqtSignal(int, int)
    file_progress = pyqtSignal(int, int, str)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict, list)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, batch: UndoBatch, parent: QObject | None = None):
        super().__init__(parent)
        self._batch = batch
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        try:
            handler = MetadataHandler()
        except FileNotFoundError as e:
            self.error.emit(str(e))
            return

        total = len(self._batch.changes)
        done = 0
        successes = 0
        failures: List[dict] = []

        self.status.emit(f"Starting undo for {total} file(s)...")

        for (path, old_values, _new_values) in self._batch.changes:
            if self._stop:
                self.status.emit("Undo cancelled.")
                self.cancelled.emit()
                return

            name = path.split("\\")[-1].split("/")[-1]
            self.file_progress.emit(done, total, name)
            self.progress.emit(done, total)

            # Split into updates vs clears (because write_metadata ignores empties)
            updates: Dict[str, str] = {}
            clears: List[str] = []
            for field, val in (old_values or {}).items():
                if (val or "").strip():
                    updates[field] = val
                else:
                    clears.append(field)

            ok = True
            err = ""

            if updates:
                ok, err = handler.write_metadata(path, updates)
            if ok and clears:
                ok, err = handler.clear_metadata_fields(path, clears)

            if not ok:
                failures.append({"filename": name, "filepath": path, "error": err})
            else:
                successes += 1

            done += 1
            self.file_progress.emit(done, total, name)
            self.progress.emit(done, total)

        stats = {"total": total, "restored": successes, "failures": len(failures)}
        self.status.emit(f"Undo complete: {successes} restored, {len(failures)} failed.")
        self.finished.emit(stats, failures)
