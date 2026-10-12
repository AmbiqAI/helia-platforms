"""Preprocess a Zephyr board devicetree with pcpp and read it with dtlib.

dtlib is loaded from the pinned Zephyr commit (``scripts/dts/python-devicetree``),
as ADR 0006 section 3 specifies, so its parsing follows the revision it reads.
pcpp stands in for ``cpp -x assembler-with-cpp -nostdinc -undef -D__DTS__``.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

from pcpp import Preprocessor

from snapshot_extractor import ExtractError

DTLIB = "scripts/dts/python-devicetree/src/devicetree/dtlib.py"
MEMORY_COMPATIBLES = frozenset({"mmio-sram", "soc-nv-flash", "zephyr,memory-region"})
CHOSEN = ("zephyr,dtcm", "zephyr,flash", "zephyr,itcm", "zephyr,sram")
_loaded: dict[Path, ModuleType] = {}


def load_dtlib(zephyr_root: Path) -> ModuleType:
    """Import ``dtlib`` from a Zephyr checkout under a name of its own."""
    path = (zephyr_root / DTLIB).resolve()
    if path not in _loaded:
        name = f"_snapshot_dtlib_{len(_loaded)}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ExtractError(f"cannot import dtlib from {DTLIB}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _loaded[path] = module
    return _loaded[path]


class _Preprocessor(Preprocessor):
    """Collect errors instead of printing them."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self.line_directive = None
        self.define("__DTS__ 1")

    def on_error(self, file: str, line: int, msg: str) -> None:
        self.errors.append(f"{Path(file).name}:{line}: {msg}")


def preprocess(source: Path, include_dirs: list[Path]) -> str:
    """The C-preprocessed text of ``source``, searching ``include_dirs`` in order."""
    preprocessor = _Preprocessor()
    for directory in include_dirs:
        preprocessor.add_path(str(directory))
    preprocessor.parse(source.read_text(encoding="utf-8"), str(source))
    out = io.StringIO()
    preprocessor.write(out)
    if preprocessor.errors or preprocessor.return_code:
        raise ExtractError(f"{source.name}: preprocessing failed: {preprocessor.errors}")
    return out.getvalue()


def parse(dtlib: ModuleType, text: str, include_dirs: list[Path]) -> Any:
    """A ``dtlib.DT`` of preprocessed devicetree source."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "board.dts.pre"
        path.write_text(text, encoding="utf-8")
        try:
            return dtlib.DT(str(path), include_path=[str(d) for d in include_dirs])
        except dtlib.DTError as exc:
            raise ExtractError(f"devicetree: {exc}") from exc


def _cells(node: Any, name: str) -> int:
    prop = node.props.get(name)
    if prop is None:
        raise ExtractError(f"{node.path} has no {name}")
    return prop.to_num()


def _join(cells: list[int]) -> int:
    value = 0
    for cell in cells:
        value = (value << 32) | cell
    return value


def _region(node: Any) -> tuple[int, int]:
    """The CPU address and size of a node with a single ``reg`` entry."""
    parent = node.parent
    address_cells, size_cells = _cells(parent, "#address-cells"), _cells(parent, "#size-cells")
    cells = node.props["reg"].to_nums()
    if len(cells) != address_cells + size_cells:
        raise ExtractError(f"{node.path}: expected one reg entry, found {cells}")
    ancestor = parent
    while ancestor.parent is not None:  # every bus up to the root maps 1:1
        ranges = ancestor.props.get("ranges")
        if ranges is None or ranges.value != b"":
            raise ExtractError(f"{node.path}: {ancestor.path} does not map addresses 1:1")
        ancestor = ancestor.parent
    return _join(cells[:address_cells]), _join(cells[address_cells:])


def _is_memory(node: Any) -> bool:
    compatible = node.props.get("compatible")
    if compatible is not None and MEMORY_COMPATIBLES & set(compatible.to_strings()):
        return True
    device_type = node.props.get("device_type")
    return device_type is not None and device_type.to_string() == "memory"


def memory_nodes(dt: Any) -> dict[str, dict[str, Any]]:
    """Each memory node by path, with its labels, ``reg`` base and size."""
    nodes: dict[str, dict[str, Any]] = {}
    for node in dt.node_iter():
        if not _is_memory(node) or "reg" not in node.props:
            continue
        base, size = _region(node)
        entry: dict[str, Any] = {"base": base, "labels": sorted(node.labels), "size": size}
        if "compatible" in node.props:
            entry["compatible"] = node.props["compatible"].to_strings()
        if "zephyr,memory-region" in node.props:
            entry["zephyr,memory-region"] = node.props["zephyr,memory-region"].to_string()
        nodes[node.path] = entry
    return nodes


def chosen(dt: Any) -> dict[str, str]:
    """The node path of each memory ``chosen`` property the board sets."""
    if not dt.has_node("/chosen"):
        return {}
    node = dt.get_node("/chosen")
    return {name: node.props[name].to_path().path for name in CHOSEN if name in node.props}
