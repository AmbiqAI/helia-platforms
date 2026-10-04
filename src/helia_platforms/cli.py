"""Command-line entry point for ``helia-platforms``."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from helia_platforms import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="helia-platforms",
        description="Shared catalogue of Ambiq SoC and board facts.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code. ``--version`` prints the version and exits 0 via
        ``SystemExit``.
    """
    build_parser().parse_args(argv)
    print(__version__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
