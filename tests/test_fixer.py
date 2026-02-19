"""Tests for check_unicode.fixer."""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from check_unicode.fixer import fix_file

if TYPE_CHECKING:
    from pathlib import Path


class TestSmartQuoteReplacement:
    """Tests for smart quote to ASCII replacement."""

    def test_replaces_smart_double_quotes(self, tmp_path: Path) -> None:
        """Smart double quotes are replaced with straight double quotes."""
        f = tmp_path / "quotes.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == 'He said "hello"\n'

    def test_replaces_smart_single_quotes(self, tmp_path: Path) -> None:
        """Smart single quotes are replaced with straight apostrophes."""
        f = tmp_path / "quotes.txt"
        f.write_text("It\u2019s fine\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "It's fine\n"


class TestDashReplacement:
    """Tests for dash and minus sign replacement."""

    def test_replaces_em_dash(self, tmp_path: Path) -> None:
        """Em dashes are replaced with double hyphens."""
        f = tmp_path / "dashes.txt"
        f.write_text("word\u2014word\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "word--word\n"

    def test_replaces_en_dash(self, tmp_path: Path) -> None:
        """En dashes are replaced with double hyphens."""
        f = tmp_path / "dashes.txt"
        f.write_text("1\u20132\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "1--2\n"

    def test_replaces_minus_sign(self, tmp_path: Path) -> None:
        """Unicode minus signs are replaced with ASCII hyphens."""
        f = tmp_path / "minus.txt"
        f.write_text("x \u2212 y\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "x - y\n"


class TestSpaceReplacement:
    """Tests for non-breaking and special space replacement."""

    def test_replaces_nbsp(self, tmp_path: Path) -> None:
        """Non-breaking spaces are replaced with regular spaces."""
        f = tmp_path / "spaces.txt"
        f.write_text("hello\u00a0world\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "hello world\n"

    def test_replaces_em_space(self, tmp_path: Path) -> None:
        """Em spaces are replaced with regular spaces."""
        f = tmp_path / "spaces.txt"
        f.write_text("a\u2003b\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "a b\n"


class TestEllipsis:
    """Tests for ellipsis character replacement."""

    def test_replaces_ellipsis(self, tmp_path: Path) -> None:
        """Unicode ellipsis is replaced with three dots."""
        f = tmp_path / "ellipsis.txt"
        f.write_text("wait\u2026\n", encoding="utf-8")
        assert fix_file(f) is True
        assert f.read_text(encoding="utf-8") == "wait...\n"


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
        # Characters with no entry in REPLACEMENT_TABLE
        f = tmp_path / "unknown.txt"
        f.write_text("caf\u00e9\n", encoding="utf-8")  # e-acute
        assert fix_file(f) is False


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
