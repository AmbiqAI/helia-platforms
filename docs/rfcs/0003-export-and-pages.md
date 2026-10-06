# RFC 0003: the JSON export and the generated catalogue pages

Status: Draft, 2026-10-06. Builds on [RFC 0002](0002-model-and-api.md)
(`Catalogue.to_dict()`, release status and `helia_platforms.export`) and
on ADRs [0002](../adr/0002-schema-format-and-runtime.md),
[0004](../adr/0004-schema-and-catalogue-versions.md) and
[0005](../adr/0005-publication-and-embargo.md), all Proposed when this was
written. Section 4 of the [review of RFC 0001](0001-platform-catalogue-review.md)
asks for "one machine-readable export (the successor of `targets.json`)
and generated per-SoC and per-board pages". This note designs both. It
does not edit RFC 0002; the edits RFC 0002 would take on acceptance are
listed at the end. RFC 0002 line numbers below are at `4bc4dea`.

## Problem

RFC 0002 names the outputs in two lines: `to_dict()` is "the JSON export"
(`docs/rfcs/0002-model-and-api.md:699`), and `helia_platforms.export`
"writes the JSON catalogue, filtered and scrubbed by effective release
status, the JSON Schema and Markdown pages" (`:845-847`). It does not say
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

One JSON document, built from a `Catalogue`, with four top-level keys:

