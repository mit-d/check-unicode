# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in `check-unicode`, please report it
through
[GitHub's private vulnerability reporting](https://github.com/mit-d/check-unicode/security/advisories/new).

**Do not open a public issue.**

You should expect an initial response within 72 hours. Once confirmed, a fix
will be prioritized and released as a patch version.

## Scope

This project is a static analysis tool for detecting Unicode-based attacks. The
following are in scope:

- Bypasses that allow dangerous characters to go undetected
- False negatives in confusable/homoglyph detection
- Issues in the fix mode that could corrupt files
