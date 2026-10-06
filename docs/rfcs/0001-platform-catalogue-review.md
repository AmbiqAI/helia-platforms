# Review of RFC 0001: weaknesses and proposed revisions

Status: working document, 2026-10-04. Reviewer notes for the next revision
of [RFC 0001](0001-platform-catalogue.md). Each item names the gap, the
evidence, and the proposed change. Evidence comes from the source
inventories in `docs/research/`, read on 2026-10-04 at the revisions named
there. Items are grouped, then ranked at the end.

Owner direction recorded on 2026-10-04 (Adam Page) and folded into the
items below:

- heliaAOT's platform redesign (helia-aot#278) is abstracted into this
  package rather than finished inside heliaAOT.
- `helia-npu` owns NPU-driver detail only (command-stream chunking, Vela,
  port behaviour). It does not own SoC or board definitions; it consumes
  them from here.
- A SoC is a specification. Implementations of it (production silicon,
  bring-up FPGA, an Arm FVP) realize all or a subset of that specification:
  less memory, peripherals removed, lower clocks. Production is the full
  set.
- Capabilities such as MVE, FP16 or NPU are derived from SoC facts by this
  package, never declared as lists. "npu" alone is too coarse; the NPU is
  described structurally (vendor Arm, family Ethos, model U85, 256 MACs).
- Memories carry speed, port count and similar detail, not just size.
- Tool opinions such as a preferred memory order do not belong in this
  package.

## 1. Consumers and scope

### 1.1 helia-estimator is missing

The RFC names two consumers. helia-estimator is a third, and it already has
its own SoC schema in its `helia-npu` workspace package: per-SoC operating
modes (ULP, HP), per-memory timing (latency, outstanding transactions,
burst length, port), an energy layer (pJ per cycle scaling, pJ per bit per
memory), and per-field provenance (status confirmed, fitted or unverified;
source; reviewer; date). It also has a private name map in its heliaAOT
codegen path, which is a fourth copy of the naming problem the RFC sets out
to fix. See `docs/research/helia-estimator.md`.

Proposed change. The RFC's "facts versus policy" split becomes three
classes:

| Class | Example | Owner | Changes when |
|---|---|---|---|
| Structural fact | DTCM size and base, core, MVE flavour, NPU present | package | silicon or SDK changes |
| Characterization | memory read latency, pJ per bit, measured current | package, with provenance per value | a measurement or fit is redone |
| Tool policy | preferred memory order, PMU counter plan, GPIO pins | the tool | the tool decides |

Characterization lives in the package because it is true of the hardware
regardless of which tool asks, which is the RFC's own test. It needs the
provenance record in 2.1 to be honest about status. The estimator's energy
model (its scaling factors and revision history) stays in the estimator as
policy until its maintainers say otherwise.

Ownership is settled by the owner direction above: `helia-npu` keeps the
NPU-driver side (command-stream chunking, Vela system configs, port rules)
and consumes SoC and board definitions from this package. Its
`SocDefinition` and `socs/atomiq110.yaml` are therefore a migration source
for this catalogue (memory timing, modes, provenance records), not a
parallel schema. The RFC should list the fields that move and which stay in
`helia-npu` as NPU-driver policy.

### 1.2 heliaAOT issue 278 is a parallel design

AmbiqAI/helia-aot#278 ("Platform model redesign: Soc/Board split, typed NPU
spec, family-aware name aliases") is open, in progress, assigned, and sits
on the AITG Roadmap under aitg-handbook#3. It proposes the same split the
RFC proposes, inside heliaAOT. The RFC does not mention it.

Proposed change. Owner direction is to abstract 278's redesign into this
package and to reference 278 from here rather than open a separate
negotiation. Concretely: RFC 0001 cites AmbiqAI/helia-aot#278 as prior
design input and imports its design notes (Soc/Board split, typed NPU
spec, family-aware aliases) with attribution; the expected end state is
that 278's in-heliaAOT scope shrinks to the adapter once this package
exists. 278 itself is left to its assignee.

### 1.3 neuralspotx cannot be both naming authority and non-consumer

