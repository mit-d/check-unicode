"""Tests for check_unicode.fixer."""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from check_unicode.checker import AllowConfig
from check_unicode.fixer import fix_file, fix_text, strip_file, strip_text

if TYPE_CHECKING:
    from pathlib import Path


class TestStripText:
    """Tests for strip_text() character removal."""

    @pytest.mark.parametrize(
        ("level", "input_text", "expected"),
        [
            ("all", "caf\u00e9\n", "caf\n"),
            ("all", "He said \u201chello\u201d\n", "He said hello\n"),
            ("dangerous", "caf\u00e9\n", "caf\u00e9\n"),
            ("dangerous", "x\u202ey\n", "xy\n"),
            ("dangerous", "a\u200bb\n", "ab\n"),
            ("all", "hello world\n", "hello world\n"),
            ("dangerous", "hello world\n", "hello world\n"),
            ("all", "", ""),
        ],
        ids=[
            "all-accented",
            "all-smart-quotes",
            "dangerous-keeps-accented",
            "dangerous-strips-bidi",
            "dangerous-strips-zwsp",
            "all-clean-passthrough",
            "dangerous-clean-passthrough",
            "all-empty",
        ],
    )
    def test_strip_text(self, level: str, input_text: str, expected: str) -> None:
        """strip_text removes characters based on level."""
        assert strip_text(input_text, level=level) == expected

    def test_strip_text_respects_allowed(self) -> None:
        """Allowed codepoints are never stripped."""
        text = "caf\u00e9 x\u202ey\n"
        allow = AllowConfig(codepoints=frozenset({0x00E9}))
        result = strip_text(text, level="all", allow=allow)
        assert result == "caf\u00e9 xy\n"

    def test_strip_dangerous_respects_allowed(self) -> None:
        """Explicitly allowed dangerous codepoints are not stripped."""
        text = "x\u202ey\n"
        allow = AllowConfig(codepoints=frozenset({0x202E}))
        result = strip_text(text, level="dangerous", allow=allow)
        assert result == "x\u202ey\n"

    def test_multiline_strips_across_lines(self) -> None:
        """Non-ASCII chars on different lines are all stripped."""
        text = "caf\u00e9\nhello\u2026\nworld\u2014end\n"
        result = strip_text(text, level="all")
        assert result == "caf\nhello\nworldend\n"

    def test_multiple_dangerous_chars_stripped(self) -> None:
        """Multiple different dangerous chars are all stripped in dangerous mode."""
        # ZWSP + bidi override + zero-width non-joiner
        text = "a\u200bb\u202ec\u200cd\n"
        result = strip_text(text, level="dangerous")
        assert result == "abcd\n"

    def test_all_level_strips_dangerous_chars(self) -> None:
        """Level 'all' strips dangerous chars as well as non-dangerous non-ASCII."""
        text = "x\u200by\u202ez\n"
        result = strip_text(text, level="all")
        assert result == "xyz\n"

    def test_allow_printable_preserves_printable(self) -> None:
        """Allow printable=True keeps printable non-ASCII but still strips dangerous."""
        text = "caf\u00e9 x\u200by\n"
        allow = AllowConfig(printable=True)
        result = strip_text(text, level="all", allow=allow)
        # e-acute is printable -> kept; ZWSP is dangerous -> stripped
        assert result == "caf\u00e9 xy\n"

    def test_allow_range_preserves_chars_in_range(self) -> None:
        """Chars within an allowed range are not stripped."""
        # Allow Latin-1 Supplement range (U+00C0 to U+00FF)
        text = "caf\u00e9 na\u00efve\n"
        allow = AllowConfig(ranges=((0x00C0, 0x00FF),))
        result = strip_text(text, level="all", allow=allow)
        assert result == "caf\u00e9 na\u00efve\n"

    def test_allow_script_preserves_chars_in_script(self) -> None:
        """Chars belonging to an allowed script are not stripped."""
        # Greek capital letter sigma
        text = "sum=\u03a3\n"
        allow = AllowConfig(scripts=frozenset({"Greek"}))
        result = strip_text(text, level="all", allow=allow)
        assert result == "sum=\u03a3\n"


