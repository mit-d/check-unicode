"""Core detection logic for non-ASCII characters."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from check_unicode.categories import DANGEROUS_INVISIBLE, REPLACEMENT_TABLE

_ASCII_SAFE = re.compile(r"[^\t\r\n\x20-\x7E]")
_BOM = 0xFEFF


@dataclass(frozen=True, slots=True)
class Finding:
    """A single non-ASCII character finding in a file."""

    file: str
    line: int  # 1-indexed
    col: int  # 1-indexed
    char: str
    codepoint: int
    name: str
    category: str
    dangerous: bool

    @property
    def fixable(self) -> bool:
        """Return True if this finding has a safe ASCII replacement."""
        return self.codepoint in REPLACEMENT_TABLE and not self.dangerous


@dataclass(frozen=True, slots=True)
class AllowConfig:
    """Configuration for codepoints, ranges, and categories to allow."""

    codepoints: frozenset[int] = frozenset()
    ranges: tuple[tuple[int, int], ...] = ()
    categories: frozenset[str] = frozenset()


def _is_allowed(cp: int, cat: str, allow: AllowConfig) -> bool:
    """Check whether a codepoint is allowed by the allow-list.

    Dangerous invisible characters are only suppressed by explicit
    --allow-codepoint, never by ranges or categories.
    """
    if cp in allow.codepoints:
        return True
    if cp in DANGEROUS_INVISIBLE:
        return False
    if any(lo <= cp <= hi for lo, hi in allow.ranges):
        return True
    return any(cat.startswith(prefix) for prefix in allow.categories)


def _char_name(cp: int) -> str:
    try:
        return unicodedata.name(chr(cp))
    except ValueError:
        return f"U+{cp:04X}"


def check_file(
    path: str | Path,
    allow: AllowConfig | None = None,
) -> list[Finding]:
    """Scan a file for non-ASCII characters, returning findings."""
    if allow is None:
        allow = AllowConfig()
    filepath = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        # Graceful handling of binary / unreadable files
        return [
            Finding(
                file=filepath,
                line=0,
                col=0,
                char="",
                codepoint=0,
                name=f"Could not read file: {exc}",
                category="",
                dangerous=False,
            )
        ]

    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _ASCII_SAFE.finditer(line):
            col = m.start() + 1  # 1-indexed
            char = m.group()
            cp = ord(char)

            # BOM at file position 0 is informational, not an error
            if cp == _BOM and lineno == 1 and col == 1:
                continue

            cat = unicodedata.category(char)
            if _is_allowed(cp, cat, allow):
                continue

            dangerous = cp in DANGEROUS_INVISIBLE
            findings.append(
                Finding(
                    file=filepath,
                    line=lineno,
                    col=col,
                    char=char,
                    codepoint=cp,
                    name=_char_name(cp),
                    category=cat,
                    dangerous=dangerous,
                )
            )
    return findings
