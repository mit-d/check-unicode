"""Tests for check_unicode.checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unicode.categories import REPLACEMENT_TABLE
from check_unicode.checker import AllowConfig, Finding, check_confusables, check_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestCleanFiles:
    """Tests for files containing only clean ASCII."""

    def test_clean_ascii_returns_empty(self) -> None:
        """Clean ASCII files produce no findings."""
        findings = check_file(FIXTURES / "clean_ascii.txt")
        assert findings == []

    def test_empty_string(self) -> None:
        """Empty text produces no findings."""
        findings = check_file("virtual.txt", text="")
        assert findings == []

    def test_only_newlines(self) -> None:
        """Text with only newlines produces no findings."""
        findings = check_file("virtual.txt", text="\n\n\n")
        assert findings == []

    def test_tabs_and_spaces(self) -> None:
        """Text with tabs and spaces produces no findings."""
        findings = check_file("virtual.txt", text="\t  \t  hello\tworld  \n")
        assert findings == []

    def test_empty_file(self, tmp_path: Path) -> None:
        """An empty file on disk produces no findings."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        findings = check_file(f)
        assert findings == []


class TestSmartQuotes:
    """Tests for smart/curly quote detection."""

    def test_detects_smart_quotes(self) -> None:
        """Smart quotes are detected as non-ASCII findings."""
        findings = check_file(FIXTURES / "smart_quotes.txt")
        assert len(findings) > 0
        codepoints = {f.codepoint for f in findings}
        assert 0x201C in codepoints  # left double quote
        assert 0x201D in codepoints  # right double quote

    def test_correct_line_and_col(self) -> None:
        """Findings report correct line and column numbers."""
        findings = check_file(FIXTURES / "smart_quotes.txt")
        # First finding should be on line 1
        first = findings[0]
        assert first.line == 1
        assert first.col > 0

    def test_smart_quotes_are_fixable(self) -> None:
        """Smart quotes are marked as fixable."""
        findings = check_file(FIXTURES / "smart_quotes.txt")
        assert all(f.fixable for f in findings)

    def test_smart_quotes_not_dangerous(self) -> None:
        """Smart quotes are not marked as dangerous."""
        findings = check_file(FIXTURES / "smart_quotes.txt")
        assert not any(f.dangerous for f in findings)


class TestTextParameter:
    """Tests for check_file with text= parameter (no disk I/O)."""

    def test_empty_text(self) -> None:
        """Empty text produces no findings."""
        findings = check_file("virtual.txt", text="")
        assert findings == []

    def test_clean_text(self) -> None:
        """Clean ASCII text produces no findings."""
        findings = check_file("virtual.txt", text="Hello, world!\n")
        assert findings == []

    def test_multiple_lines(self) -> None:
        """Findings span multiple lines with correct line numbers."""
        text = "line one \u201c\nline two \u201d\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 2
        assert findings[0].line == 1
        assert findings[1].line == 2

    def test_multiple_findings_same_line(self) -> None:
        """Multiple non-ASCII chars on the same line are all reported."""
        text = "\u201chello\u201d \u2013 world\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 3
        assert all(f.line == 1 for f in findings)
        cols = [f.col for f in findings]
        assert cols == sorted(cols)

    def test_respects_allow_config(self) -> None:
        """text= mode respects allow config."""
        text = "\u201chello\u201d\n"
        allow = AllowConfig(codepoints=frozenset([0x201C, 0x201D]))
        findings = check_file("virtual.txt", allow, text=text)
        assert findings == []

    def test_file_field_matches_path_argument(self) -> None:
        """Finding.file reflects the path argument, not a real file."""
        text = "caf\u00e9\n"
        findings = check_file("my/virtual/path.txt", text=text)
        assert len(findings) == 1
        assert findings[0].file == "my/virtual/path.txt"

    def test_col_is_one_indexed(self) -> None:
        """Column numbers are 1-indexed."""
        text = "abc\u00e9\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 1
        assert findings[0].col == 4


