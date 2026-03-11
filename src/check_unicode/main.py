"""CLI entrypoint, argparse, config discovery, and orchestration."""

from __future__ import annotations

import argparse
import fnmatch
import sys
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from check_unicode import __version__
from check_unicode.checker import AllowConfig, Finding, check_confusables, check_file
from check_unicode.fixer import fix_file
from check_unicode.output import print_findings
from check_unicode.scripts import KNOWN_SCRIPTS

_EXPECTED_RANGE_PARTS = 2

# Unicode general categories: abbreviation -> (full name, description).
# Covers all 30 categories from the Unicode standard.
UNICODE_CATEGORIES: dict[str, tuple[str, str]] = {
    "Lu": ("Letter, uppercase", "e.g. A, B, \u00c9"),
    "Ll": ("Letter, lowercase", "e.g. a, b, \u00e9"),
    "Lt": ("Letter, titlecase", "e.g. \u01c5, \u01c8"),
    "Lm": ("Letter, modifier", "e.g. \u02b0, \u02c6"),
    "Lo": ("Letter, other", "e.g. \u00aa, \u0e01, CJK ideographs"),
    "Mn": ("Mark, nonspacing", "e.g. \u0300 (combining grave accent)"),
    "Mc": ("Mark, spacing combining", "e.g. \u0903 (Devanagari visarga)"),
    "Me": ("Mark, enclosing", "e.g. \u20dd (combining enclosing circle)"),
    "Nd": ("Number, decimal digit", "e.g. 0-9, \u0660-\u0669"),
    "Nl": ("Number, letter", "e.g. \u2160 (Roman numeral one)"),
    "No": ("Number, other", "e.g. \u00b2, \u00b3, \u2153"),
    "Pc": ("Punctuation, connector", "e.g. _"),
    "Pd": ("Punctuation, dash", "e.g. -, \u2013, \u2014"),
    "Ps": ("Punctuation, open", "e.g. (, [, {"),
    "Pe": ("Punctuation, close", "e.g. ), ], }"),
    "Pi": ("Punctuation, initial quote", "e.g. \u00ab, \u2018, \u201c"),
    "Pf": ("Punctuation, final quote", "e.g. \u00bb, \u2019, \u201d"),
    "Po": ("Punctuation, other", "e.g. !, ?, @, #"),
    "Sm": ("Symbol, math", "e.g. +, =, <, >, \u00b1"),
    "Sc": ("Symbol, currency", "e.g. $, \u00a3, \u00a5, \u20ac"),
    "Sk": ("Symbol, modifier", "e.g. ^, `, \u00a8, \u02dc"),
    "So": ("Symbol, other", "e.g. \u00a9, \u00ae, \u2122"),
    "Zs": ("Separator, space", "e.g. U+0020, U+00A0, U+2003"),
    "Zl": ("Separator, line", "U+2028"),
    "Zp": ("Separator, paragraph", "U+2029"),
    "Cc": ("Other, control", "e.g. U+0000-U+001F, U+007F-U+009F"),
    "Cf": ("Other, format", "e.g. U+200B (zero-width space), U+FEFF (BOM)"),
    "Cs": ("Other, surrogate", "U+D800-U+DFFF (not valid in UTF-8)"),
    "Co": ("Other, private use", "U+E000-U+F8FF"),
    "Cn": ("Other, not assigned", "reserved codepoints"),
}


@dataclass(frozen=True, slots=True)
class Override:
    """Per-file override from [[tool.check-unicode.overrides]]."""

    patterns: tuple[str, ...]
    codepoints: frozenset[int]
    ranges: tuple[tuple[int, int], ...]
    categories: frozenset[str]
    printable: bool | None  # None = inherit global
    scripts: frozenset[str]
    severity: str | None  # None = inherit global
    check_confusables: bool | None  # None = inherit global


