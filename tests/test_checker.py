"""Tests for check_unicode.checker."""

from __future__ import annotations

from pathlib import Path

from check_unicode.checker import AllowConfig, check_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestCleanFiles:
    """Tests for files containing only clean ASCII."""

    def test_clean_ascii_returns_empty(self) -> None:
        """Clean ASCII files produce no findings."""
        findings = check_file(FIXTURES / "clean_ascii.txt")
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


class TestDangerousChars:
    """Tests for dangerous invisible character detection."""

    def test_bidi_always_flagged(self) -> None:
        """Bidi override characters are always flagged as dangerous."""
        findings = check_file(FIXTURES / "bidi_attack.txt")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    def test_bidi_not_suppressed_by_broad_range(self) -> None:
        """Bidi characters are not suppressed by broad allow ranges."""
        allow = AllowConfig(ranges=((0x0000, 0xFFFF),))
        findings = check_file(FIXTURES / "bidi_attack.txt", allow)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    def test_bidi_not_suppressed_by_category(self) -> None:
        """Bidi characters are not suppressed by category allow-lists."""
        allow = AllowConfig(categories=frozenset(["Cf"]))
        findings = check_file(FIXTURES / "bidi_attack.txt", allow)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) > 0

    def test_bidi_suppressed_by_explicit_codepoint(self) -> None:
        """Bidi characters are suppressed only by explicit codepoint allow."""
        # Get the dangerous codepoints first
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
        # Sc = Symbol, currency (covers euro sign U+20AC)
        allow = AllowConfig(categories=frozenset(["Sc"]))
        findings = check_file(FIXTURES / "mixed_allowed.txt", allow)
        assert not any(f.codepoint == 0x20AC for f in findings)


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


class TestInvalidUTF8:
    """Tests for invalid UTF-8 and binary file handling."""

    def test_binary_file_handled_gracefully(self, tmp_path: Path) -> None:
        """Binary files produce a single graceful error finding."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x80\x81\x82\xff\xfe")
        findings = check_file(f)
        assert len(findings) == 1
        assert "Could not read file" in findings[0].name
