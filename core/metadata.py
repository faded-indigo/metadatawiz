# core/metadata.py
"""
ExifTool-only bridge for PDF metadata operations.

- I/O only (read/write). Merge/sort/dedupe belongs to ops/UI layers.
- Writes are safe: copy original -> edit temp -> fsync -> atomic replace.
- Windows-friendly:
  * Extended-length path support for long/UNC paths.
  * Atomic replace with polite retries for share violations (e.g., file open).
- Update/Add: empty inputs are ignored (do nothing). Clearing uses clear_metadata_fields().
"""
from __future__ import annotations

import os
import json
import stat
import time
import random
import shutil
import tempfile
import subprocess
from typing import Dict, List, Optional, Tuple

import logging
logger = logging.getLogger("HSPMetaWizard.core.metadata")


# ------------------ exiftool path resolver (robust fallback) -----------------
def _resolve_exiftool_path(custom_path: Optional[str]) -> str:
    if custom_path:
        return custom_path
    try:
        import importlib
        m = importlib.import_module("bundled")
        fn = getattr(m, "get_exiftool_path", None)
        if callable(fn):
            p = fn()
            if p:
                return p
    except Exception:
        pass
    try:
        import importlib
        m = importlib.import_module("infra.bundled")
        fn = getattr(m, "get_exiftool_path", None)
        if callable(fn):
            p = fn()
            if p:
                return p
    except Exception:
        pass
    return "exiftool"


# --------------------------- path helpers ------------------------------------

def _is_unc(path: str) -> bool:
    return path.startswith("\\\\") or path.startswith("//")


def _win_long_path(path: str) -> str:
    
    if os.name != "nt":
        return path
    if path.startswith("\\\\?\\"):
        return path
    abs_path = os.path.abspath(path)
    # Only add when long enough to matter
    if len(abs_path) < 240:
        return abs_path
    if _is_unc(abs_path):
        # \\server\share\... -> \\?\UNC\server\share\...
        return "\\\\?\\UNC" + abs_path[1:]
    return "\\\\?\\" + abs_path


def _safe_path(path: str) -> str:
    return _win_long_path(path) if os.name == "nt" else os.path.abspath(path)


# --------------------------- FS helpers --------------------------------------

def _fsync_path(path: str) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        pass
    try:
        dir_fd = os.open(os.path.dirname(os.path.abspath(path)) or ".", os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        pass


def _ensure_writable(path: str) -> None:
    """Clear READONLY bit on Windows, if set."""
    if os.name != "nt":
        return
    try:
        st = os.stat(path)
        if st.st_mode & stat.S_IREAD:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except Exception:
        pass


def _replace_with_retries(src: str, dst: str, attempts: int = 6, base_sleep: float = 0.12) -> None:
    """
    Atomic replace with polite retries to tolerate transient locks (WinError 32 / errno 13).
    """
    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            _ensure_writable(dst)
            os.replace(src, dst)
            return
        except PermissionError as e:
            last_exc = e
        except OSError as e:
            last_exc = e
        # backoff + jitter
        time.sleep(base_sleep * (2 ** i) + random.random() * 0.05)
    if last_exc:
        raise last_exc


# Windows: keep exiftool quiet (no console pop-up)
_SUBPROC_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


# --------------------------- data container ----------------------------------

class PDFMetadata:
    def __init__(self, filepath: str):
        self.filepath: str = filepath
        self.filename: str = os.path.basename(filepath)
        self.title: str = ""
        self.author: str = ""
        self.subject: str = ""
        self.keywords: str = ""
        self.is_protected: bool = False
        self.is_corrupted: bool = False
        self.error_message: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "filepath": self.filepath,
            "filename": self.filename,
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "keywords": self.keywords,
            "is_protected": self.is_protected,
            "is_corrupted": self.is_corrupted,
            "error_message": self.error_message,
        }


# --------------------------- handler -----------------------------------------

