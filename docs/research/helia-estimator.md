# helia-estimator platform model: source inventory

- **Source:** `/Users/adam.page/Ambiq/helia/helia-estimator` (GitHub `AmbiqAI/helia-estimator`)
- **Revision:** local branch `s14-fvp-in-docker` at `8cab17d` (a feature branch, not `main`)
- **Read on:** 2026-10-04
- **Method:** Inventory from a read of the feature-branch checkout; eight citations re-checked against `8cab17d` on 2026-10-04 (results under Open questions, "Citation checks").

> **Feature branch.** `s14-fvp-in-docker` is not the default branch. Values and line numbers may differ on `main`. Re-run against `main` before reconciling.

## What it is

helia-estimator compiles LiteRT models for Arm Ethos-U85, runs them on the Corstone-320 FVP, and estimates cycles and energy for Ambiq SoCs. It splits its platform data in two: SoC facts (NPU, clock modes, memories, timing, provenance) live in the workspace member package `helia-npu`; the estimator's own platform files add an energy model and a revision history on top.

| Item | Value | Source |
| --- | --- | --- |
| Platform document type | `PlatformModel` | `helia_estimator/platform_schema.py:168` (see Citation checks) |
| Platform files directory | `PLATFORMS_DIR = helia_estimator/platforms/` | `helia_estimator/platform.py:91` |
| Loader | `load_platform(path_or_name)` | `helia_estimator/platform.py:368` |
| Shipped platform files | `at110.yaml`, `atomiq110.yaml` | `helia_estimator/platforms/` (listed 2026-10-04) |
| SoC definitions | `helia-npu` package | `packages/helia-npu/src/helia_npu/socs/` |
| Timing derivation | `derive_timing(platform, mode) -> DerivedTimingProfile` | `helia_estimator/` |

## Platform model (types, fields, data files)

### `PlatformModel` (estimator layer)

| Field | Type | Meaning | Source |
| --- | --- | --- | --- |
| `soc` | `str \| None` | Packaged helia-npu SoC id, or a path | `platform_schema.py:177` |
| `soc_overrides` | `SocOverridesModel \| None` | Per-platform overrides of SoC values | `platform_schema.py:179` |
| `energy` | `EnergyModel` | Core scaling per mode plus memory pJ/bit read and write | `platform_schema.py:181`, `EnergyModel` at `:68`, `CoreEnergyModel` at `:42` |
| `revisions` | `list[RevisionModel]` | Revision history | `platform_schema.py:184`, `RevisionModel` at `:31` |
| Inline SoC fields | `name`, `id`, `origin` (`golden` / `derived` / `custom`), `revision`, `npu`, `macs`, `axi_bus_width_bits`, more | Used when the SoC is written inline instead of referenced; `golden` is reserved for helia-npu packaged SoCs | `platform_schema.py:187-199` |

### `helia-npu` SoC definition (`socs/atomiq110.yaml`)

| Field | Value | Source |
| --- | --- | --- |
| `name` / `id` | `AT110` / `atomiq110` | `atomiq110.yaml:10-11` |
| `origin` | `golden` | `atomiq110.yaml:12` |
| `npu` | `ethos-u85` | `atomiq110.yaml:18` |
| `macs` | 256 | `atomiq110.yaml:19` |
| `axi_bus_width_bits` | 128 | `atomiq110.yaml:20` |
| `modes` | `ULP` `npu_clock_hz: 100e6`; `HP` `npu_clock_hz: 500e6` | `atomiq110.yaml:21-25` |
| Provenance per field | `status` (`confirmed` \| `fitted` \| `unverified`), `source`, `reviewed_by`, `reviewed_on` | `atomiq110.yaml` |

| Memory | AXI port | Read latency | Outstanding | Burst | Source |
| --- | --- | --- | --- | --- | --- |
| `ssram` | 0 | 120 ns | 2 | 256 B | `atomiq110.yaml:30-35`; file notes say 120 ns / 2 outstanding is a stand-in for the SRAM port's rate, not a measured value |
| `hblram` | 1 | 88 ns | 12 (file) | 256 B | `atomiq110.yaml:57-62`; read latency provenance `unverified` (architect estimate) |
| `psram` | 1 | 152 ns | 10 (file) | 256 B | `atomiq110.yaml:82-87` |
| `rram` | 1 | 240 ns | not read | not read | `atomiq110.yaml` (latency from the prior read; not re-checked) |

