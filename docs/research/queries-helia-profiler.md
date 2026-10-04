# helia-profiler: question surface

- **Source:** `/Users/adam.page/Ambiq/helia/helia-profiler` (GitHub `AmbiqAI/helia-profiler`)
- **Revision:** `origin/main` `b195e29f`
- **Read on:** 2026-10-04
- **Method:** query-surface read by a gatherer against `origin/main` (`b195e29f`). Spot checks at the end were run with `git show origin/main:<path> | sed -n 'N,Mp'`.

This note records what helia-profiler (`hpx`) code asks of a platform today. It complements [helia-profiler.md](helia-profiler.md). Caller line numbers were not given by the gatherer for most rows; those rows name the file only. The "fact or tool policy" column is the gatherer's classification.

## Public surface

All under `src/helia_profiler/platform/`.

| Module | Symbols | What it exposes |
| --- | --- | --- |
| `memory_map.py` | `LinkFamily` (`GNU`, `ARMLINK`), `LinkedRegionWindow`, `linked_memory_map(soc, linker_profile="default")`, `classify_address(address, windows) -> MemoryRegion \| None`, `link_family_for_toolchain(toolchain)`, `_MAPS` | Linked memory windows per SoC with an `app_window` per `LinkFamily`. `_MAPS` is keyed by SoC name (`apollo3p`, `apollo4p`, `apollo510`, `apollo330P`, `atomiq110`, and others). Each row carries a provenance comment citing `nsx-core/src/<soc>/<toolchain>/<script>:<line>` |
| `placement.py` | `Placement` (`TCM`, `SRAM`, `MRAM`, `PSRAM`), `ArenaRole` (`SCRATCH`, `PERSISTENT`, `CONSTANT`), `MemoryRegion` (`DTCM`, `ITCM`, `SRAM`, `MRAM`, `PSRAM`), slack constants | TCM slack 128 KB, SRAM slack 32 KB |
| `capabilities.py` | `SocCapabilities` | `reset` (`default_power_reset_strategy`, `supports_swpoi`); `transport` (`requires_attached_probe_for_cycles`, `has_usb`, `swo_trace_clock_mhz`, `swo_core_clocked`); `memory` (`has_dcache`, `has_shared_ssram_power_domain`, `placement_bases: Mapping[Placement, int]`, `app_flash_load_addr`); `clock` (`direct_burst_base_mhz`, `clean_window_timer`, `gate_debug_domain_in_window`, `broad_peripheral_shutdown`, `crypto_otp_shutdown`); properties `power_window_timer`, `clean_window_needs_probe_attach` |
| `soc.py` | `SocFamily` (`AP3`, `AP4`, `AP5`), `CoreArch`, `PmuTier` (`DWT_ONLY`, `ARMV8M_PMU`), `MemoryLayout` (`mram_kb`, `sram_kb`, `dtcm_kb`, `itcm_kb`, `psram_kb`, `nvm_kb`), `ClockDomain`, `ClockSpeed`, `PerfTier`, `SocDef` | `SocDef` fields: `name`, `family`, `core`, `pmu_tier`, `has_mve`, `memory`, `clocks`, `c_define`, `cmsis_header`, `rtt_scan_ranges`, `jlink_device`, `pmu_max_ops=2048`, `swo_trace_clock_mhz`, `has_usb=True`, `ssram_full_power_enum`, `has_radio_subsystem`, `npu`, `app_flash_load_addr`, `memory_bases_like`, `origin` (`SocOrigin`), `registered_name`; property `is_builtin` |
| `board.py` | `BoardDef` | `name`, `soc`, `channel`, `psram_kb`, `default_sync_gpio_pin` / `default_state_gpio_pin` / `default_go_gpio_pin` (defaults 10/0/0), `starter_profile_board`, `is_fpga`, `description`, `ble_reset_gpio_pin` |
| `registry.py` | `PlatformRegistry`, `build_platform_registry`, `get_soc`, `get_board`, `get_soc_for_board` (applies `psram_kb`), `list_boards`, `list_socs` | Lookup |
| `custom.py` | `CustomSocField`, `CustomMemoryField`, `CustomBoardField`, `build_custom_platform_registry(target)`, `_reject_unknown_keys` | Custom definitions with close-match hints; `based_on` chain; `app_flash_load_addr` resolves explicit, then inherited, then `None` |

Built-in SoCs (9): `apollo3p`, `apollo4p`, `apollo4l`, `apollo510`, `apollo510b`, `apollo5b`, `apollo330P`, `apollo510L`, `atomiq110`.

Example provenance comment in `memory_map.py`: `apollo4p/gcc/linker_script.ld:10-12`, `apollo4p/armclang/linker_script.sct:8-34`; MRAM is 1952 KB from `0x18000`, not the 2000 KB figure in `MemoryLayout` (source: the comment itself, see Citation checks).

## Question table

