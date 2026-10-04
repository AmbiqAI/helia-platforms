# RFC 0002: migration and output changes

Status: Draft, 2026-10-04. Part of [RFC 0002](0002-model-and-api.md),
kept in its own file for length. Terms are as defined in RFC 0002's
glossary.

Each consumer's outputs that change on adoption, and the parity test in
issue #13 that covers each. A parity test compares the consumer's current
data with the package's answer and allows only the differences on its
allow-list. The allow-list carries every change in this document,
including each pending data correction below, each with its reason.

Consumer facts at the revisions read on 2026-10-04, including runtime
dependencies, are in `docs/research/queries-*.md`.

## All consumers

| Output that changes | Parity test (#13) |
|---|---|
| None from the multicore model ([0002-multicore.md](0002-multicore.md)): every `core=` and `npu=` argument defaults to index 0, the primary application core and primary NPU, so single-core answers are unchanged | Every parity test below runs with the defaults |

## Pending data corrections

Pending verification, issue #14. Each row is a difference between a
consumer's current data and what the sources of record say. None is
applied until verified; each parity allow-list must carry the row with its
reason.

| Fact | Current data | Source says | Consumers affected | Source |
|---|---|---|---|---|
| `apollo4p_evb` PSRAM | helia-profiler 32 MB | No PSRAM on the base board; the Display Kit is the only PSRAM source and fits only the non-Blue EVB | helia-profiler | research/datasheets.md section 7 (QS-A4P p10; QS-A4PDK p10, p12) |
| `apollo4p_blue_kbr_evb` PSRAM | helia-profiler 32 MB | None listed, and the Display Kit is not compatible with the Blue EVB | helia-profiler | section 7 (QS-A4BP p10; QS-A4PDK p10) |
| `apollo330mP_evb` PSRAM | helia-profiler 32 MB, inherited from `apollo330P` | Not populated on revision 2.0 | helia-profiler | section 7 (QS-A330MP p8, p10, p30) |
| `apollo3p_evb`, `apollo3p_evb_cygnus` PSRAM | helia-profiler 8 MB | Not declared in the AmbiqSuite BSP and not mentioned in the guide | helia-profiler | research/ambiqsuite.md; section 7 (QS-A3BP p7) |
| apollo4p SSRAM | heliaAOT `apollo4p_evb` SRAM 1 MB; helia-profiler `sram_kb=1024` | 2048 kB SSRAM plus 384 kB extended SRAM plus 384 kB TCM | heliaAOT, helia-profiler | section 7 (DS-A4P p52, p58) |
| apollo3p MRAM and SRAM | helia-profiler `mram_kb=2000`, `sram_kb=700` | 2 MB flash; 704 KB main SRAM plus 64 KB TCM | helia-profiler | section 7 (DS-A3P p2, p82) |
| apollo510L and apollo330P NVM | helia-profiler `mram_kb=1984` (the SDK window from 0x00410000); heliaAOT `apollo330mp_evb` and `apollo510l_evb` budgets from the same window | NVM-APPL on the fitted 510D Lite and 330M Plus ends at 0x00593FFF; NVM-M41 is reserved per part | heliaAOT, helia-profiler | section 7 and section 3 (DS-A510LS p33; DS-A330PS p33) |
| apollo510L and apollo330P clocks | helia-profiler lp 96, hp 250 | Two HP modes: HP1 192 MHz and HP2 250 MHz | helia-profiler | section 7 (DS-A510LS p46; DS-A330PS p46) |

## heliaAOT

### Target names

The 15 registered targets at `ea5cd6c0` resolve as follows. A name is
either a catalogue id or an alias; an alias resolves to a target whose
`id` differs from the name, and the name is kept in `Target.aliases`.

| heliaAOT name | Catalogue entry | `target.id` | Artefact name |
|---|---|---|---|
| `apollo3_evb` | Board id (also a neuralspotx board id) | `apollo3_evb` | Unchanged |
| `apollo3_blue_evb` | Board id carried from heliaAOT; no neuralspotx board | `apollo3_blue_evb` | Unchanged |
| `apollo3_blue_thin_evb` | Board id carried from heliaAOT; no neuralspotx board | `apollo3_blue_thin_evb` | Unchanged |
| `apollo3p_evb` | Board id | `apollo3p_evb` | Unchanged |
| `apollo3_blue_plus_evb` | Alias of `apollo3p_evb` (a byte-identical copy today, RFC 0001 Architecture; #278 phase 4 retires it by alias) | `apollo3p_evb` | Unchanged: heliaAOT keeps the passed name (decided, below) |
| `apollo4p_evb`, `apollo4l_evb`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `apollo4l_blue_evb` | Board ids | same | Unchanged |
| `apollo330mp_evb` | Board id `apollo330mP_evb` (case differs only) | `apollo330mP_evb` | Unchanged after lowercasing |
| `apollo510_evb`, `apollo510b_evb` | Board ids | same | Unchanged |
| `apollo510l_evb` | Alias of `apollo510dL_evb` (one Lite EVB, the AP510DLEVB, RFC 0001 Architecture) | `apollo510dL_evb` | Unchanged: heliaAOT keeps the passed name (decided, below) |
| `atomiq110` | Soc id; bare Soc target | `atomiq110` | Unchanged |

Decided: when the user passes an alias, heliaAOT keeps printing and
keying artefacts by the name the user passed (lowercased), and records
`target.id` alongside it in `plan.json`. `apollo510l_evb` and
`apollo3_blue_plus_evb` stay accepted aliases of `apollo510dL_evb` and
`apollo3p_evb`, and their artefacts are not renamed. Composition aliases are not covered: they key
artefacts by `target.id` as RFC 0002 states, and no heliaAOT target today
is a composition.

Parity (#13, target names): every registered name resolves; either
`target.id.lower()` equals the name, or the name is in `target.aliases`
(case-insensitive) and is listed in the table above; artefact names equal
today's for every name.

### Budgets, capabilities and policy

| Output that changes | Parity test (#13) |
|---|---|
| Memory budgets come from a link environment chosen per module type; the fallback is the generated nsx-ambiq-sdk default environment for the board, warning if absent. External memories, which the SDK scripts do not link, come from `target.external_memories()` | Budget parity: per target and module type, budgets equal today's `platforms.py` figures except the rows in Pending data corrections and in this table |
| `apollo510_evb` PSRAM changes from 32168 KB (the literal `32168 * 1024` at `platforms.py:500`, `ea5cd6c0`) to 64 MB, hardware-measured (research/datasheets.md, Hardware-validated facts) | Budget parity, allow-listed with that reason |
| `apollo510b_evb` gains a PSRAM region and the `PSRAM` capability (64 MB, same measurement) | Budget and capability parity, allow-listed |
| Capabilities are derived; `BLE` and `USB` leave built-in lists. `MCU` is a heliaAOT policy tag its adapter adds, not a derived capability. `PSRAM` follows `target.has_external_memory("psram")` | Capability parity: per target, the adapter's set equals today's list minus `BLE` and `USB`, plus the `apollo510b_evb` `PSRAM` row |
| `min_alignment` and `preferred_memory_order` come from heliaAOT tables keyed by `target.soc.id` | Policy-table parity: values per target unchanged |
| The nsx manifest SoC list uses neuralspotx spelling (`apollo510L`, not `apollo510l`) | Manifest parity: `compatibility.socs` equals `catalogue.socs()` ids for the listed SoCs |

### Custom definitions (`platform.*`)

| Today's field | Under RFC 0002 | Shim (one release) |
|---|---|---|
| `cpu` | Soc `core` and `core_options`. A known core string maps to its `Core`; unknown cores must state `core_options` explicitly | Maps known strings; rejects an unknown core without options, with a hint |
| `speeds` | Operating points | Maps each speed to an operating point |
| `memories` (sizes, no bases) | Regions require a base. With `based_on`, the shim takes bases from the base entry or rejects with a hint. Size-only regions are allowed only without `based_on`; such an entry has no addresses: `classify_address` returns None and address-dependent queries raise, per RFC 0002's MemoryRegion rule (RFC 0001 appendix E raised in `classify_address` too; RFC 0002 returns None) | Supplies bases or rejects |
| `capabilities` | Derived. A declared capability that contradicts the facts is rejected, after one release in which it only warns | Warns, then rejects |
| `preferred_memory_order`, `min_alignment` | heliaAOT's `extensions` entry (proposal) | Reads the old keys and warns |

## helia-profiler

| Output that changes | Parity test (#13) |
|---|---|
| PSRAM removed from `apollo4p_evb`, `apollo4p_blue_kbr_evb` and `apollo330mP_evb`, and from `apollo3p_evb`, once verified (Pending data corrections) | Memory parity: per board, regions equal today's `MemoryLayout` except the allow-listed rows |
| `_BOARD_TO_AOT_PLATFORM` is deleted. `apollo510b_evb`, `apollo510dL_evb`, `apollo5b_evb` and `apollo330mP_evb`, proxied to `apollo510_evb` today (research/helia-profiler.md), plan against their own targets. `atomiq110_fpga_turbo` resolves to the built-in FPGA implementation target of that id, and heliaAOT plans against its reduced values (decided; a deliberate output change for that one target, replacing today's mapping to bare `atomiq110`). `apollo3p_evb_cygnus`, absent from the map today, gains a mapping to its own board target | heliaAOT-name parity: per board, the target hpx passes to heliaAOT, with these re-pointings allow-listed |
| The windows table is deleted; windows come from the optional dataset or the build's own script | Window parity: dataset windows equal today's `_MAPS` rows per SoC, toolchain and profile |
| `app_flash_load_addr` is replaced by `flash_load_address()` from the selected boot configuration | Boot parity: per board, the derived address equals today's value for the board's provisioning |
| `custom_socs` and `custom_boards` translate to overlays through a one-release shim | Custom-format parity: the shim's output resolves to the same facts as today's loader for the documented examples |

## helia-estimator with helia-npu

| Output that changes | Parity test (#13) |
|---|---|
| Codegen spellings in `helia_aot_codegen.py`: `apollo510` resolves to the bare Soc target, not `apollo510_evb` (the estimator calls `resolve_board("apollo510")` where it wants the board). `ap510` matches the built-in shorthand `AP510` case-insensitively and raises `AmbiguousPlatform` with candidates. `apollo510_eb` raises `UnknownPlatform`; it is not a shorthand, so it may become a built-in alias if wanted. The estimator maps its own spellings in its adapter. The `at110*` prefix rule is not reproduced; `at110` is #278's first proposed alias of `atomiq110` | Name parity: every spelling the estimator uses resolves, through the adapter, to the target it maps to today, or is listed here |
| `origin` mapping: `golden` becomes `origin: builtin`; `derived` becomes `origin: overlay` with `based_on` the built-in Soc; `custom` becomes `origin: overlay` without `based_on`. Value status maps `confirmed` to the package status that matches its source (`datasheet`, `sdk` or `measured`), `fitted` to `fitted`, `unverified` to `unverified` | Provenance parity: per value, the mapped status and source equal today's record |
| The NPU clock per mode comes from the npu-0 clock domain point of each system operating point (`target.npu_mhz(mode)`) | Clock parity: per mode, the clock equals today's `npu_clock_hz` |
| `soc_overrides` becomes a Soc overlay; a `null` memory removal becomes `memories_removed`. Corstone-320 becomes an `fvp` Implementation with `model` and many-to-one `substitutions` (its generic SRAM and DDR replace SSRAM, HBLRAM, PSRAM and RRAM, per research/queries-helia-estimator.md) | Override parity: today's override examples produce the same `SocDefinition` projection |

## neuralspotx

| Output that changes | Parity test (#13) |
|---|---|
| Shield board ids (`apollo4p_evb_disp_shield_rev2` and the others) become compositions and keep resolving, to a board target whose `id` is the base board and whose `aliases` keep the shield id | Board-id parity: every neuralspotx board id resolves to a target whose `id` equals it, except compositions, which resolve to board plus add-ons; `atomiq110_fpga_turbo` resolves to an implementation target, not a board |
| Exact-case Soc and board ids are unchanged | Id parity: every non-composition neuralspotx board id and every SoC fact-file id is a catalogue id, exact case; the catalogue may also hold ids neuralspotx lacks (`apollo3_blue_evb`, `apollo3_blue_thin_evb`) |

## Custom definitions in every tool

Custom SoC and board keys that are not facts of the new model move, with a
one-release shim in each tool that reads the old key and warns:
`jlink_device` on a custom SoC moves to the Part or Board override;
`preferred_memory_order` and `min_alignment` move to the tool's
`extensions` entry (proposal). If open question 4 rejects `extensions`,
each tool keeps a sidecar file keyed by catalogue id instead. Covered by
each tool's custom-format parity test in #13.

## Relationship to helia-aot#278

| #278 phase | Where it lands |
|---|---|
| 0: `resolve_platform` stops mutating the registry (#331) | heliaAOT, unchanged; the package's immutable catalogue removes the class of bug for adopters. |
| 1: Soc/Board split, `NpuSpec`, ISA derivation | This package. `SocPlatform` stays heliaAOT's flattened view, built by an adapter. |
| 2: `platform.soc:` config surface | heliaAOT accepts the overlay format (`platform.overlay`) and a `platform.soc:` shorthand that builds a one-entry overlay. |
| 3: NPU variant cross-check | heliaAOT, reading `NpuInstance.npu.accelerator_config` from here. |
| 4: aliases and family shorthands | This package's resolver. |

Changes relative to #278's model: an implementation layer between Soc and
Board (bring-up FPGA and FVP as implementations, not boards, and the J-Link
device per part), capabilities
derived from `CoreOptions` rather than a cpu-string table,
`preferred_memory_order` and `min_alignment` removed from the shared
model, memory regions with technology, attachment and characterization,
operating points instead of a speeds list, ordered cores and accelerators
with an explicit access matrix instead of one cpu string, provenance on
every fact, an
immutable catalogue with overlays instead of registration, and overlays
may add aliases (#278 allowed built-in aliases only), still never
shadowing a built-in id or alias.
