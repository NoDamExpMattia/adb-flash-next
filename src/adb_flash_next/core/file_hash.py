"""SHA-256 of a file, computed in chunks so even large images use little memory."""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

_CHUNK_BYTES = 4 * 1024 * 1024


def sha256_of_file(path: Path, cancel_event: threading.Event | None = None) -> str:
    """Return the lowercase hex SHA-256 of `path`.

    Raises OSError if the file cannot be read and InterruptedError if `cancel_event` is set.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Hashing was cancelled.")
            chunk = handle.read(_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
