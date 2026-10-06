# RFC 0002: private and future silicon

Status: Draft, 2026-10-04. Part of [RFC 0002](0002-model-and-api.md),
kept in its own file for length; it is as normative as the RFC. Terms are
as defined in RFC 0002's glossary.

## Rule

Unreleased SoCs, and the implementations, parts and boards that realize
them, never enter this repository. They live in a private package or in
private overlay files, and reach the catalogue only by side-loading on the
machine that has them. The export embargo filter
([Release status](0002-model-and-api.md#release-status)) is defence in
depth behind this rule, not the primary control.

## Discovery

`builtin()` (the default catalogue) loads, in this order, after the
built-in data:

1. **Entry points.** Every entry in the Python entry-point group
   `helia_platforms.catalogues`, in the order of distribution name, then
   entry name. Each entry is a callable returning an overlay mapping or a
   path to an overlay file. An installed private package (for example
   `helia-platforms-internal`, installed from a private repository) uses
   this to extend the catalogue.
2. **Environment.** `HELIA_PLATFORMS_PATH`: files or directories of
   overlay files, separated by `os.pathsep`, in the order given; a
   directory loads its `*.yaml` files in name order.

Each source is an overlay applied to the catalogue built so far, so a
later source may reference entries from an earlier one. Explicit
`load_overlay(source, base=...)` works as today on top of the result.
`builtin(include_plugins=False)` returns the built-in data alone, for
tests and for producing exports that must not depend on the machine.
Discovery reads the environment and entry points once, at the first
`builtin()` call; nothing happens at import.

## Rules for side-loaded entries

- Every side-loaded entry has origin `overlay` and a source label:
  `env:<path>` or `entry_point:<distribution>`; explicit overlays get
  `overlay:<path>` or `overlay:<mapping>`. `Catalogue.sources` maps each
  entry id to its label.
- Side-loaded entries may not shadow a built-in id, alias, composition or
  shorthand, and may not shadow an entry from an earlier source. A clash
  raises a `PlatformError` naming both sources; there is no silent
  override.
- A side-loaded entry may be built-in grade: provenance and
  `release_status` apply exactly as for built-ins. A private package should
  mark its entries `embargoed`, so that any export a tool makes omits them
  even if the export runs on a machine with the package installed.
- A failure to load one source (an unreadable path, an entry point that
  raises, an invalid overlay) raises a `PlatformError` naming the source;
  `builtin()` does not return a partial catalogue.
- `helia-platforms show --sources` lists every entry with its source
  label.

## Open question

Whether private packages are signed (RFC 0002 open question 6). A
consumer records which private catalogue it ran against through
`Catalogue.identity()` ([ADR 0004](../adr/0004-schema-and-catalogue-versions.md)).
