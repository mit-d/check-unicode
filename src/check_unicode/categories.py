"""Character sets, dangerous codepoints, and replacement tables."""

# Bidi control characters (Trojan Source CVE-2021-42574)
_BIDI_CONTROL = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))

# Zero-width and invisible formatting characters
_ZERO_WIDTH = (
    set(range(0x200B, 0x2010))  # U+200B-200F
    | {0xFEFF}  # BOM / zero-width no-break space
    | set(range(0x2060, 0x2065))  # word joiner, invisible times, etc.
    | {0x180E}  # Mongolian vowel separator
)

# Replacement character
_REPLACEMENT = {0xFFFD}

DANGEROUS_INVISIBLE: frozenset[int] = frozenset(
    _BIDI_CONTROL | _ZERO_WIDTH | _REPLACEMENT
)

# Characters that --fix will replace with ASCII equivalents.
# Dangerous invisible chars are intentionally excluded -- they must be
# reviewed manually.
REPLACEMENT_TABLE: dict[int, str] = {
    # Smart single quotes / apostrophes
    0x2018: "'",  # LEFT SINGLE QUOTATION MARK
    0x2019: "'",  # RIGHT SINGLE QUOTATION MARK
    0x201A: "'",  # SINGLE LOW-9 QUOTATION MARK
    0x201B: "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    0x2039: "'",  # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    0x203A: "'",  # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    # Smart double quotes
    0x201C: '"',  # LEFT DOUBLE QUOTATION MARK
    0x201D: '"',  # RIGHT DOUBLE QUOTATION MARK
    0x201E: '"',  # DOUBLE LOW-9 QUOTATION MARK
    0x201F: '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    0x00AB: '"',  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    0x00BB: '"',  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
    # Dashes
    0x2013: "--",  # EN DASH
    0x2014: "--",  # EM DASH
    # Minus
    0x2212: "-",  # MINUS SIGN
    # Fancy spaces -> regular space
    0x00A0: " ",  # NO-BREAK SPACE
    0x2000: " ",  # EN QUAD
    0x2001: " ",  # EM QUAD
    0x2002: " ",  # EN SPACE
    0x2003: " ",  # EM SPACE
    0x2004: " ",  # THREE-PER-EM SPACE
    0x2005: " ",  # FOUR-PER-EM SPACE
    0x2006: " ",  # SIX-PER-EM SPACE
    0x2007: " ",  # FIGURE SPACE
    0x2008: " ",  # PUNCTUATION SPACE
    0x2009: " ",  # THIN SPACE
    0x200A: " ",  # HAIR SPACE
    0x3000: " ",  # IDEOGRAPHIC SPACE
    # Ellipsis
    0x2026: "...",  # HORIZONTAL ELLIPSIS
}
