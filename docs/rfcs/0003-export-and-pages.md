# RFC 0003: the JSON export and the generated catalog pages

Status: Accepted, 2026-10-21 (drafted 2026-10-06). Builds on [RFC 0002](0002-model-and-api.md)
(`Catalog.to_dict()`, release status and `helia_platforms.export`) and
on ADRs [0002](../adr/0002-schema-format-and-runtime.md),
[0004](../adr/0004-schema-and-catalogue-versions.md) and
[0005](../adr/0005-publication-and-embargo.md), all Accepted (#50).
Section 4 of the [review of RFC 0001](0001-platform-catalogue-review.md)
asks for "one machine-readable export (the successor of `targets.json`)
and generated per-SoC and per-board pages". This note designs both,
except resolved per-target records, which it defers (see "Deferred:
resolved targets"). The edits it makes to RFC 0002 and ADR 0002 are listed
at the end, and were made on acceptance. RFC 0002 line numbers below are
at `4c7bfce`. Citations of #49's code are pinned to its merge commit
`af7482b`.

## Problem

RFC 0002 names the outputs in two lines: `to_dict()` is "the JSON export"
(`docs/rfcs/0002-model-and-api.md:707`), and `helia_platforms.export`
"writes the JSON catalog, filtered and scrubbed by effective release
status, the JSON Schema and Markdown pages" (`:853-855`). It does not say
what the JSON contains, whether derived values are in it, how it is
versioned, or who reads it. ADR 0002 leaves open whether the resolved
export needs a published schema (open question 3).

Today the only machine-readable list of Ambiq targets is heliaAOT's
`targets.json`. At `AmbiqAI/helia-aot` `1fd91daf`:

| Aspect | What it is | Source |
|---|---|---|
| Shape | An envelope with `export_schema_version: 1` and `generated_from: {version}`, then `targets`: one record per registered platform with `name`, `cpu`, `speeds_mhz`, `capabilities`, `memories` (`{name, bytes}`), `preferred_memory_order`, `min_alignment` and `supports_fp16` | `docs/src/data/generated/targets.json:1-5`; `repo_tools/docs_export.py:176-188`, `:488-505` |
| Coverage | The 15 entries of heliaAOT's registry, from `apollo330mp_evb` to `atomiq110` | `targets.json`; `helia_aot/platforms/platforms.py` |
| Content | A mix of three things: hardware facts (`cpu`, clocks, `supports_fp16`), heliaAOT's planning budgets (`memories` holds the sizes heliaAOT plans into, such as 2031616 bytes of MRAM on `apollo330mp_evb`, which [0002-migration.md](0002-migration.md) lists as a pending correction), and heliaAOT policy (`min_alignment`, `preferred_memory_order`, the `MCU` tag) | `docs/rfcs/0002-migration.md:45`, `:121-122` |
| Check | `python -m repo_tools.docs_export --check` fails when the committed file differs byte for byte from a fresh export, except `generated_from`, which release-please rewrites | `repo_tools/docs_export.py:41-49`; `release-please-config.json:45` |

Who reads it, found by searching local clones of AmbiqAI repositories
and by `gh search code` for `targets.json` and `export_schema_version`
across the organization on 2026-10-06 (GitHub code search covers default
branches only):

| Reader | How | Source |
|---|---|---|
| heliaAOT's docs site | `exports.mjs` loads it and rejects any `export_schema_version` other than 1; `render-generated.mjs` renders the public Targets reference from it; `TargetChips.astro` groups targets into families by name prefix and stops the build for a name that matches no family | `docs/scripts/exports.mjs:21-37`; `docs/scripts/render-generated.mjs:346-406`; `docs/src/components/TargetChips.astro:17`, `:28-46`, all at `1fd91daf` |
| heliaAOT's tests | A test fails when a registered platform is missing from the file, because "pip-only users rely on the published target reference" | `tests/unit/platforms/test_target_discovery.py:118-128` at `1fd91daf` |
| aitg-handbook | `mcu-coverage.yaml` records heliaAOT's targets by hand, citing the file at the `v0.24.0` tag by URL; `src/data/mcuCoverage.ts` validates the record. It records tool integration, not hardware | `AmbiqAI/aitg-handbook` at `bdc7b81e`, `mcu-coverage.yaml:1-7` |

No other reader was found. The other matches were
`mbed-os/targets/targets.json` in CMSIS-NN test scripts, which is
unrelated.

### The developer hub

The handbook names the "HELIA AI Developer Hub" as the surface for public
products, setup, integration guidance and examples
([research/ambiqai-conventions.md](../research/ambiqai-conventions.md),
`tools-and-systems.mdx:81`). It is the repository
`AmbiqAI/helia-developer-hub`, read at `fa879f22` on 2026-10-06, and
heliaAOT's docs header links to it (`docs/astro.config.mjs:59` at
`1fd91daf`). Facts that constrain this note:

- The repository is private, but its GitHub Pages site,
  `https://ambiqai.github.io/helia-developer-hub/`, is public. It deploys
  a holding page in place of the real site until the site is ready
  (`.github/workflows/deploy-pages.yml:29-40`).
- Its taxonomy says the hub "is not a replacement for Ambiq hardware
  documentation" and surfaces SoCs and EVBs through filters, support
  matrices and "works with" sections rather than a Hardware section
  (`docs/site-taxonomy.md:193-198`; also `docs/ecosystem.md:199-205`).
- Its target data is hand-written: three families (Apollo3, Apollo4,
  Apollo510) in `src/data/platform.ts:521-536`, with heliaAOT's docs site
  as the cited evidence (`:646`). It does not read `targets.json`.
- It already takes data from a private source by a committed snapshot:
  `scripts/sync-portfolio.mjs:3-6` copies the handbook's portfolio export
  because "the hub cannot fetch it at build time", and records the source
  commit in `src/data/portfolio.export.meta.json`.

So nothing in the hub defines what a per-SoC or per-board page there
would be, and its taxonomy argues against a hardware section. Where the
pages live is open question 1.

## Proposal

### What the export contains

One JSON document, built from a `Catalog`, with three top-level keys:

| Key | Content |
|---|---|
| `schema_version` | ADR 0004's integer. |
| `identity` | `Catalog.identity().to_dict()` (ADR 0004 point 4): package version, `schema_version`, `catalog_digest`, and one entry per source applied on top of the built-in data. In every export that may be published, there is no such entry (see "One publishable path"). |
| `catalog` | The entities, written as a complete document in ADR 0002's file format: `schema_version`, equal to the export's top-level `schema_version`, then `cores`, `socs`, `implementations`, `parts`, `boards`, `addons`, `memory_devices`, `compositions`, `shorthands`. Every entry is written after the `based_on` merge, so no entry carries `based_on` or a file-only delta key that applies over a base (a Soc's `memories_removed` and the like, a Soc's or Part's `image_slots_removed`; #49 at `af7482b`, `_format.py:286-301`, `:369`). The loaded entry keeps `based_on` and `Catalog.lineage()` walks it (#134); the export leaves it out because the file format reads the key as an instruction to merge over the base again, which would undo the entry's removals (2026-11-06). A Soc entry carries its `image_slots` and a Part entry only its own, each replacing the Soc's slot of the same name; `Target.image_slots` gives the merged set. An Implementation entry keeps its `subset` as in the file format, because its removals (`image_slots_removed` among them), resizes, rebases and clock caps live only there (ADR 0002 `:211-216`); a reader that wants the realized Implementation calls `resolve()` with its id. |

`catalog` is the raw data: a tool can rebuild any view from it, and
because it is in the file format, the file-format JSON Schema of the same
`schema_version` validates it (in #49's schema at `af7482b`,
`provenance` is not a required key of an entry, so an entry without it
validates). The member carries its own `schema_version` because that
schema requires the key at the top level of a document and allows no
top-level key it does not list (#49 at `af7482b`,
`helia-platforms-v1.schema.json:110-113`).

The export carries no derived values. Capabilities, ISA features, the
regions a core reaches after the implementation subset, usable NVM and
the flash load address come from `resolve()` and the `Target` queries
(RFC 0002, "`helia_platforms.target`", `:777`). A reader that cannot run
Python, such as an Astro docs site, would have to reimplement that
derivation to get them, which RFC 0002 principle P3 argues against.
Records of resolved values for such readers are deferred (see "Deferred:
resolved targets").

The export carries no tool policy and no budgets: no alignment, placement
order or linker windows, which stay with the consumers (#73; RFC 0002
open question 2, closed 2026-11-05).

The document has no timestamp, and is written with sorted keys, two-space
indentation and a final newline. The same package version and inputs
therefore give the same bytes, and a consumer that commits a copy can
check it byte for byte, as heliaAOT does.

### Release status, filtering and scrubbing

The export is always filtered by RFC 0002's rule ("Release status",
`:374-392`), which already includes ADR 0005's additions: no embargoed
entry and no target whose effective status is embargoed; embargoed ids
scrubbed from shorthands, compositions, `fits_boards`, `default_board`
and aliases; a Core or Npu dropped when no exported Soc
references it.

The export also drops a composition when its board or any of its add-ons
is scrubbed. A composition without its board is not a valid entry: #49's
schema requires `board` (#49 at `af7482b`,
`helia-platforms-v1.schema.json:1345-1365`). A composition that lost only
an add-on would ship under its alias with that add-on removed from
`addons`, so the alias would resolve to a different target from the one
it names, and the alias name itself can reveal the add-on. This tightens
RFC 0002's rule, which drops a composition only when it references only
embargoed entities (`:390-392`).

`Catalog.to_dict()` returns this filtered document. The unfiltered form
exists only for ADR 0005's distribution test, which asserts the two are
equal for the built-in catalog. No public call returns an unfiltered
dump, so a tool cannot publish one by calling `json.dump(cat.to_dict())`.

### One publishable path

Every output that may be published is built from
`builtin(include_plugins=False)` with no overlay files, as
[0002-private-silicon.md](0002-private-silicon.md) intends for "exports
that must not depend on the machine". That call reads neither entry-point
packages nor `HELIA_PLATFORMS_PATH` (RFC 0002 `:688`). The outputs that
may be published are the pages, the release assets, and any copy a
consumer commits, such as a copy in the hub. Built-in entries must be
`public` (ADR 0005 point 1), and ADR 0005's distribution test asserts
that the filtered export of this catalog equals the unfiltered one, so
on this path the filter removes nothing and is defence in depth.

The filter is not enough when other sources are loaded, because it does
not touch `identity`. Each source entry in `identity` holds the source
label, such as `entry_point:<distribution>`, `env:<file>` or
`overlay:<file>`, the distribution version for an entry point, and a
sha256 of the source's whole mapping, embargoed entries included (ADR
0004 point 4). An export built with `--include-plugins` while a private
catalog package is installed, or with `--overlay`, therefore drops the
embargoed entries but still names the private package and its version,
or the overlay file. The hub condition in "Where outputs are published"
checks only the named Socs, Parts, Boards and Implementations and would
not catch this.

The command line enforces the path:

- `--pages` and `--release` refuse `--overlay` and `--include-plugins`
  and exit with status 2, as #49's `export` does when no output option is
  given (#49 at `af7482b`, `cli.py:78-80`). `--release` also refuses
  `--provenance`.
- Before writing, both check that `identity()` lists no source and fail
  otherwise, so a source added by another route also stops the write.
- `--json` accepts `--overlay` and `--include-plugins`. Such an export is
  for internal use: its `identity` names those sources, and it is not
  attached to a release, committed into the hub or published in any other
  way.

### Provenance

The default export carries no provenance records. `catalog` omits every
`provenance` key and writes plain values in place of the `{value,
provenance}` form, as the projection that `catalog_digest` hashes does
(ADR 0004 point 1). Pages were to show the worst status per group from
`Target.provenance()`, which needs no record; that query is deferred
until the estimator adapter defines its roll-up (#58), so pages show no
status until it exists (open question 3).

`--provenance` writes the full records into `catalog` in the file
format, for `--json` only. ADR 0005 point 2 requires an audit of the
source register's document ids, the provenance notes and the
`verified_by` logins before any publication with catalog content, so an
export with full records is for internal use until that audit is done.
Reason: pages need to say how well a value is sourced, which the status
does; the full records add internal document ids and GitHub logins that
the audit has not cleared.

### Schema and versioning

ADR 0004 gives one `schema_version` to "the overlay format and the JSON
export shape" and bumps it on a schema break, including "an export field
removed or renamed". This note follows that:

- The export declares `schema_version: N`, and its `catalog` member is
  a file-format document that declares the same `schema_version: N`.
- The export gets one JSON Schema for the whole document, generated from
  `TypedDict` declarations as ADR 0002 section 3 does for the file format:
  `src/helia_platforms/schema/helia-platforms-export-v<N>.schema.json`,
  `$id` `tag:ambiq.com,2026:helia-platforms/export/v<N>`, shipped in the
  wheel, written by `--export-schema` and held by the same staleness test.
  It requires `schema_version`, `identity` and `catalog` and allows no
  other key, as the file-format schema does at its top level. `identity`
  is declared from the shape of `CatalogIdentity.to_dict()`.
- `catalog` reuses the file-format schema instead of copying its
  definitions. The generator embeds the file-format schema of version N
  under `$defs` with its own `$id`, which draft 2020-12 allows as a
  bundled schema resource, and `catalog` refers to it by `$ref`. The
  export schema therefore validates on its own, without a schema
  registry, and both schemas come from one declaration of the file format.
- Each export schema serves one N, so it checks that the versions agree
  with `const`: the top-level `schema_version`, `identity.schema_version`
  and `catalog.schema_version` must each equal N. For `catalog` this
  is an `allOf` of the `$ref` and `{"properties": {"schema_version":
  {"const": N}}}`, because the file-format schema accepts any integer
  from 1 (#49 at `af7482b`, `helia-platforms-v1.schema.json:10-13`).
- This answers ADR 0002 open question 3: yes, one schema for the whole
  export, which reuses the file-format schema for `catalog`.
- Adding a top-level member or an `identity` field is a `feat:` (a patch
  before 1.0); removing or renaming one is `feat!:` and bumps N (ADR 0004
  point 2). Adding `targets` later is therefore an addition and does not
  bump N.

The cost: a break in the export alone bumps N for overlay files too, and
overlay authors then see ADR 0004's one-release deprecation warning for a
format that did not change. Open question 2 asks whether that is
acceptable.

### How `targets.json` consumers migrate

The export does not replace `targets.json`. heliaAOT is a Python package
and reads the catalog through `resolve()`; `targets.json` stays
heliaAOT's record of which targets heliaAOT supports and how it plans
into them, because budgets and policy stay in heliaAOT (RFC 0002
principle P1). Each field of a `targets.json` record maps as follows:

| `targets.json` field | Source after adoption |
|---|---|
| `name` | The name heliaAOT registers; `resolve(name).id` is the canonical id (heliaAOT keeps a passed alias, [0002-migration.md](0002-migration.md)) |
| `cpu` | `Target.core`, the `Core` of core 0 |
| `speeds_mhz` | `Target.cpu_mhz(point)` for each point in `Target.operating_points()` |
| `capabilities` | `Target.capabilities`, mapped onto heliaAOT's enum by its adapter, plus its `MCU` tag, without `BLE` and `USB` (`0002-migration.md:121`) |
| `supports_fp16` | `Target.isa().supports_fp16` for core 0 |
| `memories` | heliaAOT's budgets, computed by its adapter from `Target.memories()`, `usable_nvm()` and `external_memories()` (`0002-migration.md:110`) |
| `preferred_memory_order`, `min_alignment` | heliaAOT policy tables, in neither the package nor the export (`0002-migration.md:122`) |

Every value in the table comes from `resolve()`, not from the export's
`catalog`. heliaAOT's adapter computes `speeds_mhz`, `capabilities` and
`memories` itself from `Target` queries; the export does not carry them.

Per reader:

- heliaAOT keeps `targets.json` and builds it from `SocPlatform.from_target`
  (RFC 0002, "Adapters, in the consumers"). Its readers and `--check`
  are unchanged. ADR 0004 point 4 asks every output that depends on
  catalog facts to record `identity()`, so the file gains an `identity`
  member; how heliaAOT versions that addition is heliaAOT's decision. A
  `soc` or `series` field would let `TargetChips.astro` drop its
  hand-kept family table; that is heliaAOT's choice. Whether heliaAOT's
  Targets reference keeps its hardware columns or links to the catalog
  pages is open question 4.
- The handbook's `mcu-coverage.yaml` records tool integration by URL and
  stays pointed at heliaAOT's file.
- The hub reads neither file today. Open question 1.

### Markdown pages

`helia_platforms.export` renders pages only on the publishable path, from
the `builtin(include_plugins=False)` catalog the export is built from.
RFC 0002 defines no filtered `Catalog` object, and this path needs
none, because the filter removes nothing from that catalog. The
renderer takes the list of Socs and boards, and every declared fact it
shows, from the filtered export document, so pages inherit the filter and
the scrubbing. It takes derived values from `Catalog.resolve()` on the
same catalog, and fails if a resolved `Target` has a `release_status`
other than `public`. Where a `Target` method raises `PlatformError`
because no boot configuration is selected, as `flash_load_address()` does
(RFC 0002 `:809`), the page says that no boot configuration is selected
instead of failing.

- One page per Soc, `socs/<id>.md`: series, cores and NPUs, the memory
  map (region, base, size, technology, attachment), clock domains and
  operating points, boot configurations and reservations, image slots
  (the Soc's and each Part's), who programs each core, its
  implementations and parts, the boards that carry it, aliases, and the
  provenance status per group.
- One page per board, `boards/<id>.md`: its part and Soc (linked),
  populated external memory, add-ons that fit and compositions, debug
  facts, the values `resolve()` derives for it (`Target.capabilities`,
  `usable_nvm()` with the other cores' image slots it leaves out,
  `cpu_mhz()` per operating point), and aliases.
- An index page listing both, grouped by series.

Pages therefore show derived values that the JSON does not carry.

Every table is a plain Markdown table and nothing depends on a site
component, because a component prop does not survive the Markdown
rendition of a page, as heliaAOT's renderer notes
(`render-generated.mjs:12-15` at `1fd91daf`). Front matter holds only
`title`, which Starlight requires (both heliaAOT's site and the hub use
Starlight), and `description`. Each page ends with the package version and
`catalog_digest`. Aliases get no page of their own. The renderer uses
only the standard library (RFC 0002 principle P8).

### Command line

#49's `export` command writes only `--schema` (#49 at `af7482b`,
`cli.py:71-81`). This note adds:

| Option | Writes |
|---|---|
| `--json [FILE]` | The export document |
| `--export-schema` | The export JSON Schema |
| `--pages DIR` | The Markdown pages; refuses `--overlay` and `--include-plugins` |
| `--release DIR` | The release assets: the export document and the pages; refuses `--overlay`, `--include-plugins` and `--provenance` |
| `--provenance` | Full provenance records in `catalog`, with `--json` only |
| `--overlay FILE` (repeatable), `--include-plugins` | Adds sources to a `--json` export for internal use; the filter still applies, and `identity` names each source |
| `--check` | Compares with the existing outputs and fails on any difference |

Tests cover the refusals, the empty-sources check before `--pages` and
`--release` write, and the export schema rejecting a document whose three
`schema_version` values differ.

### Where outputs are published

ADR 0005 governs every output here, because each one carries catalog
content.

- Nothing gets a public URL until the owner chooses a publication path
  and the data audit of ADR 0005 point 2 is done. This repository has no
  Pages site; a Pages site from a private repository is public, as
  heliaAOT's and the hub's are, so creating one would be a publication.
- The wheel ships the export code and both schemas, not generated JSON or
  pages: the package produces them on demand, and a copy in the wheel
  would be a second rendering of data the wheel already holds.
- Each GitHub release of this repository attaches the output of
  `--release`, the export document and a pages archive, built from the
  wheel that ADR 0005's build job tests (ADR 0005 point 4). While the
  repository is private, only readers with access see them; a consumer's
  CI needs the read token of ADR 0005 open question 2.
- A consumer that commits a copy, as the hub does with the handbook
  portfolio, takes it from a release asset or from `--release`, and
  records the export's `identity` beside it. That `identity` lists no
  source, which the consumer can check. Committing pages or JSON into the
  hub publishes them once the hub deploys its real site, so the hub takes
  catalog content only after the ADR 0005 audit and the owner's
  confirmation that every named Soc, Part, Board and Implementation is
  announced (ADR 0005 point 3).

## Deferred: resolved targets

An earlier draft of this note gave the export a fourth member,
`targets`: one resolved record per board, part, implementation and Soc
id, and per composition alias, keyed by that id or alias. A record held,
per group: identity (`id`, `kind`, the ids of its Soc, implementation,
part and board, `aliases`, `origin`, `category`, add-ons); structure
(cores with their `isa()` features, NPUs with `accelerator_config`,
accelerators); memory (per programmable core, the regions it reaches
after the implementation subset, `usable_nvm()` and
`flash_load_address()`, and the external memories); clocks (operating
points, the default, `cpu_mhz` and `npu_mhz` per point); boot (the
selected configuration and the names of the others); `jlink_device`,
`trace_clock_mhz` and `sdk`; sorted `capabilities`; and the worst
provenance status per group.

A per-core value was `null` when the `Target` method that computes it
raises `PlatformError` because no boot configuration is selected or
because the `app_start` region has no `base` (RFC 0002 `:187-191`,
`:809`). Overlay and plugin entries can produce both: #49's file format
lets a Soc omit `boot_configs` and `default_boot` and lets an overlay
region omit `base` (#49 at `af7482b`, `_format.py:280-281`, `:125`).
Built-in regions always carry a base (RFC 0002 `:191`; #49 at `af7482b`,
`catalog.py:344-345`), so in built-in data only a missing boot
configuration produced `null`. `targets` had its own JSON Schema, which
`--export-schema` wrote, and heliaAOT's field mapping read `cpu`,
`speeds_mhz`, `capabilities`, `supports_fp16` and the memory inputs from
the record.

It is deferred for the reasons the code owner gave in review of #55:

- No reader outside Python is identified yet (the reader survey in
  "Problem"). heliaAOT builds its own `targets.json` through its
  adapter, and the hub and the handbook read neither file.
- A record fixes `usable_nvm()` and `flash_load_address()` at the
  default boot configuration only, so a reader that selects another
  configuration gets values the record does not describe.
- Once shipped, removing a field from it is a schema break (ADR 0004
  `:131`), so an early shape is costly to correct.

`targets` is added when a consumer outside Python needs it. Until then
the public contract for resolved values is `resolve()` and the `Target`
queries. When it is added, its definitions join the export schema, and
the addition is a `feat:` (ADR 0004 point 2).

## Open questions

1. Where do the per-SoC and per-board pages live? Options: the hub, which
   its taxonomy argues against (`docs/site-taxonomy.md:193-198`); a docs
   site for this package once it is public; or each tool's docs. Does the
   hub want the JSON export to drive its filters and support matrices in
   place of its hand-written families? The hub's owners decide.
2. Is a shared `schema_version` acceptable when the export breaks and the
   overlay format does not, or should the export get its own number,
   which would amend ADR 0004?
3. Should public pages show a provenance status at all, and is showing
   `unverified` on a public page acceptable?
4. Does heliaAOT's Targets reference keep its hardware columns, or keep
   only heliaAOT's budgets and policy and link to the catalog pages?
   heliaAOT's owners decide.
5. Should FPGA and FVP implementations of a public Soc appear on the
   public pages, or only in the JSON? Their release status says they may
   be published; whether developers should see them is an editorial
   choice.
6. Are release assets worth producing, or is running
   `helia-platforms export --release` from a pinned tag enough for every
   consumer?

## Edits to other documents on acceptance

Made on acceptance, 2026-10-21.

- RFC 0002: the `to_dict()` comment (`:707`) and the
  `helia_platforms.export` sentence (`:853-855`) link here, and the
  sentence says that pages and release assets are built only from
  `builtin(include_plugins=False)`; the CLI line (`:856-861`) lists the
  new `export` options; the release status rule (`:390-392`) also drops a
  composition when its board or any of its add-ons is scrubbed.
- ADR 0002: open question 3 is answered as above.