class TestDangerousChars:
    """Tests for dangerous invisible character detection."""

    def test_bidi_always_flagged(self) -> None:
        """Bidi override characters are always flagged as dangerous."""
        findings = check_file(FIXTURES / "bidi_attack.txt")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    @pytest.mark.parametrize(
        "allow",
        [
            AllowConfig(ranges=((0x0000, 0xFFFF),)),
            AllowConfig(categories=frozenset(["Cf"])),
            AllowConfig(printable=True),
            AllowConfig(scripts=frozenset(["Latin", "Common"])),
        ],
        ids=["range", "category", "printable", "script"],
    )
    def test_dangerous_not_suppressed(self, allow: AllowConfig) -> None:
        """Dangerous characters are not suppressed by non-codepoint allows."""
        findings = check_file(FIXTURES / "bidi_attack.txt", allow)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    def test_bidi_suppressed_by_explicit_codepoint(self) -> None:
        """Bidi characters are suppressed only by explicit codepoint allow."""
        findings = check_file(FIXTURES / "bidi_attack.txt")
        dangerous_cps = frozenset(f.codepoint for f in findings if f.dangerous)
        allow = AllowConfig(codepoints=dangerous_cps)
        findings2 = check_file(FIXTURES / "bidi_attack.txt", allow)
        dangerous2 = [f for f in findings2 if f.dangerous]
        assert len(dangerous2) == 0

    def test_zero_width_flagged(self) -> None:
        """Zero-width characters are flagged as dangerous."""
        findings = check_file(FIXTURES / "zero_width.txt")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    def test_zero_width_not_fixable(self) -> None:
        """Dangerous zero-width characters are not marked as fixable."""
        findings = check_file(FIXTURES / "zero_width.txt")
        dangerous = [f for f in findings if f.dangerous]
        assert not any(f.fixable for f in dangerous)

    @pytest.mark.parametrize(
        "allow",
        [
            AllowConfig(ranges=((0x0000, 0xFFFF),)),
            AllowConfig(categories=frozenset(["Cf"])),
            AllowConfig(printable=True),
        ],
        ids=["range", "category", "printable"],
    )
    def test_zero_width_not_suppressed(self, allow: AllowConfig) -> None:
        """Zero-width chars are not suppressed by non-codepoint allows."""
        findings = check_file(FIXTURES / "zero_width.txt", allow)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0


class TestAllowList:
    """Tests for allow-list filtering of findings."""

    def test_allow_codepoint(self) -> None:
        """Explicitly allowed codepoints are excluded from findings."""
        allow = AllowConfig(codepoints=frozenset([0x00B0]))
        findings = check_file(FIXTURES / "mixed_allowed.txt", allow)
        assert not any(f.codepoint == 0x00B0 for f in findings)

    def test_allow_range(self) -> None:
        """Codepoints within an allowed range are excluded from findings."""
        allow = AllowConfig(ranges=((0x00A0, 0x00FF),))
        findings = check_file(FIXTURES / "mixed_allowed.txt", allow)
        assert not any(0x00A0 <= f.codepoint <= 0x00FF for f in findings)

    def test_allow_category(self) -> None:
        """Codepoints in an allowed Unicode category are excluded."""
        allow = AllowConfig(categories=frozenset(["Sc"]))
        findings = check_file(FIXTURES / "mixed_allowed.txt", allow)
        assert not any(f.codepoint == 0x20AC for f in findings)


class TestAllowPrintable:
    """Tests for --allow-printable filtering."""

    def test_printable_suppresses_smart_quotes(self) -> None:
        """Printable mode suppresses smart quote findings."""
        allow = AllowConfig(printable=True)
        findings = check_file(FIXTURES / "smart_quotes.txt", allow)
        assert findings == []

    def test_printable_still_flags_dangerous(self) -> None:
        """Printable mode does not suppress dangerous invisible characters."""
        allow = AllowConfig(printable=True)
        findings = check_file(FIXTURES / "bidi_attack.txt", allow)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    def test_printable_suppresses_i18n(self) -> None:
        """Printable mode suppresses all printable i18n characters."""
        allow = AllowConfig(printable=True)
        findings = check_file(FIXTURES / "printable_i18n.txt", allow)
        assert findings == []

    def test_printable_off_flags_i18n(self) -> None:
        """Without printable mode, i18n characters are flagged."""
        findings = check_file(FIXTURES / "printable_i18n.txt")
        assert len(findings) > 0


class TestAllowScript:
    """Tests for --allow-script filtering."""

    def test_allow_latin_suppresses_accented(self) -> None:
        """Allowing Latin script suppresses accented Latin characters."""
        allow = AllowConfig(scripts=frozenset(["Latin"]))
        findings = check_file(FIXTURES / "printable_i18n.txt", allow)
        assert not any(f.name.startswith("LATIN") for f in findings)
        assert len(findings) > 0

    def test_allow_script_still_flags_dangerous(self) -> None:
        """Script allow-list does not suppress dangerous characters."""
        allow = AllowConfig(scripts=frozenset(["Latin", "Common"]))
        findings = check_file(FIXTURES / "bidi_attack.txt", allow)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0