class TestFixText:
    """Tests for fix_text() pure string replacement."""

    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            ("\u201chello\u201d", '"hello"'),
            ("It\u2019s", "It's"),
            ("\u2018word\u2019", "'word'"),
            ("\u201aquote\u201b", "'quote'"),
            ("\u201equote\u201f", '"quote"'),
            ("\u00abguillemet\u00bb", '"guillemet"'),
            ("\u2039angle\u203a", "'angle'"),
            ("word\u2014word", "word-word"),
            ("1\u20132", "1-2"),
            ("x \u2212 y", "x - y"),
            ("hello\u00a0world", "hello world"),
            ("a\u2003b", "a b"),
            ("a\u2009b", "a b"),
            ("a\u200ab", "a b"),
            ("a\u3000b", "a b"),
            ("wait\u2026", "wait..."),
            ("a\u2010b", "a-b"),
            ("a\u2011b", "a-b"),
            ("a\u2012b", "a-b"),
            ("a\u2015b", "a-b"),
            ("a\ufe58b", "a-b"),
            ("soft\u00adhyphen", "softhyphen"),
            ("\u2022 item", "* item"),
            ("\u2023 item", "* item"),
            ("\u2043 item", "- item"),
            ("ch\u20241", "ch.1"),
            ("ch\u20251", "ch..1"),
            ("a \u2192 b", "a -> b"),
            ("b \u2190 a", "b <- a"),
            ("\u2191up", "^up"),
            ("\u2193down", "vdown"),
            ("2 \u00d7 3", "2 x 3"),
            ("6 \u00f7 2", "6 / 2"),
            ("1\u20442", "1/2"),
        ],
        ids=[
            "smart-double-quotes",
            "right-single-quote",
            "left-right-single-quotes",
            "low9-highrev9-single-quotes",
            "low9-highrev9-double-quotes",
            "guillemets",
            "angle-quotes",
            "em-dash",
            "en-dash",
            "minus-sign",
            "nbsp",
            "em-space",
            "thin-space",
            "hair-space",
            "ideographic-space",
            "ellipsis",
            "hyphen",
            "non-breaking-hyphen",
            "figure-dash",
            "horizontal-bar",
            "small-em-dash",
            "soft-hyphen",
            "bullet",
            "triangular-bullet",
            "hyphen-bullet",
            "one-dot-leader",
            "two-dot-leader",
            "right-arrow",
            "left-arrow",
            "up-arrow",
            "down-arrow",
            "multiplication-sign",
            "division-sign",
            "fraction-slash",
        ],
    )
    def test_fix_replaces_character(self, input_text: str, expected: str) -> None:
        """fix_text replaces known non-ASCII chars with ASCII equivalents."""
        assert fix_text(input_text) == expected

    def test_clean_text_unchanged(self) -> None:
        """Plain ASCII text passes through unchanged."""
        text = "hello world 123 !@#$%\n"
        assert fix_text(text) == text

    def test_dangerous_chars_unchanged(self) -> None:
        """Dangerous invisible chars are never replaced by fix_text."""
        text = "a\u200bb\u202ec\n"
        assert fix_text(text) == text

    def test_mixed_fixable_nonfixable_dangerous(self) -> None:
        """Only fixable chars are replaced; non-fixable and dangerous are kept."""
        # e-acute (non-fixable), smart quote (fixable), ZWSP (dangerous)
        text = "caf\u00e9 \u201chi\u201d a\u200bb\n"
        result = fix_text(text)
        assert result == 'caf\u00e9 "hi" a\u200bb\n'

    def test_multiline_text(self) -> None:
        """fix_text handles multi-line strings correctly."""
        text = "line1 \u201chi\u201d\nline2 word\u2014word\nline3 wait\u2026\n"
        expected = 'line1 "hi"\nline2 word-word\nline3 wait...\n'
        assert fix_text(text) == expected


