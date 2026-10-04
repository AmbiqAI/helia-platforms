# helia-profiler platform model: source inventory

> Superseded by [queries-helia-profiler.md](queries-helia-profiler.md) where the two conflict.

- **Source:** helia-profiler checkout (GitHub `AmbiqAI/helia-profiler`)
- **Revision:** `origin/main` at `b195e29f` (2026-10-03, "feat(runtimes): prepare the heliaRT runtime archive from its record (#453)"), read with `git show origin/main:<path>`
- **Read on:** 2026-10-04
- **Method:** Every file below was read from the `origin/main b195e29f` blob, not the working tree; citations are to that revision unless marked otherwise.

> **Stale working tree.** The local checkout is on feature branch `feat/psram-clock-diagnostics` at `ec23bac1`, which is **639 commits behind `origin/main`** and has no commits that `origin/main` lacks (`git rev-list --count` on 2026-10-04). Do not read the working tree for this inventory. All line numbers below are for `origin/main b195e29f`.

## What it is

helia-profiler (`hpx`) builds, flashes, and profiles models on Ambiq EVBs (PMU and DWT counters, memory placement, power capture). Its `platform/` package is the most detailed SoC/board model of the sources inventoried: a SoC/Board split, typed capabilities, a verified linked-memory map, and a user overlay for custom parts. Closed issue #229 named `platform/` as a future shared-package extraction seam.

### Package `src/helia_profiler/platform/` (origin/main b195e29f)

| File | Lines | Role |
| --- | --- | --- |
| `__init__.py` | 108 | Public surface |
| `soc.py` | 779 | `SocDef`, `MemoryLayout`, `ClockDomain`, enums, 9 SoC registrations |
| `board.py` | 205 | `BoardDef`, 13 board registrations, default GPIO pins |
| `registry.py` | 144 | `PlatformRegistry`, `get_soc`, `get_board`, `get_soc_for_board`, `list_*`, default-pin getters |
| `custom.py` | 627 | `target.custom_socs` / `target.custom_boards` overlay |
| `capabilities.py` | 457 | Typed capability records, reset strategy, placement bases, app-flash load address tables |
| `memory_map.py` | 454 | Verified linked-memory windows per SoC and link family |
| `placement.py` | 86 | `Placement`, `MemoryRegion` |
| `counters.py` | 270 | PMU counter definitions |

## Platform model (types, fields, data files)

All platform data is Python literals. There are no platform data files.

### `SocDef` (`soc.py:135-226`)

Classification is this note's reading for review: "fact" means a hardware, HAL, SDK, or tool fact the profiler records; "policy" means a profiler choice.

| Field | Type / default | Class | Note (source) |
| --- | --- | --- | --- |
| `name` | `str` | identity | `soc.py:139` |
| `family` | `SocFamily` (`AP3`, `AP4`, `AP5`) | policy (grouping) | `soc.py:24-27`; `atomiq110` is tagged `AP5` as "same tier" |
| `core` | `CoreArch` (`cortex-m4`, `cortex-m55`) | fact | `soc.py:30-32` |
| `pmu_tier` | `PmuTier` (`dwt`, `pmu`) | fact | `soc.py:35-37` |
| `has_mve` | `bool` | fact | `soc.py:143` |
| `memory` | `MemoryLayout`: `mram_kb`, `sram_kb`, `dtcm_kb`, `itcm_kb`, `psram_kb`, `nvm_kb` (all `int = 0`) | fact | `soc.py:73-82` |
| `clocks` | `tuple[ClockDomain, ...]`; `ClockDomain(name, speeds: tuple[ClockSpeed], default)`; `ClockSpeed(name, mhz, perf_tier)` | fact (speeds) plus policy (`lp`/`hp` naming, default) | `soc.py:108-133` |
| `c_define` | `str` | fact (SDK) | `soc.py:146` |
| `cmsis_header` | `str` | fact (SDK) | `soc.py:147` |
| `rtt_scan_ranges` | `tuple[tuple[int, int], ...]` | policy | `soc.py:148` |
| `jlink_device` | `str = ""` | fact (tool) | `soc.py:149` |
| `pmu_max_ops` | `int = 2048` | policy | `soc.py:150` |
| `swo_trace_clock_mhz` | `int \| None = None` | fact | `soc.py:157`; `None` means SWO is core-clocked |
| `has_usb` | `bool = True` | fact (SDK module support) | `soc.py:162`; gates the `usb_cdc` transport |
| `ssram_full_power_enum` | `str = "AM_HAL_PWRCTRL_SRAM_3M"` | fact (HAL) | `soc.py:174` |
| `has_radio_subsystem` | `bool = False` | fact (HAL) | `soc.py:183`; whether `am_hal_pwrctrl_rss_pwroff()` exists |
| `npu` | `str \| None = None` | fact | `soc.py:189`; Vela `--accelerator-config` spelling |
| `app_flash_load_addr` | `int \| None = None` | fact (linker/bootloader) | `soc.py:205`; built-ins leave it `None` and resolve via `capabilities.resolve_app_flash_load_addr` |
| `memory_bases_like` | `str \| None = None` | policy (internal) | `soc.py:215`; set only for `based_on` custom parts |
| `origin` | `SocOrigin = CUSTOM` | bookkeeping | `soc.py:219`; set to `BUILTIN` by `_register_soc` |
| `registered_name` | `str \| None = None` | bookkeeping | `soc.py:225` |

