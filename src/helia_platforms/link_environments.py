"""Link environments: the generated dataset and environment files (RFC 0002 "Link environments").

The dataset ships in the wheel beside the catalog but outside it (decided on #73);
``scripts/generate_link_environments.py`` writes it from the committed snapshots.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from helia_platforms import _parse, model
from helia_platforms.errors import FormatError, PlatformError

if TYPE_CHECKING:
    from helia_platforms.target import Target

#: The dataset file inside the package, and the version of its layout.
DATASET = "link_environments.json"
DATASET_FORMAT = 1
_FAMILIES = ("gnu", "armlink", "zephyr")
_STATUSES = ("public", "embargoed")
_ENVIRONMENT_KEYS = {
    "owner", "link_family", "profile", "applies_to", "regions", "source", "revision",
    "release_status",
}  # fmt: skip
_REGION_KEYS = {"start", "length", "reserved", "chosen"}


@functools.cache
def _dataset() -> Mapping[str, Any]:
    origin = f"helia_platforms/data/{DATASET}"
    text = (resources.files("helia_platforms") / "data" / DATASET).read_text(encoding="utf-8")
    data = _parse.parse_json(text, origin)
    if not isinstance(data, dict) or data.get("format") != DATASET_FORMAT:
        raise FormatError(f"{origin}: expected a mapping with format {DATASET_FORMAT}")
    environments = tuple(
        parse_environment(entry, f"{origin}: environments[{i}]")
        for i, entry in enumerate(data.get("environments", ()))
    )
    sources = tuple(MappingProxyType(dict(s)) for s in data.get("sources", ()))
    return MappingProxyType({"environments": environments, "sources": sources})


def link_environments(
    *, owner: str | None = None, link_family: str | None = None, profile: str | None = None
) -> tuple[model.LinkEnvironment, ...]:
    """The shipped environments, optionally narrowed by owner, link family and profile."""
    return tuple(
        e
        for e in _dataset()["environments"]
        if owner in (None, e.owner)
        and link_family in (None, e.link_family)
        and profile in (None, e.profile)
    )


def dataset_sources() -> tuple[Mapping[str, str], ...]:
    """Each snapshot source the dataset was generated from: repository, revision, commit."""
    return _dataset()["sources"]


def find_link_environment(
    target: Target,
    link_family: str,
    *,
    profile: str = "default",
    owner: str | None = None,
) -> model.LinkEnvironment | None:
    """The shipped environment of that family and profile that covers ``target``, if any.

    ``None`` means the dataset holds none, and the caller falls back to physical sizes.
    """
    found = [
        e
        for e in link_environments(owner=owner, link_family=link_family, profile=profile)
        if target.covered_by(e)
    ]
    if len(found) > 1:
        owners = ", ".join(sorted({e.owner for e in found}))
        raise PlatformError(f"{target.id}: several {link_family} environments cover it ({owners})")
    return found[0] if found else None


def load_link_environment(
    source: str | os.PathLike[str] | Mapping[str, Any],
) -> model.LinkEnvironment:
    """One environment from a YAML or JSON file, or a mapping, in the dataset's entry layout."""
    if isinstance(source, Mapping):
        return parse_environment(source, "<mapping>")
    path = Path(source)
    return parse_environment(_parse.parse_file(path), str(path))


def parse_environment(data: Any, origin: str) -> model.LinkEnvironment:
    """Build a ``LinkEnvironment`` from its mapping; raise ``FormatError`` listing each problem."""
    if not isinstance(data, Mapping):
        raise FormatError(f"{origin}: expected a mapping")
    problems = [f"{origin}: unknown key {k!r}" for k in sorted(set(data) - _ENVIRONMENT_KEYS)]
    for key in ("owner", "profile", "source", "revision"):
        if not isinstance(data.get(key), str) or not data[key]:
            problems.append(f"{origin}: {key} must be a non-empty string")
    if data.get("link_family") not in _FAMILIES:
        problems.append(f"{origin}: link_family must be one of {', '.join(_FAMILIES)}")
    if data.get("release_status", "embargoed") not in _STATUSES:
        problems.append(f"{origin}: release_status must be public or embargoed")
    applies_to = data.get("applies_to")
    if (
        not isinstance(applies_to, list)
        or not applies_to
        or not all(isinstance(i, str) and i for i in applies_to)
    ):
        problems.append(f"{origin}: applies_to must be a non-empty list of ids")
    regions = data.get("regions")
    if not isinstance(regions, Mapping) or not regions:
        problems.append(f"{origin}: regions must be a non-empty mapping")
        regions = {}
    built = {}
    for name, region in regions.items():
        at = f"{origin}: regions.{name}"
        if not isinstance(region, Mapping):
            problems.append(f"{at}: expected a mapping")
            continue
        problems += [f"{at}: unknown key {k!r}" for k in sorted(set(region) - _REGION_KEYS)]
        start, length = region.get("start"), region.get("length")
        if not _is_int(start) or start < 0 or not _is_int(length) or length < 0:
            problems.append(f"{at}: start and length must be integers of at least 0")
            continue
        chosen = region.get("chosen", [])
        if not isinstance(region.get("reserved", False), bool) or not isinstance(chosen, list):
            problems.append(f"{at}: reserved must be a boolean and chosen a list")
            continue
        built[name] = model.WindowRegion(
            start=start,
            length=length,
            reserved=region.get("reserved", False),
            chosen=tuple(chosen),
        )
    if problems:
        raise FormatError(problems[0], tuple(problems))
    return model.LinkEnvironment(
        owner=data["owner"],
        link_family=data["link_family"],
        profile=data["profile"],
        applies_to=tuple(applies_to),
        regions=MappingProxyType(built),
        source=data["source"],
        revision=data["revision"],
        release_status=data.get("release_status", "embargoed"),
    )


def environment_to_dict(environment: model.LinkEnvironment) -> dict[str, Any]:
    """The mapping ``parse_environment`` reads, with defaults left out."""
    regions = {}
    for name, region in environment.regions.items():
        entry: dict[str, Any] = {"start": region.start, "length": region.length}
        if region.reserved:
            entry["reserved"] = True
        if region.chosen:
            entry["chosen"] = list(region.chosen)
        regions[name] = entry
    return {
        "owner": environment.owner,
        "link_family": environment.link_family,
        "profile": environment.profile,
        "applies_to": list(environment.applies_to),
        "regions": regions,
        "source": environment.source,
        "revision": environment.revision,
        "release_status": environment.release_status,
    }


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
