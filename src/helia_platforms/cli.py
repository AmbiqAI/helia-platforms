"""Command-line entry point for ``helia-platforms``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from helia_platforms import __version__, _show
from helia_platforms import export as _export
from helia_platforms.catalog import Catalog, builtin, load_overlay
from helia_platforms.errors import FormatError, PlatformError
from helia_platforms.schema import render

app = typer.Typer(
    name="helia-platforms",
    help="Shared catalog of Ambiq SoC and board facts.",
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
    """Shared catalog of Ambiq SoC and board facts."""
    if ctx.invoked_subcommand is None:
        typer.echo(__version__)


BuiltinOnly = Annotated[
    bool,
    typer.Option(
        "--builtin-only",
        help="Leave out side-loaded catalogs (entry points, HELIA_PLATFORMS_PATH).",
    ),
]
Overlays = Annotated[
    list[Path] | None,
    typer.Option("--overlay", help="Load this overlay file on top; repeatable.", dir_okay=False),
]


def _catalog(builtin_only: bool, overlays: list[Path] | None) -> Catalog:
    """The built-in catalog, side-loaded sources unless ``builtin_only``, then ``overlays``."""
    try:
        catalog = builtin(include_plugins=not builtin_only)
        for path in overlays or ():
            catalog = load_overlay(path, base=catalog)
    except FormatError as exc:
        for problem in exc.problems:
            typer.echo(problem, err=True)
        raise typer.Exit(1) from None
    except PlatformError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    return catalog


@app.command()
def validate(
    files: Annotated[
        list[Path], typer.Argument(help="Overlay files to check.", exists=True, dir_okay=False)
    ],
    builtin_only: BuiltinOnly = False,
) -> None:
    """Check each overlay file, loaded over the built-in catalog, against the format and rules."""
    base = _catalog(builtin_only, None)
    failed = False
    for path in files:
        try:
            load_overlay(path, base=base)
        except FormatError as exc:
            failed = True
            for problem in exc.problems:
                typer.echo(problem, err=True)
        except PlatformError as exc:
            failed = True
            typer.echo(f"{path}: {exc}", err=True)
        else:
            typer.echo(f"{path}: ok")
    if failed:
        raise typer.Exit(1)


@app.command("list")
def list_(
    kind: Annotated[
        str | None,
        typer.Argument(help=f"One of {', '.join(_show.KINDS)}; all of them by default."),
    ] = None,
    builtin_only: BuiltinOnly = False,
    overlay: Overlays = None,
) -> None:
    """List the Socs, implementations, parts and boards, with each one's source."""
    if kind is not None and kind not in _show.KINDS:
        typer.echo(f"unknown kind {kind!r}; use one of {', '.join(_show.KINDS)}", err=True)
        raise typer.Exit(2)
    catalog = _catalog(builtin_only, overlay)
    typer.echo(_show.render_list(catalog, (kind,) if kind else _show.KINDS), nl=False)


@app.command()
def show(  # noqa: PLR0917 (typer reads each parameter as an argument or option)
    name: Annotated[str, typer.Argument(help="A board, part, implementation or Soc id, or alias.")],
    addon: Annotated[
        list[str] | None, typer.Option("--addon", help="Add this add-on to a board; repeatable.")
    ] = None,
    boot: Annotated[str | None, typer.Option(help="Select this boot configuration.")] = None,
    provenance: Annotated[
        bool, typer.Option("--provenance", help="Print the full record under every row.")
    ] = False,
    sources: Annotated[
        bool, typer.Option("--sources", help="Print the source each entry was loaded from.")
    ] = False,
    builtin_only: BuiltinOnly = False,
    overlay: Overlays = None,
) -> None:
    """Show a resolved target, with the provenance status of every value."""
    catalog = _catalog(builtin_only, overlay)
    try:
        target = catalog.resolve(name, addons=addon or (), boot=boot)
    except PlatformError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    typer.echo(
        _show.render_target(target, provenance=provenance, sources=sources, requested_boot=boot),
        nl=False,
    )


@app.command()
def export(  # noqa: PLR0917 (typer reads each parameter as an option)
    schema: Annotated[
        bool, typer.Option("--schema", help="Write the JSON Schema of the file format.")
    ] = False,
    export_schema: Annotated[
        bool, typer.Option("--export-schema", help="Write the JSON Schema of the export.")
    ] = False,
    json_file: Annotated[
        Path | None,
        typer.Option(
            "--json", help="Write the export to this file; - for standard output.", dir_okay=False
        ),
    ] = None,
    provenance: Annotated[
        bool,
        typer.Option("--provenance", help="Keep every provenance record (internal use only)."),
    ] = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="Fail if the --json file differs from a fresh export."),
    ] = False,
    include_plugins: Annotated[
        bool,
        typer.Option("--include-plugins", help="Add side-loaded catalogs (internal use only)."),
    ] = False,
    overlay: Overlays = None,
) -> None:
    """Write a JSON Schema or the JSON export (RFC 0003)."""
    if sum((schema, export_schema, json_file is not None)) != 1:
        _usage("pass exactly one of --schema, --export-schema and --json")
    if json_file is None and (provenance or check or include_plugins or overlay):
        _usage("--provenance, --check, --include-plugins and --overlay need --json")
    if json_file is None:
        typer.echo(render(export=export_schema), nl=False)
        return
    catalog = _catalog(not include_plugins, overlay)
    text = _export.render(_export.document(catalog, provenance=provenance))
    if str(json_file) == "-":
        if check:
            _usage("--check needs a --json file, not -")
        typer.echo(text, nl=False)
    elif check:
        current = json_file.read_text(encoding="utf-8") if json_file.is_file() else None
        if current != text:
            typer.echo(f"{json_file} differs from a fresh export", err=True)
            raise typer.Exit(1)
    else:
        json_file.write_text(text, encoding="utf-8")


def _usage(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(2)


def main() -> None:
    """Run the CLI; exits the process with the command's status code."""
    app()


if __name__ == "__main__":
    main()
