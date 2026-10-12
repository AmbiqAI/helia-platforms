"""Extract source snapshots of nsx-ambiq-sdk, neuralspotx and Zephyr (ADR 0006).

The extractor reads only committed revisions, fetched at their commit SHA, and
writes ``snapshots/<source>.json``. ``scripts/extract_snapshots.py`` is the
command line; ``python scripts/extract_snapshots.py --help`` lists the modes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

# Bumped when the output changes for unchanged input (ADR 0006 section 2).
EXTRACTOR_VERSION = 1


class ExtractError(Exception):
    """A source could not be read in the scope ADR 0006 section 3 gives the parsers."""


@contextmanager
def reading(where: str) -> Iterator[None]:
    """Prefix any ``ExtractError`` raised inside the block with ``where``."""
    try:
        yield
    except ExtractError as exc:
        raise ExtractError(f"{where}: {exc}") from exc
