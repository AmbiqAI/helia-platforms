# helia-estimator: question surface

- **Source:** `/Users/adam.page/Ambiq/helia/helia-estimator` (GitHub `AmbiqAI/helia-estimator`, with workspace package `packages/helia-npu`)
- **Revision:** `origin/main` `5991d9f1`. The local feature branch differs from it only in `docs/reference/platform.md`.
- **Read on:** 2026-10-04
- **Method:** query-surface read by a gatherer against `origin/main` (`5991d9f1`). Spot checks at the end were run with `git show origin/main:<path> | sed -n 'N,Mp'`.

This note records what helia-estimator code asks of a platform today. It complements [helia-estimator.md](helia-estimator.md), which was read from feature branch `s14-fvp-in-docker`. Paths in the question table are relative to `helia_estimator/` unless stated. The "fact or tool policy" column is this note's classification, not a label the source carries.

## Public surface

Schema in `packages/helia-npu/src/helia_npu/soc_schema.py`.

| Model | Field | Detail |
| --- | --- | --- |
| `SocModel` | `name` | Required |
| | `id` | Defaults to lowercased `name` |
| | `origin` | `golden` \| `derived` \| `custom`; default `custom` |
| | `revision` | String, or `{label, stage, date, notes}` |
| | `npu` | Family `ethos-u85` \| `ethos-u65` \| `ethos-u55` |
| | `macs` | int |
| | `axi_bus_width_bits` | Optional; per-NPU default U55 64, U65 128, U85 128 |
| | `modes` | dict name to `{npu_clock_hz}` |
| | `memories` | dict name to `MemoryModel` |
| `MemoryModel` | `axi_port` | 0 or 1. 0 is Vela `Sram` / Arm `AXI_SRAM`; 1 is Vela `Dram` / `AXI_EXT` |
| | `read_latency_ns`, `write_latency_ns` | Latency |
| | `max_outstanding` | Outstanding transactions |
| | `burst_length` | Bytes: 64, 128, or 256 on the U85 FVP |
| | `ports_used` | 1 or 2 |
| | `axi_clock_hz` or `bandwidth_fraction` | One required |
| | `provenance` | `ProvenanceModel` |
| `ProvenanceModel` | `status` | `confirmed` \| `fitted` \| `unverified` |
| | `source`, `reviewed_by`, `reviewed_on`, `notes` | Record fields |
| | `fields` | Per-value records |

### Defined SoCs

| SoC | Origin | Content |
| --- | --- | --- |
| `atomiq110` | golden | Port 0: SSRAM 3 MB. Port 1: HBLRAM (default), PSRAM, RRAM, selectable by `memory_placement`. Revision v9 (RTL, 2026-09-25); no silicon |

Only `atomiq110` is defined. `apollo510_evb` appears only as a heliaAOT codegen proxy.

### Other facts carried

| Item | Value | Source |
| --- | --- | --- |
| NPU reference energy | One row: (`ethos-u85`, 256) gives 116.749 pJ/cycle, Arm reference, status confirmed | `packages/helia-npu/src/helia_npu/npu_reference.py` (see Citation checks) |
| Python | `requires-python ==3.12.*` | `pyproject.toml` |
| heliaAOT | Pinned to git rev `d2c26db0` pending PyPI | `pyproject.toml` |
| Vela | `ethos-u-vela>=5.2.0` | `pyproject.toml` |

## Question table

| Question in plain words | API used today | Caller file:line | What it does with the answer | Fact or tool policy |
| --- | --- | --- | --- | --- |
| Which mode's NPU clock applies? | `platform.soc.resolve_mode(mode).name` | `pipeline/vela.py:52` | Vela compile, timing | Fact (clock per mode) |
| Which memory does each port carry in this run? | `platform.soc.occupants(placement)` | `pipeline/vela.py:65` | Timing adapters, energy YAML | Fact per placement; placement choice is tool policy |
| Is the NPU a U85? | `platform.soc.npu == NpuFamily.ETHOS_U85` | `pipeline/vela.py:86` | FVP runner choice | Fact |
| Do target and platform name the same SoC? | `target.soc` vs `platform.soc.id` | `pipeline/vela.py:104-106` | Validation | Identity |
| What is the platform name? | `platform.soc.name` | `pipeline/vela.py:111` | Log | Identity |
| What feeds the provenance rollup? | `soc.memories[n].params`, `soc.modes` | `platform.py:194,207-208` | Status report | Provenance |
| Which memory has this name (case-insensitive)? | `soc.resolve_memory(name)` | `platform.py:504` | Timing overrides | Identity |
| Which modes, which occupants, what AXI beat width? | `soc.modes`, `occupants()`, `axi_bus_width_bits` | `platform.py:565,567,582` | Energy YAML | Fact |
| Which Vela memory mode for a placement? | `soc.fvp_memory_mode(placement)` | `pipeline/case.py:60` | FVP runtime, results | Tool policy (FVP mapping) |
| What revision, id, origin, NPU, clock? | `soc.*` | `pipeline/case.py:97,118-119,128-129,206` | Results metadata, cycle model | Fact and provenance |
| Which NPU? | `soc.npu` | `pipeline/analysis_stage.py:140` | Analysis dispatch | Fact |
| Load an SoC by id or path and apply overrides | `load_soc("atomiq110")`, `derive_soc(base, overrides)` | `platform.py` `load_platform` | Platform assembly | Mixed |
| Which mode, by name or default? | `resolve_mode`, `modes` | `cli/platform_cmd.py:40` | Display | Fact; default choice is tool policy |