def _parse_codepoint(s: str) -> int:
    """Parse 'U+XXXX' or '0xXXXX' into an integer codepoint."""
    s = s.strip()
    for prefix in ("U+", "u+", "0x", "0X"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    return int(s, 16)


def _parse_range(s: str) -> tuple[int, int]:
    """Parse 'U+XXXX-U+YYYY' into a (lo, hi) tuple."""
    parts = s.split("-", 1)
    if len(parts) != _EXPECTED_RANGE_PARTS:
        msg = f"Invalid range: {s!r} (expected U+XXXX-U+YYYY)"
        raise argparse.ArgumentTypeError(msg)
    return _parse_codepoint(parts[0]), _parse_codepoint(parts[1])


def _discover_config() -> dict[str, Any] | None:
    """Auto-discover .check-unicode.toml or [tool.check-unicode] in pyproject.toml."""
    cwd = Path.cwd()

    # Check for dedicated config file
    config_path = cwd / ".check-unicode.toml"
    if config_path.is_file():
        with config_path.open("rb") as f:
            data = tomllib.load(f)
        result: dict[str, Any] = data.get("tool", {}).get("check-unicode", data)
        return result

    # Check pyproject.toml
    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        tool_config: dict[str, Any] | None = data.get("tool", {}).get("check-unicode")
        if tool_config:
            return tool_config

    return None


def _load_config(path: str | None) -> dict[str, Any]:
    """Load config from explicit path or auto-discover."""
    if path:
        config_path = Path(path)
        with config_path.open("rb") as f:
            data = tomllib.load(f)
        result: dict[str, Any] = data.get("tool", {}).get("check-unicode", data)
        return result
    return _discover_config() or {}


def _allow_from_config(
    config: dict[str, Any],
) -> tuple[set[int], list[tuple[int, int]], set[str], bool, set[str]]:
    """Extract allow-lists from a parsed config dictionary."""
    codepoints: set[int] = {
        _parse_codepoint(cp_str) for cp_str in config.get("allow-codepoints", [])
    }
    ranges: list[tuple[int, int]] = [
        _parse_range(r_str) for r_str in config.get("allow-ranges", [])
    ]
    categories: set[str] = set(config.get("allow-categories", []))
    printable: bool = config.get("allow-printable", False)
    scripts: set[str] = {s.title() for s in config.get("allow-scripts", [])}
    return codepoints, ranges, categories, printable, scripts


_VALID_SEVERITIES: frozenset[str] = frozenset({"error", "warning"})

_KNOWN_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "allow-codepoints",
        "allow-ranges",
        "allow-categories",
        "allow-printable",
        "allow-scripts",
        "check-confusables",
        "severity",
        "exclude-patterns",
        "overrides",
    }
)


def _warn_unknown_keys(config: dict[str, Any]) -> None:
    """Print warnings for unrecognised top-level config keys."""
    unknown = set(config) - _KNOWN_CONFIG_KEYS
    for key in sorted(unknown):
        sys.stderr.write(f"warning: unknown config key {key!r}\n")


_VALID_CATEGORIES: frozenset[str] = frozenset(UNICODE_CATEGORIES) | frozenset(
    k[0] for k in UNICODE_CATEGORIES
)


def _validate_allow_values(
    categories: set[str],
    scripts: set[str],
) -> None:
    """Raise ``argparse.ArgumentTypeError`` for invalid categories or scripts."""
    for cat in categories:
        if cat not in _VALID_CATEGORIES:
            msg = (
                f"Unknown Unicode category {cat!r}; "
                "use --list-categories to see valid values"
            )
            raise argparse.ArgumentTypeError(msg)

    for script in scripts:
        if script not in KNOWN_SCRIPTS:
            msg = f"Unknown script {script!r}; use --list-scripts to see valid names"
            raise argparse.ArgumentTypeError(msg)


def _build_allow_config(
    args: argparse.Namespace,
    config: dict[str, Any],
) -> AllowConfig:
    """Merge CLI args and config file into an AllowConfig."""
    # Config file values
    codepoints, ranges, categories, printable, scripts = _allow_from_config(config)

    # CLI args (extend, don't replace)
    if args.allow_codepoint:
        for item in args.allow_codepoint:
            for cp_str in item.split(","):
                codepoints.add(_parse_codepoint(cp_str))
    if args.allow_range:
        ranges.extend(_parse_range(r_str) for r_str in args.allow_range)
    if args.allow_category:
        categories.update(args.allow_category)
    if args.allow_printable:
        printable = True
    if args.allow_script:
        scripts.update(s.title() for s in args.allow_script)

    _validate_allow_values(categories, scripts)

    return AllowConfig(
        codepoints=frozenset(codepoints),
        ranges=tuple(ranges),
        categories=frozenset(categories),
        printable=printable,
        scripts=frozenset(scripts),
    )


def _print_scripts() -> None:
    """Print all known Unicode script names accepted by --allow-script."""
    write = sys.stdout.write
    write("Unicode scripts accepted by --allow-script:\n\n")
    for name in sorted(KNOWN_SCRIPTS):
        write(f"  {name}\n")
    write(f"\nTotal: {len(KNOWN_SCRIPTS)} scripts\n")
    write(
        "Script names are case-insensitive"
        " (e.g. 'cyrillic' and 'Cyrillic' both work).\n"
    )


