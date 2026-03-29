"""Tests for check_unicode.output formatting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from check_unicode.checker import Finding, check_file
from check_unicode.output import (
    _build_caret_line,
    _compact_ranges,
    _format_codepoint_entry,
    _print_file_findings,
    _use_color,
    print_findings,
    print_line_findings,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _make_finding(
    *,
    col: int = 1,
    char: str = "\u201c",
    codepoint: int = 0x201C,
    name: str = "LEFT DOUBLE QUOTATION MARK",
    category: str = "Ps",
    dangerous: bool = False,
    confusable: str | None = None,
    file: str = "t.txt",
    line: int = 1,
) -> Finding:
    return Finding(
        file=file,
        line=line,
        col=col,
        char=char,
        codepoint=codepoint,
        name=name,
        category=category,
        dangerous=dangerous,
        confusable=confusable,
    )


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

    def test_two_consecutive(self) -> None:
        """Two consecutive lines collapsed into a range."""
        assert _compact_ranges([5, 6]) == "5-6"

    def test_large_gap(self) -> None:
        """Large gap between lines shown comma-separated."""
        assert _compact_ranges([1, 1000]) == "1,1000"

    def test_single_element_list(self) -> None:
        """Single element list returns that element as string."""
        assert _compact_ranges([42]) == "42"


class TestBuildCaretLine:
    """Tests for caret line construction."""

    @pytest.mark.parametrize(
        ("line_text", "finding", "expected_marker", "absent_marker"),
        [
            (
                "He said \u201chello\u201d",
                _make_finding(col=9),
                "^",
                None,
            ),
            (
                "x\u202ey",
                _make_finding(
                    col=2,
                    char="\u202e",
                    codepoint=0x202E,
                    name="RIGHT-TO-LEFT OVERRIDE",
                    category="Cf",
                    dangerous=True,
                ),
                "!",
                "^",
            ),
            (
                "p\u0430ssword",
                _make_finding(
                    col=2,
                    char="\u0430",
                    codepoint=0x0430,
                    name="CYRILLIC SMALL LETTER A",
                    category="Ll",
                    confusable="a",
                ),
                "?",
                "^",
            ),
        ],
        ids=["normal-caret", "dangerous-exclamation", "confusable-question"],
    )
    def test_marker_type(
        self,
        line_text: str,
        finding: Finding,
        expected_marker: str,
        absent_marker: str | None,
    ) -> None:
        """Correct marker character used for each finding severity."""
        caret = _build_caret_line(line_text, [finding])
        assert expected_marker in caret
        if absent_marker is not None:
            assert absent_marker not in caret

    def test_multiple_findings_on_line(self) -> None:
        """Multiple findings produce multiple carets."""
        line = "\u201chello\u201d"
        findings = [
            _make_finding(col=1),
            _make_finding(
                col=7,
                char="\u201d",
                codepoint=0x201D,
                name="RIGHT DOUBLE QUOTATION MARK",
                category="Pe",
            ),
        ]
        caret = _build_caret_line(line, findings)
        assert caret.count("^") == 2

    def test_invisible_char_expansion(self) -> None:
        """Caret position accounts for <U+XXXX> expansion of invisible chars."""
        line = "a\u200bb"  # ZWS between a and b
        findings = [
            _make_finding(
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

    def test_finding_at_column_one(self) -> None:
        """Finding at column 1 produces marker at start of caret line."""
        line = "\u201chello"
        findings = [_make_finding(col=1)]
        caret = _build_caret_line(line, findings)
        assert caret.startswith("^")
        assert caret == "^"


class TestFormatCodepointEntry:
    """Tests for codepoint listing entry formatting."""

    def test_normal_no_color(self) -> None:
        """Normal finding formatted with codepoint, name, and category."""
        result = _format_codepoint_entry(_make_finding(), 1, color=False)
        assert "U+201C" in result
        assert "LEFT DOUBLE QUOTATION MARK" in result
        assert "[Ps]" in result
        assert "(x" not in result

    def test_count_shown(self) -> None:
        """Count > 1 shows (xN) suffix."""
        finding = _make_finding(
            char="\u2500",
            codepoint=0x2500,
            name="BOX DRAWINGS LIGHT HORIZONTAL",
            category="So",
        )
        result = _format_codepoint_entry(finding, 98, color=False)
        assert "(x98)" in result

    def test_dangerous_prefix(self) -> None:
        """Dangerous findings prefixed with ! [DANGEROUS]."""
        finding = _make_finding(
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
        finding = _make_finding(
            char="\u0430",
            codepoint=0x0430,
            name="CYRILLIC SMALL LETTER A",
            category="Ll",
            confusable="a",
        )
        result = _format_codepoint_entry(finding, 1, color=False)
        assert result.startswith("? [CONFUSABLE: looks like 'a']")

    def test_dangerous_with_color(self) -> None:
        """Dangerous findings use bold red ANSI codes."""
        finding = _make_finding(
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
        finding = _make_finding(file="/nonexistent/file.txt")
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
        f.write_text("\u2500\u2500\u2500\n" * 5, encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
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


class TestPrintFindingsEdgeCases:
    """Edge case tests for print_findings."""

    def test_empty_findings_only_summary(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Empty findings list produces only a zero-count summary."""
        print_findings([], no_color=True)
        err = capsys.readouterr().err
        assert "Found 0 non-ASCII characters in 0 files" in err
        # No file headers or codepoint listings
        assert "U+" not in err

    def test_summary_line_counts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Summary line shows correct character, file, and fixable counts."""
        f = tmp_path / "test.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        assert "Found 2 non-ASCII characters" in err
        assert "in 1 file" in err
        assert "2 fixable" in err

    def test_summary_singular_forms(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Single finding uses singular 'character' and 'file'."""
        f = tmp_path / "test.txt"
        f.write_text("He said \u201chello\n", encoding="utf-8")
        findings = check_file(str(f))
        print_findings(findings, no_color=True)
        err = capsys.readouterr().err
        assert "Found 1 non-ASCII character " in err
        assert "in 1 file " in err