| Derived property | Class | Source |
| --- | --- | --- |
| `capabilities` | policy | `soc.py:269` (calls `build_soc_capabilities`) |
| `has_full_pmu` | policy | `soc.py:281` |
| `requires_attached_probe_for_cycles` | policy | `soc.py:285` |
| `profiling_backends` | policy | `soc.py:302` |
| `profiling_domains` | policy | `soc.py:315` |
| `is_builtin`, `clock_domain()`, `cpu_clock` | helpers | `soc.py:228`, `:256`, `:261` |

### `BoardDef` (`board.py:15-38`)

| Field | Type / default | Source |
| --- | --- | --- |
| `name` | `str` | `board.py:18` |
| `soc` | `str` (matches `SocDef.name`) | `board.py:19` |
| `channel` | `str` (`stable` or `preview`) | `board.py:20` |
| `psram_kb` | `int \| None = None` (None inherits SoC) | `board.py:21` |
| `default_sync_gpio_pin` | `int = DEFAULT_SYNC_GPIO_PIN` (10) | `board.py:22`, `:7` |
| `default_state_gpio_pin` | `int = DEFAULT_STATE_GPIO_PIN` (0) | `board.py:23`, `:10` |
| `default_go_gpio_pin` | `int = DEFAULT_GO_GPIO_PIN` (0) | `board.py:24`, `:11` |
| `starter_profile_board` | `str \| None = None` | `board.py:25`; not set by any built-in board |
| `is_fpga` | `bool = False` | `board.py:28` |
| `description` | `str = ""` | `board.py:29` |
| `ble_reset_gpio_pin` | `int \| None = None` | `board.py:38` |

### `memory_map.py`

| Element | Shape | Source |
| --- | --- | --- |
| `LinkFamily` | `StrEnum`, two values: `gnu` (GNU ld / LLD with gcc `*.ld`, used by gcc and ATfE), `armlink` (armclang `*.sct`). No Zephyr value | `memory_map.py:79-85` |
| `link_family_for_toolchain` | `arm-none-eabi-gcc`, `gcc`, `atfe` to `gnu`; `armclang` to `armlink`; unknown raises `ValueError` | `memory_map.py:93-108` |
| `LinkedRegionWindow` | `region: MemoryRegion`; `window: MemoryRange` (classification aperture); `app_window: Mapping[LinkFamily, MemoryRange]`; `window_provenance` (`hardware-aperture` \| `linker-app-origin` \| `board-knowledge`); `app_provenance` (`linker-script` \| `board-knowledge`); `section_attributable: bool` | `memory_map.py:111-176` |
| `_MAPS` | Keyed by **SoC name only** (9 keys) to 5 window tuples: `_APOLLO3P` (3 rows), `_APOLLO4` (3), `_APOLLO5_FULL` (4), `_APOLLO330P` (3), `_ATOMIQ110` (4). 17 rows in total. `apollo510`, `apollo510b`, `apollo5b` share `_APOLLO5_FULL`; `apollo510L` shares `_APOLLO330P` (code comment: byte-identical linker scripts) | `memory_map.py:222-394` |
| Linker profile | Function argument, not a table key. `linked_memory_map(soc, linker_profile="default")` returns empty for any profile other than `default` and for any non-builtin SoC | `memory_map.py:397-443` |
| PSRAM | Appended at lookup time from `soc.memory.psram_kb` and the capabilities placement base, with `board-knowledge` provenance and `section_attributable=False` | `memory_map.py:428-442` |
| `classify_address(address, windows)` | Returns the `MemoryRegion` whose window contains the address, else `None` | `memory_map.py:446-454` |
| Provenance of the numbers | Module docstring: read from the NSX linker scripts of the default profile (`sbl` on Apollo parts, `nbl` on atomiq110), with RAM windows from the SDK's `am_reg_base_addresses.h`; citations in the form `<soc>/<toolchain>/<script>:<line>` inside `nsx-core/src` | `memory_map.py:1-63` |

