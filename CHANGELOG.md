# Changelog

## 0.1.0

Initial release.

- ASCII-only detection with configurable allow-lists (codepoints, ranges,
  Unicode categories)
- Dangerous invisible character detection (bidi control, zero-width) -- always
  flagged regardless of allow-lists
- Auto-fix mode for smart quotes, dashes, fancy spaces, ellipsis
- TOML config support (`.check-unicode.toml` or `pyproject.toml`)
- Pre-commit hooks: `check-unicode` (detect) and `fix-unicode` (auto-fix)
