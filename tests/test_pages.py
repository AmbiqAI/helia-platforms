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


def _page_names(catalog) -> set[str]:
    """One page per Soc and per board, and the index."""
    socs = {f"socs/{soc.id}.md" for soc in catalog.socs()}
    return socs | {f"boards/{board.id}.md" for board in catalog.boards()} | {"index.md"}


def test_the_built_in_pages():
    catalog = builtin(include_plugins=False)
    pages = _pages.render(catalog)
    assert list(pages) == sorted(_page_names(catalog))
    soc, board = pages["socs/apollo510.md"], pages["boards/apollo510_evb.md"]
    assert soc.startswith("---\ntitle: apollo510\ndescription: ")
    assert "| dtcm | `0x20000000` | 512K | sram | tcm |" in soc
    assert "| sbl | sbl | cm55_0: mram + 64K | sbl: mram + 0, 64K | yes |" in soc
    assert "- Boards: [apollo510_evb](../boards/apollo510_evb.md)" in soc
    assert "| mspi0 | APS512XX | psram | 64M | `0x60000000` |" in board
    assert "| cm55_0 | application | cortex-m55 | cpu | customer |" in soc
    assert "## Image slots" not in soc
    assert "Usable NVM (core 0): mram 4032K, after boot reservation sbl (mram + 0, 64K)." in board
    assert "Flash load address (core 0): `0x00410000`." in board
    assert (
        "- [apollo510](socs/apollo510.md): [apollo510_evb](boards/apollo510_evb.md)"
        in (pages["index.md"])
    )
    digest = builtin(include_plugins=False).catalog_digest
    assert all(page.endswith(f"catalog `{digest}`.\n") for page in pages.values())


def test_an_apollo3_board_page_gives_j_links_cpufreq_apart_from_the_trace_clock():
    pages = _pages.render(builtin(include_plugins=False))
    line = "- J-Link's `-cpufreq` takes 48 MHz (the HFRC) on the apollo3 series, not the 6 MHz"
    for board in ("apollo3_evb", "apollo3p_evb"):
        assert f"- Trace clock: 6 MHz\n{line} trace clock;" in pages[f"boards/{board}.md"]
    assert "`-cpufreq`" not in pages["boards/apollo4p_evb.md"]


def test_the_radio_core_pages_name_the_vendor_slot_and_who_programs_the_radio_core():
    pages = _pages.render(builtin(include_plugins=False))
    soc, board = pages["socs/apollo330P.md"], pages["boards/apollo510dL_evb.md"]
    assert "| radio_m4 | radio | cortex-m4 | radio | vendor only |" in soc
    slots = [line for line in soc.splitlines() if line.startswith("| nvm_m41 |")]
    assert slots == [
        "| nvm_m41 | the Soc | radio_m4 | mram | 2032K | 16K | vendor |",
        "| nvm_m41 | AP330BPA-CCR | radio_m4 | mram | 1760K | 288K | vendor |",
        "| nvm_m41 | AP330BPA-ICR | radio_m4 | mram | 1760K | 288K | vendor |",
        "| nvm_m41 | AP330MPA-CCR | radio_m4 | mram | 1616K | 432K | vendor |",
        "| nvm_m41 | AP330MPA-IBR | radio_m4 | mram | 1616K | 432K | vendor |",
        "| nvm_m41 | AP330MPA-CBR | radio_m4 | mram | 1616K | 432K | vendor |",
    ]
    assert (
        "Usable NVM (core 0): mram 1552K, after boot reservation sbl (mram + 0, 64K) and "
        "vendor-supplied image slot nvm_m41 of radio_m4 (mram + 1616K, 432K).\n"
        "Only the vendor programs radio_m4, so it has no usable NVM.\n"
    ) in board


def test_a_board_with_no_boot_configuration_says_so(document):
    soc = document["socs"]["soc_a"]
    del soc["boot_configs"], soc["default_boot"]
    del document["boards"]["board_a"]["provisioning"]
    board = _pages.render(overlay(public(document)))["boards/board_a.md"]
    assert "Flash load address (core 0): no boot configuration is selected." in board


def test_a_target_that_is_not_public_stops_the_pages(document):
    catalog = overlay(document)  # every entry defaults to embargoed
    with pytest.raises(PlatformError, match="pages show public targets only"):
        _pages._public(catalog, "board_a")


def test_the_release_assets_are_stable():
    catalog = builtin(include_plugins=False)
    first, second = (_pages.release(catalog) for _ in range(2))
    assert first == second
    zipped = first["helia-platforms-pages.zip"]
    assert isinstance(zipped, bytes)
    archive = zipfile.ZipFile(io.BytesIO(zipped))
    pages = _pages.render(builtin(include_plugins=False))
    assert archive.namelist() == [f"pages/{name}" for name in pages]
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