class TestAllowPriority:
    """Tests for _is_allowed evaluation order and combined allow types."""

    def test_explicit_codepoint_overrides_dangerous(self) -> None:
        """Explicit codepoint allow overrides DANGEROUS_INVISIBLE block."""
        text = "hello\u200bworld\n"
        allow = AllowConfig(codepoints=frozenset([0x200B]))
        findings = check_file("virtual.txt", allow, text=text)
        assert not any(f.codepoint == 0x200B for f in findings)

    def test_printable_checked_before_script(self) -> None:
        """Printable allows a char even without script match."""
        text = "caf\u00e9\n"
        allow_printable = AllowConfig(printable=True)
        findings = check_file("virtual.txt", allow_printable, text=text)
        assert findings == []

    def test_script_checked_before_range(self) -> None:
        """Script allows a char even without range match."""
        text = "caf\u00e9\n"
        allow_script = AllowConfig(scripts=frozenset(["Latin"]))
        findings = check_file("virtual.txt", allow_script, text=text)
        assert findings == []

    def test_range_checked_before_category(self) -> None:
        """Range allows a char even without category match."""
        text = "\u00a9 copyright\n"
        allow_range = AllowConfig(ranges=((0x00A0, 0x00FF),))
        findings = check_file("virtual.txt", allow_range, text=text)
        assert not any(f.codepoint == 0x00A9 for f in findings)

    def test_category_is_last_resort(self) -> None:
        """Category alone can allow a char."""
        text = "\u20ac100\n"
        allow_cat = AllowConfig(categories=frozenset(["Sc"]))
        findings = check_file("virtual.txt", allow_cat, text=text)
        assert findings == []

    def test_printable_plus_category_covers_all(self) -> None:
        """Combining printable + category covers all non-dangerous chars."""
        text = "caf\u00e9 \u20ac100 \u00a9 \u201chello\u201d\n"
        allow = AllowConfig(printable=True, categories=frozenset(["Sc"]))
        findings = check_file("virtual.txt", allow, text=text)
        assert findings == []

    def test_dangerous_blocked_even_with_all_other_allows(self) -> None:
        """Dangerous chars blocked even with printable + script + range + category."""
        text = "hello\u202eworld\n"
        allow = AllowConfig(
            printable=True,
            scripts=frozenset(["Latin", "Common"]),
            ranges=((0x0000, 0xFFFF),),
            categories=frozenset(["Cf"]),
        )
        findings = check_file("virtual.txt", allow, text=text)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0


class TestConfusableEdgeCases:
    """Tests for check_confusables edge cases."""

    def test_empty_text(self) -> None:
        """Empty text produces no confusable findings."""
        findings = check_confusables("virtual.txt", text="")
        assert findings == []

    def test_single_script_no_findings(self) -> None:
        """A line with only one script produces no confusable findings."""
        findings = check_confusables("virtual.txt", text="hello world\n")
        assert findings == []

    def test_latin_wins_tie(self) -> None:
        """When Latin and another script tie, Latin is dominant."""
        # 3 Latin + 3 Cyrillic confusables (U+0430, U+0441, U+043E)
        text = "abc\u0430\u0441\u043e\n"
        findings = check_confusables("virtual.txt", text=text)
        assert len(findings) == 3
        assert all(f.confusable is not None for f in findings)
        confusable_cps = {f.codepoint for f in findings}
        assert confusable_cps == {0x0430, 0x0441, 0x043E}

    def test_minority_not_in_table_no_finding(self) -> None:
        """Minority-script char not in CONFUSABLES table is not flagged."""
        # Mix Latin with a Cyrillic char NOT in CONFUSABLES (U+0436)
        text = "abcdef\u0436\n"
        findings = check_confusables("virtual.txt", text=text)
        assert findings == []

    def test_confusable_finding_has_replacement(self) -> None:
        """Confusable findings include the Latin lookalike."""
        text = "abc\u0430\n"
        findings = check_confusables("virtual.txt", text=text)
        assert len(findings) == 1
        assert findings[0].confusable == "a"

    def test_pure_cyrillic_no_findings(self) -> None:
        """Pure Cyrillic text (single script) produces no findings."""
        findings = check_confusables(FIXTURES / "pure_cyrillic.txt")
        assert findings == []

    def test_confusable_line_numbers(self) -> None:
        """Confusable findings report correct line numbers."""
        text = "hello world\nabc\u0430def\n"
        findings = check_confusables("virtual.txt", text=text)
        assert len(findings) == 1
        assert findings[0].line == 2


