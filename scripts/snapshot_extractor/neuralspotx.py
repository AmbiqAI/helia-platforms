"""Extract the neuralspotx snapshot, keyed by board, and its SDK pins (ADR 0006 section 3)."""

from __future__ import annotations

from typing import Any

import yaml

from snapshot_extractor import ExtractError, cmake, reading
from snapshot_extractor.git import Checkout

REPOSITORY = "AmbiqAI/neuralspotx"
_BOARDS = "src/neuralspotx/boards"
LOCK = "src/neuralspotx/data/registry.lock.yaml"
PATHS = (
    f"/{_BOARDS}/*/board.yaml",
    f"/{_BOARDS}/*/debug.cmake",
    f"/{_BOARDS}/*/memory.cmake",
    f"/{LOCK}",
)
# memory.cmake names scripts under the nsx-core module of nsx-ambiq-sdk.
_SCRIPT_PREFIX = "${NSX_CORE_DIR}/"
_SCRIPT_ROOT = "modules/nsx-core/"


def soc_families(checkout: Checkout) -> dict[str, str]:
    """The nsx-ambiq-sdk revision each SoC family pins."""
    with reading(LOCK):
        lock = yaml.safe_load(checkout.read(LOCK))
        families = lock.get("soc_families") if isinstance(lock, dict) else None
        if not isinstance(families, dict) or not families:
            raise ExtractError("no soc_families mapping")
        revisions: dict[str, str] = {}
        for family, entry in families.items():
            if entry.get("project") != "nsx-ambiq-sdk" or not entry.get("revision"):
                raise ExtractError(f"soc family {family} does not pin nsx-ambiq-sdk")
            revisions[str(family)] = str(entry["revision"])
    return revisions


def _board(checkout: Checkout, name: str) -> dict[str, Any]:
    directory = f"{_BOARDS}/{name}"
    descriptor = f"{directory}/board.yaml"
    with reading(descriptor):
        data = yaml.safe_load(checkout.read(descriptor))
        if not isinstance(data, dict) or not isinstance(data.get("board"), dict):
            raise ExtractError("no board mapping")
        values = {
            "cpu": data.get("cpu"),
            "soc": data["board"].get("soc"),
            "toolchains": data.get("toolchains"),
        }
        if not isinstance(values["soc"], str):
            raise ExtractError("board.soc is not a string")
    block: dict[str, Any] = {"board": {"path": descriptor, "values": values}}
    debug = f"{directory}/debug.cmake"
    if (checkout.root / debug).is_file():
        with reading(debug):
            block["debug"] = {"path": debug, "values": cmake.set_values(checkout.read(debug))}
    memory = f"{directory}/memory.cmake"
    if (checkout.root / memory).is_file():
        with reading(memory):
            defaults = cmake.default_scripts(checkout.read(memory))
            for toolchain, path in defaults.items():
                if not path.startswith(_SCRIPT_PREFIX):
                    raise ExtractError(f"{toolchain} script {path!r} is not under nsx-core")
                defaults[toolchain] = _SCRIPT_ROOT + path.removeprefix(_SCRIPT_PREFIX)
        block["linker"] = {"defaults": defaults, "path": memory}
    return block


def extract(checkout: Checkout) -> dict[str, Any]:
    """The snapshot body: every board and the ``soc_families`` pins."""
    names = sorted(path.parent.name for path in (checkout.root / _BOARDS).glob("*/board.yaml"))
    if not names:
        raise ExtractError(f"{REPOSITORY}@{checkout.revision}: no boards under {_BOARDS}")
    return {
        "boards": {name: _board(checkout, name) for name in names},
        "soc_families": {"path": LOCK, "values": soc_families(checkout)},
    }
