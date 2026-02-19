"""Tests for check_unicode.scripts."""

from __future__ import annotations

import pytest

from check_unicode.scripts import KNOWN_SCRIPTS, script_of


class TestLatinScript:
    """Tests for Latin script detection."""

    def test_ascii_letters(self) -> None:
        """Basic ASCII letters are Latin."""
        assert script_of(ord("A")) == "Latin"
        assert script_of(ord("z")) == "Latin"

    def test_accented_latin(self) -> None:
        """Accented Latin characters are Latin."""
        assert script_of(0x00E9) == "Latin"  # U+00E9 e-acute
        assert script_of(0x00F1) == "Latin"  # U+00F1 n-tilde
        assert script_of(0x00FC) == "Latin"  # U+00FC u-diaeresis


class TestCyrillicScript:
    """Tests for Cyrillic script detection."""

    def test_cyrillic_letters(self) -> None:
        """Cyrillic letters are detected correctly."""
        assert script_of(0x0430) == "Cyrillic"  # U+0430
        assert script_of(0x0410) == "Cyrillic"  # U+0410
        assert script_of(0x0441) == "Cyrillic"  # U+0441

    def test_cyrillic_uppercase(self) -> None:
        """Cyrillic uppercase letters are detected correctly."""
        assert script_of(0x0411) == "Cyrillic"  # U+0411
        assert script_of(0x0416) == "Cyrillic"  # U+0416


class TestGreekScript:
    """Tests for Greek script detection."""

    def test_greek_letters(self) -> None:
        """Greek letters are detected correctly."""
        assert script_of(0x03B1) == "Greek"  # U+03B1 alpha
        assert script_of(0x03A9) == "Greek"  # U+03A9 omega


class TestHanScript:
    """Tests for CJK/Han script detection via multi-word prefix."""

    def test_cjk_ideograph(self) -> None:
        """CJK unified ideographs map to Han."""
        assert script_of(0x4E00) == "Han"  # U+4E00
        assert script_of(0x5B57) == "Han"  # U+5B57


class TestCommonScript:
    """Tests for Common script (punctuation, digits, symbols)."""

    def test_digits_are_common(self) -> None:
        """ASCII digits are Common."""
        assert script_of(ord("0")) == "Common"
        assert script_of(ord("9")) == "Common"

    def test_punctuation_is_common(self) -> None:
        """Punctuation characters are Common."""
        assert script_of(ord(".")) == "Common"
        assert script_of(ord("!")) == "Common"

    def test_currency_is_common(self) -> None:
        """Currency symbols are Common."""
        assert script_of(0x20AC) == "Common"  # euro sign


class TestInheritedScript:
    """Tests for Inherited script (combining marks)."""

    def test_combining_marks(self) -> None:
        """Combining marks are Inherited."""
        assert script_of(0x0300) == "Inherited"  # combining grave accent
        assert script_of(0x0301) == "Inherited"  # combining acute accent


class TestJapaneseScriptQuirks:
    """Tests for Japanese characters that need special script mapping."""

    def test_prolonged_sound_mark_is_katakana(self) -> None:
        """Katakana-Hiragana prolonged sound mark (U+30FC) maps to Katakana."""
        assert script_of(0x30FC) == "Katakana"

    def test_ideographic_iteration_mark_is_han(self) -> None:
        """Ideographic iteration mark (U+3005) maps to Han."""
        assert script_of(0x3005) == "Han"

    def test_ideographic_closing_mark_is_han(self) -> None:
        """Ideographic closing mark (U+3006) maps to Han."""
        assert script_of(0x3006) == "Han"


class TestOtherScripts:
    """Tests for other script detection."""

    def test_arabic(self) -> None:
        """Arabic letters are detected correctly."""
        assert script_of(0x0627) == "Arabic"  # U+0627 alef

    def test_devanagari(self) -> None:
        """Devanagari letters are detected correctly."""
        assert script_of(0x0905) == "Devanagari"  # U+0905

    def test_hangul(self) -> None:
        """Hangul syllables are detected correctly."""
        assert script_of(0xAC00) == "Hangul"  # U+AC00

    def test_hiragana(self) -> None:
        """Hiragana characters are detected correctly."""
        assert script_of(0x3042) == "Hiragana"  # U+3042

    def test_katakana(self) -> None:
        """Katakana characters are detected correctly."""
        assert script_of(0x30A2) == "Katakana"  # U+30A2

    def test_armenian(self) -> None:
        """Armenian letters are detected correctly."""
        assert script_of(0x0531) == "Armenian"  # U+0531


class TestKnownScripts:
    """Tests for the KNOWN_SCRIPTS set."""

    @pytest.mark.parametrize("script", ["Latin", "Cyrillic", "Greek", "Han", "Arabic"])
    def test_major_scripts_in_known(self, script: str) -> None:
        """Major scripts are listed in KNOWN_SCRIPTS."""
        assert script in KNOWN_SCRIPTS

    def test_common_and_inherited_in_known(self) -> None:
        """Common and Inherited pseudo-scripts are in KNOWN_SCRIPTS."""
        assert "Common" in KNOWN_SCRIPTS
        assert "Inherited" in KNOWN_SCRIPTS
