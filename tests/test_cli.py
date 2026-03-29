"""Tests for check_unicode.main CLI."""

from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from check_unicode.checker import AllowConfig
from check_unicode.main import (
    Override,
    _build_overrides,
    _build_parser,
    _file_matches_override,
    _is_excluded,
    _preprocess_argv,
    _resolve_allow_for_file,
    _resolve_file_settings,
    main,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def smart_quotes_file(tmp_path: Path) -> Path:
    """File containing smart quotes (fixable characters)."""
    f = tmp_path / "smart.txt"
    f.write_text("He said \u201chello\u201d\n", encoding="utf-8")
    return f


@pytest.fixture
def accented_file(tmp_path: Path) -> Path:
    """File containing accented characters (non-fixable, non-dangerous)."""
    f = tmp_path / "accented.txt"
    f.write_text("caf\u00e9\n", encoding="utf-8")
    return f


@pytest.fixture
def dangerous_file(tmp_path: Path) -> Path:
    """File containing dangerous bidi characters."""
    f = tmp_path / "bidi.txt"
    f.write_text("x\u202ey\n", encoding="utf-8")
    return f


@pytest.fixture
def mixed_file(tmp_path: Path) -> Path:
    """File with fixable, non-fixable, and dangerous characters."""
    f = tmp_path / "mixed.txt"
    f.write_text("caf\u00e9 said \u201chi\u201d x\u202ey\n", encoding="utf-8")
    return f


@pytest.fixture
def stdin_from(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Fixture that sets sys.stdin to read from a string."""

    def _set(text: str) -> None:
        monkeypatch.setattr(
            "sys.stdin",
            io.TextIOWrapper(io.BytesIO(text.encode("utf-8"))),
        )

    return _set


class TestExitCodes:
    """Tests for CLI exit code behavior."""

    @pytest.mark.parametrize(
        ("args", "expected_code"),
        [
            ([str(FIXTURES / "clean_ascii.txt")], 0),
            ([str(FIXTURES / "smart_quotes.txt")], 1),
            (["--severity", "warning", str(FIXTURES / "smart_quotes.txt")], 0),
            ([str(FIXTURES / "bidi_attack.txt")], 1),
        ],
        ids=["clean-exits-0", "dirty-exits-1", "warning-exits-0", "dangerous-exits-1"],
    )
    def test_exit_code(self, args: list[str], expected_code: int) -> None:
        """Exit codes match expected values for different inputs."""
        assert main(args) == expected_code

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

    def test_fix_multiple_files_all_fixed(self, tmp_path: Path) -> None:
        """Fix mode fixes all files, not just the first one."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("He said \u201chello\u201d\n", encoding="utf-8")
        f2.write_text("word\u2014word\n", encoding="utf-8")
        assert main(["--fix", str(f1), str(f2)]) == 1
        assert f1.read_text(encoding="utf-8") == 'He said "hello"\n'
        assert f2.read_text(encoding="utf-8") == "word--word\n"

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


class TestAllowPrintableFlag:
    """Tests for --allow-printable CLI flag."""

    def test_allow_printable_suppresses_findings(self) -> None:
        """--allow-printable allows all printable non-ASCII characters."""
        assert main(["--allow-printable", str(FIXTURES / "smart_quotes.txt")]) == 0

    def test_allow_printable_still_flags_dangerous(self) -> None:
        """--allow-printable does not suppress dangerous characters."""
        assert main(["--allow-printable", str(FIXTURES / "bidi_attack.txt")]) == 1

    def test_allow_printable_i18n_fixture(self) -> None:
        """--allow-printable passes on i18n fixture."""
        assert main(["--allow-printable", str(FIXTURES / "printable_i18n.txt")]) == 0


class TestAllowScriptFlag:
    """Tests for --allow-script CLI flag."""

    def test_allow_script_suppresses_findings(self, tmp_path: Path) -> None:
        """--allow-script suppresses findings for that script."""
        f = tmp_path / "cyrillic.txt"
        f.write_text("\u0430\u0431\u0432\n", encoding="utf-8")  # U+0430-0432
        assert main(["--allow-script", "Cyrillic", str(f)]) == 0

    def test_allow_script_case_insensitive(self, tmp_path: Path) -> None:
        """--allow-script normalizes to title case."""
        f = tmp_path / "cyrillic.txt"
        f.write_text("\u0430\u0431\u0432\n", encoding="utf-8")
        assert main(["--allow-script", "cyrillic", str(f)]) == 0

    def test_allow_script_repeatable(self, tmp_path: Path) -> None:
        """--allow-script can be repeated for multiple scripts."""
        f = tmp_path / "mixed.txt"
        f.write_text("\u0430 \u03b1\n", encoding="utf-8")  # U+0430 U+03B1
        assert (
            main(["--allow-script", "Cyrillic", "--allow-script", "Greek", str(f)]) == 0
        )

    def test_allow_script_still_flags_dangerous(self) -> None:
        """--allow-script does not suppress dangerous characters."""
        assert main(["--allow-script", "Latin", str(FIXTURES / "bidi_attack.txt")]) == 1


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


class TestConfigPrintableAndScript:
    """Tests for allow-printable and allow-scripts in TOML config."""

    def test_config_allow_printable(self, tmp_path: Path) -> None:
        """allow-printable = true in config works."""
        config = tmp_path / "config.toml"
        config.write_text("allow-printable = true\n", encoding="utf-8")
        f = tmp_path / "test.txt"
        f.write_text("caf\u00e9\n", encoding="utf-8")
        assert main(["--config", str(config), str(f)]) == 0

    def test_config_allow_scripts(self, tmp_path: Path) -> None:
        """allow-scripts in config works."""
        config = tmp_path / "config.toml"
        config.write_text('allow-scripts = ["Cyrillic"]\n', encoding="utf-8")
        f = tmp_path / "test.txt"
        f.write_text("\u0430\u0431\u0432\n", encoding="utf-8")
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


class TestExcludePattern:
    """Tests for --exclude-pattern CLI flag."""

    def test_exclude_pattern_skips_file(self) -> None:
        """Excluded files are skipped entirely."""
        assert (
            main(
                [
                    "--exclude-pattern",
                    "*.txt",
                    str(FIXTURES / "smart_quotes.txt"),
                ]
            )
            == 0
        )

    def test_exclude_pattern_keeps_non_matching(self) -> None:
        """Non-matching files are still checked."""
        assert (
            main(
                [
                    "--exclude-pattern",
                    "*.js",
                    str(FIXTURES / "smart_quotes.txt"),
                ]
            )
            == 1
        )

    def test_exclude_pattern_repeatable(self) -> None:
        """--exclude-pattern can be repeated to exclude multiple patterns."""
        assert (
            main(
                [
                    "--exclude-pattern",
                    "*.txt",
                    "--exclude-pattern",
                    "*.py",
                    str(FIXTURES / "smart_quotes.txt"),
                    str(FIXTURES / "trojan_early_return.py"),
                ]
            )
            == 0
        )

    def test_exclude_pattern_matches_basename(self) -> None:
        """Patterns match against the basename of the file."""
        assert (
            main(
                [
                    "--exclude-pattern",
                    "smart_quotes*",
                    str(FIXTURES / "smart_quotes.txt"),
                ]
            )
            == 0
        )

    def test_exclude_all_files_exits_0(self, tmp_path: Path) -> None:
        """Excluding all files exits 0 (nothing to check)."""
        f = tmp_path / "dirty.txt"
        f.write_text("\u201chello\u201d\n", encoding="utf-8")
        assert main(["--exclude-pattern", "*.txt", str(f)]) == 0

    def test_exclude_pattern_with_fix(self, tmp_path: Path) -> None:
        """Excluded files are not fixed in --fix mode."""
        f = tmp_path / "fixme.min.js"
        f.write_text("\u201chello\u201d\n", encoding="utf-8")
        assert main(["--fix", "--exclude-pattern", "*.min.js", str(f)]) == 0
        # File should remain unmodified
        assert "\u201c" in f.read_text(encoding="utf-8")

    def test_exclude_pattern_from_config(self, tmp_path: Path) -> None:
        """exclude-patterns from config file are applied."""
        config = tmp_path / "config.toml"
        config.write_text(
            'exclude-patterns = ["*.min.js"]\n',
            encoding="utf-8",
        )
        f = tmp_path / "bundle.min.js"
        f.write_text("\u201chello\u201d\n", encoding="utf-8")
        assert main(["--config", str(config), str(f)]) == 0

    def test_exclude_pattern_cli_extends_config(self, tmp_path: Path) -> None:
        """CLI --exclude-pattern extends config exclude-patterns."""
        config = tmp_path / "config.toml"
        config.write_text(
            'exclude-patterns = ["*.min.js"]\n',
            encoding="utf-8",
        )
        js_file = tmp_path / "bundle.min.js"
        js_file.write_text("\u201chello\u201d\n", encoding="utf-8")
        txt_file = tmp_path / "dirty.txt"
        txt_file.write_text("\u201chello\u201d\n", encoding="utf-8")
        assert (
            main(
                [
                    "--config",
                    str(config),
                    "--exclude-pattern",
                    "*.txt",
                    str(js_file),
                    str(txt_file),
                ]
            )
            == 0
        )


class TestIsExcluded:
    """Tests for the _is_excluded helper function."""

    def test_matches_glob(self) -> None:
        """Glob patterns match correctly."""
        assert _is_excluded("foo.min.js", ["*.min.js"]) is True

    def test_no_match(self) -> None:
        """Non-matching patterns return False."""
        assert _is_excluded("foo.py", ["*.js"]) is False

    def test_matches_basename(self) -> None:
        """Patterns match against the basename."""
        assert _is_excluded("/some/deep/path/foo.min.js", ["*.min.js"]) is True

    def test_matches_full_path(self) -> None:
        """Patterns can match against the full path."""
        assert _is_excluded("vendor/lib.js", ["vendor/*"]) is True

    def test_empty_patterns(self) -> None:
        """Empty pattern list excludes nothing."""
        assert _is_excluded("foo.py", []) is False


class TestHelpOutput:
    """Tests for the -h/--help output."""

    def test_help_flag_exits_0(self) -> None:
        """--help causes SystemExit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_help_contains_argument_groups(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Help output includes named argument groups."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "allow-list options" in out
        assert "detection options" in out
        assert "output options" in out
        assert "configuration" in out
        assert "mode" in out

    def test_help_contains_examples(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Help output includes the examples epilog section."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "examples:" in out
        assert "check-unicode --fix" in out
        assert "--allow-printable" in out

    def test_help_contains_exit_codes(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Help output includes exit code documentation."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "exit codes:" in out
        assert "No findings" in out
        assert "Usage error" in out

    def test_help_contains_config_example(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Help output includes a TOML configuration example."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "allow-codepoints" in out
        assert ".check-unicode.toml" in out

    def test_parser_uses_raw_formatter(self) -> None:
        """Parser uses RawDescriptionHelpFormatter to preserve epilog formatting."""
        parser = _build_parser()
        assert parser.formatter_class is argparse.RawDescriptionHelpFormatter

    def test_help_describes_dangerous_characters(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Help mentions that dangerous characters require explicit allow-codepoint."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "dangerous" in out.lower()
        assert "--allow-codepoint" in out

    def test_help_mentions_list_flags(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Help text cross-references --list-scripts and --list-categories."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "--list-scripts" in out
        assert "--list-categories" in out

    def test_help_contains_strip_and_halt(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Help output documents --strip and --halt flags."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "--strip" in out
        assert "--halt" in out
        assert "dangerous" in out.lower()

    def test_help_contains_pipe_examples(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Help output includes pipe mode examples with new flags."""
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "check-unicode -" in out
        assert "--strip" in out


class TestListScripts:
    """Tests for the --list-scripts flag."""

    def test_list_scripts_exits_0(self) -> None:
        """--list-scripts exits with code 0."""
        assert main(["--list-scripts"]) == 0

    def test_list_scripts_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--list-scripts prints known script names."""
        main(["--list-scripts"])
        out = capsys.readouterr().out
        assert "Latin" in out
        assert "Cyrillic" in out
        assert "Greek" in out
        assert "Han" in out
        assert "Arabic" in out

    def test_list_scripts_contains_count(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--list-scripts shows a total count."""
        main(["--list-scripts"])
        out = capsys.readouterr().out
        assert "Total:" in out

    def test_list_scripts_mentions_case_insensitive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--list-scripts reminds users that names are case-insensitive."""
        main(["--list-scripts"])
        out = capsys.readouterr().out
        assert "case-insensitive" in out.lower()

    def test_list_scripts_does_not_require_files(self) -> None:
        """--list-scripts works without specifying any files."""
        assert main(["--list-scripts"]) == 0


class TestListCategories:
    """Tests for the --list-categories flag."""

    def test_list_categories_exits_0(self) -> None:
        """--list-categories exits with code 0."""
        assert main(["--list-categories"]) == 0

    def test_list_categories_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--list-categories prints all 30 Unicode general categories."""
        main(["--list-categories"])
        out = capsys.readouterr().out
        assert "Sc" in out
        assert "Lu" in out
        assert "Mn" in out
        assert "Zs" in out

    def test_list_categories_shows_major_groups(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--list-categories organizes output by major class."""
        main(["--list-categories"])
        out = capsys.readouterr().out
        assert "Letter:" in out
        assert "Symbol:" in out
        assert "Punctuation:" in out
        assert "Number:" in out
        assert "Separator:" in out

    def test_list_categories_contains_count(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--list-categories shows the total count of 30."""
        main(["--list-categories"])
        out = capsys.readouterr().out
        assert "Total: 30" in out

    def test_list_categories_contains_descriptions(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--list-categories includes human-readable descriptions."""
        main(["--list-categories"])
        out = capsys.readouterr().out
        assert "Symbol, currency" in out
        assert "Letter, uppercase" in out

    def test_list_categories_does_not_require_files(self) -> None:
        """--list-categories works without specifying any files."""
        assert main(["--list-categories"]) == 0


class TestOverrides:
    """Tests for [[tool.check-unicode.overrides]] per-file config."""

    def test_override_extends_global_allow(self, tmp_path: Path) -> None:
        """Override allows emoji in matched file but not in unmatched file."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md"]\nallow-categories = ["So"]\n',
            encoding="utf-8",
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("\u00a9 symbol\n", encoding="utf-8")  # So category
        py_file = tmp_path / "code.py"
        py_file.write_text("\u00a9 symbol\n", encoding="utf-8")

        # md file is allowed via override
        assert main(["--config", str(config), str(md_file)]) == 0
        # py file is not matched, still flagged
        assert main(["--config", str(config), str(py_file)]) == 1

    def test_multiple_overrides_multiple_patterns(self, tmp_path: Path) -> None:
        """Multiple overrides and multiple patterns per override work."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md", "*.txt"]\n'
            'allow-codepoints = ["U+00B0"]\n\n'
            '[[overrides]]\nfiles = ["*.rst"]\n'
            'allow-codepoints = ["U+00A9"]\n',
            encoding="utf-8",
        )
        md_file = tmp_path / "doc.md"
        md_file.write_text("72\u00b0F\n", encoding="utf-8")
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("72\u00b0F\n", encoding="utf-8")
        rst_file = tmp_path / "doc.rst"
        rst_file.write_text("\u00a9 2024\n", encoding="utf-8")

        assert main(["--config", str(config), str(md_file)]) == 0
        assert main(["--config", str(config), str(txt_file)]) == 0
        assert main(["--config", str(config), str(rst_file)]) == 0

    def test_per_file_severity_warning(self, tmp_path: Path) -> None:
        """Override with severity=warning doesn't affect exit code."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md"]\nseverity = "warning"\n',
            encoding="utf-8",
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("\u201chello\u201d\n", encoding="utf-8")
        py_file = tmp_path / "code.py"
        py_file.write_text("\u201chello\u201d\n", encoding="utf-8")

        # md has findings but severity=warning -> exit 0
        assert main(["--config", str(config), str(md_file)]) == 0
        # py has findings with default severity=error -> exit 1
        assert main(["--config", str(config), str(py_file)]) == 1

    def test_per_file_severity_mixed(self, tmp_path: Path) -> None:
        """Mixed severity: warning file + error file together exits 1."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md"]\nseverity = "warning"\n',
            encoding="utf-8",
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("\u201chello\u201d\n", encoding="utf-8")
        py_file = tmp_path / "code.py"
        py_file.write_text("\u201chello\u201d\n", encoding="utf-8")

        # Both files scanned: py is error -> exit 1
        assert main(["--config", str(config), str(md_file), str(py_file)]) == 1

    def test_per_file_severity_all_warnings(self, tmp_path: Path) -> None:
        """All files with severity=warning and findings -> exit 0."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*"]\nseverity = "warning"\n',
            encoding="utf-8",
        )
        f = tmp_path / "test.txt"
        f.write_text("\u201chello\u201d\n", encoding="utf-8")

        assert main(["--config", str(config), str(f)]) == 0

    def test_per_file_check_confusables_toggle(self, tmp_path: Path) -> None:
        """Override can disable check-confusables for specific files."""
        config = tmp_path / "config.toml"
        config.write_text(
            "check-confusables = true\n"
            '[[overrides]]\nfiles = ["*.md"]\ncheck-confusables = false\n',
            encoding="utf-8",
        )
        # File with a Cyrillic 'a' (U+0430) mixed into Latin text
        md_file = tmp_path / "doc.md"
        md_file.write_text("p\u0430ssword\n", encoding="utf-8")
        py_file = tmp_path / "code.py"
        py_file.write_text("p\u0430ssword\n", encoding="utf-8")

        # md has confusables disabled by override; still flagged for non-ASCII
        # but allow the Cyrillic script to isolate confusable check
        config.write_text(
            "check-confusables = true\n"
            'allow-scripts = ["Cyrillic"]\n'
            '[[overrides]]\nfiles = ["*.md"]\ncheck-confusables = false\n',
            encoding="utf-8",
        )
        # md: Cyrillic allowed, confusables OFF -> exit 0
        assert main(["--config", str(config), str(md_file)]) == 0
        # py: Cyrillic allowed, confusables ON -> exit 1 (confusable found)
        assert main(["--config", str(config), str(py_file)]) == 1

    def test_override_allow_printable(self, tmp_path: Path) -> None:
        """Override with allow-printable=true for specific files."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md"]\nallow-printable = true\n',
            encoding="utf-8",
        )
        md_file = tmp_path / "doc.md"
        md_file.write_text("caf\u00e9\n", encoding="utf-8")
        py_file = tmp_path / "code.py"
        py_file.write_text("caf\u00e9\n", encoding="utf-8")

        # md: printable allowed via override -> exit 0
        assert main(["--config", str(config), str(md_file)]) == 0
        # py: no override match -> exit 1
        assert main(["--config", str(config), str(py_file)]) == 1

    def test_override_missing_files_key(self) -> None:
        """Override without 'files' key raises ValueError."""
        with pytest.raises(ValueError, match="files"):
            _build_overrides({"overrides": [{"allow-printable": True}]})

    def test_override_no_allow_fields(self, tmp_path: Path) -> None:
        """Override with only 'files' key is valid but a no-op."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md"]\n',
            encoding="utf-8",
        )
        md_file = tmp_path / "doc.md"
        md_file.write_text("\u201chello\u201d\n", encoding="utf-8")

        # Still flagged: override is a no-op
        assert main(["--config", str(config), str(md_file)]) == 1

    def test_glob_basename_pattern(self) -> None:
        """Basename patterns like *.md match regardless of path."""
        ovr = Override(
            patterns=("*.md",),
            codepoints=frozenset(),
            ranges=(),
            categories=frozenset(),
            printable=None,
            scripts=frozenset(),
            severity=None,
            check_confusables=None,
        )
        assert _file_matches_override("docs/README.md", ovr) is True
        assert _file_matches_override("README.md", ovr) is True
        assert _file_matches_override("code.py", ovr) is False

    def test_glob_path_pattern(self) -> None:
        """Path patterns like docs/* match against full path."""
        ovr = Override(
            patterns=("docs/*",),
            codepoints=frozenset(),
            ranges=(),
            categories=frozenset(),
            printable=None,
            scripts=frozenset(),
            severity=None,
            check_confusables=None,
        )
        assert _file_matches_override("docs/guide.md", ovr) is True
        assert _file_matches_override("src/main.py", ovr) is False

    def test_glob_exact_name(self) -> None:
        """Exact file name patterns match."""
        ovr = Override(
            patterns=("README.md",),
            codepoints=frozenset(),
            ranges=(),
            categories=frozenset(),
            printable=None,
            scripts=frozenset(),
            severity=None,
            check_confusables=None,
        )
        assert _file_matches_override("README.md", ovr) is True
        assert _file_matches_override("docs/README.md", ovr) is True
        assert _file_matches_override("CHANGELOG.md", ovr) is False

    def test_resolve_allow_merges_additively(self) -> None:
        """Allow-list fields merge additively across overrides."""
        base = AllowConfig(
            codepoints=frozenset({0x00B0}),
            categories=frozenset({"Sc"}),
        )
        ovr = Override(
            patterns=("*.md",),
            codepoints=frozenset({0x00A9}),
            ranges=((0x2000, 0x200A),),
            categories=frozenset({"So"}),
            printable=None,
            scripts=frozenset({"Cyrillic"}),
            severity=None,
            check_confusables=None,
        )
        result = _resolve_allow_for_file("doc.md", base, (ovr,))
        assert 0x00B0 in result.codepoints
        assert 0x00A9 in result.codepoints
        assert "Sc" in result.categories
        assert "So" in result.categories
        assert (0x2000, 0x200A) in result.ranges
        assert "Cyrillic" in result.scripts
        assert result.printable is False  # not set in override

    def test_resolve_file_settings_last_wins(self) -> None:
        """For scalar settings, last matching override wins."""
        ovr1 = Override(
            patterns=("*",),
            codepoints=frozenset(),
            ranges=(),
            categories=frozenset(),
            printable=None,
            scripts=frozenset(),
            severity="warning",
            check_confusables=True,
        )
        ovr2 = Override(
            patterns=("*.py",),
            codepoints=frozenset(),
            ranges=(),
            categories=frozenset(),
            printable=None,
            scripts=frozenset(),
            severity="error",
            check_confusables=False,
        )
        sev, conf = _resolve_file_settings(
            "code.py",
            "error",
            global_confusables=False,
            overrides=(ovr1, ovr2),
        )
        assert sev == "error"  # ovr2 wins
        assert conf is False  # ovr2 wins

    def test_global_severity_warning_still_works(self, tmp_path: Path) -> None:
        """Global severity=warning without overrides still exits 0."""
        config = tmp_path / "config.toml"
        config.write_text(
            'severity = "warning"\n'
            '[[overrides]]\nfiles = ["*.md"]\n'
            'allow-codepoints = ["U+00B0"]\n',
            encoding="utf-8",
        )
        py_file = tmp_path / "code.py"
        py_file.write_text("\u201chello\u201d\n", encoding="utf-8")

        # Global severity is warning -> exit 0 even for unmatched files
        assert main(["--config", str(config), str(py_file)]) == 0


