"""Unicode script detection using unicodedata.name() heuristic."""

from __future__ import annotations

import unicodedata

# Multi-word Unicode name prefixes that map to a single script.
# Checked before the default first-word heuristic.
MULTI_WORD_PREFIXES: dict[str, str] = {
    "CJK": "Han",
    "CANADIAN SYLLABICS": "Canadian_Aboriginal",
    "EGYPTIAN HIEROGLYPH": "Egyptian_Hieroglyphs",
    "MODIFIER LETTER": "Common",
    "MUSICAL SYMBOL": "Common",
    "NEW TAI LUE": "New_Tai_Lue",
    "OLD ITALIC": "Old_Italic",
    "OLD PERSIAN": "Old_Persian",
    "OLD SOUTH ARABIAN": "Old_South_Arabian",
    "OLD TURKIC": "Old_Turkic",
    "TAI LE": "Tai_Le",
    "TAI THAM": "Tai_Tham",
}

# First-word -> canonical script name when the first word alone
# doesn't match the canonical form.
_FIRST_WORD_ALIASES: dict[str, str] = {
    "HANGUL": "Hangul",
    "HIRAGANA": "Hiragana",
    "IDEOGRAPHIC": "Han",
    "KATAKANA": "Katakana",
    "KATAKANA-HIRAGANA": "Katakana",
    "TIBETAN": "Tibetan",
}

# Unicode general categories that are inherently script-neutral.
_COMMON_CATEGORIES = frozenset(
    {
        "Cc",  # control
        "Cf",  # format
        "Cn",  # unassigned
        "Co",  # private use
        "Cs",  # surrogate
        "Nd",  # decimal number
        "Nl",  # letter number
        "No",  # other number
        "Pc",  # connector punctuation
        "Pd",  # dash punctuation
        "Pe",  # close punctuation
        "Pf",  # final punctuation
        "Pi",  # initial punctuation
        "Po",  # other punctuation
        "Ps",  # open punctuation
        "Sc",  # currency symbol
        "Sk",  # modifier symbol
        "Sm",  # math symbol
        "So",  # other symbol
        "Zl",  # line separator
        "Zp",  # paragraph separator
        "Zs",  # space separator
    }
)

# Categories whose script is "Inherited" (combining marks).
_INHERITED_CATEGORIES = frozenset({"Mn", "Mc", "Me"})


def script_of(cp: int) -> str:
    """Return the Unicode script name for a codepoint.

    Uses ``unicodedata.name()`` first-word heuristic:
    * ``"CYRILLIC SMALL LETTER A"`` -> ``"Cyrillic"``
    * ``"CJK UNIFIED IDEOGRAPH-4E00"`` -> ``"Han"``

    Punctuation, symbols, and numbers -> ``"Common"``.
    Combining marks -> ``"Inherited"``.
    """
    cat = unicodedata.category(chr(cp))

    if cat in _INHERITED_CATEGORIES:
        return "Inherited"
    if cat in _COMMON_CATEGORIES:
        return "Common"

    try:
        name = unicodedata.name(chr(cp))
    except ValueError:
        return "Common"

    upper_name = name.upper()

    # Check multi-word prefixes first (longest match wins).
    for prefix, script in MULTI_WORD_PREFIXES.items():
        if upper_name.startswith(prefix):
            return script

    first_word = name.split()[0]

    if first_word.upper() in _FIRST_WORD_ALIASES:
        return _FIRST_WORD_ALIASES[first_word.upper()]

    # Default: title-case the first word.
    return first_word.title()


# Canonical script names accepted by --allow-script.
KNOWN_SCRIPTS: frozenset[str] = frozenset(
    {
        "Arabic",
        "Armenian",
        "Bengali",
        "Bopomofo",
        "Canadian_Aboriginal",
        "Cherokee",
        "Common",
        "Cyrillic",
        "Devanagari",
        "Ethiopic",
        "Georgian",
        "Greek",
        "Gujarati",
        "Gurmukhi",
        "Han",
        "Hangul",
        "Hebrew",
        "Hiragana",
        "Inherited",
        "Kannada",
        "Katakana",
        "Khmer",
        "Lao",
        "Latin",
        "Malayalam",
        "Mongolian",
        "Myanmar",
        "Ogham",
        "Oriya",
        "Runic",
        "Sinhala",
        "Syriac",
        "Tamil",
        "Telugu",
        "Thaana",
        "Thai",
        "Tibetan",
        "Yi",
    }
)
