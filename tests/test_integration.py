"""Integration tests -- run against fixture files end-to-end."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from check_unicode.checker import AllowConfig, check_confusables, check_file
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


# Classic literature fixtures (see tests/fixtures/LICENSES.fixtures)

# (fixture_stem, scripts needed to cover all non-ASCII characters)
CLASSIC_TEXTS: list[tuple[str, frozenset[str]]] = [
    ("classic_arabic", frozenset({"Arabic", "Common", "Inherited"})),
    ("classic_chinese", frozenset({"Han", "Common"})),
    ("classic_cyrillic", frozenset({"Cyrillic"})),
    ("classic_devanagari", frozenset({"Devanagari", "Common", "Inherited"})),
    ("classic_greek", frozenset({"Greek", "Common"})),
    ("classic_hebrew", frozenset({"Hebrew", "Inherited"})),
    ("classic_japanese", frozenset({"Han", "Hiragana", "Katakana", "Common"})),
    ("classic_korean", frozenset({"Hangul", "Han", "Inherited"})),
]
CLASSIC_IDS = [t[0] for t in CLASSIC_TEXTS]

# Fixtures that legitimately contain DANGEROUS_INVISIBLE characters:
#   devanagari -- zero-width joiner (U+200D) for ligature formation
_HAS_DANGEROUS = {"classic_devanagari"}

# Fixtures where --allow-printable leaves non-printable residue:
#   arabic     -- U+2009 THIN SPACE (1x)
#   devanagari -- U+200D ZERO WIDTH JOINER (1x, dangerous)
#   japanese   -- U+3000 IDEOGRAPHIC SPACE (23x)
_ALLOW_PRINTABLE_RESIDUE = {
    "classic_arabic",
    "classic_devanagari",
    "classic_japanese",
}


class TestClassicTexts:
    """Integration tests for classic literature fixtures.

    Real-world multilingual texts validating --allow-printable,
    --allow-script, and --check-confusables against authentic content.
    """

    @pytest.mark.parametrize("name", CLASSIC_IDS)
    def test_has_non_ascii_findings(self, name: str) -> None:
        """Classic texts contain non-ASCII characters."""
        findings = check_file(FIXTURES / f"{name}.txt")
        assert len(findings) > 0

    @pytest.mark.parametrize("name", CLASSIC_IDS)
    def test_no_dangerous(self, name: str) -> None:
        """Most classic literature has no dangerous invisible characters."""
        findings = check_file(FIXTURES / f"{name}.txt")
        dangerous = [f for f in findings if f.dangerous]
        if name not in _HAS_DANGEROUS:
            assert dangerous == []
        else:
            # Dangerous chars exist but are legitimate in context
            assert len(dangerous) > 0

    @pytest.mark.parametrize("name", CLASSIC_IDS)
    def test_allow_printable(self, name: str) -> None:
        """--allow-printable covers all printable non-ASCII characters."""
        allow = AllowConfig(printable=True)
        findings = check_file(FIXTURES / f"{name}.txt", allow)
        if name not in _ALLOW_PRINTABLE_RESIDUE:
            assert findings == []
        else:
            # Remaining findings are non-printable spaces or
            # dangerous invisibles -- not a tool bug.
            for f in findings:
                assert not chr(f.codepoint).isprintable()

    @pytest.mark.parametrize(("name", "scripts"), CLASSIC_TEXTS)
    def test_allow_script(self, name: str, scripts: frozenset[str]) -> None:
        """--allow-script with the correct scripts covers all non-ASCII.

        Dangerous invisible characters (bidi controls, ZWS, ZWJ) are
        never suppressed by --allow-script, so they remain as findings.
        """
        allow = AllowConfig(scripts=scripts)
        findings = check_file(FIXTURES / f"{name}.txt", allow)
        non_dangerous = [f for f in findings if not f.dangerous]
        assert non_dangerous == [], (
            f"Unmatched scripts: "
            f"{sorted({f.name.split()[0] for f in non_dangerous[:20]})}"
        )

    @pytest.mark.parametrize("name", CLASSIC_IDS)
    def test_confusables(self, name: str) -> None:
        """Pure single-script content produces no confusable findings.

        All classic fixtures now use public-domain source text without
        Project Gutenberg headers, so no Latin mixing occurs.
        """
        findings = check_confusables(FIXTURES / f"{name}.txt")
        assert findings == [], f"Unexpected confusables: {findings[:5]}"
