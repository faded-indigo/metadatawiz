# services/ops.py
"""
Operations factory for WriterWorker instances.

This module centralizes creation of WriterWorker with correctly shaped
`updates` and `ops` dicts so UI handlers stay tiny and consistent.

Semantics (enforced by workers.writer.WriterWorker and core.metadata):
- Apply/Replace: write only non-empty input fields.
- Add/Append:    append/merge into current values.
                 * keywords: merge then rules-engine canonicalization
                   (dedupe + natural sort; shib-tags last; ", " delimiter).
                 * author/subject: token-merge on , ; | (case-insensitive
                   dedupe; ", " delimiter).
                 * title: append behaves like replace by design.
- Clear:         clear field value (UI should confirm first).
- From filename: set Title to the file's base name (no .pdf), computed per file.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# WriterWorker is the only dependency; it applies the per-field ops.
from workers.writer import WriterWorker


def apply_replace(
    files: List[Dict],
    updates: Dict[str, str],
    parent: Optional[object] = None,
) -> WriterWorker:
    """
    Build a WriterWorker for 'Apply' (replace non-empty fields only).

    - Empty/whitespace-only inputs are ignored (no change).
    - Each included field is marked with op='replace'.

    Args:
        files:   Selected file rows (each dict includes at least 'filepath' and display info).
        updates: Raw UI inputs (title/author/subject/keywords), may contain empty strings.
        parent:  Optional QObject parent.

    Returns:
        WriterWorker ready to start.
    """
    filtered: Dict[str, str] = {}
    ops: Dict[str, str] = {}

    for field, value in (updates or {}).items():
        if value is None:
            continue
        val = str(value).strip()
        if not val:
            # Empty input means "do nothing" (no write), by design.
            continue
        filtered[field] = val
        ops[field] = "replace"

    return WriterWorker(files, filtered, ops, parent)


def append_field(
    files: List[Dict],
    field: str,
    text: str,
    parent: Optional[object] = None,
) -> WriterWorker:
    """
    Build a WriterWorker for an 'Add' action on a single field.

    Notes:
      - keywords: merges with existing then canonicalizes via rules engine.
      - author/subject: token-merge on , ; | with case-insensitive dedupe.
      - title: append behaves like replace (per product decision).

    Args:
        files: Selected file rows.
        field: 'title' | 'author' | 'subject' | 'keywords'.
        text:  Text to add/merge (caller should ensure non-empty).
        parent: Optional QObject parent.

    Returns:
        WriterWorker.
    """
    text = (text or "").strip()
    return WriterWorker(files, {field: text}, {field: "append"}, parent)


def clear_field(
    files: List[Dict],
    field: str,
    parent: Optional[object] = None,
) -> WriterWorker:
    """
    Build a WriterWorker for 'Clear' on a single field.

    UI should show a Yes/No confirmation before calling this.

    Args:
        files:  Selected file rows.
        field:  Field to clear.
        parent: Optional QObject parent.

    Returns:
        WriterWorker.
    """
    return WriterWorker(files, {field: ""}, {field: "clear"}, parent)


def title_from_filename(
    files: List[Dict],
    parent: Optional[object] = None,
) -> WriterWorker:
    """
    Build a WriterWorker to set Title from each file's own filename
    (without the .pdf extension). The actual value is computed per file.

    Args:
        files:  Selected file rows.
        parent: Optional QObject parent.

    Returns:
        WriterWorker.
    """
    # Value is ignored; the op carries the meaning and the worker computes per-file.
    return WriterWorker(files, {"title": ""}, {"title": "from_filename"}, parent)


def build_updates_dict(
    title: str = "",
    author: str = "",
    subject: str = "",
    keywords: str = "",
) -> Dict[str, str]:
    """
    Assemble a UI→updates dict, omitting empty inputs so Apply won't touch them.

    Returns:
        Dict[str,str] with only non-empty values among: title, author, subject, keywords.
    """
    out: Dict[str, str] = {}
    if isinstance(title, str) and title.strip():
        out["title"] = title.strip()
    if isinstance(author, str) and author.strip():
        out["author"] = author.strip()
    if isinstance(subject, str) and subject.strip():
        out["subject"] = subject.strip()
    if isinstance(keywords, str) and keywords.strip():
        out["keywords"] = keywords.strip()
    return out