def _print_categories() -> None:
    """Print all Unicode general categories accepted by --allow-category."""
    write = sys.stdout.write
    write("Unicode general categories accepted by --allow-category:\n\n")
    # Group by major class (first letter)
    major_classes = {
        "L": "Letter",
        "M": "Mark",
        "N": "Number",
        "P": "Punctuation",
        "S": "Symbol",
        "Z": "Separator",
        "C": "Other",
    }
    current_major = ""
    for abbrev in sorted(UNICODE_CATEGORIES):
        major = abbrev[0]
        if major != current_major:
            current_major = major
            write(f"  {major_classes.get(major, major)}:\n")
        full_name, examples = UNICODE_CATEGORIES[abbrev]
        write(f"    {abbrev}  {full_name:<30s} {examples}\n")
    write(f"\nTotal: {len(UNICODE_CATEGORIES)} categories\n")


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    epilog = textwrap.dedent("""\
        examples:
          check-unicode src/**/*.py          Check all Python files
          check-unicode --fix *.txt          Auto-fix smart quotes, dashes, etc.
          check-unicode --allow-printable .  Allow printable non-ASCII
          check-unicode --check-confusables --allow-script Cyrillic src/
                                             Detect confusables
          check-unicode --allow-codepoint U+00B0,U+00A9 data.txt
                                             Allow specific codepoints
          check-unicode --allow-range U+0400-U+04FF src/i18n/
                                             Allow Cyrillic block
          check-unicode --severity warning --no-color src/
                                             Warn without failing CI
          check-unicode --list-scripts       Show all valid script names
          check-unicode --list-categories    Show all valid category abbreviations

        configuration:
          Settings can be defined in .check-unicode.toml or pyproject.toml under
          [tool.check-unicode]. CLI flags extend (never replace) config-file values.

          Example .check-unicode.toml:
            allow-codepoints = ["U+00B0", "U+2192"]
            allow-ranges     = ["U+00A0-U+00FF"]
            allow-categories = ["Sc"]
            allow-printable  = true
            allow-scripts    = ["Latin", "Cyrillic"]
            check-confusables = true
            severity         = "error"
            exclude-patterns = ["*.min.js", "vendor/*"]

        exit codes:
          0   No findings (or --severity=warning)
          1   Findings detected (or files were fixed in --fix mode)
          2   Usage error (bad arguments)
    """)
    description = textwrap.dedent("""\
        Detect and fix non-ASCII Unicode characters in text files.

        Catches smart quotes, em dashes, fancy spaces, dangerous invisible
        characters (Trojan Source bidi attacks, zero-width chars), and other
        copy-paste artifacts.  Use --fix to auto-replace known offenders with
        ASCII equivalents.  Dangerous characters are always flagged and never
        auto-fixed.""")
    parser = argparse.ArgumentParser(
        prog="check-unicode",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="files to check (one or more paths required)",
    )

    # Allow-list options
    allow_group = parser.add_argument_group(
        "allow-list options",
        "Suppress findings for specific characters, ranges, categories, or scripts. "
        "These flags extend (never replace) any values set in the config file. "
        "Dangerous invisible characters are always flagged unless explicitly "
        "allowed by --allow-codepoint.",
    )
    allow_group.add_argument(
        "--allow-range",
        action="append",
        metavar="RANGE",
        help=(
            "allow a Unicode range, e.g. U+00A0-U+00FF. "
            "may be repeated for multiple ranges"
        ),
    )
    allow_group.add_argument(
        "--allow-codepoint",
        action="append",
        metavar="CP",
        help=(
            "allow specific codepoints, e.g. U+00B0. "
            "comma-separated and/or repeated. "
            "this is the only flag that can suppress dangerous characters"
        ),
    )
    allow_group.add_argument(
        "--allow-category",
        action="append",
        metavar="CAT",
        help=(
            "allow a Unicode general category, e.g. Sc (Symbol, currency). "
            "may be repeated for multiple categories. "
            "use --list-categories to see all valid values"
        ),
    )
    allow_group.add_argument(
        "--allow-printable",
        action="store_true",
        help=(
            "allow all printable non-ASCII characters; "
            "only invisible/control characters will be flagged"
        ),
    )
    allow_group.add_argument(
        "--allow-script",
        action="append",
        metavar="SCRIPT",
        help=(
            "allow all characters from a Unicode script, e.g. Latin, Cyrillic, "
            "Greek. may be repeated for multiple scripts. "
            "use --list-scripts to see all valid names"
        ),
    )
    allow_group.add_argument(
        "--list-categories",
        action="store_true",
        help="list all Unicode general categories and exit",
    )
    allow_group.add_argument(
        "--list-scripts",
        action="store_true",
        help="list all known Unicode script names and exit",
    )

    # Detection options
    detect_group = parser.add_argument_group(
        "detection options",
        "Control what is detected beyond the default non-ASCII scan.",
    )
    detect_group.add_argument(
        "--check-confusables",
        action="store_true",
        help=(
            "detect mixed-script homoglyph/confusable characters "
            "(e.g. Cyrillic 'a' in a Latin identifier). "
            "not suppressed by --allow-script"
        ),
    )

    # Output options
    output_group = parser.add_argument_group(
        "output options",
        "Control output format, severity, and color.",
    )
    output_group.add_argument(
        "--severity",
        choices=["error", "warning"],
        default=None,
        help=(
            "set exit-code behavior: 'error' exits 1 on findings, "
            "'warning' prints findings but exits 0. default: error"
        ),
    )
    output_group.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI color output (also respects NO_COLOR env var)",
    )
    output_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="print summary line only, suppress per-finding details",
    )

    # Configuration
    config_group = parser.add_argument_group(
        "configuration",
        "Specify a config file or rely on auto-discovery.",
    )
    config_group.add_argument(
        "--config",
        metavar="FILE",
        help=(
            "path to a TOML config file. "
            "if omitted, auto-discovers .check-unicode.toml "
            "or [tool.check-unicode] in pyproject.toml"
        ),
    )
    config_group.add_argument(
        "--exclude-pattern",
        action="append",
        metavar="PATTERN",
        help=(
            "exclude files matching a glob pattern, e.g. '*.min.js'. "
            "may be repeated; extends config-file exclude-patterns"
        ),
    )

    # Mode
    mode_group = parser.add_argument_group(
        "mode",
    )
    mode_group.add_argument(
        "--fix",
        action="store_true",
        help=(
            "replace known offenders (smart quotes, dashes, fancy spaces, "
            "ellipsis) with ASCII equivalents. exits 1 if any file was "
            "changed. dangerous characters are never auto-fixed"
        ),
    )
    mode_group.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _is_excluded(filepath: str, patterns: list[str]) -> bool:
    """Check whether a filepath matches any exclusion pattern.

    Matches against both the full path and the basename, so
    patterns like ``*.min.js`` and ``vendor/*.js`` both work.
    """
    name = Path(filepath).name
    return any(
        fnmatch.fnmatch(filepath, pat) or fnmatch.fnmatch(name, pat) for pat in patterns
    )