class TestPrintFileFindingsWithText:
    """Tests for _print_file_findings with pre-supplied text."""

    def test_stdin_context_display(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Findings for <stdin> show context when text is provided."""
        text = "x\u202ey\n"
        findings = [
            _make_finding(
                file="<stdin>",
                col=2,
                char="\u202e",
                codepoint=0x202E,
                name="RIGHT-TO-LEFT OVERRIDE",
                category="Cf",
                dangerous=True,
            ),
        ]
        _print_file_findings("<stdin>", findings, color=False, text=text)
        err = capsys.readouterr().err
        assert "<U+202E>" in err
        assert "!" in err

    def test_stdin_no_text_no_context(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Without text param, <stdin> findings lack context."""
        findings = [
            _make_finding(
                file="<stdin>",
                col=2,
                char="\u202e",
                codepoint=0x202E,
                name="RIGHT-TO-LEFT OVERRIDE",
                category="Cf",
                dangerous=True,
            ),
        ]
        _print_file_findings("<stdin>", findings, color=False)
        err = capsys.readouterr().err
        assert "U+202E" in err
        assert "<U+202E>" not in err


class TestPrintLineFindings:
    """Tests for per-line finding output in pipe mode."""

    def test_single_line_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """print_line_findings emits context for one line."""
        line = "x\u202ey"
        findings = [
            _make_finding(
                file="<stdin>",
                line=5,
                col=2,
                char="\u202e",
                codepoint=0x202E,
                name="RIGHT-TO-LEFT OVERRIDE",
                category="Cf",
                dangerous=True,
            ),
        ]
        print_line_findings("<stdin>", 5, line, findings, no_color=True)
        err = capsys.readouterr().err
        assert "<stdin>:5:" in err
        assert "<U+202E>" in err
        assert "!" in err
        assert "U+202E" in err

    def test_multiple_findings_same_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Multiple findings on one line all appear."""
        line = "\u201chello\u201d"
        findings = [
            _make_finding(
                file="<stdin>",
                category="Pi",
            ),
            _make_finding(
                file="<stdin>",
                col=8,
                char="\u201d",
                codepoint=0x201D,
                name="RIGHT DOUBLE QUOTATION MARK",
                category="Pf",
            ),
        ]
        print_line_findings("<stdin>", 1, line, findings, no_color=True)
        err = capsys.readouterr().err
        assert "U+201C" in err
        assert "U+201D" in err
