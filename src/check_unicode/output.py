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
_YELLOW = "\033[33m"
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


def _compact_ranges(lines: list[int]) -> str:
    """Convert sorted line numbers to compact range string like '1,4-80,90'."""
    if not lines:
        return ""

    sorted_lines = sorted(set(lines))
    ranges: list[str] = []
    start = sorted_lines[0]
    end = sorted_lines[0]

    for line in sorted_lines[1:]:
        if line == end + 1:
            end = line
        else:
            ranges.append(str(start) if start == end else f"{start}-{end}")
            start = line
            end = line

    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ",".join(ranges)


def _is_more_severe(candidate: Finding, existing: Finding) -> bool:
    """Return True if *candidate* should replace *existing*."""
    if candidate.dangerous and not existing.dangerous:
        return True
    return (
        candidate.confusable is not None
        and not existing.dangerous
        and existing.confusable is None
    )


def _build_caret_line(line: str, line_findings: list[Finding]) -> str:
    """Build a caret line with ^ for normal, ! for dangerous, ? for confusable."""
    # Map column (1-indexed) to most severe finding at that column
    col_map: dict[int, Finding] = {}
    for f in line_findings:
        existing = col_map.get(f.col)
        if existing is None or _is_more_severe(f, existing):
            col_map[f.col] = f

    # Walk through the line, tracking rendered position
    markers: list[tuple[int, str]] = []
    pos = 0
    for i, ch in enumerate(line):
        col = i + 1
        if col in col_map:
            mf = col_map[col]
            match (mf.dangerous, mf.confusable):
                case (True, _):
                    marker = "!"
                case (_, str()):
                    marker = "?"
                case _:
                    marker = "^"
            markers.append((pos, marker))

        pos += len(_render_invisible(ch))

    if not markers:
        return ""

    # Build caret string
    result: list[str] = []
    last_pos = 0
    for rpos, marker in markers:
        result.append(" " * (rpos - last_pos))
        result.append(marker)
        last_pos = rpos + 1

    return "".join(result)


def _format_codepoint_entry(
    finding: Finding,
    count: int,
    *,
    color: bool,
) -> str:
    """Format a unique codepoint listing entry."""
    cp_str = f"U+{finding.codepoint:04X}"
    count_str = f" (x{count})" if count > 1 else ""

    match (finding.dangerous, finding.confusable, color):
        case (True, _, True):
            prefix = f"{_BOLD_RED}!{_RESET} {_BOLD_RED}[DANGEROUS]{_RESET} "
            cp_part = f"{_BOLD_RED}{cp_str}{_RESET}"
        case (True, _, False):
            prefix = "! [DANGEROUS] "
            cp_part = cp_str
        case (_, str() as lookalike, True):
            prefix = (
                f"{_YELLOW}?{_RESET} "
                f"{_YELLOW}[CONFUSABLE: looks like '{lookalike}']{_RESET} "
            )
            cp_part = f"{_YELLOW}{cp_str}{_RESET}"
        case (_, str() as lookalike, False):
            prefix = f"? [CONFUSABLE: looks like '{lookalike}'] "
            cp_part = cp_str
        case (_, _, True):
            prefix = ""
            cp_part = f"{_RED}{cp_str}{_RESET}"
        case _:
            prefix = ""
            cp_part = cp_str

    cat_part = (
        f"{_DIM}[{finding.category}]{_RESET}" if color else f"[{finding.category}]"
    )

    return f"{prefix}{cp_part} {finding.name} {cat_part}{count_str}"