def _build_exclude_patterns(
    args: argparse.Namespace,
    config: dict[str, Any],
) -> list[str]:
    """Merge exclude patterns from CLI args and config file."""
    patterns: list[str] = list(config.get("exclude-patterns", []))
    if args.exclude_pattern:
        patterns.extend(args.exclude_pattern)
    return patterns


def _build_overrides(config: dict[str, Any]) -> tuple[Override, ...]:
    """Parse [[overrides]] entries from the config into Override objects."""
    raw = config.get("overrides", [])
    overrides: list[Override] = []
    for entry in raw:
        if "files" not in entry:
            msg = "Each [[overrides]] entry must have a 'files' key"
            raise ValueError(msg)
        patterns = tuple(entry["files"])
        codepoints, ranges, categories, printable_val, scripts = _allow_from_config(
            entry
        )
        # For override, printable is None when not set (inherit global)
        printable: bool | None = (
            True if printable_val else None if "allow-printable" not in entry else False
        )
        severity: str | None = entry.get("severity")
        if severity is not None and severity not in {"error", "warning"}:
            msg = (
                f"Invalid override severity {severity!r}; must be 'error' or 'warning'"
            )
            raise ValueError(msg)
        check_confusables: bool | None = entry.get("check-confusables")
        overrides.append(
            Override(
                patterns=patterns,
                codepoints=frozenset(codepoints),
                ranges=tuple(ranges),
                categories=frozenset(categories),
                printable=printable,
                scripts=frozenset(scripts),
                severity=severity,
                check_confusables=check_confusables,
            )
        )
    return tuple(overrides)


def _file_matches_override(filepath: str, override: Override) -> bool:
    """Check whether a filepath matches any pattern in an override."""
    name = Path(filepath).name
    return any(
        fnmatch.fnmatch(filepath, pat) or fnmatch.fnmatch(name, pat)
        for pat in override.patterns
    )


