# helia-aot#278: platform model redesign (verbatim capture)

Source: https://github.com/AmbiqAI/helia-aot/issues/278 (OPEN, opened 2026-08-15 by apage224, updated 2026-09-26, assignee evanchen11, labels enhancement, refactor, priority:P2)
Captured: 2026-10-04 with `gh issue view 278 --json body,comments`. Text is unedited; this file exists so the design input is readable without GitHub access and pinned to the date read.

## Issue body

## Problem statement

The platform registry (`helia_aot/platforms/`) is starting to outgrow its model in three ways. None is urgent in isolation, but #276 (Ethos-U NPU gating), the atomiq110 naming discussion, and the goal of supporting customers' production boards all press on the same seams, so it's worth designing the next shape deliberately instead of patching per-PR.

### 1. `SocCapability` mixes three kinds of facts that age differently

Audit of what actually consumes each capability (as of `main` + #276):

| Capability | Consumers in codegen |
|---|---|
| `MCU`, `DSP`, `MVE` | 39 references across 7 operator kernel-selection files |
| `FP16` | `SocPlatform.supports_fp16` → kernel dispatch |
| `NPU` (new in #276) | Ethos-U convert-time gate |
| `BLE`, `USB`, `PSRAM` | **zero** |

- The **ISA tier** (`DSP`/`MVE`/`FP16`) is fully derivable from `cpu` for every registered platform (M4 → DSP; M55 → DSP+MVE+FP16). It's per-board data that can drift, encoding what is really a per-core fact. `supports_fp16` already has the right trust-unknown-cores override mechanism; it just isn't generalized.
- The **accelerator tier** (`NPU`) is a bare boolean with no variant. A command stream Vela built for `ethos-u55-128` converts cleanly against atomiq110 (Ethos-U85-256) and fails at runtime on hardware — the gate added in #276 checks presence, not compatibility. Distinguishing U55/U65/U85 (and MAC width) inside a flat enum doesn't scale.
- The **peripheral tier** (`BLE`/`USB`/`PSRAM`) is decorative. Notably, `SocCapability.PSRAM` doesn't even gate PSRAM-the-memory: the planner reads only `memories` + `preferred_memory_order`. The two spellings are already inconsistent — `apollo510_evb` declares both the capability and a `MemoryType.PSRAM: 32 MB` region; the Apollo4P boards declare the capability with no region.

### 2. Board facts and die facts are fused

`apollo510_evb`'s 32 MB PSRAM region is the EVB's soldered part, not an Apollo510 die fact. Production customers don't ship EVBs: their board has zero, or a different part, or other external memory. Today the only way to express that is to register a full custom platform — `resolve_platform` requires re-supplying `cpu`, all `memories`, `capabilities`, `preferred_memory_order`, and `min_alignment` — restating every die fact just to change one board-level number, with nothing keeping the restated facts in sync with ours.

The registry also already contains one deliberate SoC-level entry (`at110`, soon `atomiq110` per the #276 review) among 14 `*_evb` board entries. "Is this a die or a board" is currently encoded only in whether the name ends in `_evb`.

Note the external/on-die split is **per-region, not per-type**: atomiq110's `DRAM` region is on-chip HBLRAM, so "PSRAM/DRAM = external" is not a safe rule.

### 3. Naming: families, shorthands, and aliases

Ambiq's product families get referred to loosely in practice: `Apollo510`, `AP510`, `AP5` (the whole apollo5 subset); `Atomiq110`, `AT110`. The registry has no family concept, so:

- 1:1 shorthands (`AT110` → `atomiq110`) have no home. The historical workaround is copy-registering a twin platform (`apollo3p_evb`, and previously `apollo510_eb`, dropped in e3d5c667) — a live hazard, since capability edits like #276's one-liner must then be made in N places with nothing enforcing it.
- Subset shorthands (`AP5` ⊃ `apollo510_evb`, `apollo510l_evb`, `apollo510b_evb`) must not silently resolve to one member; they should produce a did-you-mean listing the candidates.
- A typo'd built-in name plus the required custom fields silently registers a *new* platform today — no warning, working-but-wrong build. Name resolution and did-you-mean belong in one place.

### Related bug (fix should not wait for this redesign)

`resolve_platform` registers custom platforms into the process-global registry. A second conversion in the same process reusing a custom platform name silently returns the first registration's config — differing fields are ignored — and logs a warning that misidentifies the custom platform as "a built-in". Bites any batch/multi-convert flow (e.g. profiling). Reproduced on `main`; will file separately.

## Proposed model

Split along the lines the data already draws — die facts vs. board composition — and make the accelerator a typed spec:

```python
@dataclass(frozen=True)
class NpuSpec:
    family: str          # "ethos-u85" | "ethos-u65" | "ethos-u55"
    macs: int            # 256 → cross-check Vela --accelerator-config "ethos-u85-256"

@dataclass(frozen=True)
class Soc:               # die facts — ours to own; users never restate them
    name: str            # "atomiq110", "apollo510"
    family: str          # "atomiq", "apollo5" — anchor for aliases/shorthands
    cpu: str
    memories: dict[MemoryType, int]     # on-die only (TCM/SRAM/MRAM; atomiq110's HBLRAM)
    npu: NpuSpec | None = None
    min_alignment: int = ...

@dataclass(frozen=True)
class Board:             # composition — what EVBs are, and what users write
    name: str            # "apollo510_evb", "my_product_rev_b"
    soc: str             # registry reference, not a copy
    external_memories: dict[MemoryType, int] = {}
```

Consequences:

- **ISA features derive from `cpu`** (with the existing explicit-declaration override for unknown/bespoke cores, generalizing the `supports_fp16` mechanism). `DSP`/`MVE`/`FP16` stop being per-board data.
- **`NpuSpec` replaces the bare `NPU` capability.** The Ethos-U gate can then cross-check the model's Vela accelerator config against the target instead of checking presence only — closing the variant-blindness gap properly (relates to #78's U85 coverage gap).
- **`BLE`/`USB`/`PSRAM` capabilities** become board metadata (docs/display only) or are dropped; nothing consumes them.
- **`preferred_memory_order` becomes derivable**: the SoC declares its on-die order; board composition appends external regions. Overridable, but no longer required input for a user adding one PSRAM part.
- **Aliases and family shorthands** hang off `Soc.name`/`Soc.family` in the single name-resolution path: 1:1 aliases resolve; family/subset shorthands raise with a did-you-mean listing members; near-miss typos get a did-you-mean instead of silently becoming a new custom platform.

### User-facing payoff

Custom production board collapses from "restate the die" to:

```yaml
platform:
  soc: atomiq110
  memories:
    psram: 8MB
```

### Migration / blast-radius containment

Keep `SocPlatform` as the **resolved, flattened view**: resolution composes `Soc` + `Board` into exactly the object the memory planner and all operator kernel-selection code consume today (`.memories`, `.capabilities`, `.supports_fp16`, `.supports_npu` unchanged). Only the registry/resolution layer changes; consumers don't move. Existing full-form custom-platform YAML keeps working as a board with an anonymous inline SoC. Existing built-in names (`apollo510_evb`, …) remain valid `platform.name` values.

Suggested sequencing:

1. #276 lands with the rename to `atomiq110` + its review items (no new mechanism).
2. `resolve_platform` registration bug fixed (separate issue; independent of the redesign).
3. Soc/Board split + `NpuSpec` + derived ISA features, `SocPlatform` kept as the resolved view.
4. Alias/family shorthand resolution, designed against the new model (`at110` → `atomiq110` as the first entry, Apollo shorthands as the hard cases).

## Open questions

1. **Should `AP510` resolve or be ambiguous?** It plausibly means `apollo510_evb`, but Lite/Blue variants exist. Proposal: only exact 1:1 aliases resolve; everything family-shaped gets a did-you-mean.
2. **SoC-only conversion targets**: is targeting a bare SoC (as `at110` is today) a supported flow, or should conversion always name a board (with an auto-generated "bare" board per SoC)?
3. **Custom aliases**: can user YAML platforms declare aliases, or is the alias table built-ins-only?
4. **Peripheral capabilities**: keep `BLE`/`USB`/`PSRAM` as parse-accepted-but-ignored for config compat, or hard-deprecate with a warning cycle (matching the warn-first config-strictness policy)?
5. **`NpuSpec` granularity**: is family+MACs sufficient to validate against Vela output, or do we need the full accelerator-config string (and does the command stream carry enough metadata to check at convert time)?
6. **Docs shape**: `docs/reference/registries/platforms.md` grouped by family (SoC page with board variants) — and should the drift guard grow to check capability/memory accuracy, not just name presence (the gap that let stale `at110` docs through in #276)?

---

Context: findings audited on `main` + PR #276; discussion in the #276 review thread. Relates to #265 (closed by #276), #78 (U85 coverage).

## Comment by apage224 on 2026-08-24

Cross-reference from the heliaPROFILER side (via the AITG roadmap review): hpx has a mature implementation of much of this shape that may save a design cycle —

- **Soc/Board split with a registry**: `helia_profiler/platform/` — frozen `SocDef`/`BoardDef` dataclasses, a build-time registry, and an `is_builtin` discipline that prevents user-declared custom parts from inheriting registered-part facts (name-collision forgeries included).
- **Typed per-part capability specs**: `SocCapabilities` (clock/memory/power/transport/reset sub-specs), family-aware defaults with per-part overrides, and characterized-vs-declared provenance kept distinct.
- **Verified memory model**: per-SoC hardware-aperture windows + per-link-family app extents characterized from the NSX linker scripts (`platform/memory_map.py`), with every constant cited to its source line and contract-tested against drift.

Related asks already filed on this repo that would ride the same typed contract: #310 (versioned memory manifest) and #318 (ITCM placement). Happy to walk through the hpx model or share the characterization tables.

## Comment by apage224 on 2026-08-25

Scoping update from the #276 (atomiq110) takeover — the capabilities weakness is now concrete enough to design against:

**The flat `SocCapability` list conflates three different kinds of fact:**
1. **CPU-derived properties** — FP16 is a property of the core (`cortex-m55` ⇒ MVE-FP), yet it sits in the same list as everything else and `supports_fp16` separately hard-codes a CPU set. One fact, two encodings, drift possible.
2. **Attached accelerators needing structure** — `NPU = auto()` can say *that* an NPU exists but not *which*: atomiq110 is specifically Ethos-**U85-256**. The Vela accelerator config (`ethos-u85-256`), the driver dependency, and the FVP choice (Corstone-320 vs -300) all derive from that identity, and today each consumer would have to hard-code it. A typed spec — e.g. `npu: EthosU(generation=U85, macs=256)` — makes `supports_npu` a derived property and gives #276's gate, the nsx manifest dependency, and future Vela integration one source of truth.
3. **Board-level peripherals with zero consumers** — BLE/USB/PSRAM have no reader anywhere in codegen (audited earlier: MCU/DSP/MVE drive kernel selection, FP16 → `supports_fp16`, NPU → the new gate, rest unused). PSRAM-the-capability doesn't even gate PSRAM-the-memory (the planner reads only `memories`). These belong on the Board side of the Soc/Board split, or nowhere.

Suggested sequencing: #276 merges with the boolean `SocCapability.NPU` as-is (shipped, gated, tested); this redesign then replaces the flat list with (cpu-derived, typed accelerator spec, board peripherals) without changing #276's user-facing behavior — `supports_npu` survives as a property over the typed spec, so the gate's call sites don't churn.

## Comment by evanchen11 on 2026-08-28

## Implementation plan

Grounded in `main` (post-#276) and a read of heliaPROFILER's `helia_profiler/platform/` (per the hpx cross-reference comment — its frozen `SocDef`/`BoardDef` dataclasses and provenance discipline are directly liftable; its fully per-run registry is not adopted wholesale, see the constraint below).

**Constraint honored throughout:** no breaking changes to the public Python API — `register_platform()` keeps its exact current behavior (process-lifetime registration, duplicate name → `KeyError`). Production users consume helia-aot via the Python API.

### Phase 0 — `fix:` resolve_platform stops mutating the registry (#331)

- `resolve_platform` no longer registers config-derived custom platforms into `_PLATFORM_REGISTRY`. It builds, validates, and returns the `SocPlatform` as a run-local value that lives only for that conversion — two conversions in one process each get platforms built from their own config, which fixes the stale-reuse bug structurally rather than by detecting collisions.
- Add built-in/custom provenance (hpx `SocOrigin`-style field: set only at built-in registration, survives `dataclasses.replace`).
- Fix the override warning: only claim "built-in" for actual built-ins; clearly name the ignored fields.
- Regression tests: same custom name + different fields resolved twice → each gets its own config; registry unchanged after custom resolution; `register_platform` semantics untouched; warning wording.

### Phase 1 — `refactor:` Soc/Board split, `NpuSpec`, ISA derivation

Internal-only; codegen snapshots must not change.

- New frozen dataclasses in `platforms/defines.py` (adapting hpx `SocDef`/`BoardDef`):
  - `NpuSpec(family, macs)` with an `accelerator_config` property (`"ethos-u85-256"`).
  - `Soc` (name, family, cpu, on-die memories, npu, min_alignment, speeds) and `Board` (name, soc reference, external memories) — external/on-die marked **per-region** (atomiq110 HBLRAM caveat).
- One ISA table (`cortex-m4 → {DSP}`, `cortex-m55 → {DSP, MVE, FP16}`) replaces `_FP16_CPUS`/`_NON_FP16_CPUS` *and* the per-registration ISA capability lists, generalizing `supports_fp16`'s existing policy: derive from known cores, trust explicit declarations on unknown cores, reject contradictions on known-incapable cores. Registrations stop declaring ISA caps; the resolved view populates them, so the ~39 kernel-selection references don't change.
- **`SocPlatform` stays as the flattened resolved view** — `Soc` + `Board` compose into it at registration. Planner, kernel selection, `supports_fp16`, `supports_npu`, and #276's gate don't move.
- Rewrite the 15 registrations as ~8 `Soc`s + boards (`apollo510_evb` = apollo510 + 32 MB external PSRAM; **atomiq110 stays a valid bare-SoC target** — open question 2 resolved: SoC-only conversion targets are supported).
- `preferred_memory_order` becomes derived (SoC on-die order + appended external regions); explicit override retained.
- **BLE/USB/PSRAM capabilities: parse-accepted with a deprecation warning** (open question 4 resolved — matches the warn-first config-strictness policy). Nothing consumes them.
- Existing full-form custom-platform YAML resolves as a board with an anonymous inline SoC — byte-identical `SocPlatform` output, test-enforced via snapshot neutrality.

### Phase 2 — `feat:` `platform.soc` config surface

- `PlatformArgs` gains `soc:` + memory overlay (extends `_ConfigBase` for unknown-key warnings), enabling:
  ```yaml
  platform:
    soc: atomiq110
    memories:
      psram: 8MB
  ```
- CLI bridge regen; refresh embedded `--help` in `docs/reference/commands/*.md`.

### Phase 3 — `feat:` NPU variant cross-check

- **Spike first** (open question 5): determine whether the Vela command stream carries enough metadata to recover the accelerator config at convert time.
- If yes: the Ethos-U gate compares the stream's config against `Soc.npu` — a `u55-128` stream targeting U85-256 → `ConfigValueError` with hint. If no: presence check stays; the mismatch gap is documented as a runtime limitation. `require_platform_npu` opt-out unchanged. Relates to #78.

### Phase 4 — `feat:` aliases & family shorthands

- Alias table in `_canonical_platform_name` (the single resolution path), **built-ins-only initially** (open question 3 resolved):
  - Exact 1:1 aliases resolve: `at110 → atomiq110` first. **`AP510` does not resolve** (open question 1 resolved) — anything family-shaped (`AP5`, `AP510`) raises with a did-you-mean listing the member platforms.
  - Near-miss typos get a did-you-mean instead of falling into the custom-platform-required error path.
- Retire the `apollo3p_evb` copy-twin via alias.
- **Docs grouped by family** (open question 6 resolved): SoC page with board variants in `docs/reference/registries/platforms.md`; **drift guard extended to check capability/memory accuracy**, not just name presence.

### Sequencing

Five squash-merged PRs (`fix:`, `refactor:`, `feat:` ×3), each independently green. Phase 0 (#331) is unblocked now; Phase 3's spike can run parallel to Phase 2; Phase 4 depends on Phase 1's `Soc.family`.

## Comment by apage224 on 2026-09-26

Folding #321 into this issue. #321's fixes (conservative DTCM map, no DRAM pool, fatal missing nsx::npu) shipped in v0.19.0. What remains is silicon-vs-FPGA provenance and how to model HBLRAM variants, which is part of this platform-model design.
