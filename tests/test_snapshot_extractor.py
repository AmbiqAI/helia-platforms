"""Tests for the snapshot extractor in ``scripts/snapshot_extractor`` (ADR 0006, issue #71).

The parsers are tested on excerpts shaped like the sources ADR 0006 cites; the
committed snapshots are checked offline for form. Regenerating them needs the
network and runs in the Snapshots workflow instead.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

from helia_platforms import _check_sources
from helia_platforms.catalog import builtin
from snapshot_extractor import (
    EXTRACTOR_VERSION,
    ExtractError,
    cdefines,
    cexpr,
    cli,
    cmake,
    devicetree,
    kconfig,
    linker,
    references,
    sdk,
    snapshot,
)
from snapshot_extractor.git import Checkout, resolve

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "snapshots"


# cexpr


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(0x10000000UL)", 0x10000000),
        ("(64UL * 1024UL)", 65536),
        ("(uint32_t)(0x1 << 3)", 8),
        ("((unsigned long) 7)", 7),
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("-7 / 2", -3),
        ("-7 % 2", -1),
        ("010", 8),
        ("0x10ULL", 16),
        ("1 << 4 | 1", 17),
        ("!0 && 1", 1),
    ],
)
def test_evaluates_c_integer_expressions(text: str, expected: int) -> None:
    assert cexpr.evaluate(text) == expected


def test_size_suffixes_only_where_allowed() -> None:
    assert cexpr.evaluate("976K", size_suffixes=True) == 976 * 1024
    assert cexpr.evaluate("2M", size_suffixes=True) == 2 * 1024 * 1024
    with pytest.raises(ExtractError, match="suffix"):
        cexpr.evaluate("976K")


def test_names_resolve_through_the_given_table() -> None:
    assert cexpr.evaluate("BASE + SIZE", {"BASE": 0x100, "SIZE": 0x10}) == 0x110
    with pytest.raises(ExtractError, match="UNKNOWN is not an integer"):
        cexpr.evaluate("UNKNOWN + 1")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0 && (1 / 0)", 0),
        ("1 || UNKNOWN", 1),
        ("0 && UNKNOWN || 1", 1),
        ("1 || (0 && 1 / 0) + UNKNOWN", 1),
        ("1 && 2", 1),
        ("0 || 3", 1),
    ],
)
def test_logical_operators_short_circuit(text: str, expected: int) -> None:
    assert cexpr.evaluate(text) == expected


def test_the_evaluated_operand_of_a_logical_operator_still_resolves() -> None:
    with pytest.raises(ExtractError, match="UNKNOWN is not an integer"):
        cexpr.evaluate("1 && UNKNOWN")
    with pytest.raises(ExtractError, match="division by zero"):
        cexpr.evaluate("0 || 1 / 0")


@pytest.mark.parametrize("text", ["(1 + 2", "1 +", "1 2", "1 @ 2", ""])
def test_malformed_expressions_raise(text: str) -> None:
    with pytest.raises(ExtractError):
        cexpr.evaluate(text)


# cdefines

# Shaped like apollo4l's am_reg_base_addresses.h:51-68 at nsx-ambiq-sdk v5.2.24.
REGISTER_HEADER = """\
#ifndef AM_REG_BASE_ADDRESSES_H
#define AM_REG_BASE_ADDRESSES_H
#define SRAM_BASEADDR                           (0x10000000UL)
#define TCM_MAX_SIZE                            (384UL * 1024UL) // trailing comment
#define SSRAM0_BASEADDR                         (SRAM_BASEADDR + TCM_MAX_SIZE)
#define SSRAM0_MAX_SIZE                         (1024UL * 1024UL)
#define EXTRAM_MAX_SIZE                         (0)
#define SSRAM1_MAX_SIZE                         (0)
/* #define COMMENTED_OUT 1 */
#if 0 // These are valid for Apollo4P.
#define EXTRAM_BASEADDR                         (SSRAM0_BASEADDR + SSRAM0_MAX_SIZE)
#define EXTRAM_MAX_SIZE                         (128UL * 1024UL)
#define SSRAM1_BASEADDR                         (EXTRAM_BASEADDR + EXTRAM_MAX_SIZE)
#else
#define AFTER_ELSE                              (2)
#endif // 0
#define SSRAM_MAX_SIZE                          (SSRAM0_MAX_SIZE + \\
                                                 SSRAM1_MAX_SIZE)