| Question in plain words | API used today | Caller file:line | What it does with the answer | Fact or tool policy |
| --- | --- | --- | --- | --- |
| Which SoC is this board? | `get_board(name).soc` | `session.py` `boards()`, `fixture_target.py`, `stages/plan_memory.py`, CLI inspect | Lookup | Fact |
| What are the SoC core, PMU, memory sizes, clocks? | `get_soc_for_board` | `fixture_target.py`, `engines/helia_aot/compile.py`, `stages/plan_memory.py` | Capacities and tiers | Fact |
| What CPU clock speeds exist and which is default? | `soc.cpu_clock.speed(name)`, `.default` | `fixture_target.fixture_cpu_hz`, `compile.py`, `session.py` reset, config | Validation, firmware render, cycle-to-time | Fact; default tier is policy |
| Which regions exist and how large? | `soc.memory` or `linked_memory_map(soc)` | `plan_memory.py`, `fixture_metrics.py` | Fit checks, `MemoryPlan` | Fact |
| What linker regions apply per toolchain? | `linked_memory_map(soc, "default")` `app_window[LinkFamily]` | `fixture_metrics.fixture_app_region`, `hostenv/memory_measurement.py` | ELF section accounting | Fact |
| Does address X fall in region Y? | `classify_address` | `hostenv/memory_measurement.py` | Load-image accounting | Fact |
| What is the J-Link device string? | `soc.jlink_device` | `session.py` `probes()` / `reset()`, `fixture_target.py`, `inspect_cmds.py`, `engines/cmsis_nn.py` | Probe match, reset, attach | Fact |
| Full PMU or DWT only? | `soc.pmu_tier` | `stages/validate.py`, counter groups | Counter group validation | Fact |
| Does the SoC have MVE? | `soc.has_mve` | Config and counter validation | Rejects the `mve` group | Fact |
| What is the app flash load address? | `soc.app_flash_load_addr` / `capabilities.memory.app_flash_load_addr` | `stages/flash.py`, `compile.py` | J-Link fallback address; the recipe wins if both are present | Fact |
| What are the placement base addresses? | `capabilities.memory.placement_bases[Placement]` | `compile.py`, firmware render | Section attributes, linker generation | Fact |
| Is PSRAM fitted on this board? | `board.psram_kb` | `plan_memory.py` | PSRAM window | Fact (board) |
| Where should RTT scan? | `soc.rtt_scan_ranges` | `transport/rtt.py` | RTT header scan | Policy over a fact |
| How should the target be reset before capture? | `capabilities.reset.default_power_reset_strategy`, `supports_swpoi` | `stages/reset.py`, `target/lifecycle.py` | Reset before capture | Policy |
| Is D-cache maintenance needed? | `capabilities.memory.has_dcache` | `transport/rtt.py` | Cache ops around RTT buffers | Fact |
| Is a probe needed for DWT cycles? | `capabilities.transport.requires_attached_probe_for_cycles` | Firmware templates | STIMER vs DWT | Policy over a fact |
| Is USB transport available? | `capabilities.transport.has_usb` | Transport selection | Rejects `usb_cdc` | Driver-support policy |
| What is the SWO trace clock? | `capabilities.transport.swo_trace_clock_mhz`, `swo_core_clocked` | Firmware TPIU config | Trace clock | Fact |
| Which timer for the clean window? | `capabilities.clock.clean_window_timer`, `power_window_timer` | Firmware render | DWT vs STIMER | Policy |
| Gate the debug domain in the window? | `capabilities.clock.gate_debug_domain_in_window` | Firmware | `am_hal_debug_disable` / `enable` | Policy |
| Is SSRAM on a shared power domain? | `capabilities.memory.has_shared_ssram_power_domain` | Firmware power config | Power enum | Fact |
| Which pin resets the BLE part? | `board.ble_reset_gpio_pin` | Power capture prep | Holds it low | Board wiring |
| Is this an FPGA carrier? | `board.is_fpga` | NPU init | Tolerates handshake failure | Fact (implementation kind) |
| Which starter profile board? | `board.starter_profile_board` | `firmware/project.py` | nsx profile derivation | Policy |
| Built-in or custom SoC? | `soc.is_builtin` | Validation | Whether per-SoC tables are available | Provenance |
| What core architecture? | `soc.core` | Probe match, counters | Gating | Fact |
| Does it have an NPU, and which? | `soc.npu` (string, for example `"ethos-u85-256"`) | Engine backend, counter groups, Vela accelerator config | Gating | Fact |
| Which HAL constants apply? | `soc.c_define`, `cmsis_header`, `ssram_full_power_enum`, `has_radio_subsystem` | Firmware includes | HAL tier, includes, enums | SDK fact |
| Which linker profile? | `linker_profile` argument | `memory_map.py` | Only `"default"` has rows | Fact |

### heliaAOT bridge

| Item | Detail |
| --- | --- |
| `_BOARD_TO_AOT_PLATFORM` | `engines/helia_aot/compile.py` about 80-89 (see Citation checks). `atomiq110_fpga_turbo` maps to `atomiq110`; `apollo5b_evb` and `apollo330mP_evb` map to `apollo510_evb`; others identity (see Citation checks) |
| `_resolve_aot_platform` order | `engine.config.platform_name` override, then the map, else `EngineError`; warns when names differ |
| What hpx passes to heliaAOT | Board name; placement intent (arena and weights `Placement`); rulesets mapping `Placement` to AOT memtype: `TCM` to `dtcm`, `SRAM` to `sram`, `MRAM` to `mram`, `PSRAM` to `psram`; alias `itcm` to `TCM` |
| Ethos-U backend | Downgrades TCM placements |
| After heliaAOT | `stages/plan_memory.py` `_apply_capacities` re-applies `soc.memory` |