class TestSeverityValidation:
    """Tests for severity value validation."""

    def test_invalid_severity_in_config(self, tmp_path: Path) -> None:
        """Invalid severity in config file causes exit code 2."""
        config = tmp_path / "config.toml"
        config.write_text('severity = "warn"\n', encoding="utf-8")
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--config", str(config), str(f)])
        assert exc_info.value.code == 2

    def test_invalid_severity_in_override(self, tmp_path: Path) -> None:
        """Invalid severity in override causes exit code 2."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*"]\nseverity = "warn"\n',
            encoding="utf-8",
        )
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--config", str(config), str(f)])
        assert exc_info.value.code == 2


class TestConfigErrorHandling:
    """Tests for config file error handling."""

    def test_missing_config_file(self, tmp_path: Path) -> None:
        """Missing config file causes exit 2 with friendly message."""
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--config", "/nonexistent/config.toml", str(f)])
        assert exc_info.value.code == 2

    def test_invalid_toml(self, tmp_path: Path) -> None:
        """Invalid TOML causes exit 2 with friendly message."""
        config = tmp_path / "bad.toml"
        config.write_text("this is not valid toml [[[", encoding="utf-8")
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--config", str(config), str(f)])
        assert exc_info.value.code == 2


class TestUnknownConfigKeys:
    """Tests for unknown config key warnings."""

    def test_unknown_key_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Unknown config keys produce a warning on stderr."""
        config = tmp_path / "config.toml"
        config.write_text('alow-codepoints = ["U+00B0"]\n', encoding="utf-8")
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        main(["--config", str(config), str(f)])
        err = capsys.readouterr().err
        assert "unknown config key" in err
        assert "alow-codepoints" in err


