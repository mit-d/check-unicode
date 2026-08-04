# Contributing

Thanks for your interest in contributing to `check-unicode`.

## Development setup

```bash
uv venv && uv sync --group dev
uvx pre-commit install
```

Nix users get `pre-commit` in the dev shell, and the git hook is installed on
first `nix develop` entry.

## Tool versions

`ruff`, `ty`, `pytest`, and `bump-my-version` are pinned exactly in
`pyproject.toml`, and `uv.lock` is the single source of truth: CI, the
pre-commit hooks, and the Nix dev shell all run those versions. Bumping one is a
single edit plus `uv lock`.

The ruff and ty hooks run through `uv run --frozen`, so `uv` has to be on `PATH`
for `git commit` to work -- it is in the Nix dev shell, and part of the uv setup
above otherwise.

## Before submitting a PR

1. Run the full test/lint suite:

   ```bash
   pytest --cov=check_unicode
   ruff check src/ tests/
   uv run ty check src/
   ```

2. Add or update tests for any new behavior.
3. Update `CHANGELOG.md` under `## Unreleased` if the change is user-facing.
4. Keep commits focused -- one logical change per PR.

## Reporting bugs

Open an issue with:

- The command you ran
- Expected vs actual output
- Python version (`python --version`)

## Security issues

If you find a security vulnerability, **do not open a public issue**. See
[SECURITY.md](SECURITY.md) for responsible disclosure instructions.