def _resolve_allow_for_file(
    filepath: str,
    base_allow: AllowConfig,
    overrides: tuple[Override, ...],
) -> AllowConfig:
    """Merge matching overrides onto the base AllowConfig for a file."""
    codepoints = set(base_allow.codepoints)
    ranges = list(base_allow.ranges)
    categories = set(base_allow.categories)
    printable = base_allow.printable
    scripts = set(base_allow.scripts)

    for ovr in overrides:
        if not _file_matches_override(filepath, ovr):
            continue
        codepoints |= ovr.codepoints
        ranges.extend(ovr.ranges)
        categories |= ovr.categories
        if ovr.printable is not None:
            printable = ovr.printable
        scripts |= ovr.scripts

    return AllowConfig(
        codepoints=frozenset(codepoints),
        ranges=tuple(ranges),
        categories=frozenset(categories),
        printable=printable,
        scripts=frozenset(scripts),
    )


def _resolve_file_settings(
    filepath: str,
    global_severity: str,
    *,
    global_confusables: bool,
    overrides: tuple[Override, ...],
) -> tuple[str, bool]:
    """Return (severity, do_confusables) for a file after applying overrides."""
    severity = global_severity
    do_confusables = global_confusables
    for ovr in overrides:
        if not _file_matches_override(filepath, ovr):
            continue
        if ovr.severity is not None:
            severity = ovr.severity
        if ovr.check_confusables is not None:
            do_confusables = ovr.check_confusables
    return severity, do_confusables


def _scan_files(
    files: list[str],
    allow: AllowConfig,
    overrides: tuple[Override, ...],
    *,
    do_confusables: bool,
    severity: str,
) -> tuple[list[Finding], bool]:
    """Scan files for non-ASCII and (optionally) confusable characters.

    Returns (findings, has_errors) where has_errors is True if any finding
    came from a file whose effective severity is "error".
    """
    findings: list[Finding] = []
    has_errors = False
    for filepath in files:
        file_allow = _resolve_allow_for_file(filepath, allow, overrides)
        file_severity, file_confusables = _resolve_file_settings(
            filepath,
            severity,
            global_confusables=do_confusables,
            overrides=overrides,
        )
        try:
            file_text = Path(filepath).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            file_text = None
        file_findings = check_file(filepath, file_allow, text=file_text)
        if file_confusables:
            file_findings.extend(check_confusables(filepath, text=file_text))
        if file_findings and file_severity == "error":
            has_errors = True
        findings.extend(file_findings)
    return findings, has_errors


def _load_and_validate_config(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], str, AllowConfig, bool, tuple[Override, ...]]:
    """Load, validate and merge all configuration.

    Returns (config, severity, allow, do_confusables, overrides).
    Calls ``parser.error`` on invalid input.
    """
    try:
        config = _load_config(args.config)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        parser.error(f"Cannot load config: {exc}")

    _warn_unknown_keys(config)

    severity = args.severity or config.get("severity", "error")
    if severity not in _VALID_SEVERITIES:
        parser.error(f"Invalid severity {severity!r}; must be 'error' or 'warning'")

    try:
        allow = _build_allow_config(args, config)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    do_confusables = args.check_confusables or config.get("check-confusables", False)

    try:
        overrides = _build_overrides(config)
    except ValueError as exc:
        parser.error(str(exc))

    return config, severity, allow, do_confusables, overrides


def main(argv: list[str] | None = None) -> int:
    """Run the check-unicode CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Informational flags that exit immediately
    if args.list_scripts:
        _print_scripts()
        return 0
    if args.list_categories:
        _print_categories()
        return 0

    if not args.files:
        parser.error("No files specified.")

    config, severity, allow, do_confusables, overrides = _load_and_validate_config(
        parser, args
    )

    # Filter out excluded files
    exclude_patterns = _build_exclude_patterns(args, config)
    files = [f for f in args.files if not _is_excluded(f, exclude_patterns)]

    if not files:
        return 0

    # Fix mode
    if args.fix:
        fixed = [fix_file(filepath) for filepath in files]
        any_fixed = any(fixed)
        all_findings, has_errors = _scan_files(
            files, allow, overrides, do_confusables=do_confusables, severity=severity
        )
        if all_findings:
            print_findings(all_findings, no_color=args.no_color, quiet=args.quiet)
        return 1 if any_fixed or all_findings else 0

    # Check mode
    all_findings, has_errors = _scan_files(
        files, allow, overrides, do_confusables=do_confusables, severity=severity
    )
    if all_findings:
        print_findings(all_findings, no_color=args.no_color, quiet=args.quiet)
        return 1 if has_errors else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
