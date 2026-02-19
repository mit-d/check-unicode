"""Integration tests -- run against fixture files end-to-end."""

from __future__ import annotations

import shutil
from pathlib import Path

from check_unicode.checker import AllowConfig, check_file
from check_unicode.fixer import fix_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestFixtureDetection:
    """Tests for detection across all fixture files."""

    def test_clean_ascii_no_findings(self) -> None:
        """Clean ASCII fixture produces no findings."""
        assert check_file(FIXTURES / "clean_ascii.txt") == []

    def test_smart_quotes_all_fixable(self) -> None:
        """Smart quote fixture findings are all fixable and not dangerous."""
        findings = check_file(FIXTURES / "smart_quotes.txt")
        assert len(findings) > 0
        assert all(f.fixable for f in findings)
        assert not any(f.dangerous for f in findings)

    def test_bidi_attack_has_dangerous(self) -> None:
        """Bidi attack fixture contains dangerous findings."""
        findings = check_file(FIXTURES / "bidi_attack.txt")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) >= 1

    def test_zero_width_has_dangerous(self) -> None:
        """Zero-width fixture contains dangerous findings."""
        findings = check_file(FIXTURES / "zero_width.txt")
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) >= 1

    def test_nerd_font_icons_detected(self) -> None:
        """Nerd font icon fixture produces findings."""
        findings = check_file(FIXTURES / "nerd_font_icons.txt")
        assert len(findings) > 0


class TestFixThenCheck:
    """Tests that fix-then-check produces expected results."""

    def test_fix_smart_quotes_then_clean(self, tmp_path: Path) -> None:
        """Fixing smart quotes results in a clean file on re-check."""
        src = FIXTURES / "smart_quotes.txt"
        dest = tmp_path / "smart_quotes.txt"
        shutil.copy2(src, dest)

        assert fix_file(dest) is True
        findings = check_file(dest)
        assert findings == []

    def test_fix_does_not_remove_dangerous(self, tmp_path: Path) -> None:
        """Fixing does not remove dangerous characters from files."""
        src = FIXTURES / "bidi_attack.txt"
        dest = tmp_path / "bidi_attack.txt"
        shutil.copy2(src, dest)

        fix_file(dest)
        findings = check_file(dest)
        dangerous = [f for f in findings if f.dangerous]
        assert len(dangerous) >= 1


class TestMixedAllowedWithConfig:
    """Tests for allow-list configuration with mixed character files."""

    def test_all_allowed_with_right_config(self) -> None:
        """All characters pass when the correct allow config is applied."""
        allow = AllowConfig(
            codepoints=frozenset([0x00B0, 0x00A9]),
            categories=frozenset(["Sc"]),
        )
        findings = check_file(FIXTURES / "mixed_allowed.txt", allow)
        assert findings == []

    def test_partial_allow(self) -> None:
        """Partially allowed config still flags non-allowed characters."""
        allow = AllowConfig(codepoints=frozenset([0x00B0]))
        findings = check_file(FIXTURES / "mixed_allowed.txt", allow)
        codepoints = {f.codepoint for f in findings}
        assert 0x00B0 not in codepoints
        assert 0x20AC in codepoints  # euro not allowed