### `custom.py` (user overlay)

| Item | Behaviour | Source |
| --- | --- | --- |
| Config keys | `target.custom_socs.<name>` and `target.custom_boards.<name>` | `custom.py:1-15` |
| Inheritance | `based_on` names a registered or earlier custom part; its facts and resolved app-flash address are inherited | `custom.py:69`, `:104`, `:138-139`, `:203-241` |
| SoC keys | `based_on`, `family`, `core`, `pmu_tier`, `has_mve`, `memory`, `clocks`, `c_define`, `cmsis_header`, `rtt_scan_ranges`, `jlink_device`, `pmu_max_ops`, `app_flash_load_addr`, `description` | `CustomSocField`, `custom.py:59-83` |
| Memory keys | `mram_kb`, `sram_kb`, `dtcm_kb`, `itcm_kb`, `psram_kb`, `nvm_kb` | `CustomMemoryField`, `custom.py:85-99` |
| Board keys | `based_on`, `soc`, `channel`, `psram_kb`, `default_sync_gpio_pin`, `default_state_gpio_pin`, `default_go_gpio_pin`, `ble_reset_gpio_pin`, `starter_profile_board`, `is_fpga`, `description` | `CustomBoardField`, `custom.py:101-115` |
| SoC `description` | Accepted but read by nothing; kept so SoC and board blocks accept the same annotation (`custom.py:62-66`) |
| Not user-writable on SoCs | `swo_trace_clock_mhz`, `has_usb`, `ssram_full_power_enum`, `has_radio_subsystem`, `npu` | absent from `CustomSocField` |
| Unknown keys | Rejected with `ConfigError` (with close-match suggestions via `difflib`) | `_reject_unknown_keys`, `custom.py:404-443` |
| Contract | Key enums pinned to the dataclass fields by tests in `tests/test_platform.py` | `custom.py:7-14` |

## Registered entries (table)

### SoCs (9; `_register_soc` calls in `soc.py`)

All have one clock domain named `cpu`. Values are the profiler's literals at `b195e29f`, not verified silicon figures.

| SoC | Line | Family | Core | PMU | MVE | MRAM / SRAM / DTCM / ITCM / PSRAM / NVM (KB) | CPU clocks (MHz, default first) | `c_define` | `jlink_device` | `npu` | `pmu_max_ops` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `apollo3p` | 347 | AP3 | M4 | dwt | no | 2000 / 700 / 64 / 0 / 0 / 0 | lp 48, hp 96 | `AM_PART_APOLLO3P` | `AMA3B2KK-KBR` | - | 2048 |
| `apollo4p` | 398 | AP4 | M4 | dwt | no | 2000 / 1024 / 384 / 0 / 0 / 0 | lp 96, hp 192 | `AM_PART_APOLLO4P` | `AMAP42KP-KBR` | - | 2048 |
| `apollo4l` | 423 | AP4 | M4 | dwt | no | 2000 / 1024 / 384 / 0 / 0 / 0 | lp 96, hp 192 | `AM_PART_APOLLO4L` | `AMAP42KL-KBR` | - | 2048 |
| `apollo510` | 448 | AP5 | M55 | pmu | yes | 4096 / 3072 / 512 / 256 / 65536 / 8192 | lp 96, hp 250 | `AM_PART_APOLLO510` | `AP510NFA-CBR` | - | 4096 |
| `apollo510b` | 489 | AP5 | M55 | pmu | yes | 4096 / 3072 / 512 / 256 / 65536 / 0 | lp 96, hp 250 | `AM_PART_APOLLO510B` | `AP510BFA-CBR` | - | 4096 |
| `apollo5b` | 525 | AP5 | M55 | pmu | yes | 4096 / 3072 / 512 / 256 / 32768 / 0 | lp 96, hp 250 | `AM_PART_APOLLO5B` | `AP510NFA-CBR` | - | 4096 |
| `apollo330P` | 558 | AP5 | M55 | pmu | yes | 1984 / 1792 / 240 / 0 / 32768 / 0 | lp 96, hp 250 | `AM_PART_APOLLO330P` | `Apollo330P_510L` | - | 512 |
| `apollo510L` | 641 | AP5 | M55 | pmu | yes | 1984 / 1792 / 240 / 0 / 32768 / 0 | lp 96, hp 250 | `AM_PART_APOLLO510L` | `AP510L` | - | 512 |
| `atomiq110` | 692 | AP5 | M55 | pmu | yes | 4096 / 3072 / 496 / 256 / 0 / 0 | lp 25 only | `PART_atomiq110` | `Atomiq110` | `ethos-u85-256` | 4096 |