def _print_summary(findings: list[Finding]) -> None:
    """Print a summary line of finding counts to stderr."""
    n_files = len({f.file for f in findings})
    n_fixable = sum(1 for f in findings if f.fixable)
    n_dangerous = sum(1 for f in findings if f.dangerous)
    n_confusable = sum(1 for f in findings if f.confusable is not None)
    parts = [
        f"Found {len(findings)} non-ASCII character{'s' if len(findings) != 1 else ''}"
    ]
    parts.append(f"in {n_files} file{'s' if n_files != 1 else ''}")
    extras = []
    if n_fixable:
        extras.append(f"{n_fixable} fixable")
    if n_dangerous:
        extras.append(f"{n_dangerous} dangerous")
    if n_confusable:
        extras.append(f"{n_confusable} confusable")
    if extras:
        parts.append(f"({', '.join(extras)})")
    sys.stderr.write(" ".join(parts) + "\n")


def _collect_codepoints(
    file_findings: list[Finding],
) -> list[tuple[Finding, int]]:
    """Collect unique codepoints with counts, preferring the most informative.

    When the same codepoint appears as both a normal finding and a confusable
    (or dangerous), the more informative classification wins.
    Findings with line == 0 (read errors) are skipped.
    Returns a sorted list of (finding, count) tuples.
    """
    cp_counts: dict[int, tuple[Finding, int]] = {}
    for f in file_findings:
        if f.line == 0:
            continue
        existing = cp_counts.get(f.codepoint)
        if existing is None:
            cp_counts[f.codepoint] = (f, 1)
        else:
            existing_f, n = existing
            best = f if _is_more_severe(f, existing_f) else existing_f
            cp_counts[f.codepoint] = (best, n + 1)

    return sorted(
        cp_counts.values(),
        key=lambda x: (
            not x[0].dangerous,
            x[0].confusable is None,
            x[0].codepoint,
        ),
    )


def _print_file_findings(
    filepath: str,
    file_findings: list[Finding],
    *,
    color: bool,
) -> None:
    """Print grouped output for a single file."""
    # Build compact line ranges for header
    lines_with_findings = sorted({f.line for f in file_findings if f.line > 0})
    ranges_str = _compact_ranges(lines_with_findings)

    # Print header
    header = f"{filepath}:{ranges_str}:" if ranges_str else f"{filepath}:"
    sys.stderr.write(header + "\n")

    # Read file for context display
    try:
        text = Path(filepath).read_text(encoding="utf-8")
        file_lines = text.splitlines()
    except (OSError, UnicodeDecodeError):
        file_lines = []

    # Group findings by line number
    by_line: dict[int, list[Finding]] = {}
    for f in file_findings:
        by_line.setdefault(f.line, []).append(f)

    # Show context lines with carets, deduplicating identical blocks
    seen_contexts: set[tuple[str, str]] = set()
    for lineno in sorted(by_line):
        if lineno < 1 or lineno > len(file_lines):
            continue
        line = file_lines[lineno - 1]
        rendered = _render_invisible(line)
        caret = _build_caret_line(line, by_line[lineno])

        context_key = (rendered, caret)
        if context_key in seen_contexts:
            continue
        seen_contexts.add(context_key)

        sys.stderr.write(f"  {rendered}\n")
        if caret:
            sys.stderr.write(f"  {caret}\n")

    # Print error findings (line == 0, e.g. couldn't read file)
    for f in file_findings:
        if f.line == 0:
            sys.stderr.write(f"  {f.name}\n")

    # List unique codepoints with counts
    for finding, count in _collect_codepoints(file_findings):
        entry = _format_codepoint_entry(finding, count, color=color)
        sys.stderr.write(f"  {entry}\n")

    sys.stderr.write("\n")


def print_findings(
    findings: list[Finding],
    *,
    no_color: bool = False,
    quiet: bool = False,
) -> None:
    """Print findings to stderr, grouped by file with compact line ranges."""
    color = _use_color(no_color=no_color)

    if not quiet:
        # Group by file, preserving first-seen order
        by_file: dict[str, list[Finding]] = {}
        for f in findings:
            by_file.setdefault(f.file, []).append(f)

        for filepath, file_findings in by_file.items():
            _print_file_findings(filepath, file_findings, color=color)

    _print_summary(findings)
