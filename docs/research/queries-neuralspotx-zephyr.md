# neuralspotx, nsx-ambiq-sdk, and Zephyr: question surface

- **Source:** neuralspotx checkout (GitHub `AmbiqAI/neuralspotx`); `nsx-ambiq-sdk` (GitHub `AmbiqAI/nsx-ambiq-sdk`, local checkout); helia-aot checkout for its nsx and Zephyr templates. No local Zephyr tree.
- **Revision:** neuralspotx `main` `6afb7d2`; nsx-ambiq-sdk `9d4463a`; heliaAOT `origin/main` `ea5cd6c0`.
- **Read on:** 2026-10-04
- **Method:** query-surface read by a gatherer against the revisions named. Spot checks at the end were run with `git -C <repo> show <rev>:<path> | sed -n 'N,Mp'`.

This note records what the neuralspotx build system and the Zephyr path ask of a platform today. It complements [neuralspotx-and-sdk.md](neuralspotx-and-sdk.md). Two first-pass readings conflicted with RFC 0001 and were resolved by a direct read recorded in the Citation checks table; the body states the verified reading.

Role on 2026-10-04: neuralspotx is a source of facts for helia-platforms, not a consumer. Its own questions (which SoC is this board, which toolchains build it, is module M compatible with SoC S) are answered by its `board.yaml` files and registry. Its runtime dependencies were not checked in this pass.

## Public surface

| Item | Location | What it exposes |
| --- | --- | --- |
| `load_board_descriptors`, `load_board` | `src/neuralspotx/board_descriptors.py:211-233` | Globs `boards/*/board.yaml`; descriptor `name` must match its directory |
| `nsx board list [--tier --registered-only --json]`, `nsx board show` | `src/neuralspotx/cli/_cmd_board.py:40-63` | Board listing and detail |
| Module compatibility | `module_discovery.py` | `compatibility.socs` matched as exact, case-sensitive strings |
| Toolchains | `board.yaml` | Per-board toolchain list |
| Starter profiles | `neuralspotx/metadata.py` `_derive_starter_profiles` | Derived from `registry.lock` `board_profiles` and `soc_families` plus `board.yaml`; keyed by exact board id; contain toolchain, channel, core modules, SoC overrides, and the `nsx-board-<board>` module |
| SoC facts | nsx-ambiq-sdk `cmake/socs/facts/` (11 files) | Per-SoC CMake facts, table below |
| Linker scripts | nsx-ambiq-sdk `modules/nsx-core/src/<soc>/<toolchain>/` | Linker profiles, table below |

### Board `debug.cmake` overrides (8 boards)

| Board | Override |
| --- | --- |
| `apollo330mP_evb` | SEGGER device `Apollo330P_510L` |
| `apollo4l_blue_evb` | `AMA4B2KL-KXR` |
| `apollo4l_evb` | `AMAP42KL-KBR` |
| `apollo4p_blue_kbr_evb` | `AMA4B2KP-KBR` |
| `apollo4p_blue_kxr_evb` | `AMA4B2KP-KXR` |
| `apollo4p_evb` | `AMAP42KP-KBR` |
| `apollo4p_evb_disp_shield_rev2` | `AMAP42KP-KBR` |
| `atomiq110_fpga_turbo` | Device `Atomiq110`, CPUFREQ 48000000, SWOFREQ 1920000 |

### SoC facts (`cmake/socs/facts/`, 11 files)

Columns as reported by the gatherer. "SEGGER CPUFREQ" is the value of `NSX_SEGGER_CPUFREQ` (see Citation checks for what the file says it means).

| SoC | Series | Core | MVE | PMU tier | SEGGER device | SEGGER CPUFREQ | PF address |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `apollo2` | apollo2 | m4 | FALSE | none | `AMA2B2KK-KBR` | 48000000 | `0x0000` |
| `apollo3` | apollo3 | m4 | FALSE | none | `AMA3B1KK-KBR` | 48000000 | `0xC000` |
| `apollo3p` | apollo3 | m4 | FALSE | none | `AMA3B2KK-KBR` | 48000000 | `0xC000` |
| `apollo4l` | apollo4 | m4 | FALSE | none | `AMAP42KL-KBR` | 96000000 | `0x18000` |
| `apollo4p` | apollo4 | m4 | FALSE | none | `AMAP42KP-KBR` | 96000000 | `0x18000` |
| `apollo330P` | apollo330 | m55 | TRUE | armv8m | `AP330MPA-CBR` | 48000000 | `0x00410000` |
| `apollo510` | apollo5 | m55 | TRUE | armv8m | `AP510NFA-CBR` | 96000000 | `0x00410000` |
| `apollo510L` | apollo5 | m55 | TRUE | armv8m | `AP510DLA-CBR` | 48000000 | `0x00410000` |
| `apollo510b` | apollo5 | m55 | TRUE | armv8m | `AP510NFA-CBR` | 96000000 | `0x00410000` |
| `apollo5b` | apollo5 | m55 | TRUE | armv8m | `AP510NFA-CBR` | 96000000 | `0x00410000` |
| `atomiq110` | atomiq | m55 | TRUE | armv8m (capabilities add `npu`) | `Atomiq110` | 25000000 | `0x22000000` |

