"""CLI entrypoint, argparse, config discovery, and orchestration."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

from check_unicode import __version__
from check_unicode.checker import AllowConfig, Finding, check_file
from check_unicode.fixer import fix_file
from check_unicode.output import print_findings

_EXPECTED_RANGE_PARTS = 2


def _parse_codepoint(s: str) -> int:
    """Parse 'U+XXXX' or '0xXXXX' into an integer codepoint."""
    s = s.strip()
    if s.upper().startswith("U+"):
        return int(s.replace("U+", "0x", 1).replace("u+", "0x", 1), 0)
    if s.lower().startswith("0x"):
        return int(s, 0)
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
) -> tuple[set[int], list[tuple[int, int]], set[str]]:
    """Extract allow-lists from a parsed config dictionary."""
    codepoints: set[int] = {
        _parse_codepoint(cp_str) for cp_str in config.get("allow-codepoints", [])
    }
    ranges: list[tuple[int, int]] = [
        _parse_range(r_str) for r_str in config.get("allow-ranges", [])
    ]
    categories: set[str] = set(config.get("allow-categories", []))
    return codepoints, ranges, categories


def _build_allow_config(
    args: argparse.Namespace,
    config: dict[str, Any],
) -> AllowConfig:
    """Merge CLI args and config file into an AllowConfig."""
    # Config file values
    codepoints, ranges, categories = _allow_from_config(config)

    # CLI args (extend, don't replace)
    if args.allow_codepoint:
        for item in args.allow_codepoint:
            for cp_str in item.split(","):
                codepoints.add(_parse_codepoint(cp_str))
    if args.allow_range:
        ranges.extend(_parse_range(r_str) for r_str in args.allow_range)
    if args.allow_category:
        categories.update(args.allow_category)

    return AllowConfig(
        codepoints=frozenset(codepoints),
        ranges=tuple(ranges),
        categories=frozenset(categories),
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="check-unicode",
        description="Detect and fix non-ASCII Unicode characters in text files.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Files to check (reads from stdin if none given)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Replace known offenders with ASCII equivalents (exit 1 if changed)",
    )
    parser.add_argument(
        "--allow-range",
        action="append",
        metavar="RANGE",
        help="Allow a Unicode range (e.g. U+00A0-U+00FF). Repeatable.",
    )
    parser.add_argument(
        "--allow-codepoint",
        action="append",
        metavar="CP",
        help="Allow specific codepoints (e.g. U+00B0). Repeatable, comma-separated.",
    )
    parser.add_argument(
        "--allow-category",
        action="append",
        metavar="CAT",
        help="Allow Unicode category (e.g. Sc). Repeatable.",
    )
    parser.add_argument(
        "--severity",
        choices=["error", "warning"],
        default=None,
        help="error (exit 1) or warning (print, exit 0). Default: error.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output.",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to TOML config file.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Summary only, no per-finding details.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the check-unicode CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.files:
        parser.error("No files specified.")

    config = _load_config(args.config)
    severity = args.severity or config.get("severity", "error")
    allow = _build_allow_config(args, config)

    # Fix mode
    if args.fix:
        fixed_results = [fix_file(filepath) for filepath in args.files]
        any_fixed = any(fixed_results)

        # After fixing, still check for remaining issues
        all_findings: list[Finding] = []
        for filepath in args.files:
            all_findings.extend(check_file(filepath, allow))

        if all_findings:
            print_findings(all_findings, no_color=args.no_color, quiet=args.quiet)
        if any_fixed or all_findings:
            return 1
        return 0

    # Check mode
    all_findings = []
    for filepath in args.files:
        all_findings.extend(check_file(filepath, allow))

    if all_findings:
        print_findings(all_findings, no_color=args.no_color, quiet=args.quiet)
        return 0 if severity == "warning" else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
