"""Core detection logic for non-ASCII characters."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from check_unicode.categories import DANGEROUS_INVISIBLE, REPLACEMENT_TABLE
from check_unicode.confusables import CONFUSABLES
from check_unicode.scripts import script_of

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
    confusable: str | None = None

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
    printable: bool = False
    scripts: frozenset[str] = frozenset()


def _is_allowed(cp: int, cat: str, allow: AllowConfig) -> bool:
    """Check whether a codepoint is allowed by the allow-list.

    Evaluation order:
    1. Explicit --allow-codepoint: allowed (even dangerous)
    2. DANGEROUS_INVISIBLE: blocked (never overridden by other flags)
    3. --allow-printable + isprintable(): allowed
    4. --allow-script + script match: allowed
    5. --allow-range: allowed
    6. --allow-category: allowed
    """
    if cp in allow.codepoints:
        return True
    if cp in DANGEROUS_INVISIBLE:
        return False
    if allow.printable and chr(cp).isprintable():
        return True
    if allow.scripts and script_of(cp) in allow.scripts:
        return True
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
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
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


def _check_line_confusables(
    filepath: str,
    lineno: int,
    line: str,
) -> list[Finding]:
    """Check a single line for mixed-script confusable characters."""
    # Collect (col, char, script) for each letter on the line.
    letters: list[tuple[int, str, str]] = []
    for i, ch in enumerate(line):
        if ch.isalpha():
            script = script_of(ord(ch))
            if script not in ("Common", "Inherited"):
                letters.append((i + 1, ch, script))

    if not letters:
        return []

    # Count scripts to find dominant.
    script_counts: dict[str, int] = {}
    for _, _, script in letters:
        script_counts[script] = script_counts.get(script, 0) + 1

    if len(script_counts) < 2:  # noqa: PLR2004
        return []  # single script, no confusable risk

    # Dominant script: highest count, tie-break to Latin.
    max_count = max(script_counts.values())
    candidates = [s for s, c in script_counts.items() if c == max_count]
    dominant = "Latin" if "Latin" in candidates else candidates[0]

    # Check minority-script letters against confusable table.
    results: list[Finding] = []
    for col, ch, script in letters:
        if script == dominant:
            continue
        cp = ord(ch)
        if cp in CONFUSABLES:
            results.append(
                Finding(
                    file=filepath,
                    line=lineno,
                    col=col,
                    char=ch,
                    codepoint=cp,
                    name=_char_name(cp),
                    category=unicodedata.category(ch),
                    dangerous=False,
                    confusable=CONFUSABLES[cp],
                )
            )
    return results


def check_confusables(
    path: str | Path,
) -> list[Finding]:
    """Detect mixed-script homoglyph/confusable characters in a file.

    Per-line algorithm:
    1. Classify every letter by its Unicode script.
    2. Determine the dominant script (most letter chars; ties to Latin).
    3. If >=2 scripts: check minority-script letters against CONFUSABLES.
    4. Emit Finding with confusable set to the Latin lookalike.

    --allow-script does NOT suppress confusable warnings.
    """
    filepath = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        findings.extend(_check_line_confusables(filepath, lineno, line))

    return findings