| Key | Content |
|---|---|
| `schema_version` | ADR 0004's integer. |
| `identity` | `Catalogue.identity().to_dict()` (ADR 0004 point 4): package version, `schema_version`, `catalogue_digest`, and one entry per source applied on top of the built-in data. |
| `catalogue` | The entities, written as a complete document in ADR 0002's file format: `schema_version`, equal to the export's top-level `schema_version`, then `cores`, `socs`, `implementations`, `parts`, `boards`, `addons`, `memory_devices`, `compositions`, `shorthands`. Every entry is written after the `based_on` merge, so no entry carries `based_on` or a file-only delta key that applies over a base (a Soc's `memories_removed` and the like, a Part's `image_slots_removed`; #49's `_format.py:286-301`, `:369`). An Implementation entry keeps its `subset` as in the file format, because its removals, resizes, rebases and clock caps live only there (ADR 0002 `:211-216`); a reader that wants the realized Implementation reads its `targets` record. |
| `targets` | One resolved record per board, part, implementation and Soc id, and per composition alias, keyed by that id or alias. |

`catalogue` and `targets` serve different readers. `catalogue` is the raw data: a
tool can rebuild any view from it, and because it is in the file format,
the file-format JSON Schema of the same `schema_version` validates it (in
the draft schema of #49, `provenance` is not a required key of an entry,
so an entry without it validates). The member carries its own
`schema_version` because that schema requires the key at the top level
of a document and allows no top-level key it does not list
(`helia-platforms-v1.schema.json:110-113`). `targets` carries what the package
computes, so that a reader that cannot run Python, such as an Astro
docs site, does not reimplement derivation (RFC 0002 principle P3). A
`targets` record holds, per group:

- identity: `id`, `kind`, the ids of its Soc, implementation, part and
  board, `aliases`, `origin`, `category` and add-ons;
- structure: cores with their `isa()` features, NPUs with
  `accelerator_config`, accelerators;
- memory: per programmable core, the regions it reaches after the
  implementation subset, `usable_nvm()` and `flash_load_address()`, each
  of which may be `null` as described below; the external memories;
- clocks: operating points, the default, and `cpu_mhz` and `npu_mhz` per
  point;
- boot: the selected boot configuration and the names of the others;
- debug and SDK: `jlink_device`, `trace_clock_mhz`, `sdk`;
- `capabilities`, sorted;
- `provenance`: `Target.provenance()`, the worst status per group.

A per-core value is `null` when the Target method that computes it raises
`PlatformError` because no boot configuration is selected or because the
`app_start` region has no `base`; RFC 0002 says `flash_load_address()`
raises in both cases (`:187-191`, `:801`). The `targets` schema allows
`null` for these values. Entries from `--overlay` files and plugins can
produce them: #49's file format lets a Soc omit `boot_configs` and
`default_boot` (`_format.py:280-281`) and lets an overlay region omit
`base` (`_format.py:125`). Built-in regions always carry a base (RFC 0002
`:191`; #49's `catalogue.py:319-321`), but no rule requires a built-in
Soc to carry a boot configuration, so in built-in data only a missing
boot configuration produces `null`.

A record carries no tool policy and no budgets: no alignment, placement
order or linker windows. The optional link-environment dataset stays
outside the export (RFC 0002 open question 2).

The document has no timestamp, and is written with sorted keys, two-space
indentation and a final newline. The same package version and inputs
therefore give the same bytes, and a consumer that commits a copy can
check it byte for byte, as heliaAOT does.

### Release status, filtering and scrubbing

The export is always filtered by RFC 0002's rule ("Release status",
`:374-387`) with ADR 0005's additions: no embargoed entry and no target
whose effective status is embargoed; embargoed ids scrubbed from
shorthands, compositions, `fits_boards`, `default_board`, `applies_to` and
aliases; a Core or Npu dropped when no exported Soc references it. The
export also drops a composition whose `board` is scrubbed, because a
composition without a board is not a valid entry: #49's schema requires
`board` (`helia-platforms-v1.schema.json:1345-1364`). This tightens RFC
0002's rule, which drops a composition only when it references only
embargoed entities (`:383-387`) and so would keep a composition of an
embargoed board and a public add-on with its `board` removed.
`Catalogue.to_dict()` returns this filtered document. The unfiltered form
exists only for ADR 0005's distribution test, which asserts the two are
equal for the built-in catalogue. No public call returns an unfiltered
dump, so a tool cannot publish one by calling `json.dump(cat.to_dict())`.

By default the export reads `builtin(include_plugins=False)`, as
[0002-private-silicon.md](0002-private-silicon.md) intends for "exports
that must not depend on the machine". Built-in entries must be `public`
(ADR 0005 point 1), so for the default export the filter removes nothing;
it matters when a caller adds `--overlay` files or `--include-plugins`.
`identity.sources` then records each source.

### Provenance

The default export carries no provenance records. `catalogue` omits every
`provenance` key and writes plain values in place of the `{value,
provenance}` form, as the projection that `catalogue_digest` hashes does
(ADR 0004 point 1). Each `targets` record carries only its per-group
worst status.

`--provenance` writes the full records into `catalogue` in the file
format. ADR 0005 point 2 requires an audit of the source register's
document ids, the provenance notes and the `verified_by` logins before
any publication with catalogue content, so an export with full records
is for internal use until that audit is done. Reason: pages need to say
how well a value is sourced, which the status does; the full records add
internal document ids and GitHub logins that the audit has not cleared.

### Schema and versioning

ADR 0004 gives one `schema_version` to "the overlay format and the JSON
export shape" and bumps it on a schema break, including "an export field
removed or renamed". This note follows that:

- The export declares `schema_version: N`, and its `catalogue` member is
  a file-format document that declares the same `schema_version: N`.
- The `targets` member gets its own JSON Schema, generated from a
  `TypedDict` declaration as ADR 0002 section 3 does for the file format:
  `src/helia_platforms/schema/helia-platforms-export-v<N>.schema.json`,
  `$id` `tag:ambiq.com,2026:helia-platforms/export/v<N>`, shipped in the
  wheel and held by the same staleness test. This answers ADR 0002 open
  question 3: yes, but only for `targets`, because `catalogue` reuses the
  file-format schema.
- Adding a field to a `targets` record is a `feat:` (a patch before 1.0);
  removing or renaming one is `feat!:` and bumps N.

The cost: a break in the export alone bumps N for overlay files too, and
overlay authors then see ADR 0004's one-release deprecation warning for a
format that did not change. Open question 2 asks whether that is
acceptable.

### How `targets.json` consumers migrate

The catalogue export replaces `targets.json` as the machine-readable
source of hardware facts. It does not replace `targets.json` as heliaAOT's
record of which targets heliaAOT supports and how it plans into them,
because budgets and policy stay in heliaAOT (RFC 0002 principle P1).
Each field of a `targets.json` record maps as follows:

| `targets.json` field | Source after adoption |
|---|---|
| `name` | The name heliaAOT registers; `targets[...].id` is the canonical id (heliaAOT keeps a passed alias, [0002-migration.md](0002-migration.md)) |
| `cpu` | Core 0 of the `targets` record |
| `speeds_mhz` | `cpu_mhz` per operating point |
| `capabilities` | `capabilities`, mapped by heliaAOT's adapter, plus its `MCU` tag, without `BLE` and `USB` (`0002-migration.md:121`) |
| `supports_fp16` | `isa.supports_fp16` of core 0 |
| `memories` | heliaAOT's budgets, computed by its adapter from the regions, `usable_nvm()` and external memories the record carries (`0002-migration.md:110`) |
| `preferred_memory_order`, `min_alignment` | heliaAOT policy tables, not in the export (`0002-migration.md:122`) |

Per reader:

- heliaAOT keeps `targets.json` and builds it from `SocPlatform.from_target`
  (RFC 0002, "Adapters, in the consumers"). Its readers and `--check`
  are unchanged. ADR 0004 point 4 asks every output that depends on
  catalogue facts to record `identity()`, so the file gains an `identity`
  member; how heliaAOT versions that addition is heliaAOT's decision. A
  `soc` or `series` field would let `TargetChips.astro` drop its
  hand-kept family table; that is heliaAOT's choice. Whether heliaAOT's
  Targets reference keeps its hardware columns or links to the catalogue
  pages is open question 4.
- The handbook's `mcu-coverage.yaml` records tool integration by URL and
  stays pointed at heliaAOT's file.
- The hub reads neither file today. Open question 1.

### Markdown pages

`helia_platforms.export` renders pages from the export document, not from
model objects. Pages therefore inherit the filter and the scrubbing, and
cannot state a fact the JSON does not carry; heliaAOT's renderer follows
the same rule (`docs/scripts/render-generated.mjs:8-9` at `1fd91daf`).

- One page per Soc, `socs/<id>.md`: series, cores and NPUs, the memory
  map (region, base, size, technology, attachment), clock domains and
  operating points, boot configurations and reservations, its
  implementations and parts, the boards that carry it, aliases, and the
  provenance status per group.
- One page per board, `boards/<id>.md`: its part and Soc (linked),
  populated external memory, add-ons that fit and compositions, debug
  facts, the resolved values of its `targets` record (capabilities,
  usable NVM, clocks), and aliases.
- An index page listing both, grouped by series.

Every table is a plain Markdown table and nothing depends on a site
component, because a component prop does not survive the Markdown
rendition of a page, as heliaAOT's renderer notes
(`render-generated.mjs:12-15`). Front matter holds only `title`, which
Starlight requires (both heliaAOT's site and the hub use Starlight), and
`description`. Each page ends with the package version and
`catalogue_digest`. Aliases get no page of their own. The renderer uses
only the standard library (RFC 0002 principle P8).

### Command line

PR #49's `export` command writes only `--schema`. This note adds:

| Option | Writes |
|---|---|
| `--json [FILE]` | The export document |
| `--export-schema` | The `targets` JSON Schema |
| `--pages DIR` | The Markdown pages |
| `--provenance` | Full provenance records in `catalogue` |
| `--overlay FILE` (repeatable), `--include-plugins` | Adds sources; the filter still applies, and their entries can give `null` per-core values in `targets` |
| `--check` | Compares with the existing outputs and fails on any difference |

### Where outputs are published

ADR 0005 governs every output here, because each one carries catalogue
content.

- Nothing gets a public URL until the owner chooses a publication path
  and the data audit of ADR 0005 point 2 is done. This repository has no
  Pages site; a Pages site from a private repository is public, as
  heliaAOT's and the hub's are, so creating one would be a publication.
- The wheel ships the export code and both schemas, not generated JSON or
  pages: the package produces them on demand, and a copy in the wheel
  would be a second rendering of data the wheel already holds.
- Each GitHub release of this repository attaches the default export and
  a pages archive, built from the wheel that ADR 0005's build job
  tests. While the
  repository is private, only readers with access see them; a consumer's
  CI needs the read token of ADR 0005 open question 2.
- A consumer that commits a copy, as the hub does with the handbook
  portfolio, records the export's `identity` beside it. Committing pages
  or JSON into the hub publishes them once the hub deploys its real site,
  so the hub takes catalogue content only after the ADR 0005 audit and
  the owner's confirmation that every named Soc, Part, Board and
  Implementation is announced (ADR 0005 point 3), and only without
  `--provenance`.

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
   only heliaAOT's budgets and policy and link to the catalogue pages?
   heliaAOT's owners decide.
5. Should FPGA and FVP implementations of a public Soc appear on the
   public pages, or only in the JSON? Their release status says they may
   be published; whether developers should see them is an editorial
   choice.
6. Are release assets worth producing, or is running
   `helia-platforms export` from a pinned tag enough for every consumer?

## Edits to other documents on acceptance

- RFC 0002: the `to_dict()` comment (`:699`) and the
  `helia_platforms.export` sentence (`:845-847`) link here; the CLI line
  (`:848-852`) lists the new `export` options; the release status rule
  (`:383-387`) also drops a composition whose `board` is scrubbed.
- ADR 0002: open question 3 is answered as above.
