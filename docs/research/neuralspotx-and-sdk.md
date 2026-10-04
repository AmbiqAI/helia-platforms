# neuralspotx and nsx-ambiq-sdk: source inventory

- **Source:** five locations

  | Location | GitHub | Role |
  | --- | --- | --- |
  | `/Users/adam.page/Ambiq/neuralspotx/neuralspotx` | `AmbiqAI/neuralspotx` | Board descriptors, module registry lock, CMake tooling |
  | `/Users/adam.page/Ambiq/neuralspotx/nsx-modules/nsx-ambiq-sdk` | `AmbiqAI/nsx-ambiq-sdk` | SoC facts, linker scripts, vendored AmbiqSuite HAL |
  | `/Users/adam.page/Ambiq/helia/neuralspotx-v5.2.24` | `AmbiqAI/neuralspotx` (tag snapshot) | Reference snapshot |
  | `/Users/adam.page/Ambiq/helia/nsx-ambiq-sdk-audit` | mirror of `AmbiqAI/nsx-ambiq-sdk` | Intake and qualification records: `docs/platform-coverage.md`, `release/nsx-ambiq-sdk-5.2.24.yaml`, `release/qualification-5.2.24.md` |
  | `/Users/adam.page/Ambiq/neuralspot` | none (not a git repo) | Legacy neuralSPOT |

- **Revision:** neuralspotx `main` at `6afb7d2`; nsx-ambiq-sdk `main` at `9d4463a`; neuralspotx-v5.2.24 tag snapshot `a07f152`; nsx-ambiq-sdk-audit `a9f4ec2`; neuralspot unversioned
- **Read on:** 2026-10-04
- **Method:** Inventory from a read of the checkouts; eleven citations re-checked on 2026-10-04 against neuralspotx `6afb7d2` and nsx-ambiq-sdk `9d4463a` (results under Open questions, "Citation checks").

## What it is

neuralspotx (NSX) is the build system and module registry for Ambiq firmware. It owns board descriptors and per-SoC module compatibility. nsx-ambiq-sdk packages the AmbiqSuite SDK as NSX modules and owns the per-SoC CMake facts, linker scripts, and HAL headers. Together they are the closest thing to a source of record for SoC identity, core, ABI, debug-probe strings, and linked memory regions.

| Item | Location |
| --- | --- |
| Board descriptors | neuralspotx `src/neuralspotx/boards/<board>/board.yaml` (17) |
| Board debug fragments | neuralspotx `src/neuralspotx/boards/<board>/debug.cmake` (17) |
| Module registry lock | neuralspotx `src/neuralspotx/data/registry.lock.yaml` |
| Module SoC compatibility | `nsx-module.yaml` `compatibility.socs` (neuralspotx `src/neuralspotx/cmake/nsx-module.yaml:24-38`) |
| SoC facts | nsx-ambiq-sdk `cmake/socs/facts/<soc>.cmake` (11; see Citation checks) |
| Linker scripts | nsx-ambiq-sdk `modules/nsx-core/src/<soc>/{gcc,armclang}/` |
| HAL headers | nsx-ambiq-sdk `modules/nsx-ambiqsuite/sdk/mcu/<soc>/regs/` |

## Platform model (types, fields, data files)

### `board.yaml` (schema_version 1)

| Field | Example (`apollo510_evb`) |
| --- | --- |
| `schema_version` | 1 |
| `board.name` | `apollo510_evb` |
| `board.tier` | `evb` |
| `board.soc` | `apollo510` |
| `board.registered` | `true` |
| `sdk_provider` | `ambiqsuite` |
| `cpu.core` | `cortex-m55` |
| `cpu.float_abi` | `hard` |
| `cpu.abi` | `thumbv8.1m-fpv5-hard` |
| `toolchains` | `arm-none-eabi-gcc`, `armclang`, `atfe` |

The file header says it is the source of truth for board to SoC / SDK-provider derivation, consumed by `neuralspotx.constants` via `neuralspotx/board_descriptors.py`, and must stay in sync with `board.cmake` (`NSX_CPU`, `NSX_ABI_FLAGS`).

### `debug.cmake`

| Item | Value | Source |
| --- | --- | --- |
| Count | 17, one per board | `src/neuralspotx/boards/*/debug.cmake` |
| Default | Toolchain defaults; `apollo510_evb/debug.cmake:5` comment: "boards with a specific probe device set NSX_SEGGER_DEVICE here" | neuralspotx |
| Boards that `set(NSX_SEGGER_DEVICE ...)` | 8: `apollo330mP_evb`, `apollo4l_evb`, `apollo4l_blue_evb`, `apollo4p_evb`, `apollo4p_evb_disp_shield_rev2`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `atomiq110_fpga_turbo` | grep on 2026-10-04 |

