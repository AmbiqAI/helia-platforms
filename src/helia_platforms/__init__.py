"""Shared catalog of Ambiq SoC and board facts."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("helia-platforms")
except PackageNotFoundError:
    __version__ = "0.2.0"

# Imported after __version__, which catalog reads at import.
from helia_platforms.catalog import (
    Catalog,
    CatalogIdentity,
    SourceIdentity,
    builtin,
    load_overlay,
)
from helia_platforms.errors import (
    AmbiguousPlatform,
    FormatError,
    PlatformError,
    PlatformWarning,
    UnknownPlatform,
)
from helia_platforms.resolve import resolve, resolve_board, resolve_soc
from helia_platforms.target import IsaFeatures, Target

__all__ = [
    "AmbiguousPlatform",
    "Catalog",
    "CatalogIdentity",
    "FormatError",
    "IsaFeatures",
    "PlatformError",
    "PlatformWarning",
    "SourceIdentity",
    "Target",
    "UnknownPlatform",
    "__version__",
    "builtin",
    "load_overlay",
    "resolve",
    "resolve_board",
    "resolve_soc",
]