| SoC | Other non-default fields |
| --- | --- |
| `apollo3p` | `swo_trace_clock_mhz=48`, `has_usb=False`, `cmsis_header="apollo3p.h"` |
| `apollo510`, `apollo510b`, `apollo5b` | `cmsis_header="apollo510.h"` (all three) |
| `apollo330P` | `ssram_full_power_enum="AM_HAL_PWRCTRL_SRAM_1P75M"`, `swo_trace_clock_mhz=48`, `has_radio_subsystem=True`; code comment: `Apollo330P_510L` is a custom Ambiq J-Link device entry, not in JLinkExe's stock database (`soc.py:604-612`) |
| `apollo510L` | Same three as `apollo330P`; `cmsis_header="apollo510L.h"` |
| `atomiq110` | `has_usb=False` |

### Boards (13; `_register_board` calls in `board.py`)

| Board | Line | SoC | Channel | `psram_kb` | Sync / state / go pins | `ble_reset_gpio_pin` | `is_fpga` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `apollo3p_evb` | 63 | apollo3p | stable | 8192 | 26 / 24 / 25 | - | no |
| `apollo3p_evb_cygnus` | 74 | apollo3p | preview | 8192 | 26 / 24 / 25 | - | no |
| `apollo4p_evb` | 89 | apollo4p | preview | 32768 | 22 / 23 / 24 | - | no |
| `apollo4l_evb` | 100 | apollo4l | preview | 32768 | 61 / 23 / 24 | - | no |
| `apollo4l_blue_evb` | 111 | apollo4l | preview | 32768 | 61 / 23 / 24 | 55 | no |
| `apollo4p_blue_kbr_evb` | 124 | apollo4p | preview | 32768 | 22 / 23 / 24 | 42 | no |
| `apollo4p_blue_kxr_evb` | 137 | apollo4p | preview | 32768 | 22 / 23 / 24 | 55 | no |
| `apollo510_evb` | 151 | apollo510 | stable | inherit | 29 / 36 / 14 | - | no |
| `apollo510b_evb` | 161 | apollo510b | preview | inherit | 29 / 36 / 14 | - | no |
| `apollo5b_evb` | 170 | apollo5b | preview | inherit | defaults | - | no |
| `apollo330mP_evb` | 172 | apollo330P | preview | inherit | defaults | - | no |
| `apollo510dL_evb` | 181 | apollo510L | preview | 0 (comment: rev 2 EVB has no PSRAM fitted) | defaults | - | no |
| `atomiq110_fpga_turbo` | 198 | atomiq110 | preview | inherit | defaults (comment: fallback defaults, no board-specific wiring) | - | yes (description: fixed 25 MHz, FPGA-only) |

## Consumers / name resolution

### Lookup

| Function | Behaviour | Source |
| --- | --- | --- |
| `get_soc(name)` | Exact, case-sensitive dict lookup; `ValueError` listing known SoCs | `registry.py:66-72` |
| `get_board(name)` | Exact, case-sensitive dict lookup; `ValueError` listing known boards | `registry.py:75-80` |
| `get_soc_for_board(board)` | Board to SoC | `registry.py:83` |
| `build_custom_platform_registry(target)` | Builtins, then custom SoCs, then custom boards | `custom.py:117-123` |

### heliaAOT bridge

