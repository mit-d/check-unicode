"""Tests for check_unicode.output formatting."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    import pytest

from check_unicode.checker import Finding, check_file
from check_unicode.output import (
    _build_caret_line,
    _compact_ranges,
    _format_codepoint_entry,
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


class TestCompactRanges:
    """Tests for compact line range formatting."""

    def test_empty(self) -> None:
        """Empty input returns empty string."""
        assert _compact_ranges([]) == ""

    def test_single_line(self) -> None:
        """Single line number returned as-is."""
        assert _compact_ranges([5]) == "5"

    def test_consecutive_lines(self) -> None:
        """Consecutive lines collapsed into a range."""
        assert _compact_ranges([1, 2, 3, 4]) == "1-4"

    def test_mixed(self) -> None:
        """Mix of singles and ranges formatted correctly."""
        assert _compact_ranges([1, 4, 5, 6, 7, 80, 90]) == "1,4-7,80,90"

    def test_unsorted_input(self) -> None:
        """Unsorted input is sorted before formatting."""
        assert _compact_ranges([90, 1, 5, 4, 80, 7, 6]) == "1,4-7,80,90"

    def test_duplicates(self) -> None:
        """Duplicate line numbers are deduplicated."""
        assert _compact_ranges([1, 1, 2, 2, 3]) == "1-3"

    def test_two_separate(self) -> None:
        """Two non-consecutive lines shown comma-separated."""
        assert _compact_ranges([3, 7]) == "3,7"


class TestBuildCaretLine:
    """Tests for caret line construction."""

    def test_single_finding(self) -> None:
        """Single finding produces one caret at correct position."""
        line = "He said \u201chello\u201d"
        findings = [
            Finding(
                file="t.txt",
                line=1,
                col=9,
                char="\u201c",
                codepoint=0x201C,
                name="LEFT DOUBLE QUOTATION MARK",
                category="Ps",
                dangerous=False,
            ),
        ]
        caret = _build_caret_line(line, findings)
        assert caret == "        ^"

    def test_dangerous_uses_exclamation(self) -> None:
        """Dangerous findings marked with ! instead of ^."""
        line = "x\u202ey"
        findings = [
            Finding(
                file="t.txt",
                line=1,
                col=2,
                char="\u202e",
                codepoint=0x202E,
                name="RIGHT-TO-LEFT OVERRIDE",
                category="Cf",
                dangerous=True,
            ),
        ]
        caret = _build_caret_line(line, findings)
        assert "!" in caret
        assert "^" not in caret

    def test_confusable_uses_question(self) -> None:
        """Confusable findings marked with ? instead of ^."""
        line = "p\u0430ssword"
        findings = [
            Finding(
                file="t.txt",
                line=1,
                col=2,
                char="\u0430",
                codepoint=0x0430,
                name="CYRILLIC SMALL LETTER A",
                category="Ll",
                dangerous=False,
                confusable="a",
            ),
        ]
        caret = _build_caret_line(line, findings)
        assert "?" in caret
        assert "^" not in caret

    def test_multiple_findings_on_line(self) -> None:
        """Multiple findings produce multiple carets."""
        line = "\u201chello\u201d"
        findings = [
            Finding(
                file="t.txt",
                line=1,
                col=1,
                char="\u201c",
                codepoint=0x201C,
                name="LEFT DOUBLE QUOTATION MARK",
                category="Ps",
                dangerous=False,
            ),
            Finding(
                file="t.txt",
                line=1,
                col=7,
                char="\u201d",
                codepoint=0x201D,
                name="RIGHT DOUBLE QUOTATION MARK",
                category="Pe",
                dangerous=False,
            ),
        ]
        caret = _build_caret_line(line, findings)
        assert caret.count("^") == 2

    def test_invisible_char_expansion(self) -> None:
        """Caret position accounts for <U+XXXX> expansion of invisible chars."""
        line = "a\u200bb"  # ZWS between a and b
        findings = [
            Finding(
                file="t.txt",
                line=1,
                col=2,
                char="\u200b",
                codepoint=0x200B,
                name="ZERO WIDTH SPACE",
                category="Cf",
                dangerous=True,
            ),
        ]
        caret = _build_caret_line(line, findings)
        # 'a' is at position 0, ZWS renders as <U+200B> starting at position 1
        assert caret == " !"


class TestFormatCodepointEntry:
    """Tests for codepoint listing entry formatting."""

    def test_normal_no_color(self) -> None:
        """Normal finding formatted with codepoint, name, and category."""
        finding = Finding(
            file="t.txt",
            line=1,
            col=1,
            char="\u201c",
            codepoint=0x201C,
            name="LEFT DOUBLE QUOTATION MARK",
            category="Ps",
            dangerous=False,
        )
        result = _format_codepoint_entry(finding, 1, color=False)
        assert "U+201C" in result
        assert "LEFT DOUBLE QUOTATION MARK" in result
        assert "[Ps]" in result
        assert "(x" not in result

    def test_count_shown(self) -> None:
        """Count > 1 shows (xN) suffix."""
        finding = Finding(
            file="t.txt",
            line=1,
            col=1,
            char="\u2500",
            codepoint=0x2500,
            name="BOX DRAWINGS LIGHT HORIZONTAL",
            category="So",
            dangerous=False,
        )
        result = _format_codepoint_entry(finding, 98, color=False)
        assert "(x98)" in result

    def test_dangerous_prefix(self) -> None:
        """Dangerous findings prefixed with ! [DANGEROUS]."""
        finding = Finding(
            file="t.txt",
            line=1,
            col=1,
            char="\u202e",
            codepoint=0x202E,
            name="RIGHT-TO-LEFT OVERRIDE",
            category="Cf",
            dangerous=True,
        )
        result = _format_codepoint_entry(finding, 1, color=False)
        assert result.startswith("! [DANGEROUS]")

    def test_confusable_prefix(self) -> None:
        """Confusable findings prefixed with ? [CONFUSABLE]."""
        finding = Finding(
            file="t.txt",
            line=1,
            col=1,
            char="\u0430",
            codepoint=0x0430,
            name="CYRILLIC SMALL LETTER A",
            category="Ll",
            dangerous=False,
            confusable="a",
        )
        result = _format_codepoint_entry(finding, 1, color=False)
        assert result.startswith("? [CONFUSABLE: looks like 'a']")

    def test_dangerous_with_color(self) -> None:
        """Dangerous findings use bold red ANSI codes."""
        finding = Finding(
            file="t.txt",
            line=1,
            col=1,
            char="\u202e",
            codepoint=0x202E,
            name="RIGHT-TO-LEFT OVERRIDE",
            category="Cf",
            dangerous=True,
        )
        result = _format_codepoint_entry(finding, 1, color=True)
        assert "[DANGEROUS]" in result
        assert "\033[1;31m" in result


class TestPrintFindings:
    """Tests for full grouped output."""

    def test_context_file_read_failure(self) -> None:
        """Findings referencing nonexistent files don't crash."""
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

    def test_grouped_header_format(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Output shows filepath:ranges: header."""
        f = tmp_path / "test.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        assert f"{f}:1:" in err

    def test_grouped_caret_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Output shows carets under non-ASCII characters."""
        f = tmp_path / "test.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        # Should have caret markers
        assert "^" in err

    def test_grouped_codepoint_listing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Output lists unique codepoints."""
        f = tmp_path / "test.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        assert "U+201C" in err
        assert "U+201D" in err

    def test_quiet_suppresses_detail(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Quiet mode shows only summary."""
        f = tmp_path / "test.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True, quiet=True)
        err = capsys.readouterr().err
        assert "Found" in err
        assert "U+201C" not in err

    def test_deduplicates_identical_context(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Identical context lines are shown only once."""
        f = tmp_path / "test.txt"
        # Write 5 identical lines with same non-ASCII char
        f.write_text("\u2500\u2500\u2500\n" * 5, encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        # The context line should appear only once despite 5 source lines
        rendered_line = "\u2500\u2500\u2500"
        assert err.count(f"  {rendered_line}") == 1

    def test_count_for_repeated_codepoints(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Repeated codepoints show (xN) count."""
        f = tmp_path / "test.txt"
        f.write_text("\u2500" * 10 + "\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        assert "(x10)" in err
