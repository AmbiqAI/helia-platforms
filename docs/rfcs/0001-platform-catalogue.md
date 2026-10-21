<!--
Provenance: imported on 2026-10-04 from a draft circulated as heliaAOT
"RFC 0005: platform SSOT" (0005-platform-ssot.md, dated 2026-09-30).
Renumbered 0001 as the founding RFC of this repository. Text is unchanged
except this header and the appendix link. The review that lists the open
weaknesses and proposed revisions is 0001-platform-catalogue-review.md.
Status here: Draft, under revision. Not yet accepted.
Superseded in part by RFC 0002, accepted 2026-10-21; see its Changes relative to RFC 0001 table.
-->

# RFC: `helia-platforms`, a single source of truth for SoC and board facts

## Status

Proposed, 2026-09-30. Not yet reviewed by the helia-profiler maintainers,
nor by neuralspotx's for the facts read from their repository.
Implementation detail, verified line by line, is in the
[appendix](0001-platform-catalogue-appendix.md).

- **Phase 1:** create `AmbiqAI/helia-platforms` from helia-profiler's
  `platform/` package, reconcile the data, publish 0.1.0 to PyPI.
- **Phase 2:** heliaAOT consumes it through an adapter.
- **Phase 3:** helia-profiler consumes it.
- **Phase 4:** 1.0.0 and the remaining hard-coded sites.

## Audience

heliaAOT and helia-profiler maintainers; neuralspotx maintainers for the
facts the package reads from their repository.

## Summary

Four repositories each keep their own description of what an Ambiq chip is:
heliaAOT's 15 hand-written `SocPlatform` literals, helia-profiler's
`SocDef`/`BoardDef` dataclasses, neuralspotx's per-board `board.yaml`, and
the `nsx-ambiq-sdk`'s CMake fact files and linker scripts. They disagree on
memory sizes, clock tiers and names, and helia-profiler bridges to heliaAOT
with a hand-written name map that sends three boards to the wrong target.

`helia-platforms` is one Python package that holds the silicon and board
facts both tools need, plus each tool's per-target settings in a section
labelled with that tool's name. It is a **declared catalog with
validators**, not a derivation engine: every value is written down per
entry, and tests enforce the invariants and compare the overlap with the
SDK. It is published to PyPI before either consumer adopts it. heliaAOT
keeps its `SocPlatform` type and builds it from the catalog; the
profiler keeps its policy modules and imports the facts.

## Motivation

- **The name map compiles three boards for the wrong target.** hpx's
  `_BOARD_TO_AOT_PLATFORM` sends `apollo330mP_evb`, `apollo510dL_evb` and
  `apollo510b_evb` to heliaAOT's `apollo510_evb`, although heliaAOT has a
  target for each. heliaAOT then plans with apollo510's capabilities,
  memories (ITCM and PSRAM present) and clocks. hpx re-applies its own
  capacities afterwards and raises on overflow, so a wrong size surfaces as
  a warning or an error rather than a silent mis-placement; the wrong
  capability set and memory list do not. `hpx analyze` takes a different
  path that passes the raw board name, which heliaAOT case-folds to the
  right target, so the two hpx commands disagree with each other.
- **Every new chip is entered four times, and the copies drift.** Apollo330P
  has 256 KB of TCM in heliaAOT and 240 KB in helia-profiler; heliaAOT lists
  a 192 MHz clock tier the profiler omits; heliaAOT's apollo510 PSRAM is a
  typo (32168 KB).
- **heliaAOT's platform facts are too thin for its own consumers.** The
  Zephyr `platform.h` template picks TCM section macros by matching the
  start of the platform *name*; the e2e harness derives fp16 support from
  the CPU string.
- **The profiler already planned the extraction.** Issue #229 names
  `platform/` as a "future shared-package seam", and a package-layout test
  keeps it importable on its own.
- **Tools need to query the facts by any spelling of a platform's name.**

## Goals

- **One entry per chip and per board,** with a schema that says which facts
  are silicon, which are board, and which are one tool's settings.
