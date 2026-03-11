# Changelog

## 0.5.0 - 2026-03-10

### Fixed

- Validate `severity` values from config files and overrides (invalid values
  like `"warn"` now exit 2 instead of silently behaving as warning)
- Catch config file errors (missing file, invalid TOML) and exit 2 with a
  friendly message instead of a raw traceback
- Validate `--allow-category` and `--allow-script` values; unknown names now
  exit 2 with a hint to use `--list-categories` or `--list-scripts`
- Warn on unrecognised top-level config keys (e.g. typo `alow-codepoints`)
- Remove dead `U+FFFD` entry from `REPLACEMENT_TABLE` (unreachable because
  U+FFFD is in `DANGEROUS_INVISIBLE`, which is checked first)
- Exclude `tests/fixtures/` from mypy (intentionally malformed Trojan Source
  files)

### Added

- Grouped output: findings are now grouped per file with a compact line range
  header (e.g. `file.txt:1,4-80,90:`), context lines shown once with multi-caret
  markers (`^` normal, `!` dangerous, `?` confusable), deduplicated identical
  context lines, and collapsed codepoint listing with `(xN)` counts

### Changed

- Refactor `_apply_replacements` to use `str.translate()` for cleaner code and
  better performance on large files
- Read each file once when `--check-confusables` is enabled (previously
  `check_file` and `check_confusables` each read the file independently)
- Simplify `_parse_codepoint` to use prefix-stripping instead of fragile
  double-replace chain
- Add `slots=True` to `Override` dataclass for consistency with `Finding` and
  `AllowConfig`

### Docs

- Document per-file `[[tool.check-unicode.overrides]]` in README and man page
- Update man page version to 0.4.0 and fix stale pre-commit `rev`
- Add man page to `bump-my-version` files list

## 0.4.0 - 2026-02-28

### Added

- `[[tool.check-unicode.overrides]]` per-file config: apply different
  allow-lists, severity, and confusable settings per file pattern
- Per-file severity: override `severity` to `"warning"` for specific file
  patterns so findings don't affect exit code
- Per-file confusable toggle: enable or disable `check-confusables` per file
  pattern
- `uv.lock` added to `.gitignore`

## 0.3.3 - 2026-02-23

### Fixed

- `--fix` mode now fixes all files, not just the first (`any()` short-circuited
  after the first fixable file, skipping the rest)

## 0.3.2 - 2026-02-21

### Added

- `CONTRIBUTING.md` guide
- `SECURITY.md` with private vulnerability reporting instructions
- Issue templates for bug reports and feature requests
- Make `bump-my-version` handle README.md version

## 0.3.1 - 2026-02-21

### Added

- PR template with changelog and testing checklist
- Coverage threshold (80%) enforced in CI
- `markdownlint` config: allow duplicate headings across sibling sections

## 0.3.0 - 2026-02-21

### Added

- Grouped CLI help with `--help` showing organized option sections
- Usage examples in `--help` output
- Man page (`docs/check-unicode.1`)
- Release workflow for automatic GitHub Releases on tag push
- `bump-my-version` config for version management

## 0.2.0 - 2026-02-19

### Added

- `--allow-printable` flag: allow all `str.isprintable()` characters, only
  flagging invisible/control characters. Opt-in, not default.
- `--allow-script SCRIPT` flag: allow entire Unicode scripts (e.g. Latin,
  Cyrillic, Han). Repeatable. Dangerous invisible characters are never
  overridden by script allow-lists.
- `--check-confusables` flag: detect mixed-script homoglyph/confusable
  characters (e.g. Cyrillic `a` in a Latin identifier). Uses a curated set of
  ~45 security-critical mappings from Unicode confusables.txt.
- `scripts.py` module: zero-dependency Unicode script detection using
  `unicodedata.name()` heuristic.
- `confusables.py` module: curated confusable character mappings (Cyrillic,
  Greek, Armenian to Latin).
- New test fixtures: Trojan Source examples, mixed Cyrillic, pure Cyrillic,
  printable i18n text.
- TOML config keys: `allow-printable`, `allow-scripts`, `check-confusables`.

## 0.1.0 - 2026-02-18

Initial release.

- ASCII-only detection with configurable allow-lists (codepoints, ranges,
  Unicode categories)
- Dangerous invisible character detection (bidi control, zero-width) -- always
  flagged regardless of allow-lists
- Auto-fix mode for smart quotes, dashes, fancy spaces, ellipsis
- TOML config support (`.check-unicode.toml` or `pyproject.toml`)
- Pre-commit hooks: `check-unicode` (detect) and `fix-unicode` (auto-fix)
