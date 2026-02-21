# Changelog

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