- **Declared facts, validated.** Tests enforce invariants (FP16 only with
  MVE-FP, MVE only on Armv8.1-M cores, regions inside physical bounds,
  unique ids and aliases, every reference resolves) and compare the overlap
  with the SDK. Only `supports_fp16/fp32/fp64` and `supports_npu` are
  computed.
- **Canonical names with aliases,** so each tool resolves its own spelling
  through the registry instead of a private map.
- **One custom-board file works in both tools.**
- **Every heliaAOT change is visible.** The adoption PR's regenerated
  `targets.json`, residency examples and baselines are the change list, and
  the plan-JSON changes are named; nothing is hidden behind a temporary data
  set.

## Non-goals

- Owning tool policy: reset strategies, clean-window timers, PMU counter
  planning, placement slack, power-sync GPIO defaults, support channels and
  driver-support flags stay in helia-profiler.
- Generating the SDK's CMake facts or linker scripts. The SDK stays the
  authority for firmware builds; this package is the authority for tools.
- Serving the legacy make-based neuralSPOT beyond what heliaAOT's
  `neuralspot` module type needs.
- Making neuralspotx a consumer. It stays a source of facts (`board.yaml`,
  per-board `debug.cmake` overrides) and the naming authority; its own
  boards that neither tool supports are not in the catalog. See
  *Alternatives considered*.
- Knowing an application's stack, heap or other `.bss`. The budget heliaAOT
  plans against is the region the link environment gives the AOT sections;
  the application owner reconciles the rest, and hpx checks the real layout.
- Toolchain flags. `fpu` records the SDK's gcc `-mfpu` spelling, not a flag
  consumers emit.

## Architecture

### Two levels, plus IP blocks

A **`SocDef`** is a chip: apollo3, apollo3p, apollo4p, apollo4l, apollo510,
apollo510b, apollo5b, apollo330P, apollo510L, atomiq110. A **`BoardDef`**
references a chip and adds what the board contributes: external memories
(PSRAM, NVM), the J-Link device name for its package, and, for an FPGA
realization, clock and trace-clock overrides. Two IP-level entities are
shared by chips: **`CoreDef`** (cortex-m4, cortex-m55: architecture class,
ISA, PMU tier) and **`NpuDef`** (ethos-u85-256: MACs per cycle, Vela
accelerator config). A chip composes them; the options Arm leaves to the
implementer (FPU flavour, MVE flavour, caches, NPU clock and base address)
are the chip's fields, not the IP's.

Every board in either tool's catalog today becomes a `BoardDef`, and
every `BoardDef` is a heliaAOT target: 13 from the profiler and 3 Apollo3
boards from heliaAOT. Two heliaAOT names become aliases:
`apollo3_blue_plus_evb` is byte-identical to `apollo3p_evb`, and
`apollo510l_evb` is the profiler's `apollo510dL_evb` (Ambiq sells one
Apollo510 Lite evaluation board, the AP510DLEVB, fitted with the D variant;
the SoC entry `apollo510L` covers the series' three parts).

An illustrative entry (field names are the design; the YAML layout is not):

```yaml
socs:
  apollo510:
    series: apollo5            # SDK product line, drift-tested
    core_tier: ap5             # profiler's policy tier, not drift-tested
    core: cortex-m55
    fpu: fpv5-sp-d16           # the SDK's -mfpu spelling
    fpu_dp: true               # CMSIS __FPU_DP
    mve: fp                    # -> supports_fp16
    has_dcache: true
    memories:
      itcm:  {kind: itcm, size: 256K,  base: 0x00000000}
      dtcm:  {kind: dtcm, size: 512K,  base: 0x20000000}
      ssram: {kind: sram, size: 3072K, base: 0x20080000}
      mram:  {kind: mram, size: 4096K, base: 0x00400000}
    clocks: {cpu: [{name: lp, mhz: 96}, {name: hp, mhz: 250}]}
    jlink_device: AP510NFA-CBR
    c_define: AM_PART_APOLLO510
    cmsis_header: apollo510.h
    zephyr_tcm_sections: [__dtcm_bss_section, __dtcm_data_section]
    helia_aot:
      capabilities: [MCU, DSP, MVE, FP16]
      preferred_memory_order: [dtcm, sram, mram]
      min_alignment: 16
boards:
  apollo510_evb:
    soc: apollo510
    tier: evb
    memories:
      psram: {kind: psram, size: 65536K, external: true}
      nvm:   {kind: nvm,   size: 8192K,  external: true}
    helia_aot:
      capabilities: [MCU, DSP, MVE, FP16, PSRAM]
      preferred_memory_order: [dtcm, sram, mram, psram]
```

