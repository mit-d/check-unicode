"""Tests for confusable/homoglyph detection."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from check_unicode.checker import Finding, check_confusables, check_file
from check_unicode.confusables import CONFUSABLES
from check_unicode.main import main
from check_unicode.output import _format_codepoint_entry, print_findings

FIXTURES = Path(__file__).parent / "fixtures"


class TestConfusablesData:
    """Tests for the CONFUSABLES mapping."""

    def test_cyrillic_a_maps_to_latin_a(self) -> None:
        """Cyrillic U+0430 maps to Latin 'a'."""
        assert CONFUSABLES[0x0430] == "a"

    def test_cyrillic_o_maps_to_latin_o(self) -> None:
        """Cyrillic U+043E maps to Latin 'o'."""
        assert CONFUSABLES[0x043E] == "o"

    def test_greek_omicron_maps_to_latin_o(self) -> None:
        """Greek U+03BF (omicron) maps to Latin 'o'."""
        assert CONFUSABLES[0x03BF] == "o"

    def test_all_values_are_ascii(self) -> None:
        """All confusable target values are ASCII characters."""
        for cp, target in CONFUSABLES.items():
            assert target.isascii(), f"U+{cp:04X} maps to non-ASCII: {target!r}"


class TestCheckConfusables:
    """Tests for the check_confusables() function."""

    def test_mixed_script_detected(self) -> None:
        """Mixed Latin/Cyrillic on same line triggers confusable finding."""
        findings = check_confusables(FIXTURES / "confusable_cyrillic.txt")
        assert len(findings) > 0
        # Should detect the Cyrillic U+0430
        assert any(f.codepoint == 0x0430 for f in findings)

    def test_confusable_field_set(self) -> None:
        """Confusable findings have the confusable field set."""
        findings = check_confusables(FIXTURES / "confusable_cyrillic.txt")
        confusables = [f for f in findings if f.confusable is not None]
        assert len(confusables) > 0
        assert confusables[0].confusable == "a"

    def test_pure_cyrillic_no_confusable(self) -> None:
        """Pure Cyrillic text does not trigger confusable detection."""
        findings = check_confusables(FIXTURES / "pure_cyrillic.txt")
        assert findings == []

    def test_clean_ascii_no_confusable(self) -> None:
        """Clean ASCII files produce no confusable findings."""
        findings = check_confusables(FIXTURES / "clean_ascii.txt")
        assert findings == []

    def test_confusable_in_tmp(self, tmp_path: Path) -> None:
        """Confusable detection works on mixed-script identifiers."""
        f = tmp_path / "test.txt"
        # Mix Cyrillic U+0435 into Latin word
        f.write_text("us\u0435r_input = True\n", encoding="utf-8")
        findings = check_confusables(f)
        assert len(findings) == 1
        assert findings[0].confusable == "e"

    def test_binary_file_no_crash(self, tmp_path: Path) -> None:
        """Binary files produce no confusable findings."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\x82\xff\xfe")
        findings = check_confusables(f)
        assert findings == []

    def test_allow_script_does_not_suppress_confusable(self) -> None:
        """--allow-script does not suppress confusable warnings.

        check_confusables() intentionally ignores allow-lists; confusable
        detection is always based purely on script mixing regardless of
        what scripts are allowed.
        """
        findings = check_confusables(FIXTURES / "confusable_cyrillic.txt")
        assert len(findings) > 0


class TestConfusableCLI:
    """Tests for --check-confusables CLI flag."""

    def test_confusable_flag_detects(self) -> None:
        """--check-confusables detects mixed-script homoglyphs."""
        result = main(
            ["--check-confusables", str(FIXTURES / "confusable_cyrillic.txt")]
        )
        assert result == 1

    def test_confusable_flag_clean_file(self) -> None:
        """--check-confusables on clean file still exits 0."""
        result = main(["--check-confusables", str(FIXTURES / "clean_ascii.txt")])
        assert result == 0

    def test_confusable_flag_pure_cyrillic_still_flags(self) -> None:
        """Pure Cyrillic triggers check_file but not confusable detection."""
        result = main(["--check-confusables", str(FIXTURES / "pure_cyrillic.txt")])
        assert result == 1

    def test_confusable_with_allow_script(self, tmp_path: Path) -> None:
        """--check-confusables + --allow-script: confusable overrides script allow."""
        f = tmp_path / "test.txt"
        # Cyrillic U+0430 mixed with Latin
        f.write_text("p\u0430ssword = 'secret'\n", encoding="utf-8")
        result = main(
            [
                "--check-confusables",
                "--allow-script",
                "Cyrillic",
                "--allow-script",
                "Latin",
                str(f),
            ]
        )
        # check_file won't flag (script allowed), but check_confusables will
        assert result == 1


class TestTrojanSourceFixtures:
    """Tests for Trojan Source attack fixtures."""

    def test_trojan_commenting_out_flagged(self) -> None:
        """Trojan Source commenting-out attack is flagged as dangerous."""
        findings = check_file(FIXTURES / "trojan_commenting_out.py")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) >= 1

    def test_trojan_early_return_flagged(self) -> None:
        """Trojan Source early-return attack is flagged as dangerous."""
        findings = check_file(FIXTURES / "trojan_early_return.py")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) >= 1


class TestConfusableOutput:
    """Tests for confusable finding output formatting."""

    def test_confusable_format_no_color(self) -> None:
        """Confusable findings show CONFUSABLE prefix without color."""
        finding = Finding(
            file="test.txt",
            line=1,
            col=4,
            char="\u0430",
            codepoint=0x0430,
            name="CYRILLIC SMALL LETTER A",
            category="Ll",
            dangerous=False,
            confusable="a",
        )
        result = _format_codepoint_entry(finding, 1, color=False)
        assert "[CONFUSABLE: looks like 'a']" in result

    def test_confusable_format_with_color(self) -> None:
        """Confusable findings show yellow CONFUSABLE prefix with color."""
        finding = Finding(
            file="test.txt",
            line=1,
            col=4,
            char="\u0430",
            codepoint=0x0430,
            name="CYRILLIC SMALL LETTER A",
            category="Ll",
            dangerous=False,
            confusable="a",
        )
        result = _format_codepoint_entry(finding, 1, color=True)
        assert "[CONFUSABLE: looks like 'a']" in result
        assert "\033[33m" in result  # yellow

    def test_confusable_summary_count(self) -> None:
        """Summary includes confusable count."""
        finding = Finding(
            file="test.txt",
            line=1,
            col=4,
            char="\u0430",
            codepoint=0x0430,
            name="CYRILLIC SMALL LETTER A",
            category="Ll",
            dangerous=False,
            confusable="a",
        )
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            print_findings([finding], no_color=True)
        output = buf.getvalue()
        assert "1 confusable" in output
