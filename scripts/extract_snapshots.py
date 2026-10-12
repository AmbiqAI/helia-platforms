#!/usr/bin/env python3
"""Regenerate or check the committed source snapshots (ADR 0006); see ``--help``.

Run with the ``extract`` dependency group: ``uv run --group extract
scripts/extract_snapshots.py extract --check``.
"""

from __future__ import annotations

import sys

from snapshot_extractor.cli import main

if __name__ == "__main__":
    sys.exit(main())
