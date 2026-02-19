"""Tests for check_unicode.main CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_unicode.main import _parse_codepoint, _parse_range, main

FIXTURES = Path(__file__).parent / "fixtures"


class TestExitCodes:
    """Tests for CLI exit code behavior."""

    def test_clean_file_exits_0(self) -> None:
        """Clean files produce exit code 0."""
        assert main([str(FIXTURES / "clean_ascii.txt")]) == 0

    def test_dirty_file_exits_1(self) -> None:
        """Files with non-ASCII characters produce exit code 1."""
        assert main([str(FIXTURES / "smart_quotes.txt")]) == 1

    def test_warning_severity_exits_0(self) -> None:
        """Warning severity mode exits 0 even with findings."""
        assert main(["--severity", "warning", str(FIXTURES / "smart_quotes.txt")]) == 0

    def test_dangerous_file_exits_1(self) -> None:
        """Files with dangerous characters produce exit code 1."""
        assert main([str(FIXTURES / "bidi_attack.txt")]) == 1

    def test_no_files_exits_error(self) -> None:
        """Providing no files causes argparse to exit with code 2."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2  # argparse error


class TestFixMode:
    """Tests for the --fix CLI flag."""

    def test_fix_modifies_file_exits_1(self, tmp_path: Path) -> None:
        """Fix mode replaces fixable characters and exits 1 when changes are made."""
        f = tmp_path / "fixme.txt"
        f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        assert main(["--fix", str(f)]) == 1
        assert f.read_text(encoding="utf-8") == 'He said "hello"\n'

    def test_fix_clean_file_exits_0(self, tmp_path: Path) -> None:
        """Fix mode on a clean file exits 0 with no changes."""
        f = tmp_path / "clean.txt"
        f.write_text("hello world\n", encoding="utf-8")
        assert main(["--fix", str(f)]) == 0

    def test_fix_dangerous_still_reported(self, tmp_path: Path) -> None:
        """Fix mode does not remove dangerous characters."""
        f = tmp_path / "bidi.txt"
        f.write_text("x\u202ey\n", encoding="utf-8")
        assert main(["--fix", str(f)]) == 1
        # Bidi char should still be in the file
        assert "\u202e" in f.read_text(encoding="utf-8")


class TestAllowFlags:
    """Tests for --allow-codepoint, --allow-range, and --allow-category flags."""

    def test_allow_codepoint(self) -> None:
        """Allowed codepoints suppress findings via CLI flag."""
        assert (
            main(
                [
                    "--allow-codepoint",
                    "U+00B0,U+00A9,U+20AC",
                    str(FIXTURES / "mixed_allowed.txt"),
                ]
            )
            == 0
        )

    def test_allow_range(self) -> None:
        """Allowed ranges suppress findings via CLI flag."""
        assert (
            main(
                [
                    "--allow-range",
                    "U+00A0-U+00FF",
                    "--allow-range",
                    "U+20A0-U+20CF",
                    str(FIXTURES / "mixed_allowed.txt"),
                ]
            )
            == 0
        )

    def test_allow_category(self) -> None:
        """Allowed categories suppress findings via CLI flag."""
        # Allow currency symbols and letter-like chars
        assert (
            main(
                [
                    "--allow-category",
                    "Sc",
                    "--allow-codepoint",
                    "U+00B0,U+00A9",
                    str(FIXTURES / "mixed_allowed.txt"),
                ]
            )
            == 0
        )


class TestConfigFile:
    """Tests for TOML configuration file loading."""

    def test_config_loads_toml(self, tmp_path: Path) -> None:
        """Allow-lists from a TOML config file are applied correctly."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[tool.check-unicode]\nallow-codepoints = ["U+00B0", "U+00A9", "U+20AC"]\n',
            encoding="utf-8",
        )
        f = tmp_path / "test.txt"
        f.write_text("72\u00b0F \u00a9 \u20ac100\n", encoding="utf-8")
        assert main(["--config", str(config), str(f)]) == 0


class TestNoColor:
    """Tests for the --no-color flag."""

    def test_no_color_flag(self) -> None:
        """The --no-color flag does not cause a crash."""
        # Should not crash
        assert main(["--no-color", str(FIXTURES / "smart_quotes.txt")]) == 1


class TestQuiet:
    """Tests for the -q/--quiet flag."""

    def test_quiet_flag(self) -> None:
        """The -q flag suppresses output without crashing."""
        # Should not crash
        assert main(["-q", str(FIXTURES / "smart_quotes.txt")]) == 1


class TestMultipleFiles:
    """Tests for scanning multiple files at once."""

    def test_multiple_files(self) -> None:
        """Exit code is 1 when any file has findings."""
        assert (
            main(
                [
                    str(FIXTURES / "clean_ascii.txt"),
                    str(FIXTURES / "smart_quotes.txt"),
                ]
            )
            == 1
        )

    def test_multiple_clean_files(self) -> None:
        """Exit code is 0 when all files are clean."""
        assert (
            main(
                [
                    str(FIXTURES / "clean_ascii.txt"),
                    str(FIXTURES / "clean_ascii.txt"),
                ]
            )
            == 0
        )


class TestParseCodepoint:
    """Tests for codepoint parsing helpers."""

    def test_parse_hex_prefix(self) -> None:
        """Codepoints with 0x prefix are parsed correctly."""
        assert _parse_codepoint("0x00B0") == 0x00B0

    def test_parse_bare_hex(self) -> None:
        """Bare hex strings without prefix are parsed correctly."""
        assert _parse_codepoint("00B0") == 0x00B0


class TestParseRange:
    """Tests for range parsing helpers."""

    def test_invalid_range_raises(self) -> None:
        """Invalid range strings raise ArgumentTypeError."""
        with pytest.raises(Exception, match="Invalid range"):
            _parse_range("NOPE")


class TestConfigDiscovery:
    """Tests for automatic config file discovery."""

    def test_discover_dedicated_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Auto-discovers .check-unicode.toml in the current directory."""
        config = tmp_path / ".check-unicode.toml"
        config.write_text(
            'allow-codepoints = ["U+00B0"]\n',
            encoding="utf-8",
        )
        f = tmp_path / "test.txt"
        f.write_text("72\u00b0F\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert main([str(f)]) == 0

    def test_discover_pyproject_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Auto-discovers [tool.check-unicode] in pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.check-unicode]\nallow-codepoints = ["U+00B0"]\n',
            encoding="utf-8",
        )
        f = tmp_path / "test.txt"
        f.write_text("72\u00b0F\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert main([str(f)]) == 0
