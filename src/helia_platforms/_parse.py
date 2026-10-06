"""Read catalogue files: YAML by the 1.2 core schema, and JSON (ADR 0002 section 2.6)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from helia_platforms.errors import FormatError

# YAML 1.2 core schema, plain scalars only (https://yaml.org/spec/1.2.2/#1023-core-schema).
_NULL = re.compile(r"^(?:~|null|Null|NULL|)$")
_BOOL = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
_INT = re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$")
_FLOAT = re.compile(
    r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
)


def _loader_class() -> type:
    import yaml  # noqa: PLC0415 (PyYAML loads with the loader, not the package; ADR 0002 §4)
    from yaml.constructor import ConstructorError  # noqa: PLC0415

    base = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

    class CoreSchemaLoader(base):  # type: ignore[misc, valid-type]
        yaml_implicit_resolvers: dict = {}  # noqa: RUF012

        def construct_yaml_int(self, node: Any) -> int:
            text = self.construct_scalar(node)
            if not _INT.fullmatch(text):  # an explicit !!int skips the resolver's check
                raise ConstructorError(
                    None, None, f"{text!r} is not a YAML 1.2 integer", node.start_mark
                )
            sign = -1 if text.startswith("-") else 1
            digits = text.lstrip("+-")
            if digits.startswith("0x"):
                return sign * int(digits[2:], 16)
            if digits.startswith("0o"):
                return sign * int(digits[2:], 8)
            return sign * int(digits, 10)

        def construct_mapping(self, node: Any, deep: bool = False) -> dict:
            if not isinstance(node, yaml.MappingNode):
                raise ConstructorError(
                    None, None, f"expected a mapping, found {node.id}", node.start_mark
                )
            mapping: dict = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str | int | float | bool | None):
                    raise ConstructorError(
                        "while reading a mapping",
                        node.start_mark,
                        "a mapping key must be a scalar",
                        key_node.start_mark,
                    )
                if key in mapping:
                    raise ConstructorError(
                        "while reading a mapping",
                        node.start_mark,
                        f"duplicate key {key!r}",
                        key_node.start_mark,
                    )
                mapping[key] = self.construct_object(value_node, deep=deep)
            return mapping

    resolver = CoreSchemaLoader.add_implicit_resolver
    resolver("tag:yaml.org,2002:null", _NULL, ["~", "n", "N", ""])
    resolver("tag:yaml.org,2002:bool", _BOOL, list("tTfF"))
    resolver("tag:yaml.org,2002:int", _INT, list("-+0123456789"))
    resolver("tag:yaml.org,2002:float", _FLOAT, list("-+0123456789.n"))
    CoreSchemaLoader.add_constructor("tag:yaml.org,2002:int", CoreSchemaLoader.construct_yaml_int)
    CoreSchemaLoader.add_constructor(
        "tag:yaml.org,2002:map", lambda loader, node: loader.construct_mapping(node, deep=True)
    )

    def reject(loader: Any, node: Any) -> None:  # YAML 1.1 types SafeLoader would build
        raise ConstructorError(
            None, None, f"{node.tag!r} is not a YAML 1.2 core schema tag", node.start_mark
        )

    for name in ("timestamp", "binary", "set", "omap", "pairs"):
        CoreSchemaLoader.add_constructor(f"tag:yaml.org,2002:{name}", reject)
    return CoreSchemaLoader


_LOADER: type | None = None


def parse_yaml(text: str, origin: str) -> Any:
    """Parse YAML text with the core-schema loader; raise FormatError on bad syntax."""
    import yaml  # noqa: PLC0415 (as above)

    global _LOADER  # noqa: PLW0603
    if _LOADER is None:
        _LOADER = _loader_class()
    try:
        return yaml.load(text, Loader=_LOADER)
    except yaml.YAMLError as exc:
        raise FormatError(f"{origin}: {exc}") from None
    except (ValueError, KeyError) as exc:  # explicit tags such as `!!float abc` or `!!bool x`
        raise FormatError(f"{origin}: a tagged value cannot be read: {exc}") from None
    except RecursionError:
        raise FormatError(f"{origin}: the document nests too deeply") from None


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def parse_json(text: str, origin: str) -> Any:
    """Parse JSON text, rejecting duplicate keys."""
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicates)
    except ValueError as exc:
        raise FormatError(f"{origin}: {exc}") from None


def parse_file(path: Path) -> Any:
    """Parse a ``.json`` file as JSON and anything else as YAML."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FormatError(f"{path}: cannot be read: {exc}") from None
    if path.suffix == ".json":
        return parse_json(text, str(path))
    return parse_yaml(text, str(path))