### SoC facts (`cmake/socs/facts/<soc>.cmake`)

| Variable | Meaning |
| --- | --- |
| `NSX_SOC_FAMILY`, `NSX_SOC_SERIES` | Family and series id |
| `NSX_SOC_CORE`, `NSX_SOC_ARCH_CLASS` | Core and architecture class |
| `NSX_SOC_HAS_DSP`, `NSX_SOC_HAS_MVE`, `NSX_SOC_HAS_FPU` | ISA feature flags |
| `NSX_SOC_PMU_TIER` | PMU tier |
| `NSX_SOC_CAPABILITIES` | Space-separated capability tokens |
| `NSX_CPU`, `NSX_FPU`, `NSX_ABI_FLAGS` | Compiler selectors |
| `NSX_SOC_COMPILE_DEFINITIONS` | Compile definitions |
| `NSX_SEGGER_DEVICE` | J-Link device string (board may override) |
| `NSX_SEGGER_CPUFREQ` | Per the facts file comment, the TPIU trace clock used for the SWO baud scaler, "not the CPU clock" (`apollo510.cmake:49-52`) |

| SoC | Series | Core | Arch | DSP / MVE / FPU | PMU | `NSX_FPU` | ABI | `NSX_SEGGER_DEVICE` | `NSX_SEGGER_CPUFREQ` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `apollo510` | apollo5 | cortex-m55 | armv8_1m | TRUE / TRUE / TRUE | armv8m | empty (`:29`) | thumbv8.1m-fpv5-hard | `AP510NFA-CBR` (`:54`) | `96000000` (`:57`) |
| `apollo3p` | apollo3 | cortex-m4 | armv7e_m | MVE FALSE | none | `fpv4-sp-d16` (`:25`) | thumbv7em-fpv4sp-hard | `AMA3B2KK-KBR` (`:49`) | `48000000` (`:52`) |
| `atomiq110` | atomiq | cortex-m55 | armv8_1m | as apollo510 | armv8m | empty (`:32`) | not re-read | `Atomiq110` (`:66`) | `25000000` (`:69`) |

Capability strings: `apollo510` is `"core:m55 isa:armv8.1-m dsp mve fpu pmu:armv8m"`; `atomiq110` adds `npu`.

Compile definitions (union across facts files): `PART_<soc>`, `AM_PART_<variant>`, `ARMCM<core>`, `__FPU_PRESENT`, `NSX_SOC_CORE_M<n>=1`, `NSX_SOC_HAS_*` flags, `NSX_SOC_PMU_ARMV8M=0|1`.

### Linker scripts

| SoC | Profiles | Source |
| --- | --- | --- |
| `apollo510` | gcc `linker_script_sbl.ld` (and armclang equivalents) | `modules/nsx-core/src/apollo510/` |
| `apollo510L`, `apollo510b`, `apollo5b` | Also `nbl` and `itcm_sbl` variants | `modules/nsx-core/src/<soc>/` |
| Others | One or more profiles per toolchain | `modules/nsx-core/src/<soc>/` |

`apollo510` gcc `linker_script_sbl.ld:8-16` MEMORY block, quoted:

| Region | Origin | Length (bytes) | Source |
| --- | --- | --- | --- |
| `MCU_ITCM` | `0x00000000` | 262144 | `linker_script_sbl.ld:10` |
| `MCU_MRAM` | `0x00410000` | 4128768 | `linker_script_sbl.ld:11` |
| `MCU_TCM` | `0x20000000` | 507904 | `linker_script_sbl.ld:12` |
| `SHARED_SRAM` | `0x20080000` | 3145728 | `linker_script_sbl.ld:13` |

### HAL headers (`am_reg_base_addresses.h`)

`apollo510`, `modules/nsx-ambiqsuite/sdk/mcu/apollo510/regs/am_reg_base_addresses.h:35-39` (comment block, quoted as written):

| Line | Text |
| --- | --- |
| 35 | `ITCM: 256KB 0x00000000 - 0x0003FFFF` |
| 36 | `NVM (MRAM): 4096MB 0x00400000 - 0x007FFFFF` (header says "MB"; see Open questions) |
| 37 | `MSPIx External memory: varies 0x60000000 - 0x8FFFFFFF` |
| 38 | `DTCM: 512KB 0x20000000 - 0x2007FFFF` |
| 39 | `System SRAM: 3072KB 0x20080000 - 0x2037FFFF` |

