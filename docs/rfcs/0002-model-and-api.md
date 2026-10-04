# RFC 0002: the platform model and the API helia-platforms exposes

Status: Draft, 2026-10-04. Builds on [RFC 0001](0001-platform-catalogue.md)
(the catalogue and its data), on AmbiqAI/helia-aot#278 (the Soc/Board
split, typed NPU spec and alias design, captured verbatim in
[research/helia-aot-278.md](../research/helia-aot-278.md)), and on the
[review of RFC 0001](0001-platform-catalogue-review.md). RFC 0001 stands
until this RFC is accepted; on acceptance, the sections listed in
[Changes relative to RFC 0001](#changes-relative-to-rfc-0001) are
superseded. RFC 0001's appendix remains the reference for the data and its
sources.

## Summary

`helia-platforms` is a queryable model of Ambiq SoCs and the things that
realize them, not a static table. It exposes:

1. a **catalogue** of specifications (SoCs), implementations of them
   (FPGA builds, FVP and RTL models, and non-default silicon), silicon
   parts, boards, add-ons and memory devices, every fact carrying
   provenance. Linker windows are not catalogue content: an optional
   generated dataset of link environments ships separately;
2. a **resolver** that turns any accepted spelling into one target, with
   aliases, compositions, family shorthands and did-you-mean in one place;
3. **derived queries**: capabilities such as MVE, FP16 or an Ethos-U85 with
   256 MACs are computed from structural facts, never declared;
4. an **overlay** mechanism so a downstream tool, customer or bring-up team
   describes a new SoC, implementation or board by reference and delta,
   never by restating die facts, and gets a new immutable catalogue back;
5. **exports**: a JSON catalogue, a JSON Schema for overlays, and a CLI.

Tools keep their opinions. heliaAOT's placement order and alignment
policy, the profiler's reset and PMU planning, the estimator's energy model
all stay in their tools, keyed by canonical id. The package answers
questions of fact.

## Glossary

Each term has one meaning in this RFC, except `revision`, whose meaning depends on the entity that carries it (rows below).

| Term | Meaning |
|---|---|
| specification | A `Soc`: the full design as its datasheet and SDK headers describe it. |
| core instance (role) | A `CoreInstance` in `Soc.cores`: one core with its `role` (`application`, `radio`, `dsp`, `other`), options, clock domain and `programmable_by`. Index 0 is the primary application core. |
| master | A core, NPU or accelerator id, as the subject of an access entry. |
| access entry | An `Access`: whether one master reaches one target (a memory region, or a memory controller whose devices inherit the entry), which power domains must be awake, and with what guidance. Never inferred; `default_access` is a declared shorthand for them. |
| image slot | An `ImageSlot`: a range of NVM owned by one core for its image, supplied by the vendor or the customer. |
| clock domain | A `ClockDomain`: cores or accelerators clocked together, with the domain's own named points. |
| operating point | A system `OperatingPoint`: one point per clock domain. `target.cpu_mhz()` and `target.npu_mhz()` read the core-0 and npu-0 domains; `cpu_mhz`/`npu_mhz` are also overlay shorthand that expands to domain points. |
| implementation (kind) | An `Implementation`: a realization of a Soc. `kind` is `silicon`, `fpga`, `fvp` or `rtl`. It realizes the whole Soc unless it declares a validated subset. An FPGA or FVP implementation is resolvable directly and carries its own carrier facts; it needs no board. |
| part | A `Part`: an orderable silicon device (ordering number, silicon revision, package, radio option). It references its Soc directly. |
| board (stage, revision) | A `Board`: a PCB carrying one Part. `stage` is `eb`, `evb` or `custom`; `revision` is the board revision, which can change the population. |
| revision (Soc) | `Soc.revision`: the design revision of the specification (for example a pre-silicon RTL revision). |
| revision (Part) | `Part.silicon_revision`: the silicon revision of the fitted die. |
| revision (Board, AddOn) | `Board.revision`, `AddOn.revision`: the board revision of the PCB. |
| revision (LinkEnvironment) | `LinkEnvironment.revision`: the revision of the source the windows were generated from (an SDK or Zephyr commit). |
| add-on | An `AddOn`: a shield or daughter board that fits named boards, occupies board interfaces and brings its own population. |
| memory device | A `MemoryDevice`: an external memory part with technology, capacity, driver family and modes. |
| interface | A `MemoryInterface` on a board: controller, modes and XIP aperture. |
| population | Which memory device sits on which interface, as a board ships or as an add-on brings it. A mapping from interface name to device id. |
| provisioning | `Board.provisioning` (or `Implementation.provisioning` for an FPGA): the name of the boot configuration the fitted part or build ships with. |
| source label | Where a catalogue entry came from: `builtin`, `entry_point:<distribution>`, `env:<path>` or `overlay:<path>`; see `Catalogue.sources`. |
| boot configuration | A `BootConfig`: a named boot layout (sbl, nbl, or a custom layout) with its reservations, one application start per programmable core (`app_start`, core 0 by default) and what it `requires`. |
| reservation | A documented range of memory no core's image may use: boot ROM, an SBL partition. Radio firmware is an image slot, not a reservation. |
| link environment | A `LinkEnvironment`: the linker windows one piece of software (an SDK, Zephyr, a customer script) gives a set of targets. Not part of the core model. |
| link family | The toolchain flavour a link environment describes: `gnu`, `armlink`, `zephyr`. |
| profile | A named linker variant within an owner and link family (for example `default`). Not the profiler's clock profile (an operating point) and not a neuralspotx starter profile. |
| series | The SDK product line (`apollo5`, `atomiq`). Not the profiler's AP3/AP4/AP5 tier, which is profiler policy. |
| origin | Catalogue origin only: `builtin` or `overlay`, where an entry came from. The address an application links at is `BootConfig.app_start`; the start of a linker window is `WindowRegion.start`. |
| provenance status | One of `datasheet`, `sdk`, `measured`, `fitted`, `derived`, `unverified` (proposal pending ADR #6). The status `derived` marks a value computed from other sourced values, such as a size computed from two addresses. |
| derived capability | A query computed from structural facts (`isa().supports_fp16`). Not the same as `derives_from` or `based_on`; see [Inheritance and derivation](#inheritance-and-derivation). |
| target | The resolved, flattened view `resolve()` returns. Its `kind` is `board`, `part`, `implementation` or `soc`. |
| owner direction | Decisions recorded by the repository owner on 2026-10-04 and folded into the [review of RFC 0001](0001-platform-catalogue-review.md). |

## Principles

| # | Principle | Consequence |
|---|---|---|
| P1 | Facts, not opinions | No `preferred_memory_order`, no tool sections on built-ins. Tools derive policy from facts the package exposes (attachment, latency, ports). |
| P2 | Specification and implementations | A SoC is the full specification. An implementation realizes all of it by default or a validated subset (bring-up FPGA with less memory and lower clocks, an FVP with substituted memories). Production silicon is the full set and says nothing extra. |
| P3 | Declared structure, derived capability | Only structural facts are declared. "Supports FP16" is a function of the core's MVE option; "has NPU" is a function of an NPU instance being present; "which NPU" is a structured record. |
| P4 | Every fact has provenance | Status (datasheet, sdk, measured, fitted, derived, unverified), source, date, reviewer. Releases reject `unverified` unless allow-listed. Proposal pending ADR #6. |
| P5 | Overlays compose by reference | `based_on`, `soc:`, `part:`; deltas and removals; unknown keys rejected with a suggestion; built-in ids cannot be shadowed. |
| P6 | One resolver | Canonical ids are the neuralspotx/SDK spellings, matched case-insensitively. Exact aliases and composition aliases resolve. Family shorthands (`AP5`, `AP510`) from the built-in shorthands table raise with candidates. Near misses suggest. |
| P7 | Immutable catalogue, no global state | Loading an overlay returns a new catalogue. Nothing registers into a process-global table (the class of bug in helia-aot#331). No I/O at import. |
| P8 | Stdlib runtime, schema as contract | Frozen dataclasses; PyYAML for overlays and typer for the CLI, nothing heavier; a published JSON Schema with `schema_version`; pydantic export as an optional extra. Proposal pending ADR #7. |

## Entity model

```
Core ───────┐                      Npu ──────────┐
 (IP: cortex-m55, cortex-m4,        (IP: arm ethos-u u85, 256 MACs)
  or a non-Arm DSP core)                          │
            ▼                                     ▼
Soc ── cores: [CoreInstance(id, role, core, options: CoreOptions, clock_domain, programmable_by)]
 │            (index 0: primary application core; CoreOptions: fpu, fpu_dp, mve, icache_kb, dcache_kb)
 │     npus: [NpuInstance(id, npu, axi_width_bits, base, irq, driven_by, clock_domain)]  accelerators: [...]
 │     memories: [MemoryRegion]   access: [Access(master, target, ...)], default_access   peripherals: [name]
 │     clock_domains: [ClockDomain]   operating_points: [OperatingPoint] (system points)
 │     boot_configs: {name: BootConfig}, default_boot    (sbl, nbl; app_start per programmable core)
 │     sdk: SdkFacts (c_define, cmsis_header, ...)   default_board   aliases, release_status, provenance
 │
 ├── Implementation (kind: silicon | fpga | fvp | rtl; model; subset of the Soc; default = all;
 │                   may replace boot_configs, operating_points, clock domain points; an FPGA
 │                   carries jlink_device, trace clock, provisioning, interfaces; no board needed)
 │
 ├── Part (silicon: references its Soc, and an Implementation only when a non-default one exists;
 │         ordering number, silicon revision, package, radio, jlink_device,
 │         per-part image slots such as the NVM-M41 radio-core slot)
 │
 ├── Board (stage: eb | evb | custom; revision; carries one Part;
 │          memory interfaces; default population; provisioning (boot config in use);
 │          probe and trace facts; aliases)
 │
 └── AddOn (shield or daughter board: fits boards, occupies board interfaces, own population)

MemoryDevice: an external part (APS25616N, IS25WX064): technology, capacity, driver family, modes
Composition: a legacy alias -> board + add-ons (apollo4p_evb_disp_shield_rev2)
Resolved target: Board + AddOns | Part | Implementation | Soc -> one flattened, queryable view
LinkEnvironment (optional generated dataset, outside the core model): toolchain windows and carve-outs
```

### Core and Npu (IP blocks)

`Core` holds architecture facts the IP vendor fixes: `id` (cortex-m4,
cortex-m55), `arch` (armv7e-m, armv8.1-m, or a non-Arm ISA such as an
Xtensa DSP core's), `pmu` (dwt, armv8m), `has_dsp_extension`. Options the
vendor leaves to the implementer live on each core instance's `options`
(`CoreOptions`): `fpu` (none, fpv4-sp-d16, fpv5-sp-d16), `fpu_dp`, `mve`
(none, int, fp), `icache_kb`, `dcache_kb`.

`Npu` is structured, as #278 proposes and the owner direction requires:
`vendor` (arm), `family` (ethos-u), `model` (u55, u65, u85),
`macs_per_cycle` (256 for atomiq110's Ethos-U85, per helia-npu
`socs/atomiq110.yaml` and nsx-npu, as recorded in
[research/helia-estimator.md](../research/helia-estimator.md),
[research/queries-helia-estimator.md](../research/queries-helia-estimator.md)
and RFC 0001 appendix J). `accelerator_config` ("ethos-u85-256") is
derived. The Soc's `NpuInstance` adds the instance facts: id, base
address, IRQ, AXI width, `driven_by` (the core that programs it) and its
clock domain. Which memories it reaches, and over which port, are its
access entries. It stores no clocks: the NPU clock comes from the system
operating point (`target.npu_mhz(point)` for npu 0), and
`Target.npu_clocks(npu=)` is a derived view keyed by operating point. Driver
behaviour (command-stream chunking, Vela system configs, port arbitration
rules) stays in `helia-npu`, which reads the instance facts from here.

### Cores, accelerators and reachability

Ambiq parts already ship with more than one core (the Apollo510 Lite and
Apollo330 Plus Cortex-M4 radio core, DS-A510LS p33, DS-A330PS p33). `Soc.cores`
and `Soc.npus` are ordered, index 0 primary, and every single-core query
defaults to core 0 and npu 0. Reachability is an explicit access matrix
keyed by (master, target), never inferred from the address space; other
cores' NVM is held in image slots; operating points couple clock domains.
Definitions, queries and an example are in [0002-multicore.md](0002-multicore.md).

### Soc (the specification)

| Field | Category | Notes |
|---|---|---|
| `id`, `series`, `aliases` | identity | `series` is the SDK product line (apollo5, atomiq). The profiler's AP3/AP4/AP5 tier is profiler policy keyed by id. |
| `cores: [CoreInstance]` | structural | Ordered; index 0 is the primary application core. Capabilities derive per core. |
| `npus: [NpuInstance]`, `accelerators` | structural | Ordered; index 0 primary; each names `driven_by` and its clock domain. |
| `memories: [MemoryRegion]` | structural, with optional characterization | See below. |
| `access: [Access]`, `default_access` | structural | Reachability per (master, target), never inferred; `default_access` is a declared shorthand with provenance. |
| `clock_domains: [ClockDomain]` | structural | Each with its own named points. |
| `peripherals: [name]` | structural | Named list; an implementation's `peripherals_removed` removes from it. |
| `operating_points: [OperatingPoint]` | structural | System points: name, one point per clock domain, system HAL mode where the HAL has one; `target.cpu_mhz()` and `target.npu_mhz()` read the core-0 and npu-0 domains. heliaAOT `speeds` and the profiler `ClockDomain` are views. |
| `default_operating_point` | SDK fact, optional | Set where the SDK names a default; otherwise absent and the choice is tool policy. |
| `boot_configs: {name: BootConfig}`, `default_boot` | structural or SDK fact | The boot layouts the SDKs support, and the default. See Boot configurations. |
| `sdk: SdkFacts` | SDK fact | `c_define`, `cmsis_header`, default trace clock, HAL enums the SDK exposes per SoC, `build` (abi, float ABI, toolchains). |
| `derives_from: Soc \| None` | structural | See [Inheritance and derivation](#inheritance-and-derivation). |
| `default_board: Board \| None` | convenience | Used only by an explicit `resolve_board(soc_id)`. Never used by `resolve()`. |
| `release_status` | governance | public or embargoed. Every entity carries one; see Release status. |
| `extensions` | per-tool, proposal | Overlay entries only; see Overlays. |

`MemoryRegion`: `name` (dtcm, ssram, mram, hblram, psram0), `technology`
(sram, mram, rram, psram, flash, nvm), `attachment` (tcm, system, external),
`size`, `base`, optional `alternate_bases` where the silicon aliases the
region, `executable`, `writeable`, `cacheable`, optional
`characterization` (read and write latency, ports, max outstanding,
burst, bandwidth) each value with provenance: latency, bandwidth and
ports only. The package carries no energy data; the estimator's energy
coefficients stay in helia-estimator.

An overlay region may omit `base` (size only, no `based_on`, as RFC 0001
appendix E allowed). Such a region is excluded from the bounds and overlap
check, `classify_address()` returns `None` for it, and `placement_ranges()`
and `flash_load_address()` raise `PlatformError` when they need its
address. Built-in regions always carry a base.

### Bring-up lifecycle

Ambiq silicon moves through bring-up phases, and the model follows them rather than
treating the end state as the only truth:

| Phase | What exists | Modelled as |
|---|---|---|
| Pre-tapeout | FPGA running a subset of the RTL: less memory, peripherals absent, lower clocks, sometimes a different address map; an Arm FVP standing in for parts of the system | `Implementation` of kind `fpga` or `fvp`, resolvable directly by its id, with no board (atomiq110_fpga_turbo; AmbiqSuite's apollo510L_fpga_turbo) |
| First silicon | Engineering board with an early silicon revision | `Part` with a `silicon_revision`, on a `Board` of stage `eb` |
| Release | Evaluation board with production silicon | `Part` on a `Board` of stage `evb`, with board `revision` (populations change between revisions) |
| Customer | The customer's own board | `Board` of stage `custom`, defined in an overlay by reference to a Part, with its own interfaces, population and add-ons |

Every phase resolves through the same API, so a tool written against an
FPGA target keeps working as the EB and EVB arrive. Stage is a fact about
a board; how well each tool supports a stage or an implementation kind is
that tool's marker.

### Implementation and Part

An `Implementation` names a `soc`, a `kind` and a subset expression:
memories removed, resized or rebased; peripherals removed from
`Soc.peripherals`; clock caps; cores or accelerators removed. Everything not mentioned is
inherited from the specification. The validator rejects an implementation
that adds a memory or exceeds a clock. Rebasing is allowed because FPGA
builds move regions (the atomiq110 FPGA places SSRAM and MRAM at different
bases from silicon).

Clock caps act on operating points: a point whose CPU or NPU clock exceeds
`max_cpu_mhz` or `max_npu_mhz` (the core-0 and npu-0 domains;
`max_domain_mhz` caps any domain) is dropped from the implementation. If the
Soc's default point is dropped, `default_operating_point` is `None`, and
`npu_clocks()` follows the remaining points. If no point survives, the
implementation must declare its own `operating_points`, adding or
replacing domain points through `Implementation.clock_domains`. The
built-in `atomiq110_fpga_turbo` Implementation runs below every
atomiq110 point (fixed 25 MHz, from helia-profiler, where it is a
supported variant; RFC 0001 appendix J), so it declares its own 25 MHz
domain points and an operating point over them, as in the FPGA example
under Overlays.

An FPGA is a reduced implementation of the specification, not a board.
An FPGA Implementation therefore carries the facts a board would
otherwise supply: `jlink_device`, `trace_clock_mhz`, its boot
configurations and `provisioning`, and, where it needs external memory,
its own `interfaces` and `population`. `atomiq110_fpga_turbo` takes its
probe facts from neuralspotx `boards/atomiq110_fpga_turbo/debug.cmake`
(device `Atomiq110`; the 48 MHz trace clock RFC 0001 appendix J records
as hardware-measured), and keeps the id neuralspotx and helia-profiler
use.

An FVP implementation names its `model` (corstone-320) and its
`substitutions`, which are many-to-one: each names a region the model
provides, the Soc regions it `replaces`, and its own size and base. The
replaced regions are removed, and the substitute does not count as an
added memory. Substitutions are allowed only for kind `fvp`. The
estimator's "Corstone-320 as a subset of atomiq110" is therefore
first-class rather than a private convention. An Implementation may also
replace the Soc's boot configurations and operating points.

Production and engineering silicon is a `Part`. A Part references its
`soc` directly and names an `implementation` only when a non-default
silicon implementation exists; there are no implicit silicon
Implementation ids. A Part carries an ordering number (AP510NFA-CBR),
`silicon_revision`, package, radio option, `jlink_device`, and per-part
image slots. On the Apollo510 Lite and Apollo330 Plus parts the top of NVM
(NVM-M41, Cortex-M4 radio firmware), 16, 288 or 432 KB depending on the
variant (DS-A510LS p33, DS-A330PS p33, as recorded in
[research/datasheets.md](../research/datasheets.md)), is the radio core's
image slot, vendor-supplied by default, so it lives on the Part, not the
Soc.

### Boot configurations

Boot layout is a named choice, not a single fact:

```
BootConfig: name, reserved: [(region, offset, size, purpose)],
            app_start: {core id: (region, offset)}   (a single (region, offset) means core 0),
            requires (sbl | none | custom), provenance
```

- The Soc carries the boot configurations its SDKs support and a
  `default_boot`. Datasheet-documented partitions (the Apollo510 NVM-SBL
  region) carry datasheet provenance. SDK conventions carry SDK
  provenance: the Apollo3 application start 0xC000 comes from the
  AmbiqSuite linker scripts and `AM_SECBOOT_DEFAULT_NONSECURE_MAIN` in
  `tools/apollo3_scripts/am_defines.py`; the Apollo4 start 0x18000 comes
  from the AmbiqSuite Apollo4 linker scripts, while
  `tools/apollo4_scripts/am_defines.py` sets 0xC000 and is recorded as a
  conflict ([research/ambiqsuite.md](../research/ambiqsuite.md)). The SBL
  reservation on Lite and 330 Plus parts is also an SDK convention.
- An Implementation can replace the set and the default. The atomiq110
  FPGA declares only its no-bootloader layout at its own MRAM base.
- A Board records its `provisioning`: which configuration the fitted part
  ships with. Ambiq EVBs ship SBL-provisioned; a customer board says what
  it uses; an FPGA Implementation records its own.
- The flash load address has one derivation:
  `Target.flash_load_address(core=0)` is the base of that core's
  `app_start` region in the selected configuration (after any
  implementation rebase) plus its offset. The selected configuration
  is the explicit `boot=` argument, else the board's provisioning, else
  the implementation's, else the default. `usable_nvm()` derives from the same selection. The package
  warns when an explicit selection differs from the board's provisioning.
- Documented reservations (boot ROM, SBL partition) and other cores'
  image slots are always subtracted. Stack, heap and toolchain carve-outs are not: they
  belong to link environments.

### Board, external memory and add-ons

A `Board` carries one Part, a `stage` (`eb`, `evb` or `custom`) and a
`revision`, probe and trace facts
(`jlink_device` override, measured trace clock), `provisioning`, and
aliases. `tier` and `channel` are gone: support level is a per-tool
marker keyed by id.

External memory is composed, not fixed, because the same board ships with
different populations across revisions (the Apollo330 Plus and Apollo510
Lite EVB rev 2.0 leave the PSRAM footprint empty), shields add memory (the
Apollo4 Plus display shield rev 1 and rev 2 carry different PSRAM and
flash), and customers add daughter boards.

- `MemoryInterface` on the Board: name, controller (mspi0, mspi1, iom4),
  modes (octal DDR, hex), XIP aperture base and maximum size. The
  controller is a memory controller of the Soc (a `Soc.peripherals`
  entry); devices populated on the interface inherit that controller's
  access entries ([0002-multicore.md](0002-multicore.md)). An interface
  without aperture fields yields devices with no base: they are not
  addressable, `external_memories()` reports them without a base, and the
  aperture validator skips them with a warning.
- `MemoryDevice`: an external part with technology, capacity,
  `driver_family`, supported modes and optional characterization, each
  value with provenance. Capacity and driver family are separate facts.
  Capacity is never inferred from a part marking or a BSP macro: the
  Apollo510 EVB PSRAM is 64 MB by hardware measurement although its BSP
  macro names a 256 Mb driver family. The driver family is recorded
  because the SDK uses it.
- `population`: which device sits on which interface as the board ships.
- `AddOn`: a shield or daughter board that names the boards it fits
  (`fits_boards`), the interfaces it occupies (`occupies`) and its own
  `population` on those interfaces.
- The resolved target is board plus selected add-ons plus overlay. The
  validator rejects two devices on one interface, an add-on on a board it
  does not fit, and a device larger than its aperture.

AmbiqSuite's per-shield board directories (`apollo4p_evb_disp_shield_rev2`)
and neuralspotx's matching board id become entries in the catalogue's
`compositions` table: an alias mapped to a board id and add-on ids.
`resolve("apollo4p_evb_disp_shield_rev2")` returns the `apollo4p_evb`
board target with the rev 2 display shield in `Target.addons`;
`Target.id` is the board id, and the legacy id is kept in
`Target.aliases`. heliaAOT artefact names use `Target.id`, except that
for a plain alias heliaAOT keeps the name the user passed and records the
canonical id alongside (decided; see [0002-migration.md](0002-migration.md)).

### Release status

Every entity (Soc, Implementation, Part, Board, AddOn, MemoryDevice)
carries a `release_status`: public or embargoed. A target's effective
status is the most restrictive status along its reference chain (board,
its part or implementation, the Soc, selected add-ons and the memory
devices they populate). A `Composition` and a `LinkEnvironment` are not
given a most-restrictive status: they are scrubbed and shipped, as below.

Unreleased SoCs never enter this repository; they are side-loaded from
private packages or overlay files (see Private and future silicon). The
export filter is defence in depth behind that rule. It uses the effective
status and never ships an embargoed
entry or a target whose effective status is embargoed, and it scrubs
embargoed ids from every table and reference: shorthands, compositions,
`fits_boards`, `default_board`, `applies_to` and aliases. A Composition or
LinkEnvironment that references only embargoed entities is dropped.

### Link environments

Linker windows are properties of software (an SDK's scripts, Zephyr's
devicetree, a customer's own script), not of the silicon. The core model
does not carry them. The package defines a `LinkEnvironment` schema
(owner, link family, profile, `applies_to`, per-region usable window,
source, revision) and accepts one wherever a budget is asked for.
`applies_to` lists the Soc, Implementation or Board ids the environment
covers. An environment applies to a target if any id on the target's
reference chain (board, part, implementation, Soc) is listed, except that
the chain stops at an implementation that rebases or resizes a region, so
a silicon environment never covers a rebased FPGA build.
`Target.budget(env)` raises if the target is not covered. An
optional dataset of environments generated from nsx-ambiq-sdk and Zephyr
at pinned revisions ships separately for consumers that want a
conservative default; the profiler's windows table seeds it, and an
extractor script regenerates it rather than hand-copying.

## Derived capabilities

The package computes, and exposes both as typed properties and as a
stable string set (`Target.capabilities`) for tools that want one:

| Query on `Target` (per core; `core=` defaults to 0) | Derived from |
|---|---|
| `isa().has_dsp` | `Core.has_dsp_extension` |
| `isa().has_mve`, `isa().mve_flavour` | `CoreOptions.mve` |
| `isa().supports_fp16` | `CoreOptions.mve == fp` |
| `isa().supports_fp32` | `CoreOptions.fpu != none` |
| `isa().supports_fp64` | `CoreOptions.fpu_dp` |
| `isa().has_pmu`, `isa().pmu_kind` | `Core.pmu` |
| `npu` (npu 0, `None` when absent), `npus()` | `Soc.npus` after the implementation subset |
| `has_external_memory(technology)` | board population plus selected add-ons |

heliaAOT maps these onto its `SocCapability` enum in its adapter; the
profiler's `SocCapabilities` builders consume them; `BLE` and `USB` tags
disappear from built-ins. Unknown or bespoke cores declared in an overlay
must state the `CoreOptions` explicitly; there is no "trust the
declaration" path because there is nothing to declare but facts.

## Resolution and naming

`resolve(name)` accepts a board id, a part id, an implementation id, a Soc
id, a composition alias, or an alias, case-insensitively, and returns one
resolved target. A Soc id always resolves to the bare Soc target, never to
a board (heliaAOT's bare `atomiq110` target stays valid, as #278
resolved). Resolution never depends on how many boards a catalogue holds.
A Soc may name a `default_board`, which only the explicit
`resolve_board(soc_id)` uses. An FPGA or FVP implementation id
(`atomiq110_fpga_turbo`) resolves directly to an implementation target.

The catalogue holds two name tables besides ids and aliases:

- `compositions`: alias to (board id, add-on ids), so legacy per-shield
  ids resolve to a board plus its add-ons (see Board, external memory and
  add-ons).
- `shorthands`: shorthand to member ids (`AP5`, `AP510`). It is the only
  source of `AmbiguousPlatform`, which lists the members. Shorthands are
  built-in only.

Near misses raise `UnknownPlatform` with suggestions. Aliases and
composition aliases are unique across all entities; overlays may add
aliases but cannot shadow a built-in id, alias, composition or shorthand.
heliaAOT keeps printing the lowercase form; the profiler keeps the
neuralspotx spelling; both come from the same resolver.

## Overlays

One format for every downstream party: a tool shipping extra entries, a
customer describing a production board, a bring-up team describing an
FPGA cut. The complete overlay syntax is specified in ADR #7 (schema
format); this RFC fixes the semantics, not the syntax. The examples below
show one entry per entity kind, with field names as in the model.

Semantics every overlay entry shares:

- `based_on` copies facts only; aliases, `default_board`, `derives_from`,
  `release_status` and the provenance of changed values are not inherited
  (see [Inheritance and derivation](#inheritance-and-derivation)).
- Defaults: `release_status` is `embargoed` unless the entry declares it,
  and a value with no declared provenance has status `unverified`.
- Size suffixes `K`, `M` and `G` mean KiB, MiB and GiB (binary bytes),
  never bits. ADR #7 may change the spelling but not the unit.
- A Soc delta uses the same vocabulary as an implementation `Subset` where
  it applies: `memories_removed`, `memories_resized`, `memories_rebased`,
  `peripherals_removed`.
- `cpu_mhz` and `npu_mhz` in an overlay operating point are shorthand: they
  expand to a point of that name in the core-0 and npu-0 clock domains. A
  single `app_start` means core 0. The multicore forms are in
  [0002-multicore.md](0002-multicore.md).

A Soc delta:

```yaml
socs:
  my_soc:
    based_on: apollo510
    memories_resized: {ssram: 2M}
```

An Implementation (an FPGA cut):

```yaml
implementations:
  atomiq110_fpga_rev3:
    soc: atomiq110
    kind: fpga
    subset:
      memories_removed: [hblram]
      memories_resized: {dtcm: 256K}
      max_cpu_mhz: 25
    clock_domains:                      # domain ids illustrative
      cpu: {points: [{name: fpga, mhz: 25}]}
      npu: {points: [{name: fpga, mhz: 25}]}
    operating_points: [{name: fpga, domains: {cpu: fpga, npu: fpga}}]
    # shorthand for the three lines above: [{name: fpga, cpu_mhz: 25, npu_mhz: 25}]
    boot_configs:
      nbl_fpga: {reserved: [], app_start: {region: mram, offset: 0}, requires: none}
    default_boot: nbl_fpga
    provisioning: nbl_fpga
    jlink_device: Atomiq110              # carrier facts: an FPGA needs no board
```

A MemoryDevice (an illustrative customer part):

```yaml
memory_devices:
  acme_psram_8m:
    technology: psram
    capacity: 8M
    driver_family: acme_xspi
    modes: [hex-ddr, octal-ddr]
```

A custom Board:

```yaml
boards:
  my_product_v1:
    stage: custom
    revision: "1.0"
    part: AP510NFA-CBR
    interfaces:
      # Apollo510 datasheet DS-A510-1p1p0 p36 and p98: MSPI0 XIP 0x60000000-0x6FFFFFFF
      mspi0: {controller: mspi0, modes: [hex-ddr], aperture_base: 0x60000000, aperture_max: 256M}
    population: {mspi0: acme_psram_8m}
    provisioning: sbl
    extensions:
      helia_profiler: {sync_gpio: 27}
```

An AddOn:

```yaml
addons:
  my_psram_daughter:
    fits_boards: [apollo4p_evb]
    occupies: [mspi1]
    population: {mspi1: acme_psram_8m}
```

`load_overlay(source) -> Catalogue` returns a new catalogue; the built-in
catalogue is never mutated. Unknown keys outside `extensions` are rejected
with a suggestion. A JSON Schema is published for editors and CI.

`extensions` is a proposal (see open question 4): an opaque, per-tool map
on Soc, Implementation, Board and AddOn entries that the package stores
and returns but never reads or validates, so one file can travel between
tools. Built-in entries may not carry it.

### Inheritance and derivation

This is the one definition of both relations.

- `based_on` is overlay inheritance and applies to any entity kind. The
  new entry copies the facts of the named entry, then applies its own
  deltas and removals. The result is an independent entry with its own id.
  Not inherited: `aliases`, `default_board`, `derives_from`, and
  `release_status` (the entry's own, default `embargoed`). Unchanged values
  keep the base entry's provenance; changed values take the overlay's
  provenance as declared, or status `unverified` where none is declared.
- `derives_from` is a relation between built-in Socs: a variant that
  shares another Soc's SDK headers (apollo510b and apollo5b derive from
  apollo510). The validator requires equal physical regions.
- An overlay `based_on` does not imply `derives_from`. `my_soc` above is
  based on apollo510 but does not derive from it, and its resized SSRAM
  would fail the `derives_from` rule.

## Question surface

The state of each consumer on 2026-10-04, with file:line references, is in
`docs/research/queries-*.md`.

Every question a consumer's code asks of a platform today, the API in this
RFC that answers it, and the questions that remain the tool's own. "Target"
below is the resolved object returned by `resolve()`.

### heliaAOT

| Question asked today | Answered by | Owner |
|---|---|---|
| Is MVE (or DSP) available, for kernel selection | `target.isa().has_mve`, `target.isa().has_dsp` (core 0); `target.capabilities` string set for the existing membership tests | package |
| Native FP16 | `target.isa().supports_fp16` | package |
| Is there an NPU, and which | `target.npu` (npu 0: `None` or `NpuInstance` with `.npu.model`, `.npu.macs_per_cycle`, `.npu.accelerator_config`); `target.npus()` for all | package |
| Which core and NPU to compile for | core 0 and npu 0 implicitly; `platform.core` and `platform.npu` are future additive options | package default; choice is heliaAOT's |
| Memories and byte sizes to budget | `target.budget(env)` with the link environment heliaAOT picks; `target.memories()` for physical regions | package; environment is heliaAOT's choice |
| Is ITCM present | `target.has_region("itcm")` | package |
| Minimum alignment | heliaAOT table keyed by `target.soc.id` (16 with MVE is a placement rule) | heliaAOT |
| Order to try memories | heliaAOT policy; inputs available as `region.attachment` and `region.characterization` | heliaAOT |
| CPU string for compiler flags | `target.core.id`, `target.core_options.fpu`, `.mve` | package |
| Name to print and to key artefacts | `target.id` (canonical) and `target.aliases`; heliaAOT lowercases, and for an alias keeps the name passed and records the canonical id (decided) | package |
| Zephyr section names for TCM | Zephyr `LinkEnvironment` from the optional dataset; heliaAOT template reads its section names | dataset, heliaAOT |
| SoC list for the nsx manifest | `catalogue.socs()` ids in neuralspotx spelling | package |
| Which link family for a module type | heliaAOT policy (`zephyr` for the zephyr module type, `gnu` otherwise) | heliaAOT |

### helia-profiler

| Question asked today | Answered by | Owner |
|---|---|---|
| Which SoC, part, implementation is this board | `resolve(board).soc`, `.part`, `.implementation` | package |
| Core, PMU kind, MVE | `target.core`, `target.core.pmu`, `target.isa()` (core 0; `target.cores()` for all) | package |
| Clock speeds, names, default | `target.operating_points()`, `target.default_operating_point` (`None` where the SDK names no default), `target.cpu_mhz(point)`; HAL mode names from `DomainPoint.hal_mode` per domain (`OperatingPoint.hal_mode` is the system mode where the HAL has one) | package where the SDK names a default; otherwise profiler policy |
| Region sizes and capacities | `target.memories()`, `target.usable_nvm()`; `target.budget(env)` with a link environment | package; environment is profiler choice |
| Linker windows per toolchain and profile | `LinkEnvironment` from the optional SDK dataset or the build's own script | dataset or profiler |
| Which region holds address X | `target.classify_address(addr)` over physical regions, as seen by core 0 (`master=` for another) | package |
| J-Link device name | `target.jlink_device` (board, else implementation, else part) | package |
| App flash load address | `target.flash_load_address()` from the selected boot configuration (explicit `boot=`, else board provisioning, else default) | package |
| Placement base addresses | `target.region(name).base` | package |
| Is PSRAM fitted | `target.has_external_memory("psram")` | package |
| D-cache present | `target.core_options.dcache_kb` | package |
| Shared SSRAM power domain, HAL enum names, C define, CMSIS header | `target.sdk` | package |
| Radio present | `target.part.radio` (`target.part` is `None` on Soc and implementation targets) | package |
| Trace clock | `target.trace_clock_mhz` (board, else implementation, else SDK default; `None` means core-clocked) | package |
| Is this an FPGA | `target.implementation.kind == "fpga"` (`target.implementation` is `None` on Soc targets and on parts with no non-default implementation) | package |
| RTT scan ranges | profiler rule over `target.region("dtcm")` or the M4 aperture | profiler |
| Reset strategy, clean-window timer, debug-domain gating, probe-attached cycle reads | profiler policy keyed by `target.soc.series` or id | profiler |
| USB transport support | profiler driver-support table | profiler |
| Sync, state, go, BLE-reset GPIO pins; channel; starter profile board | profiler board policy keyed by id, or `extensions.helia_profiler` in an overlay | profiler |
| Built-in or custom | `target.origin` (builtin, overlay) | package |
| Which heliaAOT target name | the same resolver; the private name map is deleted (see [0002-migration.md](0002-migration.md)) | package |

### helia-estimator and helia-npu

| Question asked today | Answered by | Owner |
|---|---|---|
| NPU clock in a named mode | `target.npu_mhz(name)` (npu 0), from the system operating point; `target.npu_clocks(npu=)` is a derived view | package |
| NPU family, model, MACs, AXI width | `target.npu.npu.family`, `.model`, `.macs_per_cycle`; `target.npu.axi_width_bits` | package |
| Which memories the NPU reaches and over which port class | `target.reachable(target.npu.id, region)`: the NPU's access entries, with `port` | package |
| Memory read and write latency, outstanding transactions, burst, AXI clock | `target.reachable(target.npu.id, name).characterization` where present, which overrides the region's for that master; else `target.region(name).characterization`; with provenance | package |
| Revision, origin, provenance roll-up | `target.soc.revision`, `target.origin`, `target.provenance()` | package |
| Vela memory mode for a placement; system-config file | helia-npu, from the port classes above | helia-npu |
| Burst-split codes, timing-adapter programming | helia-npu | helia-npu |
| Which memory holds const, arena, cache in a run | estimator run configuration | estimator |
| Energy per cycle and per bit | estimator model keyed by `target.soc.id` and mode | estimator |
| Per-run timing overrides | estimator | estimator |
| Load a SoC by id or path with overrides | `resolve`, `load_overlay` (merge, remove, provenance inheritance) | package |
| Same SoC on compile target and platform | `target.soc.id` equality | package |
| heliaAOT codegen proxy name | the shared resolver | package |

### neuralspotx and Zephyr

neuralspotx's role and its own questions are recorded in
[research/queries-neuralspotx-zephyr.md](../research/queries-neuralspotx-zephyr.md);
the package mirrors the facts it holds: `target.soc`,
`soc.sdk.build.toolchains`, `soc.sdk.build.abi` and the exact-case ids.
Zephyr enters through
heliaAOT's zephyr module type: the Zephyr board id equals the neuralspotx
board id. Zephyr link windows and section names come from the optional
link-environment dataset, for the boards Zephyr ships, pinned to a Zephyr
revision; the core package does not carry them.

## API

Stdlib dataclasses, frozen. No I/O at import. Runtime dependencies are
PyYAML, used only by `load_overlay`, and typer for the CLI. The typer
range must overlap every consumer's own typer pin (helia-profiler caps
it, see research/queries-helia-profiler.md and helia-profiler#459); typer
stays a core dependency (decided).

### `helia_platforms.catalogue`

```python
def builtin(include_plugins: bool = True) -> Catalogue   # cached, immutable; plugins: entry points, then HELIA_PLATFORMS_PATH
def load_overlay(source: str | Path | Mapping, *, base: Catalogue | None = None) -> Catalogue

class Catalogue:
    schema_version: int                         # split from catalogue_version: proposal pending ADR #12
    catalogue_version: str                      # data release, independent of the package version
    compositions: Mapping[str, Composition]     # alias -> board id and add-on ids
    shorthands: Mapping[str, tuple[str, ...]]   # built-in only; the only source of AmbiguousPlatform
    sources: Mapping[str, str]                  # entry id -> source label
    def socs(self) -> tuple[Soc, ...]
    def implementations(self, soc: str | None = None) -> tuple[Implementation, ...]
    def parts(self, soc: str | None = None) -> tuple[Part, ...]
    def boards(self, soc: str | None = None) -> tuple[Board, ...]
    def cores(self) -> tuple[Core, ...]
    def npus(self) -> tuple[Npu, ...]
    def find(self, **predicates) -> tuple[Target, ...]   # core="cortex-m55", npu_model="u85", has_region="psram"
    def resolve(self, name: str) -> Target
    def suggest(self, name: str) -> tuple[str, ...]
    def to_dict(self) -> dict                   # the JSON export
```

### `helia_platforms.resolve`

```python
def resolve(name: str, *, addons: Sequence[str] = (), boot: str | None = None,
            catalogue: Catalogue | None = None) -> Target
def resolve_board(name) -> Board                # a board id or alias; a Soc id returns Soc.default_board
def resolve_soc(name) -> Soc

class UnknownPlatform(PlatformError):   suggestions: tuple[str, ...]
class AmbiguousPlatform(PlatformError): candidates: tuple[str, ...]   # shorthands table only
```

Resolution order:

1. An exact id or alias of a board, part, implementation or Soc, or a
   composition alias, case-insensitively, returns that target. A Soc id
   returns the bare Soc target. A composition alias returns its board
   target with its add-ons.
2. A shorthand from the `shorthands` table raises `AmbiguousPlatform`
   listing its members.
3. Anything else raises `UnknownPlatform` with suggestions.

The number of boards carrying a Soc never changes the result.
`resolve_board(soc_id)` returns `Soc.default_board` and raises
`PlatformError` if the Soc has none; it is the only call that uses
`default_board`.

`addons=` is valid only for board targets (including a composition, whose
add-ons it extends) and raises `PlatformError` otherwise. `boot=` is valid
for any target that has boot configurations and raises if the name is not
one of them.

### `helia_platforms.model`

```python
@dataclass(frozen=True) class Provenance: status, source, verified_on, verified_by, notes
@dataclass(frozen=True) class Core:       id, arch, pmu, has_dsp_extension   # arch may be a non-Arm ISA
@dataclass(frozen=True) class CoreOptions: fpu, fpu_dp, mve, icache_kb, dcache_kb
@dataclass(frozen=True) class CoreInstance: id, role, core, options: CoreOptions, clock_domain, programmable_by: str | None
@dataclass(frozen=True) class Npu:        vendor, family, model, macs_per_cycle; accelerator_config (property)
@dataclass(frozen=True) class NpuInstance: id, npu, axi_width_bits, base_address, irq, driven_by, clock_domain
@dataclass(frozen=True) class AcceleratorInstance: id, kind, ip, driven_by, clock_domain, base_address, irq
@dataclass(frozen=True) class MemoryRegion: name, technology, attachment, size, base, alternate_bases, executable, writeable, cacheable, characterization, provenance
@dataclass(frozen=True) class Access:     master, target, access, requires_awake, guidance, reason, address: int | None, port: int | None, characterization, provenance   # target: region or memory controller name
@dataclass(frozen=True) class DefaultAccess: master, access, scope, provenance   # scope: on_die
@dataclass(frozen=True) class MemoryCharacterization: read_latency_ns, write_latency_ns, max_outstanding, burst_bytes, ports, axi_clock_hz, bandwidth_fraction  (each value may carry its own Provenance)
@dataclass(frozen=True) class ClockDomain: id, points: tuple[DomainPoint, ...]   # DomainPoint: name, mhz, hal_mode, provenance
@dataclass(frozen=True) class OperatingPoint: name, domains: Mapping[str, str], hal_mode, provenance   # domain id -> point name
@dataclass(frozen=True) class SdkFacts:   c_define, cmsis_header, trace_clock_mhz, hal_enums: Mapping[str, str], build: BuildFacts
@dataclass(frozen=True) class BuildFacts: abi, float_abi, toolchains
@dataclass(frozen=True) class Soc:        id, series, aliases, cores, npus, accelerators, memories, access, default_access: DefaultAccess | None, peripherals, clock_domains, operating_points, default_operating_point: str | None, boot_configs, default_boot, sdk, derives_from, default_board: str | None, revision, release_status, extensions, provenance
@dataclass(frozen=True) class Implementation: id, soc, kind, model: str | None, subset: Subset, clock_domains: tuple | None, operating_points: tuple | None, boot_configs: Mapping | None, default_boot: str | None, provisioning: str | None, jlink_device, trace_clock_mhz, interfaces, population, aliases, release_status, extensions, provenance   # None: inherit the Soc's (after clock caps)
@dataclass(frozen=True) class Subset:     memories_removed, memories_resized, memories_rebased, substitutions: Mapping[str, Substitution], peripherals_removed, cores_removed, npus_removed, max_cpu_mhz, max_npu_mhz, max_domain_mhz   # substitutions: kind fvp only
@dataclass(frozen=True) class Substitution: replaces: tuple[str, ...], size, base, characterization, provenance   # keyed by the FVP region name; many-to-one
@dataclass(frozen=True) class BootConfig: name, reserved: tuple[Reservation, ...], app_start: Mapping[str, AppStart], requires, provenance   # AppStart: region, offset
@dataclass(frozen=True) class Reservation: region, offset, size, purpose, provenance
@dataclass(frozen=True) class Part:       id, soc, implementation: str | None, silicon_revision, package, radio, jlink_device, image_slots, aliases, release_status, provenance
@dataclass(frozen=True) class ImageSlot:  core, region, offset, size, supplier, provenance
@dataclass(frozen=True) class MemoryInterface: name, controller, modes, aperture_base, aperture_max
@dataclass(frozen=True) class MemoryDevice: id, technology, capacity, driver_family, modes, characterization, release_status, provenance
@dataclass(frozen=True) class AddOn:      id, fits_boards, occupies, population: Mapping[str, str], revision, aliases, release_status, extensions, provenance
@dataclass(frozen=True) class Board:      id, stage, revision, part, interfaces, population: Mapping[str, str], provisioning, jlink_device, trace_clock_mhz, aliases, release_status, extensions, provenance
@dataclass(frozen=True) class Composition: alias, board, addons; release_status (property, effective from what it references)
@dataclass(frozen=True) class LinkEnvironment: owner, link_family, profile, applies_to: tuple[str, ...], regions: Mapping[str, WindowRegion], source, revision; release_status (property, effective)
@dataclass(frozen=True) class WindowRegion: start, length, app_window, section_names
```

### `helia_platforms.target` (the resolved view)

```python
@dataclass(frozen=True)
class Target:
    id: str; kind: Literal["board", "part", "implementation", "soc"]
    soc: Soc; implementation: Implementation | None; part: Part | None; board: Board | None
    origin: Literal["builtin", "overlay"]
    release_status: Literal["public", "embargoed"]            # effective: most restrictive along the reference chain
    # structure
    core: Core; core_options: CoreOptions; npu: NpuInstance | None   # core-0 and npu-0 conveniences
    def cores(self, role: str | None = None) -> tuple[CoreInstance, ...]
    def npus(self) -> tuple[NpuInstance, ...]
    def accelerators(self) -> tuple[AcceleratorInstance, ...]
    def isa(self, core: int | str = 0) -> IsaFeatures
    def reachable(self, master: str, target: str) -> Access | None   # a region's own entry, else its controller's
    def npu_clocks(self, npu: int | str = 0) -> Mapping[str, int]   # derived from system operating points
    def memories(self, core: int | str = 0) -> tuple[MemoryRegion, ...]   # regions that core reaches, after subset, plus external regions whose interface it has an entry for
    def placement_ranges(self, core: int | str = 0) -> Mapping[str, tuple[int, int]]   # (base, size) of reachable regions; raises for a region without a base
    def cpu_mhz(self, point: str | None = None, core: int | str = 0) -> int
    def npu_mhz(self, point: str | None = None, npu: int | str = 0) -> int
    def region(self, name: str) -> MemoryRegion
    def has_region(self, name: str | None = None, *, technology=None, attachment=None) -> bool
    def has_external_memory(self, technology: str | None = None) -> bool
    def operating_points(self, domain: str | None = None) -> tuple[OperatingPoint | DomainPoint, ...]
    def operating_point(self, name: str | None = None, *, domain: str | None = None) -> OperatingPoint | DomainPoint
    default_operating_point: OperatingPoint | None
    capabilities: frozenset[str]                              # derived; stable spellings
    stage: str | None; addons: tuple[AddOn, ...]              # stage is None without a board, including implementation targets
    # boot
    boot: BootConfig | None                                   # explicit boot=, else board, else implementation provisioning, else default
    def boot_configs(self) -> tuple[BootConfig, ...]
    def flash_load_address(self, core: int | str = 0) -> int   # from boot; raises if there is none
    def usable_nvm(self, core: int | str = 0) -> Mapping[str, int]   # after reservations and other cores' slots
    # external memory
    def external_memories(self) -> tuple[MemoryRegion, ...]   # population plus add-ons, at aperture bases
    # link environments (optional)
    def budget(self, environment: LinkEnvironment, core: int | str = 0) -> Mapping[str, int]   # reachable regions only (external ones through their interface's entry); raises if no id on the reference chain is in applies_to
    def classify_address(self, address: int, master: int | str = 0) -> str | None   # alternate_bases classify to the same region; per-master Access addresses resolved for master
    # debug and SDK
    jlink_device: str | None; trace_clock_mhz: int | None; sdk: SdkFacts   # board, else implementation, else part / SDK
    aliases: tuple[str, ...]
    def provenance(self) -> ProvenanceSummary                 # worst status per group, for reports
```

`core=` and `npu=` take an index or an id. `IsaFeatures` carries `has_dsp`, `has_mve`, `mve_flavour`, `supports_fp16`,
`supports_fp32`, `supports_fp64`, `has_pmu`, `pmu_kind`.

### Overlays, validation, export, CLI

`load_overlay` parses an overlay (syntax per ADR #7), validates it against
the JSON Schema and the semantic rules, and returns a new `Catalogue`. The
semantic rules: ids unique; no shadowing of built-in ids, aliases,
compositions or shorthands; overlays add no shorthands; `based_on`
resolves; regions inside physical bounds and non-overlapping; a subset
never adds a memory or exceeds a clock; an implementation whose clock caps
drop every operating point declares its own; substitutions only on kind
`fvp`;
`derives_from` requires equal physical regions; no two devices on one
interface, no add-on on a board it does not fit, no device larger than
its aperture; provenance required on built-ins; built-in entries may not
carry `extensions`. Multicore rules (this is the one list; 0002-multicore.md
refers to it): core ids unique; index 0 has role `application`; every
`driven_by` names a core; every `clock_domain` reference names a domain;
`OperatingPoint.domains` keys name domains and values name points of
those domains; every `Access` master is a core, NPU or accelerator id and
every `Access` target is a region or memory controller of the Soc; after
`default_access` expansion every region and every memory controller a
built-in interface names has at least one entry (which may be
`access: none`); a Board, AddOn or Implementation interface whose controller has no
Soc-level entries draws a warning that its devices are unreachable,
and is an error when an Implementation removed that controller; a
`default_access` expansion that would grant core 0 a region another core
has an entry for is excluded, per the multicore document;
`app_start` keys name programmable cores; every `ImageSlot` owner is a
programmable core; slots overlap neither each other nor boot
reservations. `helia_platforms.export` writes the JSON catalogue,
filtered and scrubbed by effective release status, the JSON Schema and
Markdown pages.
`helia-platforms` CLI: `list [socs|boards|parts|implementations]`,
`show <id> [--sources]`, `windows <id> [--family --profile --environment <file>]`
(reads the optional link-environment dataset or a supplied environment),
`validate <overlay>`, `check-sources` (compare against the committed SDK
and Zephyr snapshots), `export`.

### Adapters, in the consumers

- heliaAOT: `SocPlatform.from_target(t, module_type)` builds the flattened
  view (name lowercased, `memories` from `t.budget(env)` with the
  environment heliaAOT picks per module type, falling back to the
  generated nsx-ambiq-sdk default environment for the board with a warning
  if absent, plus `t.external_memories()`, `capabilities` from
  `t.capabilities` mapped onto its enum plus its own policy tags (`MCU`), `min_alignment` and `preferred_memory_order`
  from heliaAOT tables keyed by `t.soc.id`). `platform.overlay:` and
  `platform.soc:` feed `load_overlay`.
- helia-profiler: `SocDef`/`BoardDef` become views over `Target`; its
  policy layer (`SocCapabilities`, GPIO records, reset strategies) stays
  and reads facts from `Target`; its windows table is deleted in favour of
  the generated SDK environment dataset; `target.custom_socs/custom_boards`
  is translated to the overlay format by a shim for one release.
- helia-npu: `SocDefinition` becomes a projection of `Target.npu`, its
  access entries (port classes) and the regions they name, taking an
  entry's characterization where present (it overrides the region's for
  that master) and the region's otherwise; its Vela and
  timing-adapter code is unchanged.

## Relationship to helia-aot#278

How each #278 phase lands, and the changes relative to #278's model, are
in [0002-migration.md](0002-migration.md#relationship-to-helia-aot278).

## Changes relative to RFC 0001

On acceptance of this RFC, these parts of RFC 0001 are superseded. The
rest of RFC 0001, and its appendix as the reference for data and sources,
stand.

| Topic | RFC 0001 | RFC 0002 | Why |
|---|---|---|---|
| Tool settings | Per-tool sections on built-ins (`helia_aot:` capabilities, preferred memory order, alignment; `profiler:` in custom entries) ("Facts, and each tool's settings") | No tool sections on built-ins; tool policy keyed by canonical id in each tool; overlays may carry `extensions` (proposal) | P1: the package holds facts, not opinions (owner direction; review 2.5) |
| Linker windows | A windows table in the package keyed by board, profile and link family ("Memory: physical regions and linker windows") | Not in the core model; an optional generated dataset of `LinkEnvironment`s (nsx-ambiq-sdk, Zephyr) ships separately | Windows are properties of software, not silicon |
| Capabilities | Declared lists per entry | Derived from `Core`, `CoreOptions` and `NpuInstance` | P3; declared lists drift (review 2.8) |
| `tier`, `channel` | Board fields | Removed; support level is a per-tool marker keyed by id | Tool policy, not fact |
| External memory | A PSRAM (and NVM) region per board | Board `interfaces` plus `population` plus add-ons, populated by `MemoryDevice`s | Board revisions and shields change what is fitted (research/datasheets.md section 7) |
| Boot layout | `app_flash_load_addr` as an accessor over the default window's MRAM origin | Named boot configurations on the Soc, replaceable by an Implementation, with board provisioning; `flash_load_address()` derived from the selected one | Apollo510, Lite and 330 Plus, and Apollo3/4 boot layouts differ and are a choice |
| Entity levels | Two levels (`SocDef`, `BoardDef`) plus IP blocks; an FPGA is a `BoardDef` with overrides | Four levels (Soc, Implementation, Part, Board) plus add-ons and memory devices; an FPGA is an Implementation, not a board | Bring-up stages and per-part facts (review 2.2) |
| Publication | Public repo and 0.1.0 on PyPI before adoption ("Packaging and versions") | Deferred to ADR #5 (publication, embargo and the private-to-public path) | A public release would ship embargoed parts (review 3.1) |
| Cores and accelerators | One core and at most one NPU per chip | Ordered `cores` and `npus` (index 0 primary), an explicit access matrix, image slots per core, system operating points over clock domains | Shipping parts already carry a radio core (Apollo510 Lite, Apollo330 Plus); single-core queries default to core 0 |
| Soc id resolution | A Soc id resolves to its board when the Soc has exactly one ("Names") | A Soc id always resolves to the bare Soc target; `default_board` only through `resolve_board(soc_id)` | Resolution must not change when a board is added; matches #278 |

## Private and future silicon

Unreleased SoCs never enter this repository. `builtin()` side-loads them
from installed packages registered in the entry-point group
`helia_platforms.catalogues` (for example a private
`helia-platforms-internal`) and from overlay files listed in
`HELIA_PLATFORMS_PATH`; `load_overlay` works as before. Side-loaded
entries have origin `overlay` and a source label, may not shadow
built-ins, carry provenance and `release_status` like built-ins, and are
listed by `helia-platforms show --sources`. Load order, conflict errors
and the full rules are in [0002-private-silicon.md](0002-private-silicon.md).

## Migration and output changes

Each consumer's changed outputs, the pending data corrections, and the
parity test (issue #13) that covers each are in
[0002-migration.md](0002-migration.md).

## Open questions

1. Does the estimator want `OperatingPoint` to carry voltage or rail
   facts, or is that characterization with provenance like memory timing?
2. Which environments the optional link-environment dataset covers
   (nsx-ambiq-sdk toolchains and profiles, Zephyr boards), and how it is
   versioned relative to the catalogue.
3. Of `helia-npu`'s `targets` (FVP, RTL, silicon), the memory substitutions
   and clock choices are implementation description and move here; the
   FVP binary, timing-adapter registers and run flags are harness
   configuration and stay. Confirm with the estimator owners.
4. Whether to adopt `extensions` as proposed (an opaque per-tool map on
   Soc, Implementation, Board and AddOn, overlay entries only), and
   whether it is enough for the profiler's custom-board measurement wiring
   or the profiler keeps its own sidecar file.
5. How power-domain names (used in `Access.requires_awake`) are spelled
   and sourced: the SDK HAL's power-control enums, a catalogue vocabulary
   mapped to them, or both.
6. Whether private catalogue packages are signed or version-pinned, and
   how a consumer records which private catalogue it ran against
   ([0002-private-silicon.md](0002-private-silicon.md)).
