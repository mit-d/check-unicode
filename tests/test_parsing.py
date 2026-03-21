"""Tests for check_unicode.parsing -- codepoint and range parsing."""

from __future__ import annotations

import pytest

from check_unicode.parsing import parse_codepoint, parse_range


class TestParseCodepoint:
    """Tests for parse_codepoint()."""

    def test_u_plus_prefix(self) -> None:
        """U+XXXX format parses correctly."""
        assert parse_codepoint("U+00B0") == 0x00B0

    def test_u_plus_lowercase(self) -> None:
        """u+xxxx format parses correctly."""
        assert parse_codepoint("u+00b0") == 0x00B0

    def test_hex_prefix(self) -> None:
        """0xXXXX format parses correctly."""
        assert parse_codepoint("0x00B0") == 0x00B0

    def test_bare_hex(self) -> None:
        """Bare hex digits parse correctly."""
        assert parse_codepoint("00B0") == 0x00B0

    def test_short_bare_hex(self) -> None:
        """Short bare hex like 'A0' parses correctly."""
        assert parse_codepoint("A0") == 0xA0

    def test_max_unicode(self) -> None:
        """U+10FFFF (max valid codepoint) is accepted."""
        assert parse_codepoint("U+10FFFF") == 0x10FFFF

    def test_zero(self) -> None:
        """U+0000 is a valid codepoint."""
        assert parse_codepoint("U+0000") == 0

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert parse_codepoint("  U+00B0  ") == 0x00B0

    def test_rejects_empty_string(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            parse_codepoint("")

    def test_rejects_whitespace_only(self) -> None:
        """Whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            parse_codepoint("   ")

    def test_rejects_above_max_unicode(self) -> None:
        """Values above U+10FFFF raise ValueError."""
        with pytest.raises(ValueError, match=r"U\+10FFFF"):
            parse_codepoint("U+110000")

    def test_rejects_negative(self) -> None:
        """Negative values raise ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid|outside"):
            parse_codepoint("-1")

    def test_rejects_non_hex(self) -> None:
        """Non-hex strings raise ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid"):
            parse_codepoint("ZZZZ")

    def test_rejects_bare_u_plus(self) -> None:
        """'U+' with no digits raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid"):
            parse_codepoint("U+")

    def test_mixed_case_hex_digits(self) -> None:
        """Mixed case hex digits work."""
        assert parse_codepoint("U+00aB") == 0x00AB


class TestParseRange:
    """Tests for parse_range()."""

    def test_u_plus_format(self) -> None:
        """U+XXXX-U+YYYY format parses correctly."""
        assert parse_range("U+00A0-U+00FF") == (0x00A0, 0x00FF)

    def test_hex_prefix_format(self) -> None:
        """0xXXXX-0xYYYY format parses correctly."""
        assert parse_range("0x00A0-0x00FF") == (0x00A0, 0x00FF)

    def test_bare_hex_format(self) -> None:
        """Bare hex A0-FF parses correctly."""
        assert parse_range("00A0-00FF") == (0x00A0, 0x00FF)

    def test_whitespace_around_dash(self) -> None:
        """Whitespace around the dash is tolerated."""
        assert parse_range("U+00A0 - U+00FF") == (0x00A0, 0x00FF)

    def test_single_codepoint_range(self) -> None:
        """A range where lo == hi is valid."""
        assert parse_range("U+00B0-U+00B0") == (0x00B0, 0x00B0)

    def test_rejects_inverted_range(self) -> None:
        """Inverted range (hi < lo) raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]nverted|start.*end"):
            parse_range("U+00FF-U+00A0")

    def test_rejects_no_dash(self) -> None:
        """Single value without dash raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid range"):
            parse_range("U+00A0")

    def test_rejects_empty(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid range|empty"):
            parse_range("")

    def test_rejects_out_of_range(self) -> None:
        """Out-of-range codepoint in range raises ValueError."""
        with pytest.raises(ValueError, match=r"U\+10FFFF"):
            parse_range("U+0000-U+110000")

    def test_rejects_multiple_hyphens(self) -> None:
        """Multiple hyphens produce a clear error."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid"):
            parse_range("A0-B0-C0")