### Linker profiles (gcc)

| SoC | gcc scripts | armclang scatter |
| --- | --- | --- |
| `apollo2`, `apollo3`, `apollo3p`, `apollo4l`, `apollo4p` | Single `linker_script.ld` | Present, except `apollo2` (not found) |
| `apollo330P`, `apollo510`, `apollo510L`, `apollo510b` | `nbl`, `sbl`, `itcm_sbl` | Present |
| `apollo5b` | `nbl`, `sbl` | Present |
| `atomiq110` | `nbl`, `sbl`, `itcm_nbl`, `itcm_sbl` | Present |

Default profile: `sbl` for `apollo510` (`cmake/socs/apollo510.cmake:28` gcc, `:23` armclang; `cmake/nsx_toolchain_flags.cmake:81`), agreeing with RFC 0001. The first-pass reading of `nbl` was wrong. The default for apollo330P, apollo510L, apollo510b and apollo5b was not checked.

### Linker `MEMORY` regions read

| SoC and profile | Regions (as read by the gatherer) |
| --- | --- |
| `apollo510` `sbl` | `MCU_ITCM` `0x0` 256 KB; `MCU_MRAM` `0x00410000` 4128768; `MCU_TCM` `0x20000000` 507904; `SHARED_SRAM` `0x20080000` 3 MB |
| `apollo330P`, `apollo510L` `sbl` | `MCU_MRAM` `0x00410000` 2031616; `MCU_TCM` 240 KB; `SHARED_SRAM` about 1.7 MB; no `MCU_ITCM` |
| `apollo330P`, `apollo510L` `nbl` | apollo510-sized regions (256 KB ITCM, 496 KB TCM, 3 MB SRAM, 4 MB MRAM at `0x00400000`). This is the mismatch RFC 0001 appendix D describes |
| `atomiq110` `nbl` | `MCU_MRAM` `0x22000000` `LENGTH = 4194304` (4 MB) at `linker_script_nbl.ld:18`, agreeing with RFC 0001; the first-pass reading of 2 MB was wrong |

### HAL headers

The headers live in AmbiqSuite (internal SWS repository). Values were not read in this pass; see datasheets.md and ambiqsuite.md for later reads.

| Header | SoCs located |
| --- | --- |
| `mcu/<soc>/regs/am_reg_base_addresses.h` | `apollo510`, `apollo330P`, `apollo510L`, `atomiq110`, `apollo4p`, `apollo4l`, `apollo3p`, `apollo` (apollo3 lives under `mcu/apollo`) |
| `mcu/<soc>/hal/am_hal_pwrctrl.h` | Same set |
| `CMSIS/AmbiqMicro/Include/<soc>.h` | Same set |

## Question table

Caller line numbers were given only for the board loader and CLI.

| Question in plain words | API used today | Caller file:line | What it does with the answer | Fact or tool policy |
| --- | --- | --- | --- | --- |
| Which boards exist and what SoC does each use? | `load_board_descriptors` / `load_board` | `src/neuralspotx/board_descriptors.py:211-233` | Board registry | Fact (board) |
| List or show boards | `nsx board list`, `nsx board show` | `src/neuralspotx/cli/_cmd_board.py:40-63` | CLI output | Display |
| Is this module compatible with this SoC? | `compatibility.socs`, exact case | `module_discovery.py` | Module discovery | Tool policy over SoC identity |
| Which toolchains does this board support? | `board.yaml` toolchains | Board descriptor | Toolchain choice | Tool policy |
| Which starter profile for this board? | `_derive_starter_profiles` | `neuralspotx/metadata.py` | Project scaffolding | Tool policy |
| Which J-Link device, clock, and flash address? | `NSX_SEGGER_DEVICE`, `NSX_SEGGER_CPUFREQ`, `NSX_SEGGER_SWOFREQ`, `NSX_SEGGER_PF_ADDR`, board `debug.cmake` overrides | `cmake/socs/facts/*.cmake`, `boards/*/debug.cmake` | Flash and debug | Fact (package per board) |
| Core, MVE, PMU tier? | `NSX_SOC_*` facts | `cmake/socs/facts/*.cmake` | Compile flags and capabilities | Fact |
| Which linker script? | `NSX_LINKER_PROFILE` and per-SoC default | nsx-ambiq-sdk cmake | Memory layout of the build | Tool policy |
| Which DTCM section macro under Zephyr? | `platform_name.startswith(...)` | heliaAOT `aot/templates/platform.h.j2` | Emits `__dtcm_bss_section` or `__itcm_section` | Workaround for a missing family fact |
| Which SoCs does a heliaAOT nsx module support? | Static list | heliaAOT `aot/templates/nsx/nsx-module.yaml.j2` | `compatibility.socs` in generated module | Workaround |

## Overlay and custom-definition surface

| Surface | Detail |
| --- | --- |
| Board `debug.cmake` | Overrides SoC-level SEGGER device and clocks per board (8 boards above) |
| `board.yaml` | Board descriptor; directory name must match `name` |
| Starter profile SoC overrides | Carried in the derived profile |
| `NSX_LINKER_PROFILE` / `NSX_LINKER_SCRIPT` | Profile selection or explicit script |
| Zephyr | Devicetree overlays not read in this pass |

