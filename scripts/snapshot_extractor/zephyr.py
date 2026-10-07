"""Extract the Zephyr snapshot of the Ambiq boards, with hal_ambiq (ADR 0006 section 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from snapshot_extractor import ExtractError, devicetree, kconfig, reading
from snapshot_extractor.git import Checkout

REPOSITORY = "zephyrproject-rtos/zephyr"
HAL_REPOSITORY = "zephyrproject-rtos/hal_ambiq"
VENDOR = "ambiq"
PATHS = (
    f"/boards/{VENDOR}/*/board.yml",
    f"/boards/{VENDOR}/*/*.dts",
    f"/boards/{VENDOR}/*/*.dtsi",
    "/dts/",
    "/include/zephyr/dt-bindings/",
    "/include/zephyr/sys/",
    f"/soc/{VENDOR}/",
    "/scripts/dts/python-devicetree/src/",
    "/west.yml",
)
HAL_PATHS = ("/dts/", "/include/", "/zephyr/module.yml")
# Zephyr's pre_dt.cmake searches these under each DTS root; "arm" is the ARCH dir.
_DTS_ROOT_DIRS = ("include", "include/zephyr", "dts/common", "dts/vendor", "dts/arm", "dts")
_LOAD_OFFSET = "FLASH_LOAD_OFFSET"


def hal_revision(zephyr: Checkout) -> str:
    """The hal_ambiq revision Zephyr's ``west.yml`` pins."""
    with reading("west.yml"):
        manifest = yaml.safe_load(zephyr.read("west.yml"))
        for project in manifest["manifest"]["projects"]:
            if project.get("name") == "hal_ambiq":
                return str(project["revision"])
    raise ExtractError("west.yml: no hal_ambiq project")


def _hal_dts_root(hal: Checkout) -> Path:
    with reading("zephyr/module.yml"):
        module = yaml.safe_load(hal.read("zephyr/module.yml"))
        root = module.get("build", {}).get("settings", {}).get("dts_root")
        if not isinstance(root, str):
            raise ExtractError("no build.settings.dts_root")
    return hal.root / root


def _soc_symbols(zephyr: Checkout, soc: str) -> frozenset[str]:
    """The family, series and SoC Kconfig symbols ``soc.yml`` gives ``soc``."""
    with reading(f"soc/{VENDOR}/soc.yml"):
        data = yaml.safe_load(zephyr.read(f"soc/{VENDOR}/soc.yml"))
        for family in data["family"]:
            for series in family["series"]:
                if soc in (entry["name"] for entry in series["socs"]):
                    return frozenset(
                        {
                            f"SOC_FAMILY_{family['name'].upper()}",
                            f"SOC_SERIES_{series['name'].upper()}",
                            f"SOC_{soc.upper()}",
                        }
                    )
    raise ExtractError(f"soc/{VENDOR}/soc.yml does not list SoC {soc}")


def _board(zephyr: Checkout, hal_root: Path, dtlib: Any, name: str) -> dict[str, Any]:
    directory = f"boards/{VENDOR}/{name}"
    descriptor = f"{directory}/board.yml"
    with reading(descriptor):
        board = yaml.safe_load(zephyr.read(descriptor))["board"]
        socs = [entry["name"] for entry in board.get("socs", [])]
        if len(socs) != 1 or board.get("variants") or board.get("revision"):
            raise ExtractError("only single-SoC boards without variants or revisions are read")
    source = f"{directory}/{name}.dts"
    include_dirs = [
        root / sub
        for root in (hal_root, zephyr.root / directory, zephyr.root)
        for sub in _DTS_ROOT_DIRS
        if (root / sub).is_dir()
    ]
    with reading(source):
        text = devicetree.preprocess(zephyr.root / source, include_dirs)
        tree = devicetree.parse(dtlib, text, include_dirs)
        chosen = devicetree.chosen(tree)
        memory = devicetree.memory_nodes(tree)
    found = kconfig.soc_default(
        zephyr.root, f"soc/{VENDOR}/Kconfig.defconfig", _LOAD_OFFSET, _soc_symbols(zephyr, socs[0])
    )
    return {
        "board": {"path": descriptor, "values": {"soc": socs[0]}},
        "devicetree": {"chosen": chosen, "memory": memory, "path": source},
        "kconfig": {} if found is None else {_LOAD_OFFSET: {"path": found[0], "value": found[1]}},
    }


def extract(zephyr: Checkout, hal: Checkout) -> dict[str, Any]:
    """The snapshot body: every board in ``boards/ambiq``."""
    dtlib = devicetree.load_dtlib(zephyr.root)
    hal_root = _hal_dts_root(hal)
    names = sorted(p.parent.name for p in (zephyr.root / f"boards/{VENDOR}").glob("*/board.yml"))
    if not names:
        raise ExtractError(f"{REPOSITORY}@{zephyr.revision}: no boards under boards/{VENDOR}")
    return {"boards": {name: _board(zephyr, hal_root, dtlib, name) for name in names}}
