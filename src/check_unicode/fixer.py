"""Auto-fix replacement logic for known Unicode offenders."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from check_unicode.categories import DANGEROUS_INVISIBLE, REPLACEMENT_TABLE

# Pre-built translation table: all REPLACEMENT_TABLE entries that are NOT dangerous.
_TRANSLATE_TABLE: dict[int, str] = {
    cp: repl for cp, repl in REPLACEMENT_TABLE.items() if cp not in DANGEROUS_INVISIBLE
}


def fix_file(path: str | Path) -> bool:
    """Replace fixable Unicode characters in a file with ASCII equivalents.

    Dangerous invisible characters are never auto-fixed.
    Uses atomic write (temp file + rename) to avoid data loss.

    Returns True if the file was modified.
    """
    filepath = Path(path)
    try:
        original = filepath.read_text(encoding="utf-8")
        orig_mode = filepath.stat().st_mode
    except (UnicodeDecodeError, OSError):
        return False

    fixed = _apply_replacements(original)
    if fixed == original:
        return False

    # Atomic write: write to temp file in same directory, then rename
    fd, tmp_path_str = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(fixed)
        # Preserve original file permissions
        tmp_path.chmod(orig_mode)
        tmp_path.replace(filepath)
    except BaseException:
        # Clean up temp file on any failure
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise
    return True


def _apply_replacements(text: str) -> str:
    """Replace characters that have entries in REPLACEMENT_TABLE.

    Skips dangerous invisible characters -- those are never auto-fixed.
    """
    return text.translate(_TRANSLATE_TABLE)
