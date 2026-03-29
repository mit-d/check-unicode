"""Auto-fix replacement logic for known Unicode offenders."""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from check_unicode.categories import DANGEROUS_INVISIBLE, REPLACEMENT_TABLE
from check_unicode.scripts import script_of

if TYPE_CHECKING:
    from check_unicode.checker import AllowConfig

_NON_ASCII = re.compile(r"[^\t\r\n\x20-\x7E]")

# Pre-built translation table: all REPLACEMENT_TABLE entries that are NOT dangerous.
_TRANSLATE_TABLE: dict[int, str] = {
    cp: repl for cp, repl in REPLACEMENT_TABLE.items() if cp not in DANGEROUS_INVISIBLE
}


def _is_strip_allowed(cp: int, allow: AllowConfig) -> bool:
    """Return True if codepoint is exempted from stripping by the allow-list.

    Evaluation order matches checker._is_allowed: explicit codepoints are
    checked first (can exempt even dangerous chars), then dangerous chars
    are blocked, then printable/script/range/category checks.
    """
    if cp in allow.codepoints:
        return True
    if cp in DANGEROUS_INVISIBLE:
        return False
    ch = chr(cp)
    cat = unicodedata.category(ch)
    return (
        (allow.printable and ch.isprintable())
        or (bool(allow.scripts) and script_of(cp) in allow.scripts)
        or (bool(allow.ranges) and any(lo <= cp <= hi for lo, hi in allow.ranges))
        or (bool(allow.categories) and any(cat.startswith(p) for p in allow.categories))
    )


def _atomic_write(filepath: Path, content: str, orig_mode: int) -> None:
    """Write *content* to *filepath* atomically, preserving *orig_mode*."""
    fd, tmp_path_str = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        tmp_path.chmod(orig_mode)
        tmp_path.replace(filepath)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def strip_text(
    text: str,
    *,
    level: str = "all",
    allow: AllowConfig | None = None,
) -> str:
    """Remove non-ASCII characters from text based on strip level.

    level="all": remove all non-ASCII characters (except allowed).
    level="dangerous": remove only DANGEROUS_INVISIBLE characters (except allowed).
    """

    def _should_strip(ch: str) -> bool:
        cp = ord(ch)
        if allow is not None and _is_strip_allowed(cp, allow):
            return False
        if level == "dangerous":
            return cp in DANGEROUS_INVISIBLE
        return True

    return _NON_ASCII.sub(lambda m: "" if _should_strip(m.group()) else m.group(), text)


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

    fixed = fix_text(original)
    if fixed == original:
        return False

    _atomic_write(filepath, fixed, orig_mode)
    return True


def strip_file(
    path: str | Path,
    *,
    level: str = "all",
    allow: AllowConfig | None = None,
) -> bool:
    """Remove non-ASCII characters from a file based on strip level.

    Uses atomic write (temp file + rename) to avoid data loss.
    Returns True if the file was modified.
    """
    filepath = Path(path)
    try:
        original = filepath.read_text(encoding="utf-8")
        orig_mode = filepath.stat().st_mode
    except (UnicodeDecodeError, OSError):
        return False

    stripped = strip_text(original, level=level, allow=allow)
    if stripped == original:
        return False

    _atomic_write(filepath, stripped, orig_mode)
    return True


def fix_text(text: str) -> str:
    """Replace fixable Unicode characters with ASCII equivalents.

    Dangerous invisible characters are never auto-fixed.
    """
    return text.translate(_TRANSLATE_TABLE)