`_BOARD_TO_AOT_PLATFORM`, `src/helia_profiler/engines/helia_aot/compile.py:69-82` (origin/main b195e29f):

| Profiler board | heliaAOT platform | Inline comment |
| --- | --- | --- |
| `apollo3p_evb` | `apollo3p_evb` | |
| `apollo4p_evb` | `apollo4p_evb` | |
| `apollo4p_blue_kbr_evb` | `apollo4p_blue_kbr_evb` | |
| `apollo4p_blue_kxr_evb` | `apollo4p_blue_kxr_evb` | |
| `apollo4l_evb` | `apollo4l_evb` | |
| `apollo4l_blue_evb` | `apollo4l_blue_evb` | |
| `apollo510_evb` | `apollo510_evb` | |
| `apollo510b_evb` | `apollo510_evb` | same SoC family / memory layout |
| `atomiq110_fpga_turbo` | `atomiq110` | Atomiq110 FPGA (M55 + Ethos-U85-256) |
| `apollo5b_evb` | `apollo510_evb` | |
| `apollo330mP_evb` | `apollo510_evb` | Cortex-M55, AP5 family |
| `apollo510dL_evb` | `apollo510_evb` | Cortex-M55, AP5 family (as apollo330mP_evb) |

| Path | Resolution | Source |
| --- | --- | --- |
| Profile build (`_resolve_aot_platform`) | 1. `engine.config.platform_name` override; 2. `_BOARD_TO_AOT_PLATFORM`; 3. `EngineError` with the known list | `compile.py:102-125` |
| `hpx analyze` | Passes the board name straight through as `platform={"name": board}` to `ConvertArgs`; does not consult `_BOARD_TO_AOT_PLATFORM` | `evaluation/engine_analysis.py:72` |
| Board absent from the map | `apollo3p_evb_cygnus` | compare with board table |

### Import surface (origin/main b195e29f)

| Measure | Count | Note |
| --- | --- | --- |
| Stale branch, as previously reported | 14 source, 10 test files | Not re-checked; method unknown |
| `git grep -l 'helia_profiler.platform' origin/main -- src tests` | 26 files: 5 under `src` (4 inside `platform/` itself, plus `placement.py`), 21 under `tests` | Literal dotted-name match only |
| `src` files outside `platform/` importing it by absolute or relative import (`from ..platform`, `from ...platform`) | 24 | Better measure of source coupling |

`src` importers outside `platform/` (24): `__init__.py`, `cli/inspect_cmds.py`, `config/__init__.py`, `config/power.py`, `console/presentation.py`, `engines/cmsis_nn.py`, `engines/helia_aot/compile.py`, `engines/helia_rt/artifacts.py`, `firmware/context.py`, `firmware/project.py`, `fixture_image.py`, `fixture_metrics.py`, `fixture_target.py`, `hostenv/memory_measurement.py`, `pipeline.py`, `placement.py`, `runtime_records.py`, `session.py`, `stages/plan_memory.py`, `stages/preflight.py`, `stages/resolve_platform.py`, `stages/verify_placement.py`, `target/probe/jlink.py`, `validation/matrix.py`.

Test importers (21): `tests/contracts/test_board_resolution.py`, `test_firmware_render_snapshots.py`, `test_power_lockstep.py`, `test_render_compile.py`, `test_window_matrix.py`; `tests/test_aot_placement_rulesets.py`, `test_build_firmware_stage.py`, `test_counters.py`, `test_docs_pmu_catalog.py`, `test_flash_stage.py`, `test_jlink.py`, `test_memory_map.py`, `test_memory_measurement.py`, `test_pipeline.py`, `test_platform.py`, `test_power.py`, `test_probe_cli.py`, `test_runtime_records.py`, `test_session.py`, `test_verify_placement.py`; `tests/unit/test_fixture_capture.py`.

## Facts it carries that the others do not