The RFC makes neuralspotx the naming authority and the SDK the authority for
firmware builds, while this package is "the authority for tools". That is
three authorities for overlapping facts. neuralspotx's 17 `board.yaml`
files and `registry.lock.yaml` already form a catalogue, and it carries
boards the RFC excludes (apollo2_evb, apollo3_evb_cygnus,
apollo4p_evb_disp_shield_rev2).

Proposed change. The catalogue holds every board neuralspotx or any
consumer knows, with a per-tool `support` marker (supported, experimental,
unsupported) instead of omission. The direction of flow is decided once:
the package generates `board.yaml` and the J-Link line into neuralspotx at
development time with a drift check (the RFC's own open alternative), or
neuralspotx stays upstream and the package imports from it in CI. The
first keeps one source; the second keeps two with a test between them.
Recommend the first, scheduled after 1.0, and the schema must be able to
hold neuralspotx's fields (`sdk_provider`, `toolchains`, `registered`) from
the start so the generator is possible later.

## 2. Data model

### 2.1 Provenance is per entry, not per fact

The RFC has `provenance` on `MemoryRegion` and `source_tag` on windows. The
estimator's schema has a provenance record on every field: status, source,
reviewer, date. The evidence rules this team works under (no silicon number
without a source of record) need the latter.

Proposed change. One provenance record type, attachable to any fact or
group of facts: `status` (datasheet, sdk, measured, fitted, derived,
unverified), `source` (a URL, a path plus revision, or a document id),
`verified_on`, `verified_by`. Validators reject an `unverified` value in a
published release unless it is explicitly allow-listed. The CLI `show`
prints status next to each value.

### 2.2 A SoC is a specification; implementations realize all or part of it

`BoardDef.tier` is `evb | fpga | custom`, which mixes what the thing is with
how well it is supported, and `is_fpga` plus clock overrides is the only
way the RFC can describe a bring-up board. In practice a bring-up FPGA runs
a portion of the RTL: less memory, some peripheral interfaces absent, lower
clocks. The estimator uses Arm FVPs the same way, as a subset model of a
SoC (`atomiq110-fvp-corstone-320`, `atomiq110-rtl`,
`atomiq110-fpga-turbo-npu`, `atomiq110-silicon` are its targets). The RFC
excludes the Corstone FVP as "not a SoC", yet heliaAOT's e2e harness and
the estimator both run on it. Separately, the J-Link device name is per
ordering part and package (`AP510NFA-CBR`, `AP510DLA-CBR`), not per SoC or
board, and the RFC itself says the apollo510L entry "covers three parts".

Proposed change. The SoC entry is the specification. An `Implementation`
realizes it, and by default realizes all of it:

| Entity | Identity | Carries |
|---|---|---|
| `Soc` | the specification (apollo510) | core, IP blocks, physical memories with their detail, operating points, derived capabilities |
| `Implementation` | one realization of a Soc | kind: silicon, fpga, fvp, rtl; a subset expression against the Soc: memories present and their sizes if reduced, peripherals removed, clock caps; defaults to the full Soc |
| `Part` | orderable silicon (AP510NFA-CBR) | an Implementation of kind silicon plus package, J-Link device, variant options |
| `Board` | a PCB (apollo510_evb) | which Part or Implementation it carries, external memories, probe wiring, trace clock |

Production parts are the full specification and say nothing extra. A
bring-up FPGA or an FVP states only what it lacks or caps, and the
validator checks the subset against the Soc (an implementation cannot add
a memory the Soc does not have, or exceed a clock). Tools address a
`Board` or an `Implementation`. `Part` can start thin (one per Soc) and
grow. "Support tier" becomes a per-tool marker, not an entity field.

### 2.3 Operating points are flat clock lists

`clocks: {cpu: [lp 96, hp 250]}` loses the coupling the estimator needs:
on atomiq110 the NPU clock and the core clock move together per mode, and
energy is measured per mode. The HAL also exposes these as named
performance modes.

Proposed change. An `OperatingPoint` entity on `Soc`: name, CPU MHz, NPU MHz
where present, the HAL enum or mode name, and a provenance record.
heliaAOT's `speeds` and the profiler's `ClockDomain` are views over it.

### 2.4 Memory `kind` mixes technology and role

`kind: mram | sram | dtcm | itcm | psram | nvm | hblram` puts a storage
technology (MRAM, PSRAM) and a bus role (ITCM, DTCM) in one enum, and the
estimator needs attributes neither captures: port, latency, cacheable.

Proposed change. Split into `technology` (sram, mram, rram, psram, flash,
nvm), `attachment` (tcm, system bus, external bus) and `role` names, with
optional characterization (latency, bandwidth, port) under 2.1.

### 2.5 Tool opinions do not belong in the package

The RFC keeps profiler policy in the profiler, keyed by id, but puts
heliaAOT's `capabilities`, `preferred_memory_order` and `min_alignment`
inside the shared catalogue. A preferred memory order of TCM, SRAM, MRAM,
PSRAM is heliaAOT's placement opinion, possibly not the right one, and a
change to it would need a helia-platforms release. The asymmetry is not
argued for, and the owner direction is that the package holds no such
opinions.

Proposed change. No tool sections for built-in entries. Each tool keeps
its policy keyed by canonical id. The one open point is the RFC's
"one custom-board file works in both tools" goal: if that is kept, the
overlay format allows an opaque `extensions:` map, namespaced per tool,
that the package passes through unvalidated and never reads. That is a
transport convenience, not an opinion. Decide in the same ADR.

### 2.8 Capabilities are derived, not declared

heliaAOT's `capabilities` lists (`MCU`, `DSP`, `MVE`, `FP16`, `NPU`,
`BLE`, `USB`, `PSRAM`) are hand-written per board, in six different
orders, and the RFC keeps them as declared data and rejects derivation
("Derive facts from descriptors instead of declaring them"). Its reason
is that derivation would change today's outputs or need special cases.
That is an argument about migration cost, not about what is true: MVE
follows from the core's MVE option, FP16 from the MVE flavour, and the
tag `npu` says nothing about which NPU.