class TestBOM:
    """Tests for byte-order mark handling."""

    def test_bom_at_start_ignored(self, tmp_path: Path) -> None:
        """BOM at the start of a file is silently ignored."""
        f = tmp_path / "bom.txt"
        f.write_text("\ufeffhello world\n", encoding="utf-8")
        findings = check_file(f)
        assert not any(f_.codepoint == 0xFEFF for f_ in findings)

    def test_bom_midfile_flagged(self, tmp_path: Path) -> None:
        """BOM in the middle of a file is flagged as a finding."""
        f = tmp_path / "midbom.txt"
        f.write_text("hello\ufeffworld\n", encoding="utf-8")
        findings = check_file(f)
        assert any(f_.codepoint == 0xFEFF for f_ in findings)

    def test_bom_line2_col1_flagged(self) -> None:
        """BOM at line 2 col 1 is flagged (not at file start)."""
        text = "hello\n\ufeffworld\n"
        findings = check_file("virtual.txt", text=text)
        bom_findings = [f for f in findings if f.codepoint == 0xFEFF]
        assert len(bom_findings) == 1
        assert bom_findings[0].line == 2
        assert bom_findings[0].col == 1

    def test_bom_only_file(self) -> None:
        """A file containing only a BOM produces no findings (BOM at start)."""
        text = "\ufeff"
        findings = check_file("virtual.txt", text=text)
        assert not any(f.codepoint == 0xFEFF for f in findings)

    def test_bom_at_start_via_text(self) -> None:
        """BOM at start of text= input is also ignored."""
        text = "\ufeffhello world\n"
        findings = check_file("virtual.txt", text=text)
        assert not any(f.codepoint == 0xFEFF for f in findings)


class TestInvalidUTF8:
    """Tests for invalid UTF-8 and binary file handling."""

    def test_binary_file_handled_gracefully(self, tmp_path: Path) -> None:
        """Binary files produce a single graceful error finding."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\x82\xff\xfe")
        findings = check_file(f)
        assert len(findings) == 1
        assert "Could not read file" in findings[0].name


class TestFindingProperties:
    """Tests for Finding.fixable and other computed properties."""

    @pytest.mark.parametrize(
        ("codepoint", "char"),
        [
            (0x201C, "\u201c"),
            (0x201D, "\u201d"),
            (0x2018, "\u2018"),
            (0x2013, "\u2013"),
            (0x00A0, "\u00a0"),
        ],
        ids=["left-dquote", "right-dquote", "left-squote", "en-dash", "nbsp"],
    )
    def test_replacement_table_chars_are_fixable(
        self, codepoint: int, char: str
    ) -> None:
        """Characters in REPLACEMENT_TABLE are marked fixable."""
        text = f"abc{char}def\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 1
        assert findings[0].fixable
        assert findings[0].codepoint == codepoint

    def test_accented_char_not_fixable(self) -> None:
        """Accented characters not in REPLACEMENT_TABLE are not fixable."""
        text = "caf\u00e9\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 1
        assert not findings[0].fixable

    def test_dangerous_never_fixable_even_if_in_replacement_table(self) -> None:
        """Dangerous findings are never fixable, even for REPLACEMENT_TABLE chars."""
        for cp in (0x201C, 0x201D, 0x00A0):
            assert cp in REPLACEMENT_TABLE
            f = Finding(
                file="virtual.txt",
                line=1,
                col=1,
                char=chr(cp),
                codepoint=cp,
                name="TEST",
                category="Cf",
                dangerous=True,
            )
            assert not f.fixable

    def test_dangerous_zero_width_not_fixable(self) -> None:
        """Zero-width dangerous characters are not fixable."""
        text = "hello\u200bworld\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 1
        assert findings[0].dangerous
        assert not findings[0].fixable

    def test_finding_fields_populated(self) -> None:
        """All Finding fields are correctly populated."""
        text = "caf\u00e9\n"
        findings = check_file("virtual.txt", text=text)
        assert len(findings) == 1
        f = findings[0]
        assert f.file == "virtual.txt"
        assert f.line == 1
        assert f.col == 4
        assert f.char == "\u00e9"
        assert f.codepoint == 0x00E9
        assert "LATIN" in f.name
        assert f.category == "Ll"
        assert not f.dangerous
        assert f.confusable is None