| Fact | Where |
| --- | --- |
| Explicit SoC/Board split with release channel per board | `soc.py`, `board.py` |
| Named clock points (`lp`/`hp`) with a default and perf tier | `soc.py:108-133` |
| PMU tier, `pmu_max_ops`, profiling backends and domains | `soc.py` |
| CMSIS header, `AM_PART_*` define, J-Link device per SoC (including custom device strings for apollo330P/apollo510L) | `soc.py` |
| SWO trace clock, USB support, radio-subsystem power-off, SSRAM full-power HAL enum | `soc.py:150-183` |
| `nvm_kb` (apollo510 only) | `soc.py` |
| Per-board PSRAM fit and power-capture GPIO pins (sync, state, go) and BLE reset pin | `board.py` |
| Reset strategy per family (`debug_reset+swpoi_reset` on AP5, `debug_reset` otherwise), transport, memory, clock capability records | `capabilities.py:26-53`, `:419-453` |
| Placement-base and app-flash load-address tables per family and per SoC | `capabilities.py:271-372` |
| Linked-memory windows per SoC and link family with provenance strings | `memory_map.py` |
| User overlay for novel parts with strict key validation | `custom.py` |
| Power: GPIO wiring is in `board.py` (pin fields and defaults); `capabilities.py` docstring lists power-capture pins among its concerns and holds the reset strategy | `board.py:7-38`, `capabilities.py:1-11` |
| No performance, power, or energy tables keyed by SoC or board | n/a |

## Tooling to mirror

From `origin/main b195e29f`.