The full field list per entity, the seed rule for boards heliaAOT has no
literal for, and the derived properties are in appendix B.

### Facts, and each tool's settings

The test for a top-level field is whether it is true of the hardware or
the SDK regardless of which tool asks, not whether both tools read it. So
the J-Link device name, the trace clock, the compile definition, the CMSIS
header name and the HAL's SSRAM power enum are facts and live in the
package although only hpx reads them today; they are all drift-testable
against the SDK. Two fields the profiler holds do not pass the test:
`app_flash_load_addr` is the default linker window's MRAM origin and
becomes an accessor over the windows table rather than a second field to
keep in sync, and `rtt_scan_ranges` is hpx's choice of where to look for
the RTT control block (the DTCM window on M55 parts, a 1 MB aperture on M4
parts) and returns to the profiler as a rule over the package's windows.

What a tool decides *about* a target lives in a section named after the
tool: heliaAOT's `capabilities`, `preferred_memory_order` and
`min_alignment` (16 with MVE is a placement policy, not an MVE
requirement) go under `helia_aot`; a custom entry may carry a `profiler`
section (GPIO pins, channel, capture-buffer size). Profiler policy for
built-in boards stays in the profiler, keyed by id: reset strategies,
PMU counter planning, `pmu_max_ops`, the `has_usb` driver-support flag,
the RTT scan rule. Appendix C lists every profiler symbol and which side
it lands on.

Two groupings are both called "family" today and are kept apart: `series`
is the SDK's product line (`apollo5`, `apollo330`, `atomiq`) and is
drift-tested; `core_tier` is the profiler's AP3/AP4/AP5 hardware tier that
its policy tables key on.

### Names

Canonical ids are the NSX/SDK spellings (`apollo330P`, `apollo330mP_evb`,
`apollo510dL_evb`), looked up case-insensitively. `aliases` are additional
lookup keys, unique across all entities. A SoC id resolves to its board
when the SoC has exactly one, so `--platform.name atomiq110` keeps working.
heliaAOT stores and prints the lowercase form of board names (registry
keys, `SocPlatform.name`, `list-targets`, the plan JSON; its AGENTS.md §16
invariant is unchanged), while `SocPlatform.soc` keeps the NSX spelling
because neuralspotx matches SoC ids exactly in nsx manifests.
`resolve_board` and `resolve_soc` are separate calls. `_BOARD_TO_AOT_PLATFORM`
is deleted; hpx's documented `engine.config.platform_name` override survives
as an escape hatch.

### Memory: physical regions and linker windows

A memory has two honest sizes. The **physical** size comes from the SDK's
register headers (512 KB of DTCM on apollo510). The **window** is what a
given linker script hands the program, and it differs from the physical
size for reasons that vary per chip and toolchain: a bootloader region at
the start of MRAM (64 KB on Apollo5, 48 on Apollo3, 96 on Apollo4), a
stack/heap reservation at the top of TCM (16 KB in gcc scripts, 20 KB in
armclang scatter files), a stack slot carved from SRAM on apollo3p, and
bank selection on apollo4p. Zephyr's devicetrees already bake in the same
reservations for Apollo510 and reserve differently elsewhere (2 MB of SRAM
on the Apollo510 EVB, 2432 KB across three banks on apollo4p, a 64 KB TCM
on `apollo4p_blue_kxr_evb`).

