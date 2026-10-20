"""Generate the JSON Schema (draft 2020-12) of the file format from ``_format`` (ADR 0002 §3)."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, get_args

from helia_platforms import _format as fmt
from helia_platforms import _walk

SCHEMA_ID = f"tag:ambiq.com,2026:helia-platforms/schema/v{fmt.SCHEMA_VERSION}"
SCHEMA_FILE = f"helia-platforms-v{fmt.SCHEMA_VERSION}.schema.json"
EXPORT_SCHEMA_ID = f"tag:ambiq.com,2026:helia-platforms/export/v{fmt.SCHEMA_VERSION}"
EXPORT_SCHEMA_FILE = f"helia-platforms-export-v{fmt.SCHEMA_VERSION}.schema.json"


class _Generator:
    def __init__(self) -> None:
        self.defs: dict[str, Any] = {}

    def ref(self, obj: type) -> dict[str, Any]:
        name = obj.__name__.lstrip("_")
        if name not in self.defs:
            self.defs[name] = {}  # placeholder, so recursion terminates
            self.defs[name] = self.object(obj)
        return {"$ref": f"#/$defs/{name}"}

    def object(self, obj: type) -> dict[str, Any]:
        declared = _walk.fields(obj)
        facts = _walk.carries_facts(obj)
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                name: self.field_schema(field.type, facts) for name, field in declared.items()
            },
            "additionalProperties": False,
        }
        required = [name for name, field in declared.items() if field.required]
        if required and _walk.is_inheritable(obj):
            # An entry with based_on gets its required keys from the base (section 2.5).
            schema["if"] = {"required": ["based_on"]}
            schema["else"] = {"required": required}
        elif required:
            schema["required"] = required
        return schema

    def field_schema(self, tp: Any, facts: bool) -> dict[str, Any]:
        bare, markers = _walk.unwrap(tp)
        if fmt.NOT_FACT in markers:
            facts = False
        if fmt.OPAQUE in markers:
            return {}
        schema = self.plain(bare, markers, facts)
        if facts and _walk.is_scalar_like(tp):
            wrapper = {
                "type": "object",
                "properties": {"value": schema, "provenance": self.ref(fmt.Provenance)},
                "required": ["value", "provenance"],
                "additionalProperties": False,
            }
            return {"anyOf": [schema, wrapper]}
        return schema

    def plain(self, bare: Any, markers: tuple, facts: bool) -> dict[str, Any]:  # noqa: PLR0911
        if fmt.SIZE in markers:
            return {
                "anyOf": [
                    {"type": "integer", "minimum": 0},
                    {"type": "string", "pattern": fmt.SIZE_RE},
                ]
            }
        if _walk.is_object(bare):
            return self.ref(bare)
        if _walk.is_union(bare) and set(get_args(bare)) <= {int, float}:
            return self.number("number", markers)
        if _walk.is_union(bare):
            return {"anyOf": [self.field_schema(arg, facts) for arg in get_args(bare)]}
        if _walk.is_literal(bare):
            return {"enum": list(get_args(bare))}
        origin = getattr(bare, "__origin__", None)
        if origin is dict:
            key_tp, item_tp = get_args(bare)
            return {
                "type": "object",
                "propertyNames": self.plain(*_walk.unwrap(key_tp), facts=False),
                "additionalProperties": self.field_schema(item_tp, facts),
            }
        if origin is list:
            (item_tp,) = get_args(bare)
            schema: dict[str, Any] = {"type": "array", "items": self.field_schema(item_tp, facts)}
            if fmt.BY_VALUE in markers:
                schema["uniqueItems"] = True
            return schema
        if bare is str:
            pattern = _walk.marker(markers, fmt.Pattern)
            return {"type": "string", **({"pattern": pattern.regex} if pattern else {})}
        if bare is bool:
            return {"type": "boolean"}
        if bare is type(None):
            return {"type": "null"}
        if bare is int:
            return self.number("integer", markers)
        raise TypeError(f"no schema for {bare!r}")

    @staticmethod
    def number(kind: str, markers: tuple) -> dict[str, Any]:
        minimum = _walk.marker(markers, fmt.Minimum)
        return {"type": kind, **({"minimum": minimum.value} if minimum else {})}


def generate() -> dict[str, Any]:
    """Return the JSON Schema of the current schema version."""
    generator = _Generator()
    document = generator.object(fmt.Document)
    document["properties"] = {"$schema": {"type": "string"}, **document["properties"]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "helia-platforms catalog file",
        **document,
        "$defs": dict(sorted(generator.defs.items())),
    }


def generate_export() -> dict[str, Any]:
    """The JSON Schema of the whole export, with the file-format schema bundled for ``catalog``.

    Each ``schema_version`` must be this version (RFC 0003 "Schema and versioning").
    """
    generator = _Generator()
    version = {"const": fmt.SCHEMA_VERSION}
    export = {
        "type": "object",
        "properties": {
            "schema_version": version,
            "identity": generator.ref(fmt.ExportIdentity),
            "catalog": {
                "allOf": [{"$ref": SCHEMA_ID}, {"properties": {"schema_version": version}}]
            },
        },
        "additionalProperties": False,
        "required": list(_walk.fields(fmt.Export)),
    }
    generator.defs["ExportIdentity"]["properties"]["schema_version"] = version
    file_format = {k: v for k, v in generate().items() if k != "$schema"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": EXPORT_SCHEMA_ID,
        "title": "helia-platforms catalog export",
        **export,
        "$defs": {**dict(sorted(generator.defs.items())), "file-format": file_format},
    }


def render(*, export: bool = False) -> str:
    """A schema as committed: two-space JSON with a trailing newline."""
    return json.dumps(generate_export() if export else generate(), indent=2) + "\n"


def committed(*, export: bool = False) -> str:
    """A schema file shipped in the wheel."""
    name = EXPORT_SCHEMA_FILE if export else SCHEMA_FILE
    return resources.files(__name__).joinpath(name).read_text()