class MetadataHandler:
    """
    ExifTool-based PDF metadata reader/writer.

    Update/Add: empty strings are ignored (no change).
    Clearing must use clear_metadata_fields().
    """

    _FIELD_MAP = {
        "title": "Title",
        "author": "Author",
        "subject": "Subject",
        "keywords": "Keywords",
    }

    def __init__(self, exiftool_path: Optional[str] = None, timeout_read: int = 15, timeout_write: int = 30):
        self.exiftool_path = _resolve_exiftool_path(exiftool_path)
        self.timeout_read = int(timeout_read)
        self.timeout_write = int(timeout_write)
        self._validate_exiftool()

    def _validate_exiftool(self) -> None:
        if not self.exiftool_path:
            raise FileNotFoundError("ExifTool path not configured.")
        in_path = shutil.which(self.exiftool_path) is not None
        on_disk = os.path.exists(self.exiftool_path)
        if not (in_path or on_disk):
            raise FileNotFoundError(f"ExifTool not found at '{self.exiftool_path}' or in PATH.")
        logger.info("Using ExifTool at: %s", self.exiftool_path)

    # --------------------------- probes --------------------------------------

    def check_pdf_security(self, filepath: str) -> Tuple[bool, bool, str]:
        p = _safe_path(filepath)
        try:
            enc = subprocess.run(
                [self.exiftool_path, "-s", "-s", "-s", "-Encrypted", "--", p],
                capture_output=True, text=True, timeout=10, creationflags=_SUBPROC_FLAGS
            )
            if enc.returncode != 0:
                msg = enc.stderr.strip() or "unknown error"
                return False, True, f"ExifTool error: {msg}"
            if enc.stdout.strip().lower() == "yes":
                return True, False, "Password protected"

            quick = subprocess.run(
                [self.exiftool_path, "-json", "-fast", "--", p],
                capture_output=True, text=True, timeout=10, creationflags=_SUBPROC_FLAGS
            )
            if quick.returncode != 0:
                msg = quick.stderr.strip() or "unknown error"
                return False, True, f"ExifTool error: {msg}"

            return False, False, ""
        except subprocess.TimeoutExpired:
            return False, True, "Timeout checking file"
        except Exception as e:
            return False, True, f"Error checking file: {e}"

    # ----------------------------- read --------------------------------------

    def read_metadata(self, filepath: str) -> PDFMetadata:
        md = PDFMetadata(filepath)
        if not os.path.exists(filepath):
            md.is_corrupted = True
            md.error_message = "File not found"
            return md

        prot, corr, emsg = self.check_pdf_security(filepath)
        md.is_protected, md.is_corrupted, md.error_message = prot, corr, emsg
        if prot or corr:
            return md

        p = _safe_path(filepath)
        try:
            res = subprocess.run(
                [
                    self.exiftool_path,
                    "-json",
                    "-G1",
                    "-PDF:Title",
                    "-XMP-dc:Title",
                    "-PDF:Author",
                    "-XMP-pdf:Author",
                    "-PDF:Subject",
                    "-XMP-dc:Subject",
                    "-PDF:Keywords",
                    "-XMP-pdf:Keywords",
                    "--",
                    p,
                ],
                capture_output=True, text=True, timeout=self.timeout_read, creationflags=_SUBPROC_FLAGS
            )
            if res.returncode != 0:
                md.error_message = f"ExifTool error: {res.stderr.strip() or 'unknown'}"
                return md

            data = json.loads(res.stdout or "[]")
            if not data:
                return md
            d = data[0]

            def _as_text(val) -> str:
                if isinstance(val, str):
                    return val.strip()
                if isinstance(val, list):
                    parts = [str(x).strip() for x in val if str(x).strip()]
                    return ", ".join(parts)
                return ""

            def _pick_text(*keys: str) -> str:
                for k in keys:
                    txt = _as_text(d.get(k))
                    if txt:
                        return txt
                return ""

            md.title = _pick_text("PDF:Title", "XMP-dc:Title", "Title")
            md.author = _pick_text("PDF:Author", "XMP-pdf:Author", "Author")

            pdf_subject = _pick_text("PDF:Subject")
            xmp_subject = _pick_text("XMP-dc:Subject")
            if pdf_subject and xmp_subject and pdf_subject != xmp_subject:
                logger.info(
                    "Subject mismatch for %s (PDF: %r, XMP-dc: %r). Using PDF:Subject.",
                    filepath,
                    pdf_subject,
                    xmp_subject,
                )
            md.subject = pdf_subject or xmp_subject or _pick_text("Subject")

            # Prefer PDF Keywords because the UI table is meant to reflect file metadata.
            md.keywords = _pick_text("PDF:Keywords", "XMP-pdf:Keywords", "Keywords")

            return md

        except subprocess.TimeoutExpired:
            md.error_message = "Timeout reading metadata"
            return md
        except json.JSONDecodeError:
            md.error_message = "Invalid metadata format"
            return md
        except Exception as e:
            md.error_message = f"Error reading metadata: {e}"
            return md

    # ---------------------------- write/update --------------------------------

    def write_metadata(
        self,
        filepath: str,
        updates: Dict[str, Optional[str]],
        skip_security_check: bool = False,
    ) -> Tuple[bool, str]:
        """
        Writes non-empty values only. Use clear_metadata_fields() to clear.
        - Title/Author/Subject are written as single string values.
        - Keywords are written as a list: one -Keywords=... per token (prevents a single
          comma-containing value from being quoted by readers).
        - Set skip_security_check=True only when caller already validated file safety.
        """
        if not os.path.exists(filepath):
            return False, "File not found"

        if not skip_security_check:
            is_prot, is_corr, msg = self.check_pdf_security(filepath)
            if is_prot:
                return False, "Cannot modify password-protected PDF"
            if is_corr:
                return False, f"Cannot modify corrupted PDF: {msg or 'Corrupted'}"

        # Map logical field -> ExifTool tag name and filter out empties
        filtered: Dict[str, str] = {}
        for k, v in (updates or {}).items():
            if v is None:
                continue
            v = str(v).strip()
            if not v:
                continue
            tag = self._FIELD_MAP.get(k.lower())
            if tag:
                filtered[tag] = v

        if not filtered:
            return True, ""

        folder = os.path.dirname(os.path.abspath(filepath)) or "."
        fd, temp_path = tempfile.mkstemp(suffix=".pdf", dir=folder)
        os.close(fd)

        src = _safe_path(filepath)
        tmp = _safe_path(temp_path)

        try:
            shutil.copy2(src, tmp)

            # Build exiftool command
            cmd = [self.exiftool_path, "-overwrite_original"]

            for tag, value in filtered.items():
                # Special handling for Keywords: write each token as a separate list item.
                # This prevents the whole comma-joined string from being treated as one value
                # (which some tools then display with surrounding quotes).
                if tag.lower().endswith("keywords"):
                    tokens = [t.strip() for t in value.split(",") if t.strip()]
                    # If there are tokens, set the list explicitly via multiple -Keywords=
                    for t in tokens:
                        cmd.append(f"-{tag}={t}")
                else:
                    cmd.append(f"-{tag}={value}")

            cmd.extend(["--", tmp])

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_write,
                creationflags=_SUBPROC_FLAGS,
            )
            if res.returncode != 0:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return False, f"ExifTool error: {res.stderr.strip() or 'unknown'}"

            _fsync_path(tmp)
            try:
                _replace_with_retries(tmp, src)
            except PermissionError:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return False, "The PDF appears to be open or locked. Close the file and retry."
            except OSError as e:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return False, f"Error replacing file: {e}"

            _fsync_path(src)
            return True, ""

        except subprocess.TimeoutExpired:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False, "Timeout writing metadata"
        except Exception as e:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False, f"Error writing metadata: {e}"

    # ------------------------------- clear ------------------------------------

    def clear_metadata_fields(
        self,
        filepath: str,
        fields: List[str],
        skip_security_check: bool = False,
    ) -> Tuple[bool, str]:
        """
        Explicitly clear (remove) specific metadata fields on a PDF.
        - Uses ExifTool with empty assignments (e.g., -Title=) to clear values.
        - Safe write: copy -> edit temp -> fsync -> atomic replace with retries.
        - Set skip_security_check=True only when caller already validated file safety.
        Returns (ok, err_message).
        """
        if not os.path.exists(filepath):
            return False, "File not found"

        if not skip_security_check:
            is_prot, is_corr, msg = self.check_pdf_security(filepath)
            if is_prot:
                return False, "Cannot modify password-protected PDF"
            if is_corr:
                return False, f"Cannot modify corrupted PDF: {msg or 'Corrupted'}"

        # Map logical field names to ExifTool tags, de-dup
        tags: List[str] = []
        for f in fields or []:
            tag = self._FIELD_MAP.get(str(f).lower())
            if tag and tag not in tags:
                tags.append(tag)

        if not tags:
            return True, ""  # nothing to clear

        # Prepare a temp copy in the same folder for atomic replace
        folder = os.path.dirname(os.path.abspath(filepath)) or "."
        fd, temp_path = tempfile.mkstemp(suffix=".pdf", dir=folder)
        os.close(fd)

        src = _safe_path(filepath)
        tmp = _safe_path(temp_path)

        try:
            shutil.copy2(src, tmp)

            # Build ExifTool command: -Tag= clears the value
            cmd = [self.exiftool_path, "-overwrite_original"]
            for tag in tags:
                cmd.append(f"-{tag}=")
            cmd.extend(["--", tmp])

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_write,
                creationflags=_SUBPROC_FLAGS,
            )
            if res.returncode != 0:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return False, f"ExifTool error: {res.stderr.strip() or 'unknown'}"

            _fsync_path(tmp)
            try:
                _replace_with_retries(tmp, src)
            except PermissionError:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return False, "The PDF appears to be open or locked. Close the file and retry."
            except OSError as e:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return False, f"Error replacing file: {e}"

            _fsync_path(src)
            return True, ""

        except subprocess.TimeoutExpired:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False, "Timeout clearing metadata"
        except Exception as e:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False, f"Error clearing metadata: {e}"