#define __IM                                    __I
#define AM_REGADDR(base, off)                   ((base) + (off))
#endif
"""


def test_collect_skips_if_zero_and_reads_its_else() -> None:
    found = cdefines.collect(REGISTER_HEADER)
    assert "SSRAM1_BASEADDR" not in found
    assert "COMMENTED_OUT" not in found
    assert "AM_REGADDR" not in found  # function-like
    assert found["EXTRAM_MAX_SIZE"] == ["(0)"]
    assert found["AFTER_ELSE"] == ["(2)"]


def test_integers_evaluate_and_drop_non_integers() -> None:
    found = cdefines.collect(REGISTER_HEADER)
    values = cdefines.Defines(found).integers(found)
    assert values == {
        "SRAM_BASEADDR": 0x10000000,
        "TCM_MAX_SIZE": 393216,
        "SSRAM0_BASEADDR": 0x10060000,
        "SSRAM0_MAX_SIZE": 1048576,
        "EXTRAM_MAX_SIZE": 0,
        "SSRAM1_MAX_SIZE": 0,
        "AFTER_ELSE": 2,
        "SSRAM_MAX_SIZE": 1048576,
    }


def test_if_one_skips_its_else() -> None:
    found = cdefines.collect(
        "#if 1\n#define A 1\n#elif X\n#define A 2\n#else\n#define A 3\n#endif\n"
    )
    assert found == {"A": ["1"]}


def test_other_conditionals_read_both_branches_and_conflicts_are_ambiguous() -> None:
    found = cdefines.collect("#ifdef X\n#define A 1\n#else\n#define A 2\n#endif\n#define B A\n")
    defines = cdefines.Defines(found)
    with pytest.raises(cdefines.AmbiguousDefine):
        defines.value("B")


def test_collect_stops_at_the_stop_line_even_inside_a_conditional() -> None:
    text = '#ifdef __cplusplus\n#define __FPU_DP 1\n#include "core_cm55.h"\n#define LATE 2\n'
    found = cdefines.collect(text, stop=re.compile(r'\s*#\s*include\s+"core_'))
    assert found == {"__FPU_DP": ["1"]}


def test_unbalanced_conditionals_raise() -> None:
    with pytest.raises(ExtractError, match="unterminated"):
        cdefines.collect("#if 0\n")
    with pytest.raises(ExtractError, match="without #if"):
        cdefines.collect("#endif\n")


def test_later_tables_win_and_recursion_is_not_an_integer() -> None:
    defines = cdefines.Defines({"A": ["1"], "LOOP": ["LOOP + 1"]}, {"A": ["2"]})
    assert defines.value("A") == 2
    assert defines.value("LOOP") is None


# cmake

# Shaped like cmake/socs/facts/apollo510.cmake:29,34-45 at nsx-ambiq-sdk v5.2.24.
FACTS = """\
# Single source of truth.
set(NSX_SOC_SERIES "apollo5")
set(NSX_SOC_CAPABILITIES core:m55 isa:armv8.1-m dsp)
set(NSX_SOC_HAS_MVE TRUE)
set(NSX_FPU "")  # declared empty
set(NSX_SOC_COMPILE_DEFINITIONS
    PART_apollo510
    # a comment inside the list
    NSX_SOC_CORE_M55=1
)
set(NSX_SEGGER_PF_ADDR "0x00410000")
#[[ set(BRACKET_COMMENTED 1) ]]
set(NSX_QUOTED "a \\"b\\" c")
"""


def test_set_values_keep_values_as_written() -> None:
    assert cmake.set_values(FACTS) == {
        "NSX_SOC_SERIES": ["apollo5"],
        "NSX_SOC_CAPABILITIES": ["core:m55", "isa:armv8.1-m", "dsp"],
        "NSX_SOC_HAS_MVE": ["TRUE"],
        "NSX_FPU": [""],
        "NSX_SOC_COMPILE_DEFINITIONS": ["PART_apollo510", "NSX_SOC_CORE_M55=1"],
        "NSX_SEGGER_PF_ADDR": ["0x00410000"],
        "NSX_QUOTED": ['a "b" c'],
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("if(X)\n  set(A 1)\nendif()\n", "inside if"),
        ("set(A 1)\nset(A 2)\n", "set twice"),
        ('set(A 1 CACHE STRING "")\n', "CACHE"),
        ("set(A 1 PARENT_SCOPE)\n", "CACHE or PARENT_SCOPE"),
        ('set(A "unterminated)\n', "unterminated"),
    ],
)
def test_set_values_reject_what_needs_cmake_evaluation(text: str, message: str) -> None:
    with pytest.raises(ExtractError, match=message):
        cmake.set_values(text)


# The two default-script forms ADR 0006 cites: apollo510.cmake:23,28 and apollo3p.cmake:21,24.
SELECTED = """\
nsx_toolchain_is_armclang(NSX_TOOLCHAIN_IS_ARMCLANG)
if(NSX_TOOLCHAIN_IS_ARMCLANG)
    set(_nsx_linker_script_default "${CORE}/apollo510/armclang/linker_script_sbl.sct")
    set(_nsx_linker_script_itcm "${CORE}/apollo510/armclang/linker_script_itcm_sbl.sct")
