# Contributing

Thanks for your interest in contributing to `check-unicode`.

## Development setup

```bash
uv venv && uv pip install -e ".[dev]"
```

## Before submitting a PR

1. Run the full test/lint suite:

   ```bash
   pytest --cov=check_unicode
   ruff check src/ tests/
   mypy src/
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
