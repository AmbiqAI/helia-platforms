"""Command-line entry point for ``helia-platforms``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from helia_platforms import __version__
from helia_platforms.catalogue import load_overlay
from helia_platforms.errors import FormatError
from helia_platforms.schema import render

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


@app.command()
def validate(
    files: Annotated[
        list[Path], typer.Argument(help="Overlay files to check.", exists=True, dir_okay=False)
    ],
) -> None:
    """Check overlay files against the file format and the semantic rules."""
    failed = False
    for path in files:
        try:
            load_overlay(path)
        except FormatError as exc:
            failed = True
            for problem in exc.problems:
                typer.echo(problem, err=True)
        else:
            typer.echo(f"{path}: ok")
    if failed:
        raise typer.Exit(1)


@app.command()
def export(
    schema: Annotated[
        bool, typer.Option("--schema", help="Write the JSON Schema of the file format.")
    ] = False,
) -> None:
    """Write an export to standard output."""
    if not schema:
        typer.echo("nothing to export: pass --schema", err=True)
        raise typer.Exit(2)
    typer.echo(render(), nl=False)


def main() -> None:
    """Run the CLI; exits the process with the command's status code."""
    app()


if __name__ == "__main__":
    main()