else()
    set(_nsx_linker_script_default "${CORE}/apollo510/gcc/linker_script_sbl.ld")
endif()
if(NOT DEFINED NSX_LINKER_SCRIPT)
    if(COMMAND nsx_select_linker_script)
        nsx_select_linker_script(
            DEFAULT "${_nsx_linker_script_default}" ITCM "${_nsx_linker_script_itcm}"
        )
    else()
        set(NSX_LINKER_SCRIPT "${_nsx_linker_script_default}")
    endif()
endif()
"""
DIRECT = """\
if(NSX_TOOLCHAIN_IS_ARMCLANG)
    set(NSX_LINKER_SCRIPT "${CORE}/apollo3p/armclang/linker_script.sct")
else()
    set(NSX_LINKER_SCRIPT "${CORE}/apollo3p/gcc/linker_script.ld")
endif()
"""


def test_default_scripts_read_both_forms() -> None:
    assert cmake.default_scripts(SELECTED) == {
        "armclang": "${CORE}/apollo510/armclang/linker_script_sbl.sct",
        "gcc": "${CORE}/apollo510/gcc/linker_script_sbl.ld",
    }
    assert cmake.default_scripts(DIRECT) == {
        "armclang": "${CORE}/apollo3p/armclang/linker_script.sct",
        "gcc": "${CORE}/apollo3p/gcc/linker_script.ld",
    }


def test_default_scripts_without_a_branch_and_errors() -> None:
    single = 'set(NSX_LINKER_SCRIPT "${NSX_CORE_DIR}/src/apollo3/gcc/linker_script.ld")\n'
    assert cmake.default_scripts(single) == {
        "gcc": "${NSX_CORE_DIR}/src/apollo3/gcc/linker_script.ld"
    }
    with pytest.raises(ExtractError, match="no default"):
        cmake.default_scripts("set(OTHER 1)\n")
    with pytest.raises(ExtractError, match="toolchain"):
        cmake.default_scripts('set(NSX_LINKER_SCRIPT "x/iar/a.icf")\n')
    with pytest.raises(ExtractError, match="two default gcc"):
        cmake.default_scripts(single + single)


# linker

# Shaped like apollo510/gcc/linker_script_sbl.ld:14-15 and apollo3/gcc/linker_script.ld:10.
GNU_SCRIPT = """\
MEMORY
{
    MCU_MRAM     (rx)  : ORIGIN = 0x00410000, LENGTH = 4128768
    RWMEM (rwx) : ORIGIN = 0x10000000, LENGTH = 384K
    NOATTR : org = 0x0, len = 1M
    /* STACK        (rw)  : ORIGIN = 0x2007D000, LENGTH = 12288
    HEAP         (rw)  : ORIGIN = 0x2007C000, LENGTH = 4096 */
}
SECTIONS { .text : { *(.text) } > MCU_MRAM }
"""


def test_gnu_memory_reads_regions_and_skips_comments() -> None:
    assert linker.gnu_memory(GNU_SCRIPT) == {
        "MCU_MRAM": {"attributes": "rx", "length": 4128768, "origin": 0x00410000},
        "RWMEM": {"attributes": "rwx", "length": 384 * 1024, "origin": 0x10000000},
        "NOATTR": {"length": 1024 * 1024, "origin": 0},
    }


def test_gnu_memory_rejects_unreadable_blocks() -> None:
    with pytest.raises(ExtractError, match="one MEMORY block"):
        linker.gnu_memory("SECTIONS {}")
    with pytest.raises(ExtractError, match="cannot read MEMORY line"):
        linker.gnu_memory("MEMORY {\nA ORIGIN 0\n}")
    with pytest.raises(ExtractError, match="ORIGIN is not an integer"):
        linker.gnu_memory("MEMORY {\nA : ORIGIN = ORIGIN(B), LENGTH = 1\n}")
    with pytest.raises(ExtractError, match="twice"):
        linker.gnu_memory("MEMORY {\nA : o = 0, l = 1\nA : o = 1, l = 1\n}")


# Shaped like apollo510/armclang/linker_script_sbl.sct:26,39.
SCATTER = """\
; Make this 0x400000 for NBL, 0x410000 for normal
LR_1 0x00410000
{
    MCU_MRAM 0x00410000 0x003F0000
    {
        *.o (RESET, +First)
        * (+RO)
    }
    MCU_TCM 0x20000000 0x0007B000 { * (+RW, +ZI) }
    ARM_LIB_HEAP  0x2007B000 EMPTY  0x00001000
    {   ; Reserve empty region for heap
    }
    ARM_LIB_STACK 0x20080000 EMPTY - 0x00004000
    {
    }
    NOINIT 0x20100000 UNINIT 0x100 { * (.noinit) }
}
"""


def test_scatter_regions_record_empty_ranges() -> None:
    assert linker.scatter_regions(SCATTER) == {
        "MCU_MRAM": {"length": 0x3F0000, "origin": 0x410000},
        "MCU_TCM": {"length": 0x7B000, "origin": 0x20000000},
        "ARM_LIB_HEAP": {"empty": True, "length": 0x1000, "origin": 0x2007B000},
        "ARM_LIB_STACK": {"empty": True, "length": 0x4000, "origin": 0x2007C000},
        "NOINIT": {"attributes": ["UNINIT"], "length": 0x100, "origin": 0x20100000},
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("LR 0x0 { ER +0 0x10 { } }", "no absolute base"),
        ("LR 0x0 { ER 0x0 -0x10 { } }", "only for an EMPTY"),
        ("LR 0x0 { ER 0x0 ALIGN 8 { } }", "cannot read"),
        ("LR 0x0 { ER 0x0 0x10 { } ER 0x10 0x10 { } }", "declared twice"),
        ("LR 0x0 { ER 0x0 0x10 { ", "unterminated"),
    ],
)
def test_scatter_regions_reject_unsupported_forms(text: str, message: str) -> None:
    with pytest.raises(ExtractError, match=message):
        linker.scatter_regions(text)


# kconfig

# Shaped like soc/ambiq/apollo3x/Kconfig.defconfig.apollo3_blue:40-43 at zephyr 8f62a4ab.
KCONFIG_FILES = {
    "soc/v/Kconfig.defconfig": 'if SOC_FAMILY_V\nrsource "*/Kconfig.defconfig"\nendif\n',
    "soc/v/s1/Kconfig.defconfig": 'if SOC_SERIES_S1\nrsource "Kconfig.defconfig.*"\nendif\n',
    "soc/v/s1/Kconfig.defconfig.a": (
        "if SOC_A\n\nconfig NUM_IRQS\n\tdefault 31\n\n"
        "config FLASH_LOAD_OFFSET\n\tdefault 0x1000 if BT\n\nif !BOOTLOADER_MCUBOOT\n\n"
        "config FLASH_LOAD_OFFSET\n\tdefault 0xc000\n\thelp\n\t  default 0x9999 in help\n\n"
        "endif # !BOOTLOADER_MCUBOOT\n\nendif # SOC_A\n"
    ),
    "soc/v/s1/Kconfig.defconfig.b": "if SOC_B\nconfig NUM_IRQS\n\tdefault 33\nendif\n",
}
ENABLED_A = frozenset({"SOC_FAMILY_V", "SOC_SERIES_S1", "SOC_A"})


@pytest.fixture
def kconfig_tree(tmp_path: Path) -> Path:
    for name, text in KCONFIG_FILES.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_kconfig_default_without_mcuboot(kconfig_tree: Path) -> None:
    found = kconfig.soc_default(
        kconfig_tree, "soc/v/Kconfig.defconfig", "FLASH_LOAD_OFFSET", ENABLED_A
    )
    assert found == ("soc/v/s1/Kconfig.defconfig.a", 0xC000)


def test_kconfig_default_absent_for_another_soc(kconfig_tree: Path) -> None:
    enabled = frozenset({"SOC_FAMILY_V", "SOC_SERIES_S1", "SOC_B"})
    assert (
        kconfig.soc_default(kconfig_tree, "soc/v/Kconfig.defconfig", "FLASH_LOAD_OFFSET", enabled)
        is None
    )


def test_kconfig_condition_outside_scope_raises(tmp_path: Path) -> None:
    (tmp_path / "K").write_text("if A || B\nconfig X\n\tdefault 1\nendif\n", encoding="utf-8")
    with pytest.raises(ExtractError, match="cannot evaluate"):
        kconfig.soc_default(tmp_path, "K", "X", frozenset())


# devicetree


def test_preprocess_expands_macros_in_node_names_and_keeps_cell_properties(tmp_path: Path) -> None:
    include = tmp_path / "include"
    include.mkdir()
    (include / "soc.h").write_text(
        "#define SSRAM_BASE_NAME 20080000\n#define SSRAM_BASE_ADDR 0x20080000UL\n", encoding="utf-8"
    )
    source = tmp_path / "board.dts"
    source.write_text(
        "/dts-v1/;\n#include <soc.h>\n/ {\n\t#address-cells = <1>;\n"
        "\tsram0: memory@SSRAM_BASE_NAME {\n\t\treg = <SSRAM_BASE_ADDR 0x200000>;\n\t};\n};\n",
        encoding="utf-8",
    )
    text = devicetree.preprocess(source, [include])
    assert "#address-cells = <1>;" in text
    assert "memory@20080000" in text
    assert "reg = <0x20080000UL 0x200000>;" in text


def test_preprocess_reports_a_missing_include(tmp_path: Path) -> None:
    source = tmp_path / "board.dts"
    source.write_text("#include <missing.h>\n", encoding="utf-8")
    with pytest.raises(ExtractError, match="preprocessing failed"):
        devicetree.preprocess(source, [])


class _Prop:
    """The part of ``dtlib.Property`` the extractor reads."""

    def __init__(self, value: Any) -> None:
        self.value: Any = b"" if value is None else value

    def to_num(self) -> Any:
        return self.value

    def to_nums(self) -> Any:
        return self.value

    def to_strings(self) -> Any:
        return self.value

    def to_string(self) -> Any:
        return self.value


class _Node:
    def __init__(self, path: str, parent: _Node | None, labels: list[str], **props: Any) -> None:
        self.path, self.parent, self.labels = path, parent, labels
        cells = {"address_cells": "#address-cells", "size_cells": "#size-cells"}
        self.props = {cells.get(key, key): _Prop(value) for key, value in props.items()}


class _Tree:
    def __init__(self, nodes: list[_Node]) -> None:
        self.nodes = nodes

    def node_iter(self) -> list[_Node]:
        return self.nodes


def test_memory_nodes_take_cpu_addresses_through_identity_ranges() -> None:
    root = _Node("/", None, [], address_cells=1, size_cells=1)
    soc = _Node("/soc", root, [], ranges=None, address_cells=1, size_cells=1)
    flash = _Node(
        "/soc/flash@410000", soc, ["flash0"], compatible=["soc-nv-flash"], reg=[0x410000, 0x3F0000]
    )
    sram = _Node("/memory@20080000", root, ["sram0", "sram"], device_type="memory", reg=[1, 2])
    cpu = _Node("/cpus/cpu@0", root, [], device_type="cpu", reg=[0])
    assert devicetree.memory_nodes(_Tree([root, soc, flash, sram, cpu])) == {
        "/soc/flash@410000": {
            "base": 0x410000,
            "compatible": ["soc-nv-flash"],
            "labels": ["flash0"],
            "size": 0x3F0000,
        },
        "/memory@20080000": {"base": 1, "labels": ["sram", "sram0"], "size": 2},
    }


def test_memory_nodes_reject_translated_buses_and_several_reg_entries() -> None:
    root = _Node("/", None, [], address_cells=1, size_cells=1)
    bus = _Node("/bus", root, [], ranges=b"\x00", address_cells=1, size_cells=1)
    node = _Node("/bus/m@0", bus, [], compatible=["mmio-sram"], reg=[0, 1])
    with pytest.raises(ExtractError, match="1:1"):
        devicetree.memory_nodes(_Tree([node]))
    double = _Node("/m@0", root, [], compatible=["mmio-sram"], reg=[0, 1, 2, 3])
    with pytest.raises(ExtractError, match="one reg entry"):
        devicetree.memory_nodes(_Tree([double]))


# snapshot


def test_dumps_is_the_normalised_form() -> None:
    data = snapshot.dumps({"b": [1, {"y": "é", "x": 2}], "a": {}})
    expected = (
        '{\n  "a": {},\n  "b": [\n    1,\n    {\n      "x": 2,\n'
        '      "y": "\\u00e9"\n    }\n  ]\n}\n'
    )
    assert data == expected.encode("ascii")


def test_summary_prints_integers_in_hex() -> None:
    old = {"s": {"base": 16, "gone": "x", "same": [1]}}
    new = {"s": {"base": 32, "new": True, "same": [1]}}
    assert snapshot.summary(old, new) == [
        "~ s > base: 0x10 -> 0x20",
        '- s > gone: "x"',
        "+ s > new: true",
    ]


# references


def test_count_definitions_by_file_kind() -> None:
    assert references.count_definitions(FACTS, "cmake/socs/facts/a.cmake", "NSX_FPU") == 1
    assert references.count_definitions(FACTS, "CMakeLists.txt", "NSX_MISSING") == 0
    header = (
        "#define A 1\n// #define A 2\n#  define B 2\n"
        "typedef enum { E_ONE = 1, E_TWO, A } e_t;\nenum other { E_TWO };\n"
    )
    assert references.count_definitions(header, "x.h", "A") == 2
    assert references.count_definitions(header, "x.h", "B") == 1
    assert references.count_definitions(header, "x.h", "E_ONE") == 1
    assert references.count_definitions(header, "x.h", "E_TWO") == 2


def test_find_and_check_references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sdk = "AmbiqAI/nsx-ambiq-sdk"
    (tmp_path / "socs").mkdir()
    (tmp_path / "socs" / "a.yaml").write_text(
        yaml.safe_dump(
            {
                "provenance": {
                    "source": [
                        f"repo:{sdk}@v1:facts.cmake#NSX_FPU",
                        f"repo:{sdk}@v1:facts.cmake:3-4#NSX_MISSING",
                        f"repo:{sdk}@v1:gone.h#X",
                        f"repo:{sdk}@v9:facts.cmake#NSX_FPU",
                        f"repo:{sdk}@v1:facts.cmake",
                        "repo:AmbiqAI/helia-aot@v1:a.py#X",
                        "doc:DS@1:p1",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    found = references.find(tmp_path)
    assert [(r.revision, r.path, r.symbol) for r in found] == [
        ("v1", "facts.cmake", "NSX_FPU"),
        ("v1", "facts.cmake", "NSX_MISSING"),
        ("v1", "gone.h", "X"),
        ("v9", "facts.cmake", "NSX_FPU"),
    ]
    files = {"facts.cmake": FACTS}
    monkeypatch.setattr(Checkout, "blob", lambda self, path: files.get(path))
    checkout = Checkout("AmbiqAI/nsx-ambiq-sdk", "v1", "0" * 40, tmp_path)
    problems = references.check(found, lambda _, rev: checkout if rev == "v1" else None)
    assert len(problems) == 3
    assert "NSX_MISSING: 0 definitions, expected one" in problems[0]
    assert "no such file" in problems[1]
    assert "no such revision" in problems[2]


# git and cli


def test_resolve_returns_a_full_sha_unchanged() -> None:
    assert resolve("AmbiqAI/neuralspotx", "a" * 40) == "a" * 40


def test_recorded_pins_and_version_order() -> None:
    docs = {
        name: json.loads((SNAPSHOTS / file).read_text()) for name, file in snapshot.FILES.items()
    }
    recorded = cli._recorded(docs)
    assert (
        recorded[("AmbiqAI/nsx-ambiq-sdk", "v5.2.26")] == "ba0621638d57b71a7b0d4f76ddccf0706745ad77"
    )
    assert cli._pin(docs["neuralspotx"], "AmbiqAI/neuralspotx") == "neuralspotx-v0.9.0"
    assert sorted(["v5.2.10", "v5.2.9"], key=cli._version_key) == ["v5.2.9", "v5.2.10"]


# The committed snapshots


@pytest.mark.parametrize("file", sorted(snapshot.FILES.values()))
def test_committed_snapshot_is_normalised(file: str) -> None:
    data = (SNAPSHOTS / file).read_bytes()
    document = json.loads(data)
    assert snapshot.dumps(document) == data
    metadata = document["metadata"]
    assert metadata["extractor_version"] == EXTRACTOR_VERSION
    for source in metadata["sources"]:
        assert set(source) == {"commit", "repository", "revision"}
        assert re.fullmatch(r"[0-9a-f]{40}", source["commit"])


def test_sdk_snapshot_covers_every_soc_the_extractor_knows() -> None:
    """The SDK pins are helia-platforms' own, not neuralspotx's lock (#18)."""
    document = json.loads((SNAPSHOTS / "nsx-ambiq-sdk.json").read_text())
    assert set(document["socs"]) == set(sdk.HEADERS)
    revisions = {source["revision"] for source in document["metadata"]["sources"]}
    assert {block["revision"] for block in document["socs"].values()} == revisions


def test_an_empty_snapshot_directory_extracts_neuralspotx_at_its_frozen_pin(tmp_path, monkeypatch):
    seen = {}

    def extract_all(sources, nsx_revision, sdk_pins, zephyr_revision):
        seen.update(nsx=nsx_revision, sdk=set(sdk_pins.values()), zephyr=zephyr_revision)
        raise ExtractError("stop")

    monkeypatch.setattr(cli, "extract_all", extract_all)
    args = ["--snapshots", str(tmp_path), "--cache", str(tmp_path / "cache"), "extract"]
    assert cli.main([*args, "--sdk", "v9", "--zephyr", "a" * 40]) == 2
    assert seen == {"nsx": "neuralspotx-v0.9.0", "sdk": {"v9"}, "zephyr": "a" * 40}


def test_sdk_pins_come_from_the_sdk_snapshot_unless_a_refresh_names_a_tag() -> None:
    committed = {"socs": {"apollo510": {"revision": "v1"}, "apollo3": {"revision": "v2"}}}
    assert cli._sdk_pins(committed, None) == {"apollo510": "v1", "apollo3": "v2"}
    assert cli._sdk_pins(committed, "v3") == dict.fromkeys(sorted(sdk.HEADERS), "v3")
    assert cli._sdk_pins(None, None) == {}


def unnamed(directory: Path) -> list[tuple[str, ...]]:
    """Exception paths the snapshot lacks, except where a finding is at exactly that path."""
    path = directory / "exceptions.yaml"
    result = _check_sources.check(builtin(include_plugins=False), directory)
    exact = {e for f, e in result.excepted if f.at == e.at and f.rule != _check_sources.MISSING}
    lacking = []
    for exception in _check_sources.load_exceptions(path):
        value: Any = json.loads((directory / exception.snapshot).read_text())
        for key in exception.at:
            if not isinstance(value, dict) or key not in value:
                if key != exception.at[-1] or exception not in exact:
                    lacking.append(exception.at)
                break
            value = value[key]
    return lacking


def test_exceptions_name_snapshot_values() -> None:
    entries = yaml.safe_load((SNAPSHOTS / "exceptions.yaml").read_text())["exceptions"]
    assert entries
    for entry in entries:
        assert set(entry) == {"snapshot", "at", "rule", "reason", "issue"}
        assert re.fullmatch(r"(?:[\w.-]+/[\w.-]+)?#\d+", entry["issue"])
    assert unnamed(SNAPSHOTS) == []


def test_an_exception_path_the_snapshot_lacks_needs_a_finding_there(tmp_path: Path) -> None:
    directory = tmp_path / "snapshots"
    shutil.copytree(SNAPSHOTS, directory)
    sdk_path = directory / "nsx-ambiq-sdk.json"
    data = json.loads(sdk_path.read_text())
    del data["socs"]["apollo3"]["flash"]["values"]["AM_HAL_FLASH_TOTAL_SIZE"]
    sdk_path.write_text(json.dumps(data))
    added = [
        (["socs", "apollo3", "flash", "values", "AM_HAL_FLASH_TOTAL_SIZE"], "flash header"),
        (["socs", "apollo3", "flash", "values", "AM_HAL_FLASH_TYPO"], "flash header"),
        (["socs", "apollo2", "linker", "gcc", "scripts", "typo.ld"], "region containment"),
    ]
    path = directory / "exceptions.yaml"
    document = yaml.safe_load(path.read_text())
    document["exceptions"] += [
        {"snapshot": _check_sources.SDK, "at": at, "rule": rule, "reason": "x", "issue": "#1"}
        for at, rule in added
    ]
    path.write_text(yaml.safe_dump(document))
    assert unnamed(directory) == [tuple(at) for at, _ in added[1:]]


def test_extractor_dependencies_are_not_runtime_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = " ".join(project["project"]["dependencies"])
    assert "pcpp" not in runtime
    assert any(spec.startswith("pcpp") for spec in project["dependency-groups"]["extract"])
