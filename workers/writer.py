# workers/writer.py
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PyQt6.QtCore import QThread, pyqtSignal

from core.metadata import MetadataHandler
from core.rules import process_keywords

# Logging helper (best-effort; no hard failure if not present)
try:
    from infra.logging import log_worker_event  # type: ignore
except Exception:  # pragma: no cover
    def log_worker_event(worker_type: str, event: str, details: str = "") -> None:  # type: ignore
        pass


class WriterWorker(QThread):
    """
    Threaded writer that applies metadata updates to a list of PDF files.
    - Uses core.metadata.MetadataHandler for IO (read/write/clear).
    - Applies per-field operations:
        * "replace": write non-empty text
        * "append":  merge into existing value (keywords -> canonicalize; author/subject -> token-merge)
        * "clear":   cleared explicitly via clear_metadata_fields()
        * "from_filename": title only, uses file stem
    - Journals changes for Undo: list of tuples (path, old_values, new_values)
    """

    # Signals
    progress = pyqtSignal(int, int)                 # (done, total)
    file_progress = pyqtSignal(int, int, str)       # (step, steps, filename) - 1 step per file here
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    finished = pyqtSignal(dict, list, list)         # (stats, failures, journal)

    def __init__(
        self,
        files: List[Dict[str, Any]] | List[str],
        updates: Dict[str, str],
        ops: Dict[str, str],
        parent: Optional[object] = None,
    ) -> None:
        super().__init__(parent)
        self._files = files or []
        self._updates = {str(k).lower(): v for k, v in (updates or {}).items()}
        self._ops = {str(k).lower(): str(v) for k, v in (ops or {}).items()}
        self._cancel = False

    # -------------------- API --------------------

    def cancel(self) -> None:
        self._cancel = True

    # -------------------- Helpers ----------------

    @staticmethod
    def _filename_stem(path: str) -> str:
        return Path(path).stem

    @staticmethod
    def _resolve_path(item: Dict[str, Any] | str) -> str:
        if isinstance(item, str):
            return item
        return item.get("filepath") or item.get("path") or item.get("fullpath") or item.get("full_path") or ""

    # -------------------- Core -------------------

    def _compute_updates_for_file(self, path: str, current) -> Dict[str, str]:
        """
        Compute new values for this file, based on self._updates and self._ops.
        Returns a dict field->new_value. Empty values are not included.
        Notes:
          - Field names are normalized to lowercase keys: 'title', 'author', 'subject', 'keywords'
          - 'from_filename' is only valid for 'title'
          - 'clear' is handled in run(), not here
          - Keywords are canonicalized via core.rules.process_keywords(combined)
          - Author/Subject 'append' merges tokens from ', ; |' with case-insensitive de-dup and emits comma+space
        """
        per_file: Dict[str, str] = {}

        for field, op in (self._ops or {}).items():
            field_l = (field or "").lower()
            op_l = (op or "replace").lower()

            # Special op: from_filename (title only)
            if op_l == "from_filename" and field_l == "title":
                per_file[field_l] = self._filename_stem(path)
                continue

            # 'clear' handled later
            if op_l == "clear":
                continue

            # Pull candidate text; skip empties/None
            val = self._updates.get(field_l)
            if val is None:
                continue
            text = str(val).strip()
            if not text:
                continue

            # Keywords: canonicalize (append -> base + ", " + text; replace -> text)
            if field_l == "keywords":
                base = getattr(current, field_l, "") or ""
                combined = text if op_l != "append" else (f"{base}, {text}" if base else text)
                per_file[field_l] = process_keywords(combined)
                continue

            # Author/Subject: append merges on , ; | with CI de-dup; replace direct
            if field_l in ("author", "subject"):
                if op_l == "append":
                    base = getattr(current, field_l, "") or ""
                    base_parts = [p.strip() for p in re.split(r"[;,|]", base) if p.strip()] if base else []
                    add_parts = [p.strip() for p in re.split(r"[;,|]", text) if p.strip()]
                    seen = {p.casefold() for p in base_parts}
                    merged: List[str] = base_parts[:]
                    for p in add_parts:
                        k = p.casefold()
                        if k not in seen:
                            seen.add(k)
                            merged.append(p)
                    per_file[field_l] = ", ".join(merged)
                else:
                    per_file[field_l] = text
                continue

            # Title (and any other string field): append == replace for title; normal replace otherwise
            if op_l == "append" and field_l != "title":
                base = getattr(current, field_l, "") or ""
                per_file[field_l] = f"{base} {text}" if base else text
            else:
                per_file[field_l] = text

        return per_file

    # -------------------- Thread entry --------------------

    def run(self) -> None:  # noqa: C901
        try:
            handler = MetadataHandler()
        except FileNotFoundError as e:
            self.error.emit(str(e))
            self.finished.emit({"total": 0, "successes": 0, "skipped": 0, "failures": 1}, [{"error": str(e)}], [])
            return

        total = len(self._files)
        done = 0
        successes = 0
        skipped = 0
        failures: List[Dict[str, str]] = []
        journal: List[Tuple[str, Dict[str, str], Dict[str, str]]] = []

        log_worker_event("Writer", "start", f"{total} file(s)")

        for item in (self._files or []):
            if self._cancel:
                self.cancelled.emit()
                log_worker_event("Writer", "cancelled")
                break

            path = self._resolve_path(item)
            name = os.path.basename(path) if path else "(unknown)"
            if not path or not os.path.exists(path):
                failures.append({"filename": name, "filepath": path, "error": "File not found"})
                done += 1
                self.file_progress.emit(1, 1, name)
                self.progress.emit(done, total)
                continue

            # Read current metadata
            try:
                current = handler.read_metadata(path)
            except Exception as e:
                failures.append({"filename": name, "filepath": path, "error": f"Read error: {e}"})
                done += 1
                self.file_progress.emit(1, 1, name)
                self.progress.emit(done, total)
                continue

            if current.is_protected:
                # Non-blocking skip with reason
                skipped += 1
                done += 1
                self.status.emit(f"Skipped protected PDF: {name}")
                self.file_progress.emit(1, 1, name)
                self.progress.emit(done, total)
                continue

            if current.is_corrupted:
                failures.append({"filename": name, "filepath": path, "error": current.error_message or "Corrupted PDF"})
                done += 1
                self.file_progress.emit(1, 1, name)
                self.progress.emit(done, total)
                continue

            per_file_updates = self._compute_updates_for_file(path, current) or {}

            # Compute fields to clear (lowercase keys)
            clear_fields_l = [
                (f or "").lower()
                for f, op in (self._ops or {}).items()
                if (op or "").lower() == "clear" and (f or "").lower() not in per_file_updates
            ]

            # Nothing to do? benign skip
            if not per_file_updates and not clear_fields_l:
                skipped += 1
                done += 1
                self.file_progress.emit(1, 1, name)
                self.progress.emit(done, total)
                continue

            # Build journal old/new
            old_values: Dict[str, str] = {}
            new_values: Dict[str, str] = {}
            for f, newv in per_file_updates.items():
                old_values[f] = getattr(current, f, "")
                new_values[f] = newv
            for f in clear_fields_l:
                old_values[f] = getattr(current, f, "")
                new_values[f] = ""

            # Write
            ok = True
            err = ""
            try:
                if per_file_updates:
                    # Security/protection was already checked by read_metadata() above.
                    ok, err = handler.write_metadata(path, per_file_updates, skip_security_check=True)
                if ok and clear_fields_l:
                    ok, err = handler.clear_metadata_fields(path, clear_fields_l, skip_security_check=True)
            except Exception as e:
                ok, err = False, str(e)

            if not ok:
                failures.append({"filename": name, "filepath": path, "error": err})
            else:
                successes += 1
                journal.append((path, old_values, new_values))

            done += 1
            self.file_progress.emit(1, 1, name)  # one step per file
            self.progress.emit(done, total)

        stats = {"total": total, "successes": successes, "skipped": skipped, "failures": len(failures)}
        log_worker_event("Writer", "finished", f"Success: {successes}, Skip: {skipped}, Fail: {len(failures)}")
        self.status.emit(f"Write complete: {successes} succeeded, {skipped} skipped, {len(failures)} failed.")
        self.finished.emit(stats, failures, journal)
