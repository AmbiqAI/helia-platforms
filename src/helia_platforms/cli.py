"""Command-line entry point for ``helia-platforms``."""

from __future__ import annotations

from typing import Annotated

import typer

from helia_platforms import __version__

app = typer.Typer(
    name="helia-platforms",
    help="Shared catalogue of Ambiq SoC and board facts.",
    no_args_is_help=False,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Shared catalogue of Ambiq SoC and board facts."""
    if ctx.invoked_subcommand is None:
        typer.echo(__version__)


def main() -> None:
    """Run the CLI; exits the process with the command's status code."""
    app()


if __name__ == "__main__":
    main()
