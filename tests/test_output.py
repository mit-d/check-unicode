"""Tests for check_unicode.output formatting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from check_unicode.checker import Finding, check_file
from check_unicode.output import (
    _context_line,
    _format_finding,
    _use_color,
    print_findings,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestUseColor:
    """Tests for color detection logic."""

    def test_no_color_env_var(self) -> None:
        """NO_COLOR environment variable disables color."""
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            assert _use_color(no_color=False) is False


class TestFormatFinding:
    """Tests for finding formatting with and without color."""

    def test_dangerous_with_color(self) -> None:
        """Dangerous findings include bold red [DANGEROUS] prefix with color."""
        findings = check_file(FIXTURES / "bidi_attack.txt")
        dangerous = [f for f in findings if f.dangerous]
        result = _format_finding(dangerous[0], color=True)
        assert "[DANGEROUS]" in result
        assert "\033[1;31m" in result

    def test_non_dangerous_with_color(self) -> None:
        """Non-dangerous findings use red codepoint with color."""
        findings = check_file(FIXTURES / "smart_quotes.txt")
        result = _format_finding(findings[0], color=True)
        assert "\033[31m" in result
        assert "[DANGEROUS]" not in result


class TestContextLine:
    """Tests for source context line display."""

    def test_out_of_range_line(self) -> None:
        """Out-of-range line numbers return empty string."""
        finding = Finding(
            file="test.txt",
            line=999,
            col=1,
            char="\u201c",
            codepoint=0x201C,
            name="LEFT DOUBLE QUOTATION MARK",
            category="Ps",
            dangerous=False,
        )
        assert _context_line(finding, ["only one line"]) == ""


class TestPrintFindings:
    """Tests for full finding output."""

    def test_context_file_read_failure(self) -> None:
        """Findings referencing nonexistent files don't crash context display."""
        finding = Finding(
            file="/nonexistent/file.txt",
            line=1,
            col=1,
            char="\u201c",
            codepoint=0x201C,
            name="LEFT DOUBLE QUOTATION MARK",
            category="Ps",
            dangerous=False,
        )
        # Should not raise
        print_findings([finding], no_color=True)