`helia-npu` also provides `SocDefinition`, `soc_schema`, `vela.system_config`, and `npu_reference`. Its targets: `atomiq110-fvp-corstone-320`, `atomiq110-rtl`, `atomiq110-fpga-turbo-npu`, `atomiq110-silicon`.

### Energy values in `platforms/at110.yaml`

These are the estimator's current model values with `helia_estimator/platforms/at110.yaml` as the source. They are not silicon facts.

| Item | Value | Source |
| --- | --- | --- |
| Core scaling `ULP` | 0.311 of an Arm pJ/cycle reference | `at110.yaml:81` |
| Core scaling `HP` | 0.554 of an Arm pJ/cycle reference | `at110.yaml:82` |

| Memory | Read pJ/bit | Write pJ/bit | Source |
| --- | --- | --- | --- |
| `ssram` | 0.282 | 0.253 | `at110.yaml:91-93` |
| `hblram` | 1.0 | 1.0 | `at110.yaml:100-102` |
| `psram` | 12.7 | 12.7 | `at110.yaml:107-109`; file note: write assumed equal to read |
| `rram` | 5.0 | 5.0 | `at110.yaml:114-116`; file provenance: placeholder, no Ambiq RRAM figure exists yet |

| Revisions | Value | Source |
| --- | --- | --- |
| Entries | 9 (`v1` to `v9`) | `at110.yaml:24-66` |
| `v9` | PSRAM and RRAM join HBLRAM as port-1 memories of one platform; selected with `memory_placement` | `at110.yaml:63-66` |

### Retired platforms

| Name | Replacement | Source |
| --- | --- | --- |
| `at110_psram` | `at110` with `memory_placement` const `psram` | `platform.py:95-99` |
| `at110_rram` | `at110` with `memory_placement` const `rram` | `platform.py:95-99` |

## Registered entries (table)

| Platform file | SoC | Origin | Energy model | Revisions | Source |
| --- | --- | --- | --- | --- | --- |
| `at110.yaml` | `atomiq110` (helia-npu) | golden SoC | Yes (above) | 9 | `helia_estimator/platforms/at110.yaml` |
| `atomiq110.yaml` | not read in this pass | not read | not read | not read | `helia_estimator/platforms/atomiq110.yaml` |

| helia-npu SoC | Targets | Source |
| --- | --- | --- |
| `atomiq110` | `atomiq110-fvp-corstone-320`, `atomiq110-rtl`, `atomiq110-fpga-turbo-npu`, `atomiq110-silicon` | `packages/helia-npu/` |

## Consumers / name resolution

| Path | Input | Result | Source |
| --- | --- | --- | --- |
| `load_platform` | Built-in name, case-insensitive (for example `"at110"`) | `platforms/at110.yaml` | `platform.py:368-389` |
| `load_platform` | Retired name | `PlatformError` with the replacement text | `platform.py:383-385` |
| heliaAOT codegen bridge | `ap510`, `apollo510`, `apollo510_eb`, `apollo510_evb` (case-insensitive, `-` normalised to `_`) | heliaAOT `apollo510_evb` | `runtime/helia_aot_codegen.py:48-58` |
| heliaAOT codegen bridge | Any name starting `at110` | `at110` | `runtime/helia_aot_codegen.py:56-57` |
| heliaAOT codegen bridge | Anything else | `None` | `runtime/helia_aot_codegen.py:58` |
| Example config | `"platform": {"name": "apollo510_evb"}` | n/a | `case_tools.py:248` (see Citation checks) |

| Dependency | Kind | Note |
| --- | --- | --- |
| `helia-aot>=0.17.1` | Optional | Imported in `runtime/helia_aot_codegen.py`; heliaAOT platform types are not imported |
| `helia-npu` | Workspace member | SoC definitions and Vela system config |

## Facts it carries that the others do not

