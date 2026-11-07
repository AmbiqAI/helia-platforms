# 0004. Version the schema separately and ship data corrections as patches

Date: 2026-10-05
Status: Accepted; amended 2026-10-28 (#66)

## Amendment, 2026-10-28: no `schema_version` bump before 1.0 (#66)

Before 1.0, a schema break keeps `schema_version` (`SCHEMA_VERSION` in
`_format.py`) and is marked only by its `feat!:` commit and the minor
release. In the table of point 2, the schema-break row's `schema_version`
is unchanged before 1.0 and +1 from 1.0, and point 1's "Increments only on
a schema break" applies from 1.0. The owner decided this on 2026-10-28,
reviewing #126 (apollo4p and apollo4l built-in data), whose
occupied-interface rule rejects version-1 overlays the base accepted.

## Context

RFC 0001 ("Packaging and versions") gives the package one version number.
It makes data corrections `feat:` PRs, which it calls a minor bump, and has
consumers pin `>=0.y,<0.(y+1)`, so a corrected PSRAM size would force
heliaAOT and helia-profiler to re-release
([review](../rfcs/0001-platform-catalogue-review.md) item 3.3, and RFC 0001
"Risks & mitigations", "Lockstep releases before 1.0"). RFC 0002 gives
`Catalogue` a `schema_version: int` and a `catalogue_version: str`, pending
this record (RFC 0002 at `c3d3e78`,
`docs/rfcs/0002-model-and-api.md:669-670`), and leaves open how a consumer
records which private catalogue it ran against
([0002-private-silicon.md](../rfcs/0002-private-silicon.md), "Open
question").

Facts that constrain the choice:

- This repository's `release-please-config.json:3-4` sets both
  `bump-minor-pre-major` and `bump-patch-for-minor-pre-major`. Before 1.0, a
  breaking change therefore bumps the minor, and a `feat:` or `fix:` bumps
  the patch. `AmbiqAI/helia-profiler` at `ed2f0a15` uses the same two
  settings (`release-please-config.json:3-4`), and its 0.1.5 release, a
  patch over 0.1.4, has a Features section (`CHANGELOG.md:140`). RFC 0001's
  "minor bump" for a `feat:` does not hold under this configuration.
- release-please's Python strategy shows `feat`, `fix`, `perf`, `deps`,
  `revert` and `docs` commits in the changelog and hides `style`, `chore`,
  `refactor`, `test`, `build` and `ci` (`googleapis/release-please` at
  `edce3d80`, `src/strategies/python.ts:32-43`). It skips the release when
  the rendered notes are empty (`src/strategies/base.ts:331`), and a
  breaking change is rendered whatever its type. So a `docs:` merge cuts a
  release today: release PR #27 lists #24 under Documentation.
- The repository squash-merges, with the squash title set to
  `COMMIT_OR_PR_TITLE` (GitHub repository settings, read 2026-10-05).
- The catalogue data ships only inside the wheel, so every data change
  reaches users as a package release.
- `AmbiqAI/helia-profiler` at `ed2f0a15` pins `neuralspotx==0.8.1`
  exactly (`pyproject.toml:32`) and caps its `aot` extra at
  `helia-aot>=0.23.0,<0.26.0` (`pyproject.toml:47`). The heliaAOT cap
  records hardware qualification: five `feat:` commits between 2026-09-03
  (`02671b67`) and 2026-09-30 (`e944de4c`) moved it with heliaAOT's
  minors, and `e944de4c` admits 0.25.x "but not yet verified". Its 0.1.3
  and 0.1.5 releases each shipped one neuralspotx promotion as a fix
  (`CHANGELOG.md:175`, `:149`).
- `AmbiqAI/helia-aot` at `1fd91daf` declares only lower bounds on its
  runtime dependencies (`pyproject.toml:46-60`) and depends on no AmbiqAI
  package. Its release-please config sets `bump-minor-pre-major` without
  the patch setting (`release-please-config.json:7`), so each heliaAOT
  `feat:` is a minor. It stamps its own version into generated sources
  (`helia_aot/aot/templates/macros.j2:158`). The profiler records
  `hpx_version` and a free-form `platform` object in its run metadata
  (`src/helia_profiler/data/run_metadata.schema.v1.json:6`, `:14`, at
  `ed2f0a15`).

## Decision

**1. What each version identifies.**

| Identifier | Form | Identifies |
|---|---|---|
| Package version | semver, set by release-please | One wheel: the Python API, the overlay format and JSON Schema it reads, and the built-in data it ships. Its compatibility promise covers the API and the schema, not fact values. |
| `schema_version` | integer, starting at 1 | The overlay format and the JSON export shape. Carried in every overlay file and export, and in the JSON Schema. Increments only on a schema break. |
| `catalogue_digest` | `sha256:<hex>` | The built-in data, without provenance, as defined below. |

RFC 0002's `catalogue_version` is dropped. It would equal the package
version, which `helia_platforms.__version__` and `Catalogue.identity()`
(point 4) already report, so it would add no information.

`schema_version` promises backward compatibility only. An overlay that
uses an optional field needs a package at least as new as the release that
added the field; an older package rejects the unknown key with an error
that tells the user to upgrade `helia-platforms`.

`catalogue_digest` hashes the data projection of
`builtin(include_plugins=False)`: every entity's model fields, including
ids, aliases and `release_status`, and the `compositions` and `shorthands`
tables, with every `provenance` and `field_provenance` value (ADR 0002
(#7) section 4; records per ADR 0003 (#6)) removed.

Amendment (2026-11-06, #134): `based_on`, the non-fact field that names
an overlay entry's base, is also left out of the projection; a built-in
entry never carries it. The projection is
built from the model, not from `to_dict()`, so a field added only to the
export does not change it. Each collection is projected according to its
kind in ADR 0002 (#7) section 2.4, whatever its runtime type, so that an
order that is not a fact does not reach the hash:

- A collection keyed by name or id becomes a JSON object keyed by that
  name or id, which `sort_keys` orders. This includes collections the
  model holds as tuples, such as `clock_domains` (and each domain's
  points) and `operating_points` (RFC 0002 at `c3d3e78`, `:167`,
  `:169`), and `reserved`, keyed by `purpose`.
- `access` is a list sorted by (`master`, `target`).
- Lists keyed by value (`peripherals`, `aliases`, `modes`,
  `fits_boards`, `occupies`, `alternate_bases`, `Substitution.replaces`)
  are sorted.
- `cores`, `npus` and `accelerators`, whose order is a fact (ADR 0002
  (#7) section 2.4), keep declaration order.

The bytes hashed are:

```python
json.dumps(projection, sort_keys=True, separators=(",", ":"),
           ensure_ascii=False, allow_nan=False).encode("utf-8")
```

Keys are strings only. Equal digests mean the same data. A different
digest means a fact value or an identity or governance field changed,
`cores`, `npus` or `accelerators` were reordered, or the model gained a
field; never a provenance-only or export-only change, or a reordering of
anything else.

Reason: the data reaches users only in the wheel, so a separate data
number would only have to be mapped back to a wheel. The digest answers
what that number was meant to answer, whether the data changed, and also
covers a development checkout. Review item 3.3's "and date" is dropped:
the release date is the tag's. Rejected: a calendar `catalogue_version` in
a data file (maintained by hand, and concurrent data PRs conflict on it); a
second release-please component for the data directory (two tags and two
changelogs for one wheel).

**2. Which change bumps what.** The commit type decides the bump; the
`data` scope marks catalogue changes in the changelog. Because the
repository squash-merges with `COMMIT_OR_PR_TITLE`, the PR title, or a
one-commit PR's commit subject, carries the type and scope. A PR that
spans several rows takes the row with the largest bump.

| Change | Commit | `schema_version` | Before 1.0 | From 1.0 |
|---|---|---|---|---|
| Python API break (public name removed or renamed, signature or return type changed) | `feat!:` | unchanged | minor | major |
| Schema break (an overlay valid before is rejected or means something else; an export field removed or renamed) | `feat!:` | +1 | minor | major |
| Built-in id or alias removed | `feat(data)!:` | unchanged | minor | major |
| Data correction that removes a member of a collection (a region a board does not have, a peripheral, core, clock domain or point, boot configuration, operating point or `access` pair) | `fix(data)!:` | unchanged | minor | major |
| Schema or API addition (new optional overlay field, export field, function) | `feat:` | unchanged | patch | minor |
| New Soc, Implementation, Part, Board, AddOn or MemoryDevice; built-in id renamed with the old id kept as an alias | `feat(data):` | unchanged | patch | minor |
| Data correction that changes a value (a wrong size, base or clock) | `fix(data):` | unchanged | patch | patch |
| Provenance-only change (citation, source revision, verification status; no value changes) | `chore(data):` | unchanged | no release | no release |
| Source register or allow-list change (ADR 0003 (#6)) | `chore(data):` | unchanged | no release | no release |
| Snapshot refresh with no fact change (ADR 0006 (#11)), including the provenance revisions that cite the snapshots | `chore(data):` | unchanged | no release | no release |
| Link-environment dataset change | as the addition or correction rows if the dataset ships in the wheel, otherwise `chore(data):`; it is outside the digest (open question 2) | unchanged | patch or none | minor, patch or none |
| Documentation only | `docs:` | unchanged | no release | no release |

Reason: a correction that changes a value changes no contract, so semver
gives it a patch even though consumer outputs such as placement budgets
change; that change is the purpose of a correction. A correction that
removes a member breaks overlays, because ADR 0002 (#7) section 2.5 makes
a delta that names a key the base lacks an error, and a reference to the
removed name no longer resolves. If 0.3.5 removed `psram` from
`apollo510_evb`, an overlay with `based_on: apollo510_evb` and
`memories_resized: {psram: 32M}` that loads on 0.3.4 would raise on
0.3.5, inside the `<0.4` range of point 4; as `fix(data)!:` the removal
ships as 0.4.0 instead. A provenance-only change leaves
`catalogue_digest` unchanged and ships with the next release. Rejected:
RFC 0001's `feat:` for corrections (it would make every correction a minor
from 1.0 and invite consumers to cap below it).

**3. How the versions are produced.** The package version that
`identity()` records is `helia_platforms.__version__`, read from the
installed distribution's metadata, including that attribute's fallback
literal when no metadata exists, which release-please rewrites to the last
release (#27); the digest still identifies the data in that case.
`catalogue_digest` is computed at load. Nothing is stored, so nothing can
drift. release-please keeps setting the package version and keeps both
pre-1.0 settings until 1.0, after which they have no effect. It needs one
change, which this PR makes: `changelog-sections` in
`release-please-config.json` repeats the Python strategy's list with `docs`
hidden, so a documentation-only merge cuts no release and does not move the
package version. The `data` scope needs no configuration: the changelog
groups by type and prints the scope in bold before the subject, as in
helia-profiler's `**compatibility:**` entries (`CHANGELOG.md:149` at
`ed2f0a15`). Rejected: stamping the version into a data file
through `extra-files`, as heliaAOT does for its docs exports (it duplicates
the metadata and still reports the last release in a development checkout).

**4. How consumers pin and record.** A consumer pins the schema and API
major: `helia-platforms>=0.y.z,<0.(y+1)` before 1.0 and `>=1.y.z,<2` after,
with the floor at the release whose API or schema it uses. Within that
range, a correction that changes a value or a new Soc reaches the
consumer's users when they install or upgrade, with no consumer release. The consumer pays a lock
refresh and regenerates any committed export derived from the catalogue,
such as heliaAOT's `targets.json`. A consumer that qualifies each
dependency release, as the profiler does for heliaAOT, may pin tighter;
that is its policy, and it then pays a qualification PR per data release.
A new Soc needs a consumer change only where the consumer keys its own
policy by id (RFC 0002, "Adapters, in the consumers").

Every consumer output that depends on catalogue facts records
`Catalogue.identity()`, a new frozen record with `to_dict()`:
`package_version`, `schema_version`, `catalogue_digest`, and one entry
per source applied on top of the built-in data, both side-loaded sources
and explicit `load_overlay` sources (heliaAOT's `platform.overlay:` is the
latter). Each entry holds the source label with any directory removed
(`env:board.yaml`, not the full path that `Catalogue.sources` keeps, so a
shared report carries no local path), the distribution version for an entry
point, the declared `schema_version`, and a sha256 of the source's parsed
overlay mapping in `catalogue_digest`'s canonical JSON, so a file and the
same mapping passed in memory hash alike. Before hashing, each
`provenance` key is removed and each `{value, provenance}` form is
unwrapped to its value, but only on keys the format declaration defines
(ADR 0002 (#7) section 2.7); a key the format reads and ignores as
deprecated (`Access.port` since #93, 2026-11-06) is left out, in either
form. `extensions` values are opaque tool data and are hashed unchanged,
including any key in them named `provenance`.
heliaAOT writes the record next to the tool version it already
stamps; the profiler writes it into run metadata. Reason: the version names
the release, the digest shows whether two runs used the same data, and the
source entries cover data that has no version. Rejected: recording only the
package version (it cannot tell a development checkout or an overlay
apart).

**5. Side-loaded private catalogues.** Every overlay file, and every
mapping an entry point in `helia_platforms.catalogues` returns, declares
`schema_version` at its top level, as ADR 0002 (#7) specifies.
A mapping passed directly to `load_overlay` may omit it and is read at the
package's current version, because its caller already pins the package.
A package reads its current schema version and the previous one,
converting the previous one on load with a deprecation warning, so an
overlay survives one schema break; any other version raises
`PlatformError` naming the source and both versions. The conversion serves
loose files, in `HELIA_PLATFORMS_PATH` or passed to `load_overlay`; an
entry-point package is already bounded by its dependency range. A private
catalogue package declares `helia-platforms` with the same major range as
a consumer, never an exact version, so public data patches still reach
machines that have it installed; `identity()` records its distribution
version. Reason: the schema version, not the package version, says whether
an overlay can be read, and the dependency range lets the installer refuse
an incompatible pair before load. Rejected: overlays declaring a
`helia-platforms` version range (it duplicates an entry-point package's
dependency metadata and is meaningless for a loose file).

## Consequences

- Before 1.0, only a breaking release forces consumers to re-release. This
  replaces RFC 0001's lockstep risk and its "data corrections are `feat:`
  PRs" rule. A correction that removes a wrongly listed region or other
  member is breaking, so consumers must widen their range to receive it;
  a correction that changes a value needs no consumer change.
- A data patch can change a consumer's behaviour with no consumer release:
  a correction that shrinks a memory can turn a passing heliaAOT
  conversion into one that no longer fits. The recorded identity explains
  the difference; exact reproduction needs the consumer's lock file or an
  exact pin.
- This PR adds the `changelog-sections` list of point 3 to
  `release-please-config.json`. On acceptance, RFC 0002 changes: the
  `Catalogue` API loses `catalogue_version` and gains `catalogue_digest`
  and `identity()`, and open question 6 and the private-silicon open
  question are narrowed to signing.
- Each schema break carries a converter from the previous version, and the
  wheel ships the JSON Schema for every `schema_version` it reads. ADR 0005
  (#5) decides how the schema is published: `helia-platforms export
  --schema` writes it, with no public URL until the repository is public.
- Tests must cover: the digest ignores provenance-only and export-only
  changes and the order of every collection other than `cores`, `npus` and
  `accelerators`, and changes when any of those three is reordered; a source hash keeps `extensions` unchanged; an overlay at N-1 loads with a warning and at N-2 fails with the
  named error; an unknown key names the upgrade; side-loaded and explicit
  overlays appear in `identity()` without directories.
- CONTRIBUTING gains the `data` scope, the PR-title rule and the table in
  point 2.

## Open questions

1. Whether private catalogue packages are signed (RFC 0002 open question
   6); this record settles only their versioning and recording.
2. How the optional link-environment dataset is versioned relative to the
   catalogue (RFC 0002 open question 2).
