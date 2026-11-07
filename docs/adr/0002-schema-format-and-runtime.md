# 0002. Ship the catalogue as YAML data with a generated JSON Schema and a stdlib dataclass runtime

Date: 2026-10-05
Status: Accepted; amended 2026-10-29 (#65)

## Amendment, 2026-10-29: a Soc's image slots (#65)

Section 2 changes as follows:

- A Soc carries `image_slots` as a Part does, keyed by slot name with
  `core` as a field, and has `image_slots_removed` under rule 3.
- `Subset` gains `image_slots_removed`, which removes a Soc's image slot
  for every Part of the Implementation.
- A Part's `image_slots_removed` applies over its `based_on` Part only.
  Naming a slot its Soc also carries is an error, because the Soc's slot
  would take the removed one's place.

## Context

The data format is a contract: three tools read the catalogue, and
customers and bring-up teams write overlays in it
([review of RFC 0001](../rfcs/0001-platform-catalogue-review.md), item
2.6). The review also asks that the catalogue be built data first (item
3.6). [RFC 0002](../rfcs/0002-model-and-api.md) fixes the model, the
overlay semantics and principles P7 (immutable catalogue, no I/O at
import) and P8 (stdlib runtime, schema as contract), and defers the
overlay syntax to this record. Side-loaded private catalogues use the same
format ([0002-private-silicon.md](../rfcs/0002-private-silicon.md)).
Sibling records decide the provenance record (ADR 0003 (#6)), the version
numbers (ADR 0004 (#12)), publication (ADR 0005 (#5)) and the drift
snapshots (ADR 0006 (#11)). RFC 0002 line numbers below are at `c3d3e78`.

What the consumers declare, read from each `pyproject.toml`:

| Consumer | Revision | `requires-python` | PyYAML | pydantic | typer |
|---|---|---|---|---|---|
| `AmbiqAI/helia-aot` | `1fd91daf` | `>=3.11` (`:10`) | `>=6.0.0` (`:51`) | `>=2.6.1` (`:47`) | `>=0.16.0` (`:50`) |
| `AmbiqAI/helia-profiler` | `ed2f0a15` | `>=3.11` (`:6`) | `>=6.0` (`:28`) | `>=2.7,<3` (`:36`) | `>=0.16,<0.28` (`:41`) |
| `AmbiqAI/helia-estimator` | `5991d9f1` | `==3.12.*` (`:7`) | `>=6.0.2` (`:18`) | `>=2.11,<3` (`:24`) | `>=0.16,<1` (`:25`) |
| `helia-npu` (in helia-estimator) | `5991d9f1` | `>=3.11` (`packages/helia-npu/pyproject.toml:7`) | `>=6.0.2` (`:25`) | `>=2.11,<3` (`:24`) | none |
| `AmbiqAI/neuralspotx` | `b930d59` | `>=3.11` (`:5`) | `>=6.0` (`:25`) | none | none |

helia-estimator's `main` at `c401807b` declares the same values on the
same lines. Every consumer declares PyYAML; none declares `jsonschema` or
`ruamel.yaml`. Consumers already author platform data in YAML: helia-npu's
`socs/atomiq110.yaml` ([research/helia-estimator.md](../research/helia-estimator.md))
and neuralspotx's `src/neuralspotx/boards/<board>/board.yaml`, all 17 of
which declare `schema_version: 1` at `b930d59` (line 8 in 15 files, line 10
in `apollo510dL_evb`, line 14 in `apollo4p_evb_disp_shield_rev2`). This repository
already declares `requires-python = ">=3.11"` (`pyproject.toml:7`).

Library behaviour checked on 2026-10-05:

- PyYAML 6.0.3's `safe_load` follows YAML 1.1: `010` is 8, `no` is
  `False`, `1:30` is 90, and of two duplicate keys the last wins silently.
  Replacing only the implicit resolvers is not enough: `010` still loads
  as 8, because `SafeConstructor.construct_yaml_int` reads a leading zero
  as octal.
- `jsonschema` 4.26.0 requires `attrs`, `jsonschema-specifications`,
  `referencing` and `rpds-py` (wheel metadata); `rpds-py` is a compiled
  extension. Validating with it at run time would break P8.
- In a module with `from __future__ import annotations`,
  `TypedDict.__required_keys__` ignores `Required` and `NotRequired` on
  Python 3.11 to 3.14, with both `typing` and `typing_extensions`. Without
  that import, `typing` reports them correctly on 3.11 and 3.14.

## Decision

### 1. Built-in data: YAML files in the wheel, one file per Soc

The built-in catalogue is YAML under `src/helia_platforms/data/`, shipped
as package data and read through `importlib.resources`:

| File | Holds |
|---|---|
| `socs/<soc id>.yaml` | One Soc, with the implementations, parts and boards that realize it |
| `ip.yaml` | `cores` (Core IP blocks) |
| `addons.yaml`, `memory_devices.yaml` | Add-ons and memory devices, which several boards share |
| `names.yaml` | `compositions` and `shorthands` |
| `sources.yaml` | ADR 0003's source register (top-level keys `documents` and `repositories`) |
| `unverified.yaml` | ADR 0003's release allow-list (`unverified_allowed`: entries of `fact`, `reason`, `issue`) |

All of them use the file format of section 2. The loader merges their
top-level tables into one document (an id defined twice is an error) and
loads it as one source with origin `builtin`. A file per Soc is the unit
that changes together: a datasheet revision or a drift finding touches one
Soc and what realizes it, and a reviewer sees that in one diff.
CODEOWNERS (#17) can own each file. An abridged `socs/apollo510.yaml`,
with values from DS-A510 p35 and p298 as recorded in
[research/datasheets.md](../research/datasheets.md) sections 2 and 4:

```yaml
# yaml-language-server: $schema=../../schema/helia-platforms-v1.schema.json
schema_version: 1
socs:
  apollo510:
    release_status: public
    provenance:                  # illustrative record; its fields are ADR 0003's (#6)
      status: datasheet
      source: ["doc:DS-A510@1.1.0:p35", "doc:DS-A510@1.1.0:p298"]
      verified_on: 2026-10-05
      verified_by: <login>
    memories:
      dtcm:  {technology: sram, attachment: tcm, base: 0x20000000, size: 512K}
      ssram: {technology: sram, attachment: system, base: 0x20080000, size: 3M}
      mram:  {technology: mram, attachment: system, base: 0x00400000, size: 4M}
    boot_configs:
      sbl:
        reserved: {sbl: {region: mram, offset: 0, size: 64K}}  # by purpose
        app_start: {region: mram, offset: 64K}
        requires: sbl
    default_boot: sbl
    # cores, npus, access, clock_domains, operating_points, sdk: elided
parts: {}    # the Apollo510 parts
boards: {}   # the boards that carry them
```

**Built-in-only rules.** Beyond the shared rules, the loader enforces for
built-in files: every fact resolves to a provenance record, and
`unverified` is written out (ADR 0003 (#6)); `release_status` is written
out as `public` (ADR 0005 (#5)); every memory region has a `base` (RFC
0002 at `c3d3e78`, `:191`);
after `default_access` expansion, every region and every memory controller
a built-in interface names has an access entry (RFC 0002 at `c3d3e78`, `:819-822`);
there is no `extensions`; and `shorthands`, `documents`, `repositories`
and `unverified_allowed` appear only here. Built-in entries may not use
`based_on`, because each variant cites its own datasheet: Apollo510B's
regions come from DS-A510B p34 and p263 and Apollo510's from DS-A510 p35
and p298 ([research/datasheets.md](../research/datasheets.md) section 4),
and a value inherited through `based_on` would keep the base's record and
cite the other document. Variants that share headers use `derives_from`,
whose meaning is RFC 0002's.

### 2. File syntax

RFC 0002 fixes the semantics and this section fixes the spelling, except
that section 2.5 amends RFC 0002's semantics in the places listed under
Consequences.

**2.1 Top-level keys.** `schema_version`, then any of `cores`, `socs`,
`implementations`, `parts`, `boards`, `addons`, `memory_devices`,
`compositions`, and the built-in-only keys of section 1. A JSON file may
also carry `$schema`, which the loader ignores. Each entity table maps an
id to an entry. An Npu IP block has no id in the model, so it is written
inline in its `NpuInstance`. A composition is
`<alias>: {board: <id>, addons: [<id>, ...]}`. An unknown key anywhere
outside `extensions` is rejected with a did-you-mean suggestion and a hint
that a newer `helia-platforms` may know it (ADR 0004 (#12)).

**2.2 `schema_version`.** Every file, built-in or overlay, declares it as
an integer, and so does every mapping an entry point returns. A mapping
passed directly to `load_overlay` may omit it and is read at the package's
current schema version, because its caller already pins the package (ADR
0004 (#12), section 5). Which versions a package reads is ADR 0004's.

**2.3 Ids and names.**

- An entry id is its mapping key, matches `^[A-Za-z][A-Za-z0-9_-]{0,63}$`,
  and keeps the case written, because canonical ids are the neuralspotx
  and SDK spellings (`apollo330mP_evb`, `AP510NFA-CBR`).
- Ids and aliases of socs, implementations, parts and boards, composition
  aliases and shorthands share one namespace, unique case-insensitively,
  because `resolve()` accepts them all. Cores, add-ons (with their
  aliases) and memory devices each have their own case-insensitive
  namespace; an add-on is named only in `addons=` and in compositions.
- Names inside an entry (regions, peripherals, core, NPU and accelerator
  instances, clock domains and points, operating points, boot
  configurations, reservation purposes, image slots, interfaces and memory
  controllers) are written lowercase, `^[a-z][a-z0-9_]*$`. Lookups by name
  fold case, so the estimator's `npu_mhz("HP")` finds point `hp` without
  an adapter. The names `value` and `provenance` are reserved and
  rejected, because as keys of a collection they would be read as the
  `{value, provenance}` form of section 2.7.

**2.4 Collections.** Every collection is keyed. A collection is a mapping
keyed by name or id wherever possible, because a mapping cannot hold a key
twice: `memories`, `clock_domains` (each domain a mapping of point name to
point), `operating_points`, `boot_configs`, a boot configuration's
`reserved` (keyed by purpose: `reserved: {sbl: {region: mram, offset: 0,
size: 64K}}`), `interfaces`, `population`, a Part's `image_slots` (keyed
by slot name, with `core` as a field), an FVP Implementation's
`substitutions` (keyed by the region the model provides), and
`max_domain_mhz` (domain id to MHz). Three kinds of list remain:

- `cores`, `npus` and `accelerators`, because their order is a fact:
  declaration order, index 0 primary (RFC 0002 at `c3d3e78`, `:163-164`).
  Each item carries `id`, which keys it.
- `access`, keyed by the pair (`master`, `target`). A mapping would split
  one entry across two levels; the loader rejects a repeated pair.
- Lists of names or values (`peripherals`, `aliases`, `modes`,
  `fits_boards`, `occupies`, a region's `alternate_bases`, which are
  addresses, and a substitution's `replaces`, which are region names),
  keyed by the value itself; the loader rejects a repeated value.

**2.5 `based_on` and deltas.** One merge rule applies to an overlay entry
over its `based_on` entry and to an Implementation over its Soc:

1. A scalar the entry writes replaces the base value. A nested object (a
   memory region, a boot configuration, a `characterization`, an `npu`
   record) is replaced whole. `extensions` is the exception: it merges per
   tool key, and `based_on` copies it, which extends RFC 0002's list of
   what `based_on` copies.
2. A collection the entry writes merges by key: the base's order is kept,
   an existing key is replaced, and new keys are appended. A collection of
   collections merges at both levels, so an Implementation's
   `clock_domains: {cpu: {fpga: {mhz: 25}}}` adds or replaces point `fpga`
   and keeps the Soc's other points.
3. `<collection>_removed` removes keys and exists for every keyed
   collection that rule 2 merges (`memories_removed`, `cores_removed`,
   `npus_removed`, `accelerators_removed`, `peripherals_removed`,
   `clock_domains_removed`, `boot_configs_removed`,
   `operating_points_removed`, and on a Part `image_slots_removed`);
   `access_removed` takes `{master, target}` pairs. A collection inside a
   nested object, such as a boot configuration's `reserved`, is replaced
   with that object and has no `_removed` key. `clock_domains_removed`
   takes a domain (`cpu`), which removes the domain, or a domain and point
   written `<domain>.<point>` (`cpu.hp`), which removes that one point.
4. `memories_resized: {<name>: <size>}` and
   `memories_rebased: {<name>: <address>}` change one field of a region.

Amendment (2026-11-06, #134): the merged entry keeps `based_on` as a
non-fact runtime field naming its own base (a chain does not pass the
base's on), so `Catalog.lineage()` can walk an overlay entry to the first
entry that names none; `based_on` is not inherited, not in the digest, and
is written by the export for overlay entries.

A delta that names a key the base lacks is an error. References, such
as an operating point that names a removed point, are checked after the
merge. An Implementation writes its removals, resizes, rebases and clock
caps under `subset:`; `Subset` gains a field for each `_removed` key,
including `accelerators_removed`, which RFC 0002's prose allows (`:214`)
but its `Subset` (`:738`) lacks; a Part's `image_slots_removed` is not a
subset field. Because collections merge, an FPGA that must not offer the
Soc's `sbl` configuration says `boot_configs_removed: [sbl]`. In
an entry with `based_on` no key is required, because the base supplies
them; required keys are checked after the merge. RFC 0002's shorthands
expand at load: `cpu_mhz` and `npu_mhz` on an operating point, and a
single `app_start`, which is told apart from the per-core form by its
values (scalars in `{region, offset}`, mappings in the per-core form).

An example with illustrative values and provenance omitted:

```yaml
socs:
  soc_a:
    memories:
      tcm: {technology: sram, attachment: tcm, base: 0x20000000, size: 512K}
      nvm: {technology: mram, attachment: system, base: 0x00400000, size: 4M}
    clock_domains:
      cpu: {lp: {mhz: 96}, hp: {mhz: 192}}
    boot_configs:
      sbl:
        reserved: {sbl: {region: nvm, offset: 0, size: 64K}}
        app_start: {region: nvm, offset: 64K}
        requires: sbl
      nbl: {reserved: {}, app_start: {region: nvm, offset: 0}, requires: none}
    default_boot: sbl
implementations:
  soc_a_fpga:
    soc: soc_a
    kind: fpga
    clock_domains: {cpu: {lp: {mhz: 24}, fpga: {mhz: 25}}}
    default_boot: nbl
    subset:
      memories_resized: {tcm: 256K}
      clock_domains_removed: [cpu.hp]
      boot_configs_removed: [sbl]
```

`soc_a_fpga` resolves to these values:

```yaml
memories:            # tcm resized (rule 4), nvm inherited
  tcm: {technology: sram, attachment: tcm, base: 0x20000000, size: 256K}
  nvm: {technology: mram, attachment: system, base: 0x00400000, size: 4M}
clock_domains:       # lp replaced, fpga appended (rule 2), hp removed (rule 3)
  cpu: {lp: {mhz: 24}, fpga: {mhz: 25}}
boot_configs:        # sbl removed (rule 3)
  nbl: {reserved: {}, app_start: {region: nvm, offset: 0}, requires: none}
default_boot: nbl    # the Implementation's; the Soc's sbl no longer exists
```

**2.6 Scalars.**

- A size is an integer number of bytes or a string `<integer><K|M|G>`,
  K, M and G being 1024, 1024² and 1024³ bytes. `256k`, `256KB`,
  `256KiB`, `256Kb` and `1.5M` are rejected with a hint.
- An address is an integer, written in hex by convention.
- YAML is read with a subclass of `yaml.CSafeLoader`, or of
  `yaml.SafeLoader` when PyYAML is built without libyaml and has no
  `CSafeLoader` (`getattr(yaml, "CSafeLoader", yaml.SafeLoader)`). Both
  take their resolver and constructor from `Resolver` and
  `SafeConstructor`, so one mixin serves either: it resolves plain scalars
  by the YAML 1.2 core schema (`no` and `1:30` stay strings), overrides
  the integer constructor so that `010` is ten, and rejects duplicate
  keys.
- A string field that receives a number, such as an unquoted
  `revision: 1.0` or `1e3`, is rejected with a hint to quote it.
- A `.json` file is read with stdlib `json`, rejecting duplicate keys
  through `object_pairs_hook`. A directory in `HELIA_PLATFORMS_PATH` loads
  only its `*.yaml` files, as RFC 0002 says; `.yml` and `.json` files load
  when named explicitly.

**2.7 Provenance.** The record is ADR 0003's (#6). It attaches as
`provenance: <record>` to an entry or to any object in it, and covers
every fact in that object that has no nearer record. A single value with
its own record is written `{value: <value>, provenance: <record>}`, for
example `read_latency_ns: {value: 120, provenance: {status: fitted, ...}}`.
Values that a `based_on` entry or an Implementation inherits unchanged keep
the record they had in the base (RFC 0002 at `c3d3e78`, `:561-563`;
ADR 0003 (#6), section 3). The format declaration marks the keys that are not facts
(`id`, `aliases`, `release_status`, `default_board`, `derives_from`,
`extensions`, `based_on`, `provenance`); `{value, provenance}` is accepted
only on the other keys. This list is the single definition of the keys
that are not facts; ADR 0003 (#6) cites it.

**2.8 `extensions`: recommended.** Adopt RFC 0002's proposal (open
question 4): an `extensions` mapping on overlay entries of `socs`,
`implementations`, `boards` and `addons`, keyed by tool name
(`^[a-z][a-z0-9_]*$`, by convention the tool's import name), with any
JSON-compatible value. The package stores it deep-frozen and returns it,
and never reads it. One overlay file can then describe a custom board to
every tool while the package holds only facts.

### 3. The JSON Schema and run-time validation

- **Coverage.** One JSON Schema (draft 2020-12) for the file format of
  section 2, built-in and overlay alike. Rules a schema cannot express
  (references resolve, regions do not overlap, a subset adds no memory)
  stay in the loader's semantic stage. The resolved JSON export is not
  covered.
- **One declaration, two checkers.** The format is declared once with
  stdlib `typing` (`TypedDict`, `Literal`, `Annotated` constraints) in a
  module that does not use `from __future__ import annotations` (see
  Context). A generator writes the JSON Schema from it, and the loader's
  structural stage walks it, matching patterns with `re.fullmatch`. The
  schema expresses the `based_on` difference in required keys with
  `if`/`then`. A field-parity test checks that every entity key maps to a
  field of the runtime dataclass and back, except listed file-only keys
  (`based_on`, the delta keys and the shorthands) and the model-only
  field `field_provenance`, which files write as `{value, provenance}`.
- **File name and `$id`.** The schema for version N is
  `src/helia_platforms/schema/helia-platforms-v<N>.schema.json`, with
  `$id` `tag:ambiq.com,2026:helia-platforms/schema/v<N>`, a `tag:` URI
  that names the schema without needing to resolve. The wheel ships every version the package reads. A unit test
  fails when a committed file is stale, and `helia-platforms export
  --schema` writes the current one. Hosting is ADR 0005's (#5): the
  schema has no public URL until the repository is public.
- **Editors.** Files carry a `yaml-language-server` modeline that points
  at the schema file, by relative path inside this repository.
- **CI.** This repository parses every built-in file, and every overlay
  example in RFC 0002 and later documents or marked as an example (not
  RFC 0001's), with the package's YAML loader, then validates the
  result with `jsonschema`, which is a development dependency only. A
  conformance corpus of valid and invalid documents must get the same
  verdict from the loader's structural stage and from `jsonschema`.
  Consumers validate overlays with `helia-platforms validate` or
  `load_overlay`.
- **Run time.** The loader validates, and `jsonschema` is never imported.
  The JSON Schema serves editors and CI.

### 4. Runtime representation

- Model types are `@dataclass(frozen=True, slots=True, kw_only=True)`, so
  a field can be added without breaking callers. Sequences are tuples and
  mappings are read-only `types.MappingProxyType` views over private
  copies, which makes the types unhashable; tools key caches by id.
- Each dataclass that carries facts keeps RFC 0002's `provenance` field
  for its entry or group record, and adds
  `field_provenance: Mapping[str, Provenance]` for the per-value records
  of section 2.7. A key is the value's path relative to that object, in
  the field-path grammar of ADR 0003's (#6) `fact:` references, so the
  key appended to the object's own field path gives the value's field
  path in a `fact:` reference. The keys a path passes through are ids and
  names (section 2.3), whose patterns admit no `.`, `@` or `:`, so the
  grammar needs no escaping.
- PyYAML parses files for `builtin()` and `load_overlay()` and is
  imported inside the loader, not at package import. Nothing is written
  as YAML; exports use stdlib `json`.

### 5. Python floor

`requires-python = ">=3.11"`, unchanged. Every consumer accepts 3.11 except
helia-estimator's `==3.12.*`, which lies inside that range. CI covers 3.11
to 3.14, because helia-aot (`.github/workflows/ci.yml:144` at `1fd91daf`)
and helia-profiler (`.github/workflows/ci.yml:70` at `ed2f0a15`) test
3.14.

### Rejected alternatives

- One file for the whole catalogue: every change and merge conflict lands
  in it.
- One file per entity, or a directory per kind: a Soc and the boards that
  realize it would be reviewed across several files.
- A JSON copy compiled at build time: a second, generated copy of every
  file to keep in step, for a parse-time saving nobody has measured.
- TOML: `tomllib` is stdlib, but in TOML 1.0, which it reads, an inline
  table must fit on one line, which suits memory and access tables
  poorly; and every consumer already authors YAML and declares PyYAML.
- JSON as the authoring format: no comments.
- `ruamel.yaml`: a dependency no consumer has, for what a PyYAML loader
  subclass provides.
- `jsonschema` at run time: four dependencies, one of them compiled.
- pydantic, attrs or msgspec as the runtime model: P8. helia-aot,
  helia-profiler, helia-estimator and helia-npu already require pydantic
  (`>=2.6.1` to `>=2.11`, table in Context), so for them it would add
  nothing; neuralspotx does not, and would gain pydantic and its compiled
  `pydantic-core`. msgspec is compiled (0.22.0 ships
  `msgspec._core` as a C extension) and no consumer declares it.
- pydantic or msgspec as a development-only schema generator, replacing
  the bespoke one. pydantic 2.13.4's `TypeAdapter(...).json_schema()`
  reads a stdlib `TypedDict` but drops `Annotated` metadata it does not
  know, so each stdlib constraint marker would need a
  `__get_pydantic_json_schema__` hook, and the `based_on` `if`/`then`
  would still be written by hand. msgspec 0.22.0's `msgspec.json.schema`
  reads constraints only from `msgspec.Meta`, which would make the
  declaration, and so the run-time loader, import msgspec. pydantic would
  save walking the declaration, at the cost of a committed schema that
  changes whenever pydantic's output does.
- A hand-written schema beside a hand-written checker: two sources that
  drift.
- Lists of named objects for every collection: each list needs a
  uniqueness rule that a mapping gives for free.

## Consequences

- Built-in data, side-loaded catalogues and customer overlays share one
  format, one loader and one schema.
- The repository maintains a format declaration, a schema generator, the
  staleness, parity and conformance tests, and a custom YAML loader.
- Must follow, in the PR that refers to #7 (the issue closes on
  acceptance): a schema stub that validates RFC 0002's example overlays,
  the issue's acceptance criterion. It targets RFC 0002's examples because
  RFC 0001's (`kind:`, per-tool sections, `remove:`) are superseded. RFC
  0002's examples are structurally valid after the edits below.
- On acceptance, RFC 0002 at `c3d3e78` takes these edits. Its examples
  declare `schema_version`. An Implementation's boot configurations and
  operating points merge with the Soc's instead of replacing them
  (`:258-259`, `:293`). `based_on` copies `extensions`. `Subset` gains
  the `_removed` fields of section 2.5. A boot configuration's `reserved`
  is a mapping keyed by purpose (`:278`; the FPGA example's
  `reserved: []` at `:500` becomes `reserved: {}`), so a purpose is a
  name (section 2.3) and is unique within its boot configuration.
  `BootConfig.reserved` stays `tuple[Reservation, ...]` (`:740`), in the
  order the keys are written, and the key fills `Reservation.purpose`
  (`:741`). The FPGA example removes, with
  `subset: {boot_configs_removed: [...]}`, whichever of the Soc's boot
  configurations the FPGA must not offer (for example `sbl`, which the
  SDK keeps for future silicon), and writes its clock domains,
  points and operating points as mappings. P8 (`:86`) links here, and its
  pydantic extra becomes this record's open question 2. The API section
  drops "PyYAML, used only by `load_overlay`" (`:656-657`). CI and
  the classifiers add 3.14 (now 3.11 to 3.13,
  `.github/workflows/ci.yml:35`).

## Open questions

1. Whether `extensions` is enough for the profiler's custom-board
   measurement wiring, or the profiler keeps a sidecar file (RFC 0002
   open question 4; #15).
2. Whether to offer a pydantic extra. pydantic 2.13.4's `TypeAdapter`
   validates the frozen dataclasses, but `dump_json` fails on a
   `MappingProxyType` field, and `validate_python` would build model
   objects without the loader's semantic rules.
3. Whether the resolved JSON export (`Catalogue.to_dict()`) needs a
   published schema of its own. Answered by
   [RFC 0003](../rfcs/0003-export-and-pages.md), accepted 2026-10-21: yes,
   one schema for the whole export, which reuses the file-format schema
   for `catalog`.