| Fact | Where |
| --- | --- |
| NPU MAC count and AXI bus width | `atomiq110.yaml:19-20` |
| NPU clock modes `ULP` and `HP` | `atomiq110.yaml:21-25` |
| Per-memory AXI port, latency, outstanding transactions, burst length | `atomiq110.yaml` |
| HBLRAM as a modelled memory (heliaAOT has no type for it) | `atomiq110.yaml`, `at110.yaml` |
| Per-field provenance with status, source, reviewer, review date | `atomiq110.yaml` |
| Energy model (core scaling, pJ/bit per memory) with revision history | `at110.yaml` |
| Only repo with energy data keyed to a platform | `at110.yaml` |

## Tooling to mirror

| Area | Setting | Source |
| --- | --- | --- |
| Python | `requires-python ==3.12.*` | `pyproject.toml` |
| Build | hatchling | `pyproject.toml` |
| Lint | ruff line length 99 | `pyproject.toml` |
| Types | ty (config at line 135) | `pyproject.toml` |
| CI | `.github/workflows/ci.yml` runs `scripts/gates.py` plus a separate FVP gate | `.github/workflows/ci.yml` |
| pre-commit | None | repo root |
| Ownership | No CODEOWNERS | repo root |
| Docs | `docs/AT110_Platform_Guide.md`, `at110_power_energy_parameters.md`, `at110_system_architecture.md`, `npu_estimation_methodology.md`, `corstone_fvp_contract.md` | `docs/` |
| Design records | No RFC or ADR series | repo |

## Other helia repos (grep sweep)

| Repo | Per-SoC definitions | Note |
| --- | --- | --- |
| helia-core | None | |
| helia-rt | None | |
| helia-edge | None | |
| helia-dsp | None | |
| helia-ml | None | References `apollo510b_evb` only in `tools/profiling/fixtures/` as a reference board |
| helia-sdlc | None | SDLC planning docs and templates (`product-record.md`, `release-readiness-review.md`, `compatibility-matrix.md`), not a repo scaffold |

## Open questions

### Issues (from the prior read; not re-queried)

| Issue | State | Topic |
| --- | --- | --- |
| #60 | OPEN | AT110 SRAM port model |
| #54 | OPEN | FVP SRAM0/SRAM1 port rule |
| #55 | OPEN | at110 v9 SSRAM stand-in HP generalization |
| #56 | OPEN | Zero-MAC energy estimation |
| #53 | CLOSED | NPU SRAM burst split |

### Questions

| # | Question |
| --- | --- |
| 1 | Does `main` differ from `s14-fvp-in-docker` in `platform_schema.py`, `platforms/`, or `helia-npu/socs/`? |
| 2 | What does `platforms/atomiq110.yaml` contain, and how does it relate to `at110.yaml`? It was listed but not read. |
| 3 | Should SoC timing and provenance (helia-npu) move into helia-platforms, or should helia-platforms reference helia-npu? The two overlap on SoC identity and memories. |
| 4 | The heliaAOT bridge maps only Apollo510 aliases and `at110*`. heliaAOT now has a first-class `atomiq110` entry; the bridge returns `at110`, which is not a heliaAOT registered name at `e537d293`. Confirm the intended heliaAOT target for AT110. |
| 5 | Where is the estimator's project board? Not identified in this pass. |

### Citation checks (2026-10-04, against `8cab17d`)

| Citation given | Result |
| --- | --- |
| `platform_schema.py:1-59` for `PlatformModel` | Mismatch. The file is 342 lines. 1-59 holds the module docstring, imports, `PlatformSchemaError` (24), `RevisionModel` (31), and `CoreEnergyModel` (42). `PlatformModel` is at 168, with fields `soc`, `soc_overrides`, `energy`, `revisions` at 177-184. |
| `platform.py:91` `PLATFORMS_DIR` | Match. |
| `platform.py:368-389` `load_platform`, case-insensitive | Match. `def load_platform` at 368; case-insensitive stem match in the body. |
| `runtime/helia_aot_codegen.py:48-58` name map | Match. Mappings at 48-53; `at110` prefix rule at 56-57. |
| `case_tools.py:24` uses `apollo510_evb` | Mismatch. Line 24 is an import. `apollo510_evb` appears at line 248. |
| `atomiq110.yaml` fields `id`, `npu`, `macs`, `axi_bus_width_bits`, modes | Match (lines 11-25). |
| `at110.yaml` core scaling and memory pJ/bit values | Match (lines 81-82, 91-116). |
| Nine revision entries | Match (`v1` to `v9`, lines 25-63). |