class TestAllowValueValidation:
    """Tests for --allow-category and --allow-script validation."""

    def test_invalid_category(self, tmp_path: Path) -> None:
        """Invalid category name causes exit 2."""
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--allow-category", "Foo", str(f)])
        assert exc_info.value.code == 2

    def test_valid_major_category(self, tmp_path: Path) -> None:
        """Major category prefix (single letter) is accepted."""
        f = tmp_path / "test.txt"
        f.write_text("\u00a9\n", encoding="utf-8")  # copyright sign, category So
        # "S" should allow all Symbol categories
        assert main(["--allow-category", "S", str(f)]) == 0

    def test_invalid_script(self, tmp_path: Path) -> None:
        """Invalid script name causes exit 2."""
        f = tmp_path / "test.txt"
        f.write_text("hello\n", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            main(["--allow-script", "Klingon", str(f)])
        assert exc_info.value.code == 2


class TestPipeMode:
    """Tests for pipe mode: reading from stdin via `-`."""

    def test_dash_clean_input_passes_through(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Clean ASCII input is passed through to stdout unchanged, exit 0."""
        stdin_from("hello world\n")
        assert main(["-"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "hello world\n"

    def test_dash_dirty_input_passes_through_with_findings(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Non-ASCII input passes through to stdout, findings on stderr."""
        text = "He said \u201chello\u201d\n"
        stdin_from(text)
        assert main(["-"]) == 1
        captured = capsys.readouterr()
        assert captured.out == text
        assert "U+201C" in captured.err

    def test_dash_fix_mode_writes_fixed_to_stdout(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Fix mode replaces smart quotes and writes fixed text to stdout."""
        text = "He said \u201chello\u201d\n"
        stdin_from(text)
        assert main(["--fix", "-"]) == 1
        captured = capsys.readouterr()
        assert captured.out == 'He said "hello"\n'

    def test_dash_fix_mode_clean_input(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Fix mode with clean input passes through unchanged, exit 0."""
        stdin_from("clean\n")
        assert main(["--fix", "-"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "clean\n"

    def test_dash_fix_mode_dangerous_still_reported(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Fix mode preserves dangerous chars in output and stderr."""
        stdin_from("x\u202ey\n")
        result = main(["--fix", "-"])
        assert result == 1
        captured = capsys.readouterr()
        # Dangerous char preserved in output
        assert "\u202e" in captured.out
        assert "DANGEROUS" in captured.err

    def test_dash_with_allow_flags(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Allow flags work with pipe mode."""
        text = "72\u00b0F\n"
        stdin_from(text)
        assert main(["--allow-codepoint", "U+00B0", "-"]) == 0
        captured = capsys.readouterr()
        assert captured.out == text

    def test_dash_filename_in_findings(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Findings use '<stdin>' as the filename."""
        stdin_from("\u201chello\u201d\n")
        main(["-"])
        captured = capsys.readouterr()
        assert "<stdin>" in captured.err


class TestStripAndHaltFlags:
    """Tests for --strip and --halt flag parsing."""

    def test_strip_default_level(self) -> None:
        """--strip with no argument defaults to 'all'."""
        parser = _build_parser()
        args = parser.parse_args(["--strip", "test.txt"])
        assert args.strip == "all"

    def test_strip_explicit_dangerous(self) -> None:
        """--strip dangerous sets level to 'dangerous'."""
        parser = _build_parser()
        args = parser.parse_args(["--strip", "dangerous", "test.txt"])
        assert args.strip == "dangerous"

    def test_strip_explicit_all(self) -> None:
        """--strip all sets level to 'all'."""
        parser = _build_parser()
        args = parser.parse_args(["--strip", "all", "test.txt"])
        assert args.strip == "all"

    def test_halt_default_level(self) -> None:
        """--halt with no argument defaults to 'dangerous'."""
        parser = _build_parser()
        args = parser.parse_args(["--halt", "test.txt"])
        assert args.halt == "dangerous"

    def test_halt_explicit_all(self) -> None:
        """--halt all sets level to 'all'."""
        parser = _build_parser()
        args = parser.parse_args(["--halt", "all", "test.txt"])
        assert args.halt == "all"

    def test_halt_explicit_dangerous(self) -> None:
        """--halt dangerous sets level to 'dangerous'."""
        parser = _build_parser()
        args = parser.parse_args(["--halt", "dangerous", "test.txt"])
        assert args.halt == "dangerous"

    def test_strip_and_halt_together(self) -> None:
        """--strip and --halt can be combined."""
        parser = _build_parser()
        args = parser.parse_args(["--strip", "all", "--halt", "dangerous", "test.txt"])
        assert args.strip == "all"
        assert args.halt == "dangerous"

    def test_fix_strip_halt_together(self) -> None:
        """All three action flags can be combined."""
        parser = _build_parser()
        args = parser.parse_args(
            [
                "--fix",
                "--strip",
                "dangerous",
                "--halt",
                "dangerous",
                "test.txt",
            ]
        )
        assert args.fix is True
        assert args.strip == "dangerous"
        assert args.halt == "dangerous"

    def test_no_strip_defaults_none(self) -> None:
        """Without --strip, args.strip is None."""
        parser = _build_parser()
        args = parser.parse_args(["test.txt"])
        assert args.strip is None

    def test_no_halt_defaults_none(self) -> None:
        """Without --halt, args.halt is None."""
        parser = _build_parser()
        args = parser.parse_args(["test.txt"])
        assert args.halt is None


class TestStripFileMode:
    """Tests for --strip on files."""

    def test_strip_all_removes_non_ascii(self, accented_file: Path) -> None:
        """--strip all removes non-fixable non-ASCII from file."""
        assert main(["--strip", "all", str(accented_file)]) == 1
        assert accented_file.read_text(encoding="utf-8") == "caf\n"

    def test_strip_dangerous_only(self, dangerous_file: Path) -> None:
        """--strip dangerous removes only dangerous chars."""
        assert main(["--strip", "dangerous", str(dangerous_file)]) == 1
        assert dangerous_file.read_text(encoding="utf-8") == "xy\n"

    def test_strip_dangerous_keeps_accented(self, accented_file: Path) -> None:
        """--strip dangerous does not remove accented characters."""
        assert main(["--strip", "dangerous", str(accented_file)]) == 1
        content = accented_file.read_text(encoding="utf-8")
        assert "\u00e9" in content

    def test_fix_strip_combined(self, mixed_file: Path) -> None:
        """--fix --strip all fixes fixable, strips the rest."""
        assert main(["--fix", "--strip", "all", str(mixed_file)]) == 1
        content = mixed_file.read_text(encoding="utf-8")
        assert content == 'caf said "hi" xy\n'

    def test_fix_strip_dangerous(self, mixed_file: Path) -> None:
        """--fix --strip dangerous fixes fixable, strips dangerous."""
        assert main(["--fix", "--strip", "dangerous", str(mixed_file)]) == 1
        content = mixed_file.read_text(encoding="utf-8")
        assert content == 'caf\u00e9 said "hi" xy\n'

    def test_strip_clean_file_exits_0(self, tmp_path: Path) -> None:
        """--strip on a clean file exits 0 with no changes."""
        f = tmp_path / "clean.txt"
        f.write_text("hello world\n", encoding="utf-8")
        assert main(["--strip", str(f)]) == 0

    def test_strip_respects_allow_codepoint(self, accented_file: Path) -> None:
        """--strip all respects --allow-codepoint."""
        assert (
            main(
                [
                    "--strip",
                    "all",
                    "--allow-codepoint",
                    "U+00E9",
                    str(accented_file),
                ]
            )
            == 0
        )
        content = accented_file.read_text(encoding="utf-8")
        assert content == "caf\u00e9\n"


class TestHaltFileMode:
    """Tests for --halt on files."""

    def test_halt_dangerous_stops_on_bidi(self, dangerous_file: Path) -> None:
        """--halt dangerous exits 1 on dangerous character."""
        assert main(["--halt", str(dangerous_file)]) == 1

    def test_halt_dangerous_ignores_accented(self, accented_file: Path) -> None:
        """--halt dangerous does not trigger halt on accented chars."""
        # Still exits 1 because findings exist, but no halt behavior
        assert main(["--halt", str(accented_file)]) == 1

    def test_halt_all_stops_on_any_non_ascii(self, accented_file: Path) -> None:
        """--halt all exits 1 on any non-ASCII."""
        assert main(["--halt", "all", str(accented_file)]) == 1

    def test_halt_does_not_modify_file(self, dangerous_file: Path) -> None:
        """--halt with --fix does not write the halting file."""
        original = dangerous_file.read_text(encoding="utf-8")
        main(["--fix", "--halt", str(dangerous_file)])
        assert dangerous_file.read_text(encoding="utf-8") == original

    def test_halt_skips_remaining_files(
        self, dangerous_file: Path, tmp_path: Path
    ) -> None:
        """--halt stops processing remaining files after trigger."""
        second = tmp_path / "second.txt"
        second.write_text("\u201chello\u201d\n", encoding="utf-8")
        original_second = second.read_text(encoding="utf-8")
        main(["--fix", "--halt", str(dangerous_file), str(second)])
        assert second.read_text(encoding="utf-8") == original_second

    def test_halt_respects_allow_codepoint(self, dangerous_file: Path) -> None:
        """--halt does not trigger on allowed codepoints."""
        result = main(
            [
                "--halt",
                "dangerous",
                "--allow-codepoint",
                "U+202E,U+202C",
                str(dangerous_file),
            ]
        )
        assert result == 0

    def test_halt_reports_finding(
        self,
        dangerous_file: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--halt reports the triggering finding on stderr."""
        main(["--halt", str(dangerous_file)])
        err = capsys.readouterr().err
        assert "DANGEROUS" in err


class TestPipeModeStreaming:
    """Tests for streaming pipe mode with --strip and --halt."""

    def test_pipe_strip_all(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--strip all removes all non-ASCII from pipe output."""
        stdin_from("caf\u00e9\n")
        assert main(["--strip", "all", "-"]) == 1
        assert capsys.readouterr().out == "caf\n"

    def test_pipe_strip_dangerous(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--strip dangerous removes only dangerous chars."""
        stdin_from("caf\u00e9 x\u202ey\n")
        assert main(["--strip", "dangerous", "-"]) == 1
        captured = capsys.readouterr()
        assert "\u00e9" in captured.out
        assert "\u202e" not in captured.out

    def test_pipe_fix_strip_combined(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--fix --strip all: fix fixable, strip the rest."""
        stdin_from("caf\u00e9 said \u201chi\u201d\n")
        assert main(["--fix", "--strip", "all", "-"]) == 1
        assert capsys.readouterr().out == 'caf said "hi"\n'

    def test_pipe_halt_dangerous(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--halt dangerous stops on dangerous char, no stdout for that line."""
        stdin_from("line1\nx\u202ey\nline3\n")
        assert main(["--halt", "-"]) == 1
        captured = capsys.readouterr()
        assert "line1\n" in captured.out
        assert "\u202e" not in captured.out
        assert "line3" not in captured.out
        assert "DANGEROUS" in captured.err

    def test_pipe_halt_all(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--halt all stops on any non-ASCII."""
        stdin_from("clean\ncaf\u00e9\nmore\n")
        assert main(["--halt", "all", "-"]) == 1
        captured = capsys.readouterr()
        assert "clean\n" in captured.out
        assert "\u00e9" not in captured.out

    def test_pipe_fix_halt_dangerous(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--fix --halt: fix fixable, halt on dangerous."""
        stdin_from("\u201chi\u201d\nx\u202ey\n")
        assert main(["--fix", "--halt", "-"]) == 1
        captured = capsys.readouterr()
        assert '"hi"' in captured.out
        assert "\u202e" not in captured.out

    def test_pipe_context_display(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pipe mode shows context lines with caret markers."""
        stdin_from("x\u202ey\n")
        main(["-"])
        err = capsys.readouterr().err
        assert "<U+202E>" in err
        assert "!" in err

    def test_pipe_summary_after_stream(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pipe mode prints summary line after stdin exhausted."""
        stdin_from("\u201chello\u201d\n")
        main(["-"])
        err = capsys.readouterr().err
        assert "Found" in err
        assert "non-ASCII" in err

    def test_pipe_strip_respects_allow(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--strip all with --allow-codepoint preserves allowed."""
        stdin_from("caf\u00e9\n")
        assert main(["--strip", "all", "--allow-codepoint", "U+00E9", "-"]) == 0
        assert capsys.readouterr().out == "caf\u00e9\n"

    def test_pipe_halt_respects_allow(
        self,
        stdin_from: Callable[[str], None],
    ) -> None:
        """--halt dangerous with allowed bidi char does not halt."""
        stdin_from("x\u202ey\n")
        result = main(
            [
                "--halt",
                "dangerous",
                "--allow-codepoint",
                "U+202E,U+202C",
                "-",
            ]
        )
        assert result == 0


class TestPipeModeEdgeCases:
    """Edge case tests for pipe mode."""

    def test_pipe_empty_stdin(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Empty input should exit 0 and produce no stdout/stderr."""
        stdin_from("")
        assert main(["-"]) == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_pipe_no_trailing_newline(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Input without trailing newline passes through without adding one."""
        stdin_from("hello")
        assert main(["-"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "hello"

    def test_pipe_halt_on_first_line(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--halt with dangerous char on line 1 should NOT write line 1 to stdout."""
        stdin_from("x\u202ey\nline2\n")
        assert main(["--halt", "-"]) == 1
        captured = capsys.readouterr()
        assert "\u202e" not in captured.out
        assert "line2" not in captured.out

    def test_pipe_multiline_summary_counts(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Multi-line input with findings on multiple lines; verify summary count."""
        stdin_from("\u201ca\u201d\n\u201cb\u201d\n")
        main(["-"])
        err = capsys.readouterr().err
        assert "Found" in err
        # 4 smart quote chars total (2 per line)
        assert "4" in err

    def test_pipe_preserves_blank_lines(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Blank lines in input are preserved in output."""
        stdin_from("a\n\nb\n")
        assert main(["-"]) == 0
        assert capsys.readouterr().out == "a\n\nb\n"

    def test_pipe_strip_equals_syntax(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--strip=all works (equals syntax doesn't break preprocessing)."""
        stdin_from("caf\u00e9\n")
        assert main(["--strip=all", "-"]) == 1
        assert capsys.readouterr().out == "caf\n"

    def test_pipe_halt_clean_input_exits_0(
        self,
        stdin_from: Callable[[str], None],
    ) -> None:
        """--halt with clean input exits 0."""
        stdin_from("hello world\n")
        assert main(["--halt", "-"]) == 0


class TestPreprocessArgv:
    """Tests for _preprocess_argv optional-level flag rewriting."""

    @pytest.mark.parametrize(
        ("argv", "expected"),
        [
            (["--strip", "test.txt"], ["--strip=all", "test.txt"]),
            (["--strip", "dangerous", "test.txt"], ["--strip=dangerous", "test.txt"]),
            (["--strip", "all", "test.txt"], ["--strip=all", "test.txt"]),
            (["--halt", "test.txt"], ["--halt=dangerous", "test.txt"]),
            (["--halt", "all", "test.txt"], ["--halt=all", "test.txt"]),
            (["--halt", "dangerous", "test.txt"], ["--halt=dangerous", "test.txt"]),
            (
                ["--strip", "--halt", "test.txt"],
                ["--strip=all", "--halt=dangerous", "test.txt"],
            ),
            (
                ["--fix", "--strip", "test.txt"],
                ["--fix", "--strip=all", "test.txt"],
            ),
            (
                ["--strip", "all", "--halt", "dangerous", "test.txt"],
                ["--strip=all", "--halt=dangerous", "test.txt"],
            ),
            (["test.txt"], ["test.txt"]),
            ([], []),
            (["--fix", "test.txt"], ["--fix", "test.txt"]),
            (["-"], ["-"]),
            (["--strip", "-"], ["--strip=all", "-"]),
        ],
        ids=[
            "strip-no-level-defaults-all",
            "strip-dangerous",
            "strip-all-explicit",
            "halt-no-level-defaults-dangerous",
            "halt-all",
            "halt-dangerous-explicit",
            "strip-then-halt-no-levels",
            "fix-then-strip",
            "strip-all-halt-dangerous",
            "no-flags",
            "empty-args",
            "unrelated-flag",
            "dash-alone",
            "strip-with-dash",
        ],
    )
    def test_preprocess_argv(self, argv: list[str], expected: list[str]) -> None:
        """_preprocess_argv correctly rewrites optional-level flags."""
        assert _preprocess_argv(argv) == expected


class TestFlagInteractionsWithConfig:
    """Tests for action flag interactions with config/overrides."""

    def test_strip_with_config_allow_codepoints(self, tmp_path: Path) -> None:
        """Config allow-codepoints are respected by --strip."""
        config = tmp_path / "config.toml"
        config.write_text('allow-codepoints = ["U+00E9"]\n', encoding="utf-8")
        f = tmp_path / "test.txt"
        f.write_text("caf\u00e9 na\u00efve\n", encoding="utf-8")
        main(["--config", str(config), "--strip", "all", str(f)])
        content = f.read_text(encoding="utf-8")
        assert "\u00e9" in content
        assert "\u00ef" not in content

    def test_strip_with_override_allow(self, tmp_path: Path) -> None:
        """Per-file override allow-lists are respected by --strip."""
        config = tmp_path / "config.toml"
        config.write_text(
            '[[overrides]]\nfiles = ["*.md"]\nallow-printable = true\n',
            encoding="utf-8",
        )
        md = tmp_path / "doc.md"
        md.write_text("caf\u00e9\n", encoding="utf-8")
        py = tmp_path / "code.py"
        py.write_text("caf\u00e9\n", encoding="utf-8")
        main(["--config", str(config), "--strip", "all", str(md), str(py)])
        assert "\u00e9" in md.read_text(encoding="utf-8")
        assert "\u00e9" not in py.read_text(encoding="utf-8")

    def test_halt_with_severity_warning(self, dangerous_file: Path) -> None:
        """--halt still exits 1 regardless of --severity warning."""
        result = main(["--severity", "warning", "--halt", str(dangerous_file)])
        assert result == 1

    def test_strip_with_severity_warning(self, accented_file: Path) -> None:
        """--strip modifies file; exit 1 even with --severity warning."""
        result = main(["--severity", "warning", "--strip", "all", str(accented_file)])
        assert result == 1
        assert "\u00e9" not in accented_file.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        ("flags", "input_text", "expected_out"),
        [
            (["--fix"], "\u201chi\u201d\n", '"hi"\n'),
            (["--strip", "all"], "caf\u00e9\n", "caf\n"),
            (["--fix", "--strip", "all"], "caf\u00e9 \u201chi\u201d\n", 'caf "hi"\n'),
            (
                ["--fix", "--strip", "dangerous"],
                "\u201chi\u201d x\u202ey\n",
                '"hi" xy\n',
            ),
            (
                ["--strip", "dangerous"],
                "caf\u00e9 x\u202ey\n",
                "caf\u00e9 xy\n",
            ),
        ],
        ids=[
            "fix-only",
            "strip-all",
            "fix-strip-all",
            "fix-strip-dangerous",
            "strip-dangerous-only",
        ],
    )
    def test_pipe_flag_combinations(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        flags: list[str],
        input_text: str,
        expected_out: str,
    ) -> None:
        """Parametrized test of flag combinations in pipe mode."""
        stdin_from(input_text)
        main([*flags, "-"])
        assert capsys.readouterr().out == expected_out

    def test_quiet_flag_with_strip(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--quiet suppresses per-finding output in pipe mode."""
        stdin_from("caf\u00e9\n")
        main(["--quiet", "--strip", "all", "-"])
        err = capsys.readouterr().err
        assert "Found" in err
        assert "U+00E9" not in err.split("Found")[0]

    def test_no_color_with_halt(
        self,
        stdin_from: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--no-color works with --halt."""
        stdin_from("x\u202ey\n")
        main(["--no-color", "--halt", "-"])
        err = capsys.readouterr().err
        assert "\033[" not in err
        assert "DANGEROUS" in err