Proposed change. The package derives capability predicates from structural
facts and exposes them as typed properties and as a stable string set for
tools that want one: `has_mve`, `mve_flavour`, `supports_fp16`,
`supports_fp32`, `supports_fp64`, `has_dsp_extension`, `has_npu`,
`npu` (structured, see below), `has_external_psram` per board. heliaAOT
maps those onto its `SocCapability` enum in its adapter; the ordering
problem disappears because the enum set is unordered and heliaAOT's docs
export sorts. `BLE` and `USB` are dropped from built-ins as the RFC
already proposes. The migration cost the RFC worried about lands in the
parity allow-list (3.5), where it belongs.

The NPU is a structured record, not a tag: `vendor: arm`,
`family: ethos-u`, `model: u85`, `macs_per_cycle: 256`, plus the
instance facts the RFC already has (clocks, base address, IRQ) and the
Vela accelerator config string as a derived view.

### 2.6 The schema is the contract, so it needs a format decision

The RFC says "the YAML layout is not [the design]", yet the overlay format
is customer-facing and the catalogue will be read by three tools. Which
runtime representation (dataclasses, pydantic, attrs) and which on-disk
format (YAML in the wheel, JSON Schema published) are undecided. Consumers
differ: heliaAOT uses pydantic v2, the profiler uses dataclasses, the
estimator is on Python 3.12 only.

Proposed change. An ADR deciding: data as YAML files shipped in the wheel;
a published JSON Schema with `$schema` and `schema_version`; a stdlib
dataclass runtime API with no heavy dependency, with pydantic model export
as an optional extra. Python floor `>=3.11`.

### 2.7 Variants that share headers need an explicit relation

apollo510, apollo510b and apollo5b share one set of register headers and
differ in radio and package. The RFC repeats their memories per entry.

Proposed change. A `derives_from` relation between Socs, resolved at load
time and visible in `show`, so the validator can require that shared
headers produce equal physical regions.

## 3. Release, publication and governance

### 3.1 Public PyPI before the repo is public leaks unreleased parts

The RFC publishes 0.1.0 to PyPI before adoption. The repo is private today
and the catalogue would include parts the SDK calls experimental or
descriptor-only. A public wheel from a private repo also cannot be audited
by the people installing it.

Proposed change. An ADR on publication: a `release_status` field per Soc,
Part and Board (public, embargoed) with a publish-time filter and a test
that embargoed entries never reach a built wheel; a private index or git
tag dependency until the repo is public; PyPI only after the repo is
public. Consumers' smoke tests that need PyPI are adjusted for the interim.

