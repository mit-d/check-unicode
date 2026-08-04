# Changelog

## Unreleased

### Added

- Nix flake: `nix run` the CLI, `nix build` the package (version read from
  `__init__.py` so bump-my-version stays the single source of truth, man page
  installed via `installShellFiles`), and `nix develop` for a dev shell.
  `.envrc` (`use flake`) provided for direnv users.
- Dev shell provides Python 3.11, uv, pre-commit, and the pinned dev tooling
  (ruff, ty, pytest, bump-my-version), and pre-wires `PYTHONPATH` to `src/` so
  the working tree is importable without an editable install.
- That dev tooling, in the shell and in `nix flake check` alike, is built from
  `uv.lock` with [uv2nix](https://github.com/pyproject-nix/uv2nix), so it is the
  exact set of versions CI and pre-commit run and `flake.nix` never restates a
  tool version. The shipped package remains a plain nixpkgs
  `buildPythonApplication` -- the CLI has zero runtime dependencies, so there is
  nothing there for the lock to pin.
- Dev shell installs the pre-commit git hook on first entry, so `nix develop`
  (or `direnv allow`) is the only setup step needed for commit-time checks. It
  installs only when `.pre-commit-config.yaml` is in the current directory and
  no `pre-commit` hook exists yet, so entering the shell from another repo
  cannot touch that repo's hooks.
- `nix flake check` gates the test suite, ruff lint and format, and ty. ty is
  safe to gate because its version comes from `uv.lock` rather than nixpkgs.
  Only pre-commit is excluded: it fetches its hook repos over the network, which
  the build sandbox forbids, so it is provided in the dev shell instead.
- `python -m check_unicode` now works as an alternative to the `check-unicode`
  console script.

### Changed

- Dev dependencies are pinned exactly in `pyproject.toml` (`ruff==0.16.1`,
  `ty==0.0.66`, `pytest==9.1.1`, `pytest-cov==7.1.0`, `pytest-sugar==1.1.1`,
  `bump-my-version==1.5.0`), replacing unbounded specifiers. `uv.lock` is now
  the single source of truth for tool versions.
- CI and the pre-commit `ty` hook run `uv run ty` instead of `uvx ty@latest`, so
  a ty release can no longer change what a green build means.
- The `ruff` and `ruff-format` hooks run from `uv.lock` via `uv run --frozen`
  instead of the `ruff-pre-commit` mirror, whose `rev` was a second place to
  state the ruff version. Every tool version now appears exactly once. `uv` must
  be on `PATH` for the hooks to run.
- Ignore ruff `CPY001` (per-file copyright headers), newly stabilized in ruff
  0.16 and picked up by `select = ["ALL"]`; the MIT notice lives in `LICENSE`.
- The repo's own `check-unicode` pre-commit hook prefers
  `.venv/bin/check-unicode` and falls back to `python -m check_unicode`, so it
  dogfoods the working tree under both the uv and the Nix workflow (a Nix-only
  checkout has no `.venv`).

## 0.6.0 - 2026-03-29

### Added

- Pipe mode: `check-unicode -` reads stdin line-by-line and writes to stdout,
  enabling use as a streaming Unix filter for log monitoring, CI pipelines, and
  editor buffer filtering
- `--strip [dangerous|all]` flag to remove non-ASCII characters; `dangerous`
  strips only invisible/bidi chars, `all` (default) strips any remaining
  non-ASCII after allow-list processing
- `--halt [dangerous|all]` flag to stop immediately on first matching character;
  `dangerous` (default) halts on invisible/bidi chars, `all` halts on any
  non-ASCII
- `--fix`, `--strip`, and `--halt` are fully composable and work identically
  across file and pipe modes

### Changed

- En dash and em dash now replace to `-` instead of `--`
- Expanded `--fix` replacement table with: hyphen variants (U+2010-2012, U+2015,
  U+FE58), soft hyphen (removed), bullets, dot leaders, arrows (`->`, `<-`, `^`,
  `v`), and math operators (`x`, `/`)
- Add `pytest-sugar` for improved test output
- Replace mypy with [ty](https://github.com/astral-sh/ty) for type checking
- Move dev dependencies from `optional-dependencies` to `dependency-groups`
- Switch CI from pip to uv for faster, reproducible installs; check in `uv.lock`
- Extract codepoint/range parsing into `check_unicode.parsing` module for reuse
- Codepoint parser now validates the Unicode range (0..U+10FFFF) and rejects
  empty/invalid input with clear error messages
- Range parser now rejects inverted ranges (lo > hi) and tolerates whitespace
  around the dash separator

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