class TestFixFileReplacements:
    """Tests for fix_file() character replacements via atomic write."""

    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            ("\u201chello\u201d", '"hello"'),
            ("It\u2019s", "It's"),
            ("\u2018word\u2019", "'word'"),
            ("word\u2014word", "word-word"),
            ("1\u20132", "1-2"),
            ("x \u2212 y", "x - y"),
            ("hello\u00a0world", "hello world"),
            ("a\u2003b", "a b"),
            ("wait\u2026", "wait..."),
        ],
        ids=[
            "smart-double-quotes",
            "right-single-quote",
            "left-right-single-quotes",
            "em-dash",
            "en-dash",
            "minus-sign",
            "nbsp",
            "em-space",
            "ellipsis",
        ],
    )
    def test_fix_replaces_character(
        self, tmp_path: Path, input_text: str, expected: str
    ) -> None:
        """fix_file replaces known non-ASCII chars and returns True."""
        f = tmp_path / "test.txt"
        f.write_text(input_text + "\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == expected + "\n"


class TestDangerousCharsNotFixed:
    """Tests that dangerous characters are never auto-fixed."""

    def test_zero_width_space_preserved(self, tmp_path: Path) -> None:
        """Zero-width spaces are not removed by the fixer."""
        f = tmp_path / "zws.txt"
        f.write_text("ab\u200bcd\n", encoding="utf-8")
        assert fix_file(f) is False
        assert "\u200b" in f.read_text(encoding="utf-8")

    def test_bidi_preserved(self, tmp_path: Path) -> None:
        """Bidi override characters are not removed by the fixer."""
        f = tmp_path / "bidi.txt"
        f.write_text("x\u202ey\u202cz\n", encoding="utf-8")
        assert fix_file(f) is False
        assert "\u202e" in f.read_text(encoding="utf-8")


class TestNoOpOnClean:
    """Tests that clean files are not modified."""

    def test_clean_file_unchanged(self, tmp_path: Path) -> None:
        """Clean ASCII files return False and are not modified."""
        f = tmp_path / "clean.txt"
        f.write_text("hello world\n", encoding="utf-8")
        assert fix_file(f) is False

    def test_no_replacement_chars_unchanged(self, tmp_path: Path) -> None:
        """Characters without replacement mappings are left untouched."""
        f = tmp_path / "unknown.txt"
        f.write_text("caf\u00e9\n", encoding="utf-8")  # e-acute
        assert fix_file(f) is False


class TestStripFile:
    """Tests for strip_file() with atomic writes."""

    def test_strip_file_removes_non_ascii(self, tmp_path: Path) -> None:
        """strip_file removes non-ASCII characters and returns True."""
        f = tmp_path / "strip.txt"
        f.write_text("caf\u00e9\n", encoding="utf-8")
        assert strip_file(f) is True
        assert f.read_text(encoding="utf-8") == "caf\n"

    def test_strip_file_clean_returns_false(self, tmp_path: Path) -> None:
        """strip_file on a clean ASCII file returns False."""
        f = tmp_path / "clean.txt"
        f.write_text("hello world\n", encoding="utf-8")
        assert strip_file(f) is False

    def test_strip_file_preserves_permissions(self, tmp_path: Path) -> None:
        """File permissions are preserved after stripping."""
        f = tmp_path / "perms.txt"
        f.write_text("caf\u00e9\n", encoding="utf-8")
        f.chmod(0o755)
        strip_file(f)
        mode = stat.S_IMODE(f.stat().st_mode)
        assert mode == 0o755

    def test_strip_file_with_allow_config(self, tmp_path: Path) -> None:
        """strip_file respects AllowConfig, keeping allowed codepoints."""
        f = tmp_path / "allow.txt"
        f.write_text("caf\u00e9 \u201chi\u201d\n", encoding="utf-8")
        allow = AllowConfig(codepoints=frozenset({0x00E9}))
        assert strip_file(f, allow=allow) is True
        assert f.read_text(encoding="utf-8") == "caf\u00e9 hi\n"

    def test_strip_file_dangerous_level(self, tmp_path: Path) -> None:
        """strip_file with level='dangerous' only removes dangerous chars."""
        f = tmp_path / "danger.txt"
        f.write_text("caf\u00e9 a\u200bb\n", encoding="utf-8")
        assert strip_file(f, level="dangerous") is True
        assert f.read_text(encoding="utf-8") == "caf\u00e9 ab\n"

    def test_strip_file_binary_returns_false(self, tmp_path: Path) -> None:
        """Binary files that fail UTF-8 decode return False."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\xff")
        assert strip_file(f) is False


class TestAtomicWrite:
    """Tests for atomic file writing behavior."""

    def test_preserves_permissions(self, tmp_path: Path) -> None:
        """File permissions are preserved after fixing."""
        f = tmp_path / "perms.txt"
        f.write_text("\u201chello\u201d\n", encoding="utf-8")
        f.chmod(0o644)
        fix_file(f)
        mode = stat.S_IMODE(f.stat().st_mode)
        assert mode == 0o644

    def test_binary_file_no_crash(self, tmp_path: Path) -> None:
        """Binary files do not cause crashes and return False."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\xff")
        assert fix_file(f) is False

    def test_cleanup_on_write_failure(self, tmp_path: Path) -> None:
        """Temp file is cleaned up if an error occurs during write."""
        f = tmp_path / "fixme.txt"
        f.write_text("\u201chello\u201d\n", encoding="utf-8")
        with (
            patch("check_unicode.fixer.Path.chmod", side_effect=OSError("fail")),
            pytest.raises(OSError, match="fail"),
        ):
            fix_file(f)
        # Temp file should be cleaned up
        remaining = list(tmp_path.glob(".*"))
        assert remaining == []
