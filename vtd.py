#!/usr/bin/env python3
"""VTD local test installer. Run without arguments for an interactive menu."""
import sys

if sys.version_info < (3, 10):
    raise SystemExit('VTD installer requires Python 3.10 or later.')

from tools.install import main

if __name__ == '__main__':
    raise SystemExit(main())