`apollo3p`, `modules/nsx-ambiqsuite/sdk/mcu/apollo3p/regs/am_reg_base_addresses.h:26-47`:

| Define | Value | Line |
| --- | --- | --- |
| `SRAM_BASEADDR` | `0x10000000UL` | 26 |
| `TCM_BASEADDR` | `SRAM_BASEADDR` | 31 |
| `TCM_MAX_SIZE` | `64UL * 1024UL` | 32 |
| `FLASH_BASEADDR` | `0x00000000UL` | 37 |
| `MSPI0/1/2_XIP_BASEADDR` | `0x02000000UL` / `0x04000000UL` / `0x06000000UL` | 42, 44, 46 |

## Registered entries (table)

### Boards (17 `board.yaml`)

| Board | Board | Board |
| --- | --- | --- |
| `apollo2_evb` | `apollo4l_blue_evb` | `apollo510_evb` |
| `apollo330mP_evb` | `apollo4l_evb` | `apollo510b_evb` |
| `apollo3_evb` | `apollo4p_blue_kbr_evb` | `apollo510dL_evb` |
| `apollo3_evb_cygnus` | `apollo4p_blue_kxr_evb` | `apollo5b_evb` |
| `apollo3p_evb` | `apollo4p_evb` | `atomiq110_fpga_turbo` |
| `apollo3p_evb_cygnus` | `apollo4p_evb_disp_shield_rev2` | |

Only `apollo510_evb/board.yaml` was read field by field in this pass.

### SoC ids (case-sensitive)

| SoC id | Facts file | nsx-ambiq-sdk version (lock) | In `nsx-module.yaml` compatibility |
| --- | --- | --- | --- |
| `apollo2` | yes | v5.2.24 | yes |
| `apollo3` | yes | v5.2.24 | yes |
| `apollo3p` | yes | v5.2.24 | yes |
| `apollo4l` | yes | v5.2.24 | yes |
| `apollo4p` | yes | v5.2.24 | yes |
| `apollo5b` | yes | v5.2.24 | yes |
| `apollo510` | yes | v5.2.24 | yes |
| `apollo510b` | yes | v5.2.24 | yes |
| `apollo510L` | yes | v5.2.24 | yes |
| `apollo330P` | yes | v5.2.24 | yes |
| `atomiq110` | yes | v5.2.25 (override at `registry.lock.yaml:435`) | yes |

### Pinned modules (`registry.lock.yaml`)

| Module | Revision | Source |
| --- | --- | --- |
| `nsx-ambiq-sdk` | v5.2.24 | `registry.lock.yaml:17-21` (project entry, `revision` at line 20) |
| `nsx-npu` (atomiq110 only) | v5.2.25 | `registry.lock.yaml:208-211`; see `AmbiqAI/neuralspotx#248` |
| `ns-cmsis-nn` | v7.29.2 | `registry.lock.yaml` |
| `nsx-pmu-armv8m` | v0.2.0 | `registry.lock.yaml` |
| `helia-rt` | v1.18.0 | `registry.lock.yaml` |
| `soc_families` block | per-SoC module lists and revisions | `registry.lock.yaml:310-459` |

## Consumers / name resolution

| Resolution | Behaviour | Source |
| --- | --- | --- |
| Board to SoC | `board.yaml` `board.soc`, read by `neuralspotx/board_descriptors.py` | `board.yaml` header |
| SoC to module set and SDK revision | `soc_families.<soc>` in the lock (YAML merge keys; `atomiq110` merges `*fam_apollo5` and overrides `revision`) | `registry.lock.yaml:310-459` |
| Module compatibility | `compatibility.socs` list, exact ids | `nsx-module.yaml:24-38` |
| Case | SoC ids are case-sensitive (`apollo510L`, `apollo330P`) | facts file names, lock keys |
| Board to J-Link device | SoC facts default, overridden in 8 boards' `debug.cmake` | facts files, `debug.cmake` |

## Facts it carries that the others do not

| Fact | Where |
| --- | --- |
| ABI and float-ABI strings per board and SoC | `board.yaml`, facts files |
| Supported toolchains per board | `board.yaml` |
| Board tier and `registered` flag | `board.yaml` |
| Compile definitions per SoC (`PART_*`, `AM_PART_*`, `ARMCM*`) | facts files |
| Linker MEMORY regions per SoC and profile (`sbl`, `nbl`, `itcm_sbl`) and per toolchain | `modules/nsx-core/src/` |
| Hardware address map from the vendor HAL | `am_reg_base_addresses.h` |
| SDK version pinned per SoC family | `registry.lock.yaml` |
| SoCs and boards absent from heliaAOT and helia-profiler: `apollo2`, `apollo3` (as an SoC id), `apollo3_evb_cygnus`, `apollo4p_evb_disp_shield_rev2` | neuralspotx |
| No power or performance characterization keyed by SoC or board | n/a |

