"""Support `python -m check_unicode` alongside the console script."""

from __future__ import annotations

import sys

from check_unicode.main import main

if __name__ == "__main__":
    sys.exit(main())