### 3.2 The drift test needs private sources from a public CI

The SDK and neuralspotx are private. A public repo's CI cannot check them
out without a token that would then live in a public workflow.

Proposed change. The drift test runs in two parts: an extractor script in
this repo that reads the SDK and writes a committed snapshot (`facts.cmake`
values, linker `MEMORY` blocks, header defines) with the SDK tag in the
file; and a CI test that compares the catalogue with the snapshot. Refreshing
the snapshot is a reviewed PR. The Zephyr comparison can stay live because
Zephyr is public. (Superseded: [ADR 0006](../adr/0006-drift-test-snapshots.md)
snapshots Zephyr as well.)

### 3.3 Schema version and data version are one number

Data corrections as minor bumps, pinned `>=0.y,<0.(y+1)`, force three
consumers to re-release for a corrected PSRAM size.

Proposed change. Two versions: the package version follows the schema and
API (semver); the catalogue carries a `catalogue_version` and date. Data-only
releases are patch bumps. Consumers pin the schema major.

### 3.4 Governance of a fact change is unspecified

Nothing says who approves a change to a silicon number or how a PR proves
its source.

Proposed change. `CODEOWNERS` per data directory; a fact-change PR
template that requires the provenance record; the validator rejects a
changed value whose provenance did not change.

### 3.5 Adoption parity needs a test, not a diff reading

The RFC proves Phase 2 by regenerating `targets.json` and reading the diff.

Proposed change. Before adoption, a parity test in this repo loads each
consumer's current literals (heliaAOT's `targets.json`, the profiler's
registry, the estimator's `at110.yaml`) and asserts the catalogue matches
except for an explicit allow-list of intended changes with reasons. The
allow-list is the change list.

### 3.6 Phase 1 lifts code; it should start from data

Phase 1 moves the profiler's `platform/` package and adds fields. A
catalogue is better built data-first: schema, YAML entries migrated by a
script from all three sources, validators, then a thin API.

Proposed change. Reorder Phase 1: schema and provenance ADRs, migration
script with parity tests, validators, API, CLI. The profiler's
`memory_map.py` windows table and its `custom.py` overlay semantics are the
parts worth lifting as code.

## 4. Smaller items

- Line references in the appendix are to moving branches. The appendix
  gives shas for some sources; it should for all. heliaAOT's local clone
  was 45 commits behind origin when checked, and the profiler clone was on
  a feature branch 255 commits behind, which is how the first local
  verification of this RFC failed.
- Python floor: heliaAOT, neuralspotx and the profiler are on `>=3.11`;
  the estimator pins `==3.12.*`. `>=3.11` for the package is consistent
  with all four; the estimator pin is its own constraint.
- Documentation output: the package should publish one machine-readable
  export (the successor of `targets.json`) and generated per-SoC and
  per-board pages, so the developer hub and each tool's docs read one
  source.
- Open hardware questions the RFC lists (apollo4p_evb PSRAM populated or
  not; J-Link names against SEGGER's database; atomiq110 NPU memory reach
  and Vela memory mode) need an owner and an issue each, not an RFC
  footnote.
- `ethos-u55-128` on Corstone-300 is excluded as "not a SoC". Under 2.2 it
  is a `Target` of kind `fvp`, and heliaAOT's e2e harness is a consumer.
- Glossary: `series`, `family`, `core_tier`, `tier`, `channel` all appear.
  Define each once.

## 5. Ranking

Blocking for the next RFC revision (must be settled before any schema code):

1. 1.1 estimator as consumer and the characterization class
2. 1.2 reconciliation with helia-aot#278
3. 3.1 publication and embargo
4. 2.1 provenance record
5. 2.2 specification and implementations
6. 2.6 schema format and runtime representation
7. 2.8 derived capabilities and structured NPU

Should be in the revision:

8. 2.3 operating points
9. 2.5 no tool opinions in the package
10. 3.2 drift test against snapshots
11. 3.3 two versions
12. 3.5 parity tests

Can follow as issues:

13. 1.3 neuralspotx direction
14. 2.4 memory kind split and memory detail (speed, ports)
15. 2.7 derives_from
16. 3.4 governance
17. section 4 items