## Tooling to mirror (neuralspotx)

| Area | Setting |
| --- | --- |
| Python | `>=3.11`, setuptools |
| Lint | ruff `>=0.11`, line-length 100, target py311, preview on |
| Types | ty `==0.0.74` (pinned) |
| Tests | pytest, hypothesis, pytest-timeout |
| pre-commit | pre-commit-hooks; gitleaks v8.30.1; ruff v0.15.7; clang-format v22.1.8; uv-lock v0.12.6; local `todo-needs-issue` (`scripts/hooks/todo_needs_issue.py`); ty on pre-push |
| Workflows | `release.yml`, `docs.yml`, `ci.yml` |

## Open questions

| # | Question |
| --- | --- |
| 1 | Not read in this pass: `__FPU_DP` in CMSIS device headers; `am_hal_pwrctrl.h` NPU and CPU modes; the `apollo330P`, `apollo510L`, `apollo4p`, `apollo4l`, `apollo3` HAL headers. |
| 2 | Do the `apollo330P` and `apollo510L` `nbl` and `itcm_sbl` scripts carry `apollo510` sizes? Not confirmed here. helia-profiler's `platform/memory_map.py` docstring (origin/main `b195e29f`) says the apollo330P `itcm`-profile scripts declare AP510-sized regions, "the upstream NSX bug reported in #176" (helia-profiler numbering). |
| 3 | The `apollo510` HAL header comment reads `NVM (MRAM): 4096MB` while its address range `0x00400000 - 0x007FFFFF` spans 4 MB. Treat the comment unit as a header typo, or raise it upstream? |
| 4 | `cmake/socs/facts/` holds 11 files, not 12. Which SoC was expected as the twelfth? |
| 5 | The lock's per-SoC version split (v5.2.24 for ten SoCs, v5.2.25 for `atomiq110`) is stated in the `soc_families` block; lines 17-21 only show the project-level pin. |
| 6 | `apollo510` `NSX_FPU` is empty by design (the facts comment at `apollo510.cmake:24-27` says no separate `-mfpu` flag is emitted for Armv8.1-M). Confirm the catalogue should record the ABI string rather than an FPU name for M55 parts. |
| 7 | How does the nsx-ambiq-sdk-audit mirror (`a9f4ec2`) relate to nsx-ambiq-sdk `main` (`9d4463a`)? Not compared in this pass. |

### Citation checks (2026-10-04)

| Citation given | Result |
| --- | --- |
| neuralspotx `registry.lock.yaml:17-21` for SDK versions per SoC | Partial match. Lines 17-21 are the `nsx-ambiq-sdk` project entry pinned at v5.2.24 (line 20). The per-SoC list is in `soc_families`, not in this range. |
| `registry.lock.yaml:208-211` `nsx-npu` v5.2.25 | Match. |
| `registry.lock.yaml:435` atomiq110 override | Match (`revision: v5.2.25` under `atomiq110:` at 433). |
| `registry.lock.yaml:310-459` `soc_families` | Match (`soc_families:` at 310). |
| `cmake/nsx-module.yaml:24-38` `compatibility.socs` | Match (`compatibility:` at 24; last SoC `atomiq110` at 38). |
| 17 `board.yaml` and `apollo510_evb` contents | Match. |
| 12 facts files | Mismatch. 11 files: apollo2, apollo3, apollo330P, apollo3p, apollo4l, apollo4p, apollo510, apollo510L, apollo510b, apollo5b, atomiq110. |
| apollo510 `linker_script_sbl.ld:8-16` MEMORY | Match. Values as tabled. |
| apollo510 `am_reg_base_addresses.h:35-39` | Match on lines and values, with the `4096MB` wording noted above. The prior summary's "SSRAM" label is "System SRAM" in the header. Path is under `modules/nsx-ambiqsuite/sdk/`; a git-ignored copy also exists under `sdk-intake/local/work/`. |
| apollo3p `am_reg_base_addresses.h:26-47` | Match. |
| RFC claim that eight boards override the J-Link device in `debug.cmake` | Confirmed: 8 boards call `set(NSX_SEGGER_DEVICE ...)` (listed above). |