## Overlay and custom-definition surface

| Surface | Detail |
| --- | --- |
| Config keys | `target.custom_boards`, `target.custom_socs` |
| Inheritance | `based_on` chain |
| Board fields documented | `channel`, GPIO pins, `jlink_device`, `rtt_scan_ranges`, `starter_profile_board` |
| Validation | Unknown keys rejected with did-you-mean; built-in collisions rejected; address literals decimal or `0x` hex |
| Docs | `astro-site/src/content/docs/guide/boards.mdx`, section "Add a custom board or SoC" |
| CLI | `hpx boards`; `hpx inspect board\|soc\|clock`; `hpx probes`. No CLI for memory windows |

## Name resolution

| Aspect | Behaviour |
| --- | --- |
| Board and SoC lookup | Case handling in `get_board` / `get_soc` not read in this pass |
| Starter profiles | `board.starter_profile_board` or `board.name`, exact case |
| nsx tier (`-r3` / `-r4` / `-r5`) | Derived from `soc.family` |
| heliaAOT name | `_BOARD_TO_AOT_PLATFORM` map plus `engine.config.platform_name` override |
| Test fixture | `fixture_target.py`: `FIXTURE_BOARD` `apollo510_evb`, `FIXTURE_CLOCK_PROFILE` `lp` |

## Workarounds for missing model facts

| Workaround | Where | Missing fact it stands in for |
| --- | --- | --- |
| Board-to-heliaAOT name map, with several boards proxied to `apollo510_evb` | `engines/helia_aot/compile.py` | Shared SoC identity between hpx and heliaAOT |
| `_apply_capacities` re-applies `soc.memory` after heliaAOT | `stages/plan_memory.py` | heliaAOT sizes not matching the profiler's per-SoC sizes |
| Linker windows copied into `_MAPS` with provenance comments | `platform/memory_map.py` | Linker-window facts from the SDK |
| `MemoryLayout` datasheet figure differs from the linked window (example: apollo4p MRAM 1952 KB linked vs 2000 KB in `MemoryLayout`) | `platform/memory_map.py` comment | Distinction between die capacity and linker window |
| Ethos-U backend downgrades TCM placements | heliaAOT engine path | NPU-reachable memory per region |

## Open points

| Point | Status |
| --- | --- |
| No test asserts that `memory_map` constants still match the SDK scripts | Gatherer finding. `tests/test_memory_map.py` has tests named `test_apollo510_windows_are_the_linker_script_values` and `test_atomiq110_windows_are_the_nbl_linker_script_values`; whether they read the SDK scripts or pin literals was not read in this pass |
| Caller line numbers for the question table | Not read in this pass |
| Case sensitivity of `get_board` / `get_soc` | Not read in this pass |
| Boards mapped to `apollo510_evb` that are not apollo510 parts | `apollo330mP_evb` and `apollo510dL_evb`; whether heliaAOT's own `apollo330mp_evb` entry should be used instead not read in this pass |

## Citation checks

Run on 2026-10-04 against `origin/main` `b195e29f`.

| Citation given | Result | Detail |
| --- | --- | --- |
| `engines/helia_aot/compile.py` about 80-89 for `_BOARD_TO_AOT_PLATFORM` | Partial | The dict opens at 69 and closes at 82; 84-92 is `_EXPECTED_PRAGMA_SUFFIXES`. `atomiq110_fpga_turbo` at 78, `apollo5b_evb` at 79, `apollo330mP_evb` at 80 match the stated targets |
| "others identity" in the same map | Partial | `apollo510b_evb` (77) and `apollo510dL_evb` (81) also map to `apollo510_evb`, not to themselves; 69-76 not read line by line |
| `_resolve_aot_platform` order | Match | Defined at 102; override, then `_BOARD_TO_AOT_PLATFORM.get(board)` at 116, else `EngineError` at 120 |
| `fixture_target.py` `FIXTURE_BOARD`, `FIXTURE_CLOCK_PROFILE` | Match | `FIXTURE_BOARD = "apollo510_evb"` at 10; `FIXTURE_CLOCK_PROFILE = "lp"` at 12 |
| `memory_map.py` apollo4p provenance comment | Match | Lines 245-248 cite `apollo4p/gcc/linker_script.ld:10-12` and `apollo4p/armclang/linker_script.sct:8-34`, and state MRAM is 1952 KB from `0x18000`, not the 2000 KB figure in `MemoryLayout` |
| `placement.py` slack constants | Match | `TCM_PLACEMENT_SLACK_BYTES = 128 * 1024` at 19; `SRAM_PLACEMENT_SLACK_BYTES = 32 * 1024` at 20 |
