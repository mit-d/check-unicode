"""Codepoint and range parsing for user input (CLI args and config files)."""

from __future__ import annotations

_MAX_UNICODE = 0x10FFFF


def parse_codepoint(s: str) -> int:
    """Parse a Unicode codepoint string into an integer.

    Accepted formats: ``U+XXXX``, ``u+xxxx``, ``0xXXXX``, bare hex digits.

    Raises:
        ValueError: If the string is empty, not valid hex, or out of the
            Unicode range (0..U+10FFFF).

    """
    s = s.strip()
    if not s:
        msg = "Codepoint string is empty"
        raise ValueError(msg)

    raw = s
    if s[:2].upper() == "U+" or s[:2].lower() == "0x":
        s = s[2:]

    if not s:
        msg = f"Invalid codepoint: {raw!r}"
        raise ValueError(msg)

    try:
        value = int(s, 16)
    except ValueError:
        msg = f"Invalid codepoint: {raw!r}"
        raise ValueError(msg) from None

    if value < 0 or value > _MAX_UNICODE:
        msg = f"Codepoint {raw!r} is outside the valid Unicode range (0..U+10FFFF)"
        raise ValueError(msg)

    return value


def parse_range(s: str) -> tuple[int, int]:
    """Parse a Unicode range string into a (lo, hi) tuple.

    Accepted formats: ``U+XXXX-U+YYYY``, ``0xXXXX-0xYYYY``.
    Splits on the last hyphen so that bare-hex ranges like ``A0-FF``
    work correctly (hex digits and ``U+``/``0x`` prefixes never
    contain hyphens).

    Raises:
        ValueError: If the string cannot be split into two parts,
            either part is invalid, or lo > hi.

    """
    s = s.strip()
    idx = s.rfind("-")
    if idx <= 0:
        msg = f"Invalid range: {s!r} (expected U+XXXX-U+YYYY)"
        raise ValueError(msg)

    lo = parse_codepoint(s[:idx])
    hi = parse_codepoint(s[idx + 1 :])

    if lo > hi:
        msg = f"Inverted range: lo U+{lo:04X} > hi U+{hi:04X} (start must be <= end)"
        raise ValueError(msg)

    return lo, hi