| Area | Setting | Source |
| --- | --- | --- |
| Python | `requires-python = ">=3.11"` | `pyproject.toml:6` |
| Lint | `[tool.ruff]` `line-length = 100`, `target-version = "py311"`; `[tool.ruff.lint]` `select = ["E4", "E7", "E9", "F", "I"]`, `ignore = ["E741"]`; per-file `"**/__init__.py" = ["F401"]` | `pyproject.toml:119-142` |
| Format | `[tool.ruff.format]` `quote-style = "double"`, `indent-style = "space"`, `skip-magic-trailing-comma = false`, `line-ending = "auto"` | `pyproject.toml:135-139` |
| Types | `ty==0.0.74` pinned in the `lint` dependency group; CI runs `uv run --no-sync ty check src/helia_profiler tests` | `pyproject.toml:66-71`, `.github/workflows/ci.yml:57` |
| Tests | `testpaths = ["tests", "tools/tests"]`, `addopts = "-m 'not hardware and not compile_hw'"`, `strict_markers = true` | `pyproject.toml:110-117` |
| pre-commit | pre-commit-hooks v5.0.0; ruff-pre-commit v0.11.13 (`ruff-check`, `ruff-format`); local `todo-needs-issue` (`tools/hooks/todo_needs_issue.py`); local `strip-ai-trailers` (`prepare-commit-msg`) | `.pre-commit-config.yaml` |
| CI | `ci.yml` jobs `typecheck`, `unit-tests` (3 OS x Python 3.11, 3.12, 3.13, 3.14), `analysis-tests`, `pre-commit`, `package`, gate `lint-and-test` | `.github/workflows/ci.yml:19-250` |
| Other workflows | `docs.yml`, `hardware-validation.yml`, `publish.yml` (release-please-action v4) | `.github/workflows/` |
| Release | `release-please-config.json`: `release-type: python`, `include-v-in-tag: true`, `extra-files: ["src/helia_profiler/_version.py", "uv.lock"]`; `.release-please-manifest.json` | repo root |
| Docs | Astro site (`astro-site/`); guides include `boards.mdx`, `configuration.mdx`, `memory.mdx`, `power.mdx`, `pmu-counters.mdx` | `astro-site/src/content/docs/guide/` |
| Ownership and records | No CODEOWNERS; no RFC or ADR series | `git ls-tree` |
| Project | heliaPROFILER (#37) | `gh` |

## Open questions

### History (via `gh` on 2026-10-04)

| Item | State | Date (UTC) | Title |
| --- | --- | --- | --- |
| PR #176 | MERGED | 2026-08-23 | #133 Phase 1: measured section inventory and verified linked-memory map |
| PR #177 | MERGED | 2026-08-23 | #133 Phase 2: measured `memory_regions` owns region truth |
| PR #179 | MERGED | 2026-08-23 | #133 Phase 3: symbol attribution, planned hpx consumers, reconciliation |
| PR #264 | MERGED | 2026-09-05 | Add the Apollo510 Lite (`apollo510L` SoC, `apollo510dL_evb` board) |
| PR #284 | MERGED | 2026-09-16 | atomiq110 Ethos-U85 NPU profiling via helia-rt and helia-aot |
| Issue #133 | CLOSED | | `memory_plan` only counts what HPX placed |
| Issue #229 | CLOSED | | Codebase hygiene and architecture cleanup, including extraction seams |

### Questions

| # | Question |
| --- | --- |
| 1 | The heliaAOT bridge maps `apollo510b_evb`, `apollo330mP_evb`, and `apollo510dL_evb` to heliaAOT `apollo510_evb`, although heliaAOT (`e537d293`) registers `apollo510b_evb`, `apollo330mp_evb`, and `apollo510l_evb`. Is the coarser mapping intended? |
| 2 | `hpx analyze` passes the profiler board name to heliaAOT unmapped (`engine_analysis.py:72`). Boards whose names differ from heliaAOT's (`apollo330mP_evb`, `apollo510dL_evb`, `atomiq110_fpga_turbo`, `apollo5b_evb`) would not resolve to a registered heliaAOT entry. Confirm intended behaviour. |
| 3 | `apollo3p_evb_cygnus` has no heliaAOT mapping. |
| 4 | Memory literals differ from heliaAOT for the same parts: profiler `mram_kb=2000` vs heliaAOT 2 MB (Apollo3P/4P/4L); profiler Apollo3P `sram_kb=700` vs heliaAOT 704 KB; profiler `apollo510` `psram_kb=65536` vs heliaAOT `32168 * 1024`. Which is authoritative, and against which source of record? |
| 5 | `psram_kb` lives on both `MemoryLayout` (SoC) and `BoardDef` (board override). The catalogue needs one owner per fact. |
| 6 | `capabilities._FAMILY_MEMORY_BASES` and `memory_map._MAPS` disagree by design (module docstring, `memory_map.py:15-21`); a contract test pins the divergence until callers migrate. Which one does the catalogue adopt? |

### Citation checks against the coordinator's facts (origin/main b195e29f)

| Fact given | Result |
| --- | --- |
| Package file list | Match (9 files; line counts tabled above). |
| `SocDef` fields including `app_flash_load_addr`, `npu` | Match. Three more fields exist: `memory_bases_like`, `origin`, `registered_name`. |
| `BoardDef` fields including `is_fpga` | Match. |
| 9 SoCs, 13 boards | Match. |
| `memory_map.py`: `LinkFamily` (gnu, armlink, zephyr?) | `gnu` and `armlink` only; no `zephyr`. |
| `memory_map.py`: `_MAPS` keys (board, linker profile, link family) | Mismatch. `_MAPS` is keyed by SoC name only. Linker profile is a function argument (only `default` supported); link family keys `app_window` inside each row. |
| `linked_memory_map`, `classify_address`, `link_family_for_toolchain` present | Match (397, 446, 101). |
| `_BOARD_TO_AOT_PLATFORM` | Match; full map at `compile.py:69-82` (12 entries). |
| `engine_analysis.py` around line 72 | Match; `platform={"name": board}` at line 72. |
| Power-capture GPIO wiring in `capabilities.py` | Partial. Pin values live in `board.py`; `capabilities.py` holds reset strategies and names power-capture pins in its docstring. |
| PR #264 merged 2026-09-04 | Mismatch. `gh` reports `mergedAt` 2026-09-05T17:07:39Z. |
| PR #284 merged 2026-09-08 | Mismatch. `gh` reports `mergedAt` 2026-09-16T17:16:32Z. |
| PRs #176, #177, #179 merged 2026-08-23 | Match. |
| Ruff `target py310`, ignore `E741, F401, F841, I001` | Mismatch. `target-version = "py311"`; `ignore = ["E741"]`; `F401` ignored only for `**/__init__.py`. |
| No pre-commit config | Mismatch. `.pre-commit-config.yaml` exists (contents tabled above). |
| No mypy/pyright/ty | Mismatch. ty `0.0.74` is pinned and run in CI. No mypy or pyright found. |
| pytest default `-m "not hardware"` | Mismatch. `-m 'not hardware and not compile_hw'`. |
| `ci.yml` 3 OS x 2 Python | Mismatch. 3 OS x 4 Python (3.11 to 3.14). |
| Docs via mkdocs-material with `boards.md`, `configuration.md`, `memory.md`, `power.md`, `pmu-counters.md` | Mismatch on format. Docs are an Astro site; the guides exist as `.mdx` under `astro-site/src/content/docs/guide/`. |
| `release-please-config.json` with `include-v-in-tag` and the two extra files | Match. |
