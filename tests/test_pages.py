"""The Markdown pages and the release assets (RFC 0003 "Markdown pages", #74)."""

import io
import json
import warnings
import zipfile

import pytest
from typer.testing import CliRunner

from helia_platforms import _pages, cli
from helia_platforms.catalog import builtin, load_overlay
from helia_platforms.cli import app
from helia_platforms.errors import PlatformError

runner = CliRunner()
_TABLES = ("socs", "implementations", "parts", "boards", "addons", "memory_devices")


def overlay(document):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_overlay(document, base=None)


def public(document):
    for kind in _TABLES:
        for entry in document.get(kind, {}).values():
            entry["release_status"] = "public"
    return document


def test_the_built_in_pages():
    pages = _pages.render(builtin(include_plugins=False))
    assert list(pages) == [
        "boards/apollo510_evb.md",
        "boards/atomiq110_fpga_turbo.md",
        "index.md",
        "socs/apollo510.md",
        "socs/atomiq110.md",
    ]
    soc, board = pages["socs/apollo510.md"], pages["boards/apollo510_evb.md"]
    assert soc.startswith("---\ntitle: apollo510\ndescription: ")
    assert "| dtcm | `0x20000000` | 512K | sram | tcm |" in soc
    assert "| sbl | sbl | cm55_0: mram + 64K | sbl: mram + 0, 64K | yes |" in soc
    assert "- Boards: [apollo510_evb](../boards/apollo510_evb.md)" in soc
    assert "| mspi0 | APS512XX | psram | 64M | `0x60000000` |" in board
    assert "Usable NVM (core 0): mram 4032K." in board
    assert "Flash load address (core 0): `0x00410000`." in board
    assert (
        "- [apollo510](socs/apollo510.md): [apollo510_evb](boards/apollo510_evb.md)"
        in (pages["index.md"])
    )
    digest = builtin(include_plugins=False).catalog_digest
    assert all(page.endswith(f"catalog `{digest}`.\n") for page in pages.values())


def test_a_board_with_no_boot_configuration_says_so(document):
    soc = document["socs"]["soc_a"]
    del soc["boot_configs"], soc["default_boot"]
    del document["boards"]["board_a"]["provisioning"]
    board = _pages.render(overlay(public(document)))["boards/board_a.md"]
    assert "Flash load address (core 0): no boot configuration is selected." in board


def test_an_fpga_board_page_names_its_implementation(document):
    document["implementations"] = {"soc_a_fpga": {"soc": "soc_a", "kind": "fpga"}}
    document["boards"]["fpga_a"] = {"category": "fpga", "implementation": "soc_a_fpga"}
    pages = _pages.render(overlay(public(document)))
    assert (
        "- Implementation: `soc_a_fpga`, of Soc [soc_a](../socs/soc_a.md)"
        in (pages["boards/fpga_a.md"])
    )
    assert "[fpga_a](../boards/fpga_a.md)" in pages["socs/soc_a.md"]
    assert "[fpga_a](boards/fpga_a.md)" in pages["index.md"]


def test_a_target_that_is_not_public_stops_the_pages(document):
    catalog = overlay(document)  # every entry defaults to embargoed
    with pytest.raises(PlatformError, match="pages show public targets only"):
        _pages._public(catalog, "board_a")


def test_the_release_assets_are_stable():
    first, second = (_pages.release(builtin(include_plugins=False)) for _ in range(2))
    assert first == second
    zipped = first["helia-platforms-pages.zip"]
    assert isinstance(zipped, bytes)
    archive = zipfile.ZipFile(io.BytesIO(zipped))
    assert sorted(archive.namelist()) == [
        "pages/boards/apollo510_evb.md",
        "pages/boards/atomiq110_fpga_turbo.md",
        "pages/index.md",
        "pages/socs/apollo510.md",
        "pages/socs/atomiq110.md",
    ]
    assert json.loads(first["helia-platforms-export.json"])["identity"]["sources"] == []


@pytest.mark.parametrize(
    "extra", [["--overlay", "x.yaml"], ["--include-plugins"], ["--provenance"]]
)
@pytest.mark.parametrize("output", ["--pages", "--release"])
def test_pages_and_release_take_the_built_in_catalog_only(tmp_path, output, extra):
    result = runner.invoke(app, ["export", output, str(tmp_path / "out"), *extra])
    assert result.exit_code == 2, result.output
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("output", ["--pages", "--release"])
def test_a_catalog_that_names_a_source_is_refused(tmp_path, monkeypatch, output, document):
    monkeypatch.setattr(cli, "_catalog", lambda *_: overlay(public(document)))
    result = runner.invoke(app, ["export", output, str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "names a source besides the built-in data" in result.output
    assert not (tmp_path / "out").exists()


def test_the_cli_writes_and_checks_the_pages(tmp_path):
    out = tmp_path / "pages"
    assert runner.invoke(app, ["export", "--pages", str(out)]).exit_code == 0
    assert (out / "socs" / "apollo510.md").is_file()
    assert runner.invoke(app, ["export", "--pages", str(out), "--check"]).exit_code == 0
    (out / "socs" / "stale.md").write_text("gone\n")
    result = runner.invoke(app, ["export", "--pages", str(out), "--check"])
    assert result.exit_code == 1
    assert _pages.differences(out, _pages.render(builtin(include_plugins=False))) == [
        "socs/stale.md"
    ]