Neither tool is consistent about which size it stores today. The package
stores both: each region carries its physical size and base, and a separate
**windows table**, keyed by (board, linker profile, link family) with the
SDK or Zephyr revision it was verified against, is lifted from the
profiler's `memory_map.py` as data. Link families are `gnu`, `armlink` and
`zephyr`; the `zephyr` rows exist for the six boards Zephyr ships.

heliaAOT budgets by link family, selected per module type: a `SocPlatform`
carries `budgets: {gnu, zephyr}`, `resolve_platform` receives the module
type from the converter and picks `zephyr` for the `zephyr` module type and
`gnu` for the rest (a board with no `zephyr` row uses `gnu` with a warning),
and `target-info` and `targets.json` print every budget. hpx's capacity
checks read the window of the toolchain family it builds with. All numbers,
sources and the Zephyr table are in appendix D.

### Custom boards

The package owns one overlay format: `socs:`/`boards:` maps, `based_on`
(copies every field of the base, then applies the entry's keys), regions by
name, `remove:` for an inherited region, per-tool sections, unknown keys
rejected with a suggestion.

```yaml
boards:
  my_product_v1:
    based_on: apollo510_evb
    remove: [nvm]
    memories:
      psram: {kind: psram, size: 8192K, external: true}
    profiler: {default_sync_gpio_pin: 27, channel: dev}
```

The same file is passed to heliaAOT as `platform.overlay: <path>` and to
hpx as `target.overlay: <path>`, so a customer describes a board once. heliaAOT's existing
`platform:` block still builds a run-local platform exactly as today; hpx
translates its current inline `custom_socs`/`custom_boards` shape with a
logged deprecation warning for a release. The shim's field mapping and the
two v1 behaviours that change are in appendix E.

### Query API and CLI

`resolve_board`, `resolve_soc`, `get_*`/`list_*`, `boards_for(soc)`,
`socs_with(...)`, `linked_memory_map(soc, board, profile, family)`,
`placement_ranges`, `classify_address`, the board-aware accessors
(`jlink_device_for`, `swo_trace_clock_for`, `clocks_for`) and
`load_overlay`; no I/O at import time. A `helia-platforms` CLI (`list`,
`show`, `windows`, `validate`, `check-sdk`) gives the catalog a view of
its own; `target-info` and `hpx boards` remain each tool's view.

### Authority

The `nsx-ambiq-sdk` stays the authority for firmware builds; this package is
the authority for tools, and its CI checks the overlap. It checks out the
SDK at the tags neuralspotx pins (`v5.2.24`, `v5.2.25` for atomiq110) and
compares series, core, MVE/FPU, PMU tier, NPU presence, compile define,
flash address, trace clock, the default-profile gcc windows and the
physical sizes; the field-to-key table and the exclusions (the J-Link name,
until its spellings are reconciled against SEGGER's device database) are in
appendix G. The `zephyr` rows are checked against a pinned Zephyr revision.

### Packaging and versions

The repo is public and 0.1.0 is on PyPI before either consumer adopts it,
so consumers depend on the PyPI package from the start: heliaAOT's release
workflow smoke-installs its wheel with plain pip, so a dependency that is
not on PyPI would fail it. Co-development uses
`uv run --with-editable ../helia-platforms`. Before 1.0, consumers pin
`>=0.y,<0.(y+1)` and releases go package → heliaAOT → helia-profiler in one
window; data corrections are `feat:` PRs (a minor bump, since they change
generated code and placement budgets). 1.0.0 is tagged once both consumers
are on the package; then `>=1.y,<2`. Name: `helia-platforms`, import
`helia_platforms`, repo `AmbiqAI/helia-platforms`; the PyPI name is free.

## Alternatives considered

- **Derive facts from descriptors instead of declaring them.** Rejected. The
  values both tools carry were hand-chosen: heliaAOT's capability lists are
  in six different orders and its docs export prints them in list order
  under a byte-for-byte check; BLE appears on some boards with no field
  anywhere that says a board has a radio; the RTT scan ranges are a 1 MB
  aperture on M4 and the TCM window on M55. A rule would either change
  today's outputs or need a special case per entry, which is declaring with
  extra steps. Only `supports_fp16/fp32/fp64` and `supports_npu` are derived.
- **Lift the profiler's whole `platform/` closure.** Rejected: it carries
  reset strategies, PMU counter planning and placement slack that are hpx's
  decisions, not facts about the chip. Facts move; policy stays, keyed by
  id.
- **A minimal shared core holding only what both tools read** (core,
  MVE/FPU, memories, clocks, NPU), with hpx keeping a per-chip table of
  J-Link names, trace clocks, defines and HAL enums. Rejected: a new chip
  would again need entries in two repositories, the SDK drift test would
  split across them, and a custom-board file could not describe a board
  well enough for hpx to flash it without hpx-only keys in the shared
  format. The boundary is facts versus policy, not the intersection of
  readers.
- **A chip level above `SocDef`** (a chip references a SoC and an NPU).
  Rejected: no two chips share an MCU subsystem (apollo510 and atomiq110
  differ in DTCM, SSRAM and clocks), so the level would add a hop without
  deduplicating anything. The SoC is the composition; `CoreDef` and `NpuDef`
  are its IP-level peers.
- **MVE and FPU on `CoreDef`.** Rejected: on the Cortex-M55 they are
  implementation options (MVE none/int/fp, FPU optional, caches
  configurable), so they are per-chip fields; `CoreDef` keeps architecture
  facts only.
- **One memory budget per target** (physical everywhere, or the nsx window
  everywhere). Rejected: nsx and Zephyr differ in opposite directions on
  the same chip (Zephyr hands the Apollo510 EVB 2 MB of SRAM where nsx
  hands 3 MB; nsx reserves TCM that Zephyr's Apollo4 devicetree does not),
  so any single table over-promises one environment. Budgets per link
  family, selected by module type.
- **Lowercase canonical ids.** Rejected after tracing where the mixed-case
  ids are load-bearing: hpx looks up starter profiles with an exact-case
  dictionary read against neuralspotx's registry, the hardware-CI runner
  label must equal the board id, and fourteen hpx test files spell them.
  Canonical ids are the NSX spellings; heliaAOT lowercases internally, which
  costs nothing because lookup is case-insensitive.
- **Prove the heliaAOT adoption byte-identical** via a temporary package
  version carrying heliaAOT's legacy values. Rejected: heliaAOT's snapshot
  suite renders one platform and no platform header, so it cannot prove
  it; the real byte-for-byte gate is `targets.json`; and a legacy-value tag
  fails the package's own SDK check and is a third copy of the data. The
  adoption PR regenerates `targets.json` and lists every change instead.
- **Submodule or git source during development.** Rejected once it was
  clear the package must be on PyPI before any consumer release anyway;
  a PyPI dependency from day one plus `uv run --with-editable` for
  co-development has fewer moving parts.
- **Namespaced tool sections in the custom-board format as a breaking
  change**, or accepting hpx's flat keys in the shared schema. Rejected in
  favour of the new format plus a translating shim in hpx: existing
  customer configs and hpx's documented shape keep working, and
  profiler-only keys stay out of the shared schema.
- **Keep BLE and USB in heliaAOT's capability list** by adding hardware
  fields. Rejected: nothing in codegen reads them, no field records a radio,
  and the profiler's `has_usb` means "the nsx USB driver supports this
  chip", which is a software fact that disagrees with heliaAOT on apollo4l.
  The tags are dropped from built-ins; the enum members stay so existing
  configs validate.
- **neuralspotx as a consumer.** Open. Every `board.yaml` field maps onto
  the model (an `nsx` section would hold `sdk_provider` and `toolchains`),
  and a generator writing `board.yaml` and the J-Link line into the board
  directories at development time, drift-checked, would leave neuralspotx's
  layout and CMake untouched with no runtime dependency. It needs
  neuralspotx's three extra boards (including an `apollo2` SoC) and its
  maintainers' agreement; the RFC currently treats neuralspotx as a source
  only.

## Migration & rollout plan

Each phase's steps, with the readers, tests and generated files they
touch, are in appendix I. The visible changes:

1. **Phase 1 — the package and 0.1.0.** Create the public repo; move the
   symbols in appendix C; add the new fields, the windows table, the overlay
   parser, the CLI and the validators; reconcile the data (appendix J);
   get helia-profiler's sign-off on the facts/policy boundary; publish.
2. **Phase 2 — heliaAOT.** One PR replaces the literals with an adapter and
   regenerates `targets.json`, the residency examples and the config/CLI
   schemas; its diffs are the change list. Budgets move to the nsx windows
   (apollo510 DTCM 512→496 KB, MRAM 4096→4032; apollo330P/510L 256→240 and
   2048→1984; Apollo4 MRAM 2000→1952; Apollo3 boards' MRAM 1024→976), a
   Zephyr budget column appears, PSRAM is added where the boards have it,
   the apollo510 PSRAM typo is fixed, BLE/USB tags go, four targets are
   added and three names become aliases, and the plan JSON's capability
   list and placement budgets move accordingly. The Zephyr `platform.h`
   template and the e2e harness read facts instead of name prefixes and
   CPU strings.
3. **Phase 3 — helia-profiler.** `platform/` keeps policy only and imports
   the facts; the name map is deleted, so `apollo330mP_evb`,
   `apollo510dL_evb` and `apollo510b_evb` compile against their own heliaAOT
   targets and `apollo5b_evb` gains one; hpx's own capacity checks tighten
   on Apollo4 and Apollo5 boards to the linker windows; `target.overlay`
   and the shim land; the heliaAOT version pins move to the Phase 2 release.
4. **Phase 4 — 1.0 and follow-ups.** Tag 1.0.0 and relax the pins; the hpx
   fixture code stops hard-coding `apollo510_evb`; `tests/e2e_zephyr` gains
   a map-file assertion so the Zephyr rows are checked by a real build.

## Validation

- Package: validators and the SDK drift test in CI, against both SDK tags
  and the pinned Zephyr revision.
- heliaAOT: the unit tests named in appendix I; `repo_tools.docs_export
  --check`; snapshot baselines regenerated only for the listed changes; the
  e2e matrix on `apollo4p_blue_kbr_evb` and `apollo510_evb`;
  `tests/e2e_zephyr` builds.
- helia-profiler: the rewritten tests named in appendix I; hardware
  validation on `apollo510_evb` and `apollo330mP_evb`.

## Risks & mitigations

- **helia-profiler has not reviewed this.** Phase 1 gates 0.1.0 on its
  maintainers' agreement with the facts/policy boundary; Phase 3 is theirs
  to schedule.
- **Two copies of the lifted code exist between Phase 1 and Phase 3.** Any
  change to the profiler's `platform/` in that window is mirrored; the two
  are diffed before Phase 3 starts.
- **Lockstep releases before 1.0.** A package minor forces both consumers to
  re-release in order. Acceptable while only our two tools consume it; 1.0
  ends it.
- **Budgets shrink on nsx targets in both tools** (apollo510 DTCM 512→496
  KB). A model that fit before may now be reported as not fitting; that
  report is correct, because the previous plan could not link.
- **The SDK or Zephyr changes a window or a fact.** The drift test fails
  when a pinned revision moves; the fix is a data release.
- **Zephyr window rows are checked only by inspection until Phase 4.**

## Open questions

- Whether the plain `apollo4p_evb` has populated PSRAM (the profiler says
  32 MB; neuralspotx says only the Display Kit shield has it).
- Which memories the atomiq110 NPU can reach and at what bandwidth, i.e.
  the Vela system config and memory mode (`Sram_Only`, `Shared_Sram`,
  `Dedicated_Sram`) the profiler should pass; no repository records it.
- Whether the nsx manifest's unconditional SoC list should narrow to the
  SoCs whose windows fit the plan; today every module claims all nine.
- Whether neuralspotx adopts the package (see *Alternatives considered*).
