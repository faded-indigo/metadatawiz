# core/atomic.py
from __future__ import annotations

import os
import time
import errno
import random
import stat
from typing import Optional


def _clear_readonly(path: str) -> None:
    try:
        if not os.path.exists(path):
            return
        mode = os.stat(path).st_mode
        if (mode & stat.S_IREAD) and not (mode & stat.S_IWRITE):
            os.chmod(path, mode | stat.S_IWRITE)
    except Exception:
        # Best effort only
        pass


def replace_file(src: str, dst: str, attempts: int = 12, base_backoff: float = 0.06) -> None:
    """
    Robust replace with retries (Windows-friendly).
    - Attempts os.replace(src, dst) up to 'attempts' times.
    - On Windows, clears read-only bit on 'dst' before trying.
    - Exponential backoff with jitter to ride out transient locks.

    Raises OSError/PermissionError if all attempts fail.
    """
    if os.name == "nt" and os.path.exists(dst):
        _clear_readonly(dst)

    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except OSError as e:
            last_exc = e
            # Retry only for common transient cases
            # EEXIST is not expected from os.replace on modern Python/platforms, so it's omitted.
            if e.errno in (errno.EACCES, errno.EPERM, errno.ETXTBSY, errno.EBUSY):
                sleep_time = (base_backoff * (2 ** i)) + random.uniform(0, base_backoff)
                time.sleep(min(sleep_time, 1.0))
                if os.name == "nt":
                    _clear_readonly(dst)
                continue
            # Not a transient error -> bail out
            break

    # If we get here, we failed all attempts
    if last_exc:
        raise last_exc
    # This fallback should not be hit; included as a safeguard for unexpected control flow.
    raise OSError("replace_file: failed without an explicit exception")