## Name resolution

| Aspect | Behaviour |
| --- | --- |
| Board ids | Exact; must equal the directory name |
| SoC ids in module compatibility | Exact, case-sensitive |
| heliaAOT nsx template | Lists `apollo510l` lowercase, which does not match neuralspotx `apollo510L` |
| Zephyr board id | heliaAOT `tests/e2e_zephyr` uses `apollo510_evb`, the same string as the nsx board id |

## Workarounds for missing model facts

| Workaround | Where | Missing fact it stands in for |
| --- | --- | --- |
| Name-prefix dispatch for Zephyr section names `__dtcm_bss_section` / `__itcm_section` | heliaAOT `platform.h.j2` | SoC family and Zephyr section names |
| Static `compatibility.socs` list | heliaAOT `nsx-module.yaml.j2` | Canonical SoC id list |
| `nbl` scripts for `apollo330P` / `apollo510L` carry apollo510-sized regions | nsx-ambiq-sdk linker scripts | Per-SoC linker windows (RFC 0001 appendix D) |
| Per-board `debug.cmake` overriding the SoC SEGGER device | neuralspotx boards | Package (part number) as a board fact |

## Open points

| Point | Status |
| --- | --- |
| Apollo5 default linker profile | Verified `sbl` for `apollo510`; apollo330P, apollo510L, apollo510b, apollo5b not checked |
| `atomiq110` `nbl` MRAM | Verified 4 MB at `linker_script_nbl.ld:18` |
| Zephyr pins differ | heliaAOT pins Zephyr v4.3.0 (`3568e1b6d5cdd51a6b964a2a1d6d29200fea2056`) and zephyr-sdk 0.17.4; RFC 0001 appendix D cites Zephyr `d8be6be`. The two revisions differ |
| Zephyr devicetree memory sizes | Not read in this pass (no local Zephyr tree) |
| AmbiqSuite HAL header values | Not read in this pass |
| `apollo2` armclang scatter | Not found by the gatherer |

## Citation checks

Run on 2026-10-04 against neuralspotx `6afb7d2`, nsx-ambiq-sdk `9d4463a`, heliaAOT `origin/main` `ea5cd6c0`.

| Citation given | Result | Detail |
| --- | --- | --- |
| `board_descriptors.py:211-233` | Partial | `@lru_cache` at 211, `def load_board_descriptors()` at 212, glob `*/board.yaml` at 223, name-vs-directory check at 226-230, `return` at 233. `load_board` is not in this range |
| `cli/_cmd_board.py:40-63` | Partial | `board list` command hint at 40-46 and `cmd_board_list` at 47-63 with `tier`, `registered_only`, `json`. `nsx board show` is not in this range |
| `boards/apollo330mP_evb/debug.cmake` | Match | `set(NSX_SEGGER_DEVICE "Apollo330P_510L")` at 7 |
| `boards/atomiq110_fpga_turbo/debug.cmake` | Match | Device `Atomiq110` at 4; CPUFREQ 48000000 at 17; SWOFREQ 1920000 at 18 |
| `cmake/socs/facts/apollo510.cmake` | Match | Series `apollo5`, core `cortex-m55`, `HAS_MVE TRUE`, PMU tier `armv8m`; device `AP510NFA-CBR` at 54, PF `0x00410000` at 56, CPUFREQ 96000000 at 57. The comment at 51 says `NSX_SEGGER_CPUFREQ` is the TPIU trace clock |
| `cmake/socs/facts/atomiq110.cmake` | Match | Capabilities include `npu` at 22; device `Atomiq110` at 66; PF `0x22000000` at 68; CPUFREQ 25000000 at 69 |
| `apollo510/gcc/linker_script_sbl.ld` `MEMORY` | Match | Lines 10-13: ITCM 262144 at `0x0`, MRAM 4128768 at `0x00410000`, TCM 507904 at `0x20000000`, SHARED_SRAM 3145728 at `0x20080000` |
| `atomiq110/gcc/linker_script_nbl.ld` `MCU_MRAM` 2 MB | Mismatch | Line 18: `MCU_MRAM (rx) : ORIGIN = 0x22000000, LENGTH = 4194304` (4 MB), consistent with RFC 0001 |
| Apollo5 default profile `nbl` | Mismatch for `apollo510` | `cmake/socs/apollo510.cmake:28` sets the gcc default to `linker_script_sbl.ld` (armclang `linker_script_sbl.sct` at 23); `cmake/nsx_toolchain_flags.cmake:81` comments that "default" keeps the standard SBL layout. Other Apollo5 parts not checked |
| heliaAOT `nsx-module.yaml.j2` `apollo510l` | Match | `apollo510l` at 49 |
| heliaAOT Zephyr pins | Match | `tests/e2e_zephyr/tools/zephyr_deps.py:193-194` (v4.3.0, `3568e1b6d5cdd51a6b964a2a1d6d29200fea2056`), `:228` (sdk 0.17.4) |
