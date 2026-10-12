"""Extract the nsx-ambiq-sdk snapshot, keyed by SoC family (ADR 0006 section 3)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

from snapshot_extractor import ExtractError, cdefines, cmake, linker, reading
from snapshot_extractor.git import Checkout

REPOSITORY = "AmbiqAI/nsx-ambiq-sdk"
_AMBIQSUITE = "modules/nsx-ambiqsuite/sdk"
_CORE = "modules/nsx-core/src"
_SCRIPT_GLOBS = {"armclang": "*.sct", "gcc": "*.ld"}

# SoC family to (mcu/<dir>, CMSIS <header>), reviewed with the extractor. apollo510b
# and apollo5b have no headers of their own and read apollo510's.
HEADERS: dict[str, tuple[str, str]] = {
    "apollo2": ("apollo2", "apollo2"),
    "apollo3": ("apollo3", "apollo3"),
    "apollo3p": ("apollo3p", "apollo3p"),
    "apollo330P": ("apollo330P", "apollo330P"),
    "apollo4l": ("apollo4l", "apollo4l"),
    "apollo4p": ("apollo4p", "apollo4p"),
    "apollo5b": ("apollo510", "apollo510"),
    "apollo510": ("apollo510", "apollo510"),
    "apollo510b": ("apollo510", "apollo510"),
    "apollo510L": ("apollo510L", "apollo510L"),
    "atomiq110": ("atomiq110", "atomiq110"),
}
# Apollo3 parts take their flash and SRAM sizes from hal/am_hal_flash.h.
FLASH_DEFINES: dict[str, tuple[str, ...]] = {
    soc: (
        "AM_HAL_FLASH_ADDR",
        "AM_HAL_FLASH_INSTANCE_SIZE",
        "AM_HAL_FLASH_NUM_INSTANCES",
        "AM_HAL_FLASH_TOTAL_SIZE",
        "AM_HAL_FLASH_SRAM_ADDR",
        "AM_HAL_FLASH_SRAM_SIZE",
    )
    for soc in ("apollo3", "apollo3p")
}
# The CMSIS processor configuration ends where the core header is included.
_CMSIS_END = re.compile(r"\s*#\s*include\s+\"core_")


def _registers_path(soc: str) -> str:
    return f"{_AMBIQSUITE}/mcu/{_headers(soc)[0]}/regs/am_reg_base_addresses.h"


def _flash_path(soc: str) -> str:
    return f"{_AMBIQSUITE}/mcu/{_headers(soc)[0]}/hal/am_hal_flash.h"


def _cmsis_path(soc: str) -> str:
    return f"{_AMBIQSUITE}/CMSIS/AmbiqMicro/Include/{_headers(soc)[1]}.h"


def _headers(soc: str) -> tuple[str, str]:
    if soc not in HEADERS:
        raise ExtractError(f"SoC family {soc} is not in the SoC-to-header map (sdk.HEADERS)")
    return HEADERS[soc]


def paths(socs: Iterable[str]) -> list[str]:
    """The sparse-checkout patterns for ``socs``."""
    patterns = ["/cmake/socs/"]
    for soc in sorted(set(socs)):
        patterns += [f"/{_CORE}/{soc}/gcc/*.ld", f"/{_CORE}/{soc}/armclang/*.sct"]
        patterns += [f"/{_registers_path(soc)}", f"/{_cmsis_path(soc)}"]
        if soc in FLASH_DEFINES:
            patterns.append(f"/{_flash_path(soc)}")
    return patterns


def _linker(checkout: Checkout, soc: str) -> dict[str, Any]:
    soc_cmake = f"cmake/socs/{soc}.cmake"
    with reading(soc_cmake):
        defaults = cmake.default_scripts(checkout.read(soc_cmake))
    groups: dict[str, Any] = {}
    for toolchain in cmake.TOOLCHAINS:
        directory = f"{_CORE}/{soc}/{toolchain}"
        files = sorted((checkout.root / directory).glob(_SCRIPT_GLOBS[toolchain]))
        if not files and toolchain not in defaults:
            continue
        read = linker.gnu_memory if toolchain == "gcc" else linker.scatter_regions
        group: dict[str, Any] = {"path": directory, "scripts": {}}
        for file in files:
            with reading(f"{directory}/{file.name}"):
                group["scripts"][file.name] = read(checkout.read(f"{directory}/{file.name}"))
        if toolchain in defaults:
            written = PurePosixPath(defaults[toolchain].removeprefix("${NSX_ROOT}/"))
            if str(written.parent) != directory or written.name not in group["scripts"]:
                raise ExtractError(f"{soc_cmake}: default script {written} is not in {directory}")
            group["default"] = written.name
        groups[toolchain] = group
    return groups


def extract_soc(checkout: Checkout, soc: str) -> dict[str, Any]:
    """One SoC block, read at ``checkout``'s revision."""
    facts = f"cmake/socs/facts/{soc}.cmake"
    with reading(facts):
        fact_values = cmake.set_values(checkout.read(facts))
    registers = _registers_path(soc)
    with reading(registers):
        register_defines = cdefines.collect(checkout.read(registers))
        register_values = cdefines.Defines(register_defines).integers(register_defines)
    cmsis = _cmsis_path(soc)
    with reading(cmsis):
        cmsis_defines = cdefines.collect(checkout.read(cmsis), stop=_CMSIS_END)
        cmsis_values = cdefines.Defines(cmsis_defines).integers(
            name for name in cmsis_defines if name.startswith("__")
        )
    block: dict[str, Any] = {
        "cmsis": {"path": cmsis, "values": cmsis_values},
        "facts": {"path": facts, "values": fact_values},
        "linker": _linker(checkout, soc),
        "registers": {"path": registers, "values": register_values},
        "revision": checkout.revision,
    }
    if soc in FLASH_DEFINES:
        flash = _flash_path(soc)
        with reading(flash):
            environment = cdefines.Defines(register_defines, cdefines.collect(checkout.read(flash)))
            values = environment.integers(FLASH_DEFINES[soc])
            missing = sorted(set(FLASH_DEFINES[soc]) - set(values))
            if missing:
                raise ExtractError(f"no integer value for {missing}")
        block["flash"] = {"path": flash, "values": values}
    return block