## Overlay and custom-definition surface

| Surface | Detail |
| --- | --- |
| Platform YAML `soc:` | SoC id or path |
| `soc_overrides` keys | `name`, `id`, `origin` (hardware changes force `derived`), `revision`, `npu`, `macs`, `axi_bus_width_bits`, `modes` (replaces the table), `memories` (merge; `null` removes; the first memory on a port stays default unless removed) |
| Inline SoC | Used when `soc` is `None`; overrides forbidden |
| Validation | Every port-0 memory required; golden requires provenance on every memory; the energy model must name every mode and memory |
| Provenance of overrides | User overrides carry no per-field provenance. Base provenance carries forward; a per-memory override replaces that memory's provenance |
| Retired platforms | `RETIRED_PLATFORMS`: `at110_psram`, `at110_rram` point to `at110` plus `memory_placement` |

## Name resolution

| Aspect | Behaviour |
| --- | --- |
| Platform files | `load_platform` uses a case-insensitive glob in `helia_estimator/platforms` |
| SoC memories | `resolve_memory` is case-insensitive (`platform.py:504`) |
| heliaAOT codegen name | `runtime/helia_aot_codegen.py` maps `ap510`, `apollo510`, `apollo510_eb`, `apollo510_evb` to `apollo510_evb`; names starting `at110` map to `at110` |
| Target vs platform | `target.soc` must equal `platform.soc.id` (`pipeline/vela.py:104-106`) |

## Workarounds for missing model facts

| Workaround | Where | Missing fact it stands in for |
| --- | --- | --- |
| FVP Corstone-320 models the U85 at the same base `0x50004000`, with generic SRAM and DDR plus timing adapters (TA0 `0x50006000`, TA1 `0x50006800`) in place of SSRAM, HBLRAM, PSRAM, RRAM | FVP path | Real atomiq110 memory subsystem |
| Port-1 latency clamped to port-0 when port-0 is bandwidth-bound | `write_system_config` | Port interaction under load |
| Not modelled: sleep modes, HBLRAM controller, PSRAM XSPI queue, RRAM pipeline, SSRAM striping | FVP path | Same |
| `apollo510_evb` used as heliaAOT codegen proxy; `at110*` collapsed to `at110` | `runtime/helia_aot_codegen.py` | Shared SoC identity with heliaAOT |
| `RETIRED_PLATFORMS` redirect | Platform loader | Placement as a run choice rather than a platform |

## Proposed ownership split (gatherer's judgement)

This table is the gatherer's proposal, not a decision.

| Content | Proposed owner |
| --- | --- |
| `id`, `name`, `origin`, `revision`, `npu`, `macs`, `axi_bus_width_bits`, `modes` | SoC structural facts in helia-platforms |
| `memories` timing and bandwidth fields | Characterization with provenance in helia-platforms |
| Burst-split code, Vela `system_config` writer, `fvp_memory_mode` | helia-npu |
| Energy coefficients, timing overrides, `memory_placement` | helia-estimator |

## Open points

| Point | Status |
| --- | --- |
| `at110` vs `atomiq110` naming across `RETIRED_PLATFORMS`, codegen map, and `load_soc("atomiq110")` | Which spelling is canonical in platform YAML not read in this pass |
| heliaAOT pin `d2c26db0` vs heliaAOT `origin/main` `ea5cd6c0` | Platform-model differences between the two not read in this pass |
| `pyproject.toml` also declares `helia-aot>=0.17.1,<0.18` alongside the git override | See Citation checks; how the two interact not read in this pass |

## Citation checks

Run on 2026-10-04 against `origin/main` `5991d9f1`.

| Citation given | Result | Detail |
| --- | --- | --- |
| `pipeline/vela.py:52` | Match | `mode = platform.soc.resolve_mode(config.platform_mode).name` |
| `pipeline/vela.py:65` | Match | `occupancy = platform.soc.occupants(placement)` |
| `pipeline/vela.py:86` | Match | `if platform.soc.npu == NpuFamily.ETHOS_U85 and _fvp_enabled(config):` |
| `pipeline/vela.py:104-106` | Match | `if target.soc != platform.soc.id:` then `ConfigError` |
| `pipeline/vela.py:111` | Match | `platform.soc.name` in the log call |
| `platform.py:504` | Match | `resolved_memory = platform.soc.resolve_memory(str(memory_name))` |
| `pipeline/case.py:60` | Match | `fvp_memory_mode = platform.definition.soc.fvp_memory_mode(placement) if placement else memory_mode` |
| `cli/platform_cmd.py:40` | Match | `resolve_mode(mode or sorted(platform.soc.modes)[0]).name` |
| `npu_reference.py` 116.749 pJ/cycle | Match | `("ethos-u85", 256)` at 25, `pj_per_cycle=116.749` at 28 |
| `requires-python`, Vela, heliaAOT pin | Match | `pyproject.toml:7` `==3.12.*`; `:14` `ethos-u-vela>=5.2.0`; `:92` rev `d2c26db0a0ab71738832d40e201a06a767193d0b`. Also `:39` `helia-aot>=0.17.1,<0.18` |
| `runtime/helia_aot_codegen.py` map | Match | `ap510` at 49, `apollo510_eb` at 51, `startswith("at110")` to `at110` at 56-57 |
