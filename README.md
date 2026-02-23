# check-unicode

[![CI](https://github.com/mit-d/check-unicode/actions/workflows/test.yml/badge.svg)](https://github.com/mit-d/check-unicode/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

A pre-commit hook to detect and fix non-ASCII Unicode characters in text files.

Catches smart quotes, em dashes, fancy spaces, dangerous invisible characters
(Trojan Source bidi attacks, zero-width chars), and other copy-paste artifacts.

## Installation

### As a pre-commit hook

```yaml
repos:
  - repo: https://github.com/mit-d/check-unicode
    rev: v0.3.3
    hooks:
      - id: check-unicode
      # or for auto-fix:
      - id: fix-unicode
```

### Standalone

```bash
pip install check-unicode
check-unicode path/to/file.txt
```

## Usage

```text
check-unicode [OPTIONS] [FILES...]
```

| Flag                    | Description                                           | Default       |
| ----------------------- | ----------------------------------------------------- | ------------- |
| `--fix`                 | Replace known offenders with ASCII, exit 1 if changed | off           |
| `--allow-range RANGE`   | Allow a Unicode range (e.g. `U+00A0-U+00FF`). Repeat. | none          |
| `--allow-codepoint CP`  | Allow codepoints (e.g. `U+00B0`). Repeat/comma-sep.   | none          |
| `--allow-category CAT`  | Allow Unicode category (e.g. `Sc`). Repeatable.       | none          |
| `--allow-printable`     | Allow all printable chars (only flag invisibles)      | off           |
| `--allow-script SCRIPT` | Allow Unicode script (e.g. `Latin`). Repeatable.      | none          |
| `--check-confusables`   | Detect mixed-script homoglyph/confusable characters   | off           |
| `--severity LEVEL`      | `error` (exit 1) or `warning` (print, exit 0)         | `error`       |
| `--no-color`            | Disable ANSI color                                    | auto-detect   |
| `--config FILE`         | Path to TOML config                                   | auto-discover |
| `-q` / `--quiet`        | Summary only                                          | off           |
| `-V` / `--version`      | Print version                                         |               |

## What it catches

- **Smart quotes**: `\u201c` `\u201d` `\u2018` `\u2019` and variants
- **Dashes**: em dash `\u2014`, en dash `\u2013`, minus sign `\u2212`
- **Fancy spaces**: non-breaking space, em space, thin space, etc.
- **Ellipsis**: `\u2026`
- **Dangerous invisible characters** (always flagged):
  - Bidi control (Trojan Source CVE-2021-42574): U+202A-202E, U+2066-2069
  - Zero-width: U+200B-200F, U+FEFF (mid-file), U+2060-2064, U+180E
  - Replacement character: U+FFFD
- **Confusable homoglyphs** (with `--check-confusables`):
  - Mixed-script identifiers where minority-script chars look like Latin
  - Cyrillic/Greek/Armenian letters that visually resemble Latin letters
  - e.g. Cyrillic `a` (U+0430) mixed with Latin `ccess_level`

## Auto-fix

`--fix` replaces known offenders with ASCII equivalents:

| Unicode      | Replacement |
| ------------ | ----------- |
| Smart quotes | `'` or `"`  |
| En/em dashes | `--`        |
| Minus sign   | `-`         |
| Fancy spaces | ` `         |
| Ellipsis     | `...`       |

Dangerous invisible characters are **never auto-fixed** -- they require manual
review.

## Configuration

Create `.check-unicode.toml` or add to `pyproject.toml`:

```toml
[tool.check-unicode]
allow-codepoints = ["U+00B0", "U+2192"]
allow-ranges = ["U+00A0-U+00FF"]
allow-categories = ["Sc"]
allow-printable = true
allow-scripts = ["Latin", "Cyrillic"]
check-confusables = true
severity = "error"
```

## Output

```text
path/to/file.txt:42:17: U+201C LEFT DOUBLE QUOTATION MARK [Ps]
  He said \u201chello\u201d to the crowd
          ^
Found 5 non-ASCII characters in 2 files (3 fixable, 1 dangerous)
```

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -v --cov
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/
```

## License

MIT
