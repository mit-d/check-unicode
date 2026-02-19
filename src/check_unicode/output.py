"""Terminal formatting, color, and context display."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from check_unicode.checker import Finding

# ANSI escape codes
_RED = "\033[31m"
_BOLD_RED = "\033[1;31m"
_DIM = "\033[2m"
_RESET = "\033[0m"

# Highest codepoint considered "normal" ASCII for display purposes
_MAX_ASCII = 0x7E


def _use_color(*, no_color: bool) -> bool:
    """Determine whether to emit ANSI colour codes on stderr."""
    if no_color:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stderr.isatty()


def _render_invisible(line: str) -> str:
    """Replace invisible/zero-width characters with visible <U+XXXX> placeholders."""
    out: list[str] = []
    for ch in line:
        cp = ord(ch)
        if cp > _MAX_ASCII and not ch.isprintable():
            out.append(f"<U+{cp:04X}>")
        else:
            out.append(ch)
    return "".join(out)


def _format_finding(f: Finding, *, color: bool) -> str:
    """Format a single finding as file:line:col: U+XXXX NAME [Cat]."""
    cp_str = f"U+{f.codepoint:04X}"
    if color:
        if f.dangerous:
            prefix = f"{_BOLD_RED}[DANGEROUS]{_RESET} "
            cp_part = f"{_BOLD_RED}{cp_str}{_RESET}"
        else:
            prefix = ""
            cp_part = f"{_RED}{cp_str}{_RESET}"
        cat_part = f"{_DIM}[{f.category}]{_RESET}"
    else:
        prefix = "[DANGEROUS] " if f.dangerous else ""
        cp_part = cp_str
        cat_part = f"[{f.category}]"
    return f"{f.file}:{f.line}:{f.col}: {prefix}{cp_part} {f.name} {cat_part}"


def _context_line(finding: Finding, file_lines: list[str]) -> str:
    """Show the source line with a caret pointing at the character."""
    if finding.line < 1 or finding.line > len(file_lines):
        return ""
    line = file_lines[finding.line - 1]
    rendered = _render_invisible(line)
    # Compute caret position accounting for invisible char expansion
    caret_pos = 0
    for i, ch in enumerate(line):
        if i == finding.col - 1:
            break
        cp = ord(ch)
        if cp > _MAX_ASCII and not ch.isprintable():
            caret_pos += len(f"<U+{cp:04X}>")
        else:
            caret_pos += 1
    return f"  {rendered}\n  {' ' * caret_pos}^"


def print_findings(
    findings: list[Finding],
    *,
    no_color: bool = False,
    quiet: bool = False,
) -> None:
    """Print findings to stderr."""
    color = _use_color(no_color=no_color)

    # Group by file for context lines
    files_cache: dict[str, list[str]] = {}

    if not quiet:
        for f in findings:
            line = _format_finding(f, color=color)
            sys.stderr.write(line + "\n")

            # Show context if the finding has valid line info
            if f.line > 0:
                if f.file not in files_cache:
                    try:
                        text = Path(f.file).read_text(encoding="utf-8")
                        files_cache[f.file] = text.splitlines()
                    except (OSError, UnicodeDecodeError):
                        files_cache[f.file] = []
                ctx = _context_line(f, files_cache[f.file])
                if ctx:
                    sys.stderr.write(ctx + "\n")

    # Summary
    n_files = len({f.file for f in findings})
    n_fixable = sum(1 for f in findings if f.fixable)
    n_dangerous = sum(1 for f in findings if f.dangerous)
    parts = [
        f"Found {len(findings)} non-ASCII character{'s' if len(findings) != 1 else ''}"
    ]
    parts.append(f"in {n_files} file{'s' if n_files != 1 else ''}")
    extras = []
    if n_fixable:
        extras.append(f"{n_fixable} fixable")
    if n_dangerous:
        extras.append(f"{n_dangerous} dangerous")
    if extras:
        parts.append(f"({', '.join(extras)})")
    sys.stderr.write(" ".join(parts) + "\n")
