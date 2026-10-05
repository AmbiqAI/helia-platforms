# RFC 0001 appendix D and J: verification against pinned sources

- **Source:** the numbers in sections D and J of [RFC 0001's appendix](../rfcs/0001-platform-catalogue-appendix.md), checked against

  | Repository | Revision | What was read |
  | --- | --- | --- |
  | `AmbiqAI/nsx-ambiq-sdk` | `v5.2.24` (`a9f4ec2`); `v5.2.25` (`aefce2c`) for atomiq110 | HAL register headers, HAL flash and power-control headers, the atomiq110 CMSIS header `atomiq110.h` and `mcu/atomiq110/am_mcu_apollo.h`, linker scripts, the apollo510 gcc startup file, SoC CMake, board BSP headers, `nsx-psram` (CMake and README), `nsx-npu` |
  | `AmbiqAI/neuralspotx` | `b930d59` | board `memory.cmake`, `debug.cmake`, READMEs |
  | `zephyrproject-rtos/zephyr` | `d8be6be` (v4.4.0-1273) | Ambiq SoC and board devicetrees, SoC Kconfig, Apollo5 `shared_ram.ld`, the Cortex-M linker script |
  | `zephyrproject-rtos/hal_ambiq` | `c03d2f9` | `dts/apollo510/am_apollo510.h` |
  | `AmbiqAI/helia-aot` | `1fd91daf` | `helia_aot/platforms/platforms.py`, `tests/e2e` |
  | `AmbiqAI/helia-profiler` | `ed2f0a15` | `src/helia_profiler/platform/soc.py`, `board.py`, `capabilities.py`, `registry.py` |

- **Revision:** as in the table
- **Read on:** 2026-10-05
- **Method:** every file was read at the named revision (`git show <rev>:<path>` for the git repositories, checkouts of the two SDK tags with clean working trees). C expressions and hex sizes were evaluated with a throwaway script. Datasheet facts are recorded in [datasheets.md](datasheets.md) and are not sources here.

This note verifies the appendix rather than replacing it. Of 163 rows, 146 match, 11 differ and 6 cannot be checked from these sources. Four of the eleven differing rows (J1, J5, J21, J25) record heliaAOT sizes that helia-aot has since changed to linker-window sizes. Under the #28 decision, J1, J21 and J25 are parity allow-list rows that the adoption changes, and J5's 4128768 B is the value #28 keeps. Five are errors in the appendix: the Apollo4 board PSRAM, the explanation of the Apollo5 gcc TCM gap, and the Zephyr `apollo4p_evb` TCM and SRAM split. The other two are PSRAM rows where the SDK and the board guides disagree. For `apollo510dL_evb` the appendix agrees with the board guide, and the SDK claims a PSRAM that is not fitted on revision 2.0 boards. For `apollo330mP_evb` the appendix agrees with the SDK's 32 MB, and the board guide says the PSRAM is not fitted on revision 2.0 boards. All are listed under [Disagreements](#disagreements), together with the places where helia-aot or helia-profiler today carry a value the sources contradict.

## How to read the tables

There is one row per number in the appendix. A J row with several columns becomes several rows, one per column. Numbers in J's "resolution" column get a row only when they appear nowhere else in that row.

- **Appendix** is the value as the appendix states it.
- **Source** is the value at the pinned revision. For the heliaAOT and helia-profiler columns of J, the source is the consumer's own code, so the verdict says whether the appendix still records the consumer correctly. Whether the consumer agrees with the SDK is covered under Disagreements.
- **Verdict** is one of: matches, differs, or not checkable from these sources. D39 matches its source but is contradicted by a board guide recorded in [datasheets.md](datasheets.md), so it is counted as differing.

Path abbreviations in the Provenance column: `mcu/` is nsx-ambiq-sdk `modules/nsx-ambiqsuite/sdk/mcu/`, `nsx-core/` is `modules/nsx-core/src/`, and `nsx-psram/` is `modules/nsx-psram/`. SDK rows are at `v5.2.24` unless they say `v5.2.25`. The register headers cited for apollo510, apollo330P, apollo510L, apollo4p, apollo4l, apollo3p and apollo3 are byte-identical in the two tags, and so is every linker script under `nsx-core/`. Zephyr paths are relative to the zephyr repository, and `am_apollo510.h` is hal_ambiq `dts/apollo510/am_apollo510.h`.

## Appendix D

### Physical regions

| # | Fact | Appendix | Source | Provenance | Verdict |
| --- | --- | --- | --- | --- | --- |
| D1 | apollo510 ITCM | 256 KB | 256 KB | `mcu/apollo510/regs/am_reg_base_addresses.h:45` `ITCM_MAX_SIZE` | matches |
| D2 | apollo510 DTCM | 512 KB | 512 KB | same file `:47` `DTCM_MAX_SIZE` | matches |
| D3 | apollo510 SSRAM | 3072 KB | 3072 KB | same file `:53` `SSRAM_MAX_SIZE` | matches |
| D4 | apollo510 MRAM | 4096 KB | 4096 KB | same file `:71` `MRAM_MAX_SIZE` | matches |
| D5 | apollo510b and apollo5b have no headers of their own | no headers | no `mcu/apollo510b` or `mcu/apollo5b` directory | `mcu/` directory listing | matches |
| D6 | apollo330P DTCM | 256 KB | 256 KB | `mcu/apollo330P/regs/am_reg_base_addresses.h:43` | matches |
| D7 | apollo330P SSRAM | 1792 KB | 1792 KB | same file `:49` | matches |
| D8 | apollo330P MRAM | 2048 KB | 2048 KB | same file `:55` | matches |
| D9 | apollo510L DTCM | 256 KB | 256 KB | `mcu/apollo510L/regs/am_reg_base_addresses.h:43` | matches |
| D10 | apollo510L SSRAM | 1792 KB | 1792 KB | same file `:49` | matches |
| D11 | apollo510L MRAM | 2048 KB | 2048 KB | same file `:55` | matches |
| D12 | atomiq110 DTCM | 512 KB | 512 KB | `v5.2.25` `mcu/atomiq110/regs/am_reg_base_addresses.h:30` | matches |
| D13 | atomiq110 SSRAM | 3072 KB | 3072 KB | same file `:36` | matches |
| D14 | atomiq110 RRAM | 4096 KB | 4096 KB | same file `:48` `RRAM_MAX_SIZE` | matches |
| D15 | atomiq110 HBLRAM | 13312 KB | 13312 KB | same file `:42` `HBLRAM_MAX_SIZE` | matches |
| D16 | atomiq110 ITCM, from the linker script because the header has no define | 256 KB | no `ITCM` define in the header; `MCU_ITCM` LENGTH 262144 B (256 KB) | `v5.2.25` same header (searched); `nsx-core/atomiq110/gcc/linker_script_nbl.ld:17` | matches |
| D17 | apollo4p TCM | 384 KB | 384 KB | `mcu/apollo4p/regs/am_reg_base_addresses.h:38` | matches |
| D18 | apollo4p SSRAM0 | 1024 KB | 1024 KB | same file `:45` | matches |
| D19 | apollo4p SSRAM1 | 1024 KB | 1024 KB | same file `:62` | matches |
| D20 | apollo4p EXTRAM | 384 KB | 128 + 256 = 384 KB | same file `:53`, `:55`, `:56` | matches |
| D21 | apollo4p MRAM | 2048 KB | 2048 KB | same file `:78` | matches |
| D22 | apollo4l TCM | 384 KB | 384 KB | `mcu/apollo4l/regs/am_reg_base_addresses.h:36` | matches |
| D23 | apollo4l SSRAM0 | 1024 KB | 1024 KB | same file `:42` | matches |
| D24 | apollo4l MRAM | 2048 KB | 2048 KB | same file `:84` | matches |
| D25 | apollo4l SSRAM1 | 0 | 0 | same file `:48`; the non-zero definitions at `:56-67` are inside the `#if 0` block at `:51-68` | matches |
| D26 | apollo4l EXTRAM | 0 | 0 | same file `:47` | matches |
| D27 | apollo3p TCM | 64 KB | 64 KB | `mcu/apollo3p/regs/am_reg_base_addresses.h:32` | matches |
| D28 | apollo3p SRAM (768 − TCM) | 704 KB | `AM_HAL_FLASH_SRAM_SIZE` 768 KB, which includes the 64 KB DTCM at its start; 768 − 64 = 704 KB | `mcu/apollo3p/hal/am_hal_flash.h:71`, `:73-74` | matches |
| D29 | apollo3p flash | 2048 KB | 512 KB × 4 instances = 2048 KB | same file `:86-87` | matches |
| D30 | apollo3 TCM | 64 KB | 64 KB | `mcu/apollo3/regs/am_reg_base_addresses.h:32` | matches |
| D31 | apollo3 SRAM (384 − TCM) | 320 KB | 384 − 64 = 320 KB | `mcu/apollo3/hal/am_hal_flash.h:71`, `:73-74` | matches |
| D32 | apollo3 flash | 1024 KB | 512 KB × 2 instances = 1024 KB | same file `:82-83` (the appendix says "same headers"; the lines differ from apollo3p's) | matches |

### Board external regions

| # | Fact | Appendix | Source | Provenance | Verdict |
| --- | --- | --- | --- | --- | --- |
| D33 | `apollo3p_evb` PSRAM | 8192 KB | `NSX_PSRAM_DEVICE_SIZE_BYTES` 8388608 B (8192 KB) for this board | `nsx-psram/CMakeLists.txt:22-29` | matches; whether the part is fitted is open (#29) |
| D34 | `apollo3p_evb_cygnus` PSRAM | 8192 KB | 8388608 B (8192 KB) | `nsx-psram/CMakeLists.txt:22-29` | matches |
| D35 | PSRAM on the five Apollo4 boards | 32768 KB on all five, with a caveat for plain `apollo4p_evb` | none: the plain and Blue apollo4l and apollo4p EVBs "do not populate PSRAM"; only `apollo4p_evb_disp_shield_rev2` does, at 33554432 B | `nsx-psram/CMakeLists.txt:31-38`, `:46-47`; neuralspotx `src/neuralspotx/boards/apollo4p_evb_disp_shield_rev2/README.md:7-9` | differs |
| D36 | `apollo510_evb` PSRAM | 65536 KB | 67108864 B (65536 KB); Zephyr gives the PSRAM node `size = <DT_SIZE_M(512)>`, in bits per the binding, which is 65536 KB (the node is `status = "disabled"`) | `nsx-psram/CMakeLists.txt:121-129`; zephyr `boards/ambiq/apollo510_evb/apollo510_evb.dts:169`, `:171`, `dts/bindings/mtd/jedec,jesd216.yaml:25-27` | matches |
| D37 | `apollo510b_evb` PSRAM | 65536 KB | 67108864 B (65536 KB) | `nsx-psram/CMakeLists.txt:121-129` | matches |
| D38 | `apollo5b_evb` PSRAM | 32768 KB | `nsx-psram` has no mapping for this board and stops at configure; no other source states a size | `nsx-psram/CMakeLists.txt:50-58` | not checkable from these sources |
| D39 | `apollo330mP_evb` PSRAM | 32768 KB | 33554432 B (32768 KB), a "conservative" default for an unvalidated board; the board's BSP defines `AM_BSP_MSPI_PSRAM_DEVICE_APS25616BA` and `USE_APS51216BA` | `modules/nsx-ambiqsuite/sdk/boards/apollo330mP_evb/bsp/am_bsp.h:134`, `:136`; `nsx-psram/CMakeLists.txt:130-137`, `:150-152` | differs; the source agrees with the appendix, but the board guide says revision 2.0 is unpopulated ([datasheets.md](datasheets.md), QS-A330MP p8, p10, p30) |
| D40 | `apollo510dL_evb` PSRAM | none | populated: the board's BSP defines `AM_BSP_MSPI_PSRAM_DEVICE_APS25616BA` and `USE_APS51216BA`; `nsx-psram` calls that macro its Apollo5 presence guard, maps the board to MSPI0, says all staged Apollo5-class EVBs are populated, and defaults the size to 32 MB (it has no default driver for this board) | `modules/nsx-ambiqsuite/sdk/boards/apollo510dL_evb/bsp/am_bsp.h:150`, `:152`; `nsx-psram/README.md:14-15`; `nsx-psram/CMakeLists.txt:53`, `:60-64`, `:138-146`, `:150-152` | differs; the board guide says revision 2.0 is unpopulated ([datasheets.md](datasheets.md), QS-A510DL p8, p10, p30) |
| D41 | `atomiq110_fpga_turbo` PSRAM | none | no `nsx-psram` mapping for the board, and no PSRAM in its neuralspotx board files | `nsx-psram/CMakeLists.txt:50-58`, `:147-148`; neuralspotx `src/neuralspotx/boards/atomiq110_fpga_turbo/` (searched) | matches |
| D42 | `apollo510_evb` NVM | 8192 KB | the `is25wx064` node has `size = <DT_SIZE_M(64)>`, in bits, which is 8192 KB (node `status = "disabled"`) | zephyr `boards/ambiq/apollo510_evb/apollo510_evb.dts:206-210` | matches |

### nsx windows (`gnu`, `armlink`)

| # | Fact | Appendix | Source | Provenance | Verdict |
| --- | --- | --- | --- | --- | --- |
| D43 | Apollo5 `sbl` bootloader region at the start of MRAM | 64 KB | `MCU_MRAM` ORIGIN 0x00410000, `MRAM_BASEADDR` 0x00400000: 64 KB | `nsx-core/apollo510/gcc/linker_script_sbl.ld:11`; `mcu/apollo510/regs/am_reg_base_addresses.h:70` | matches |
| D44 | Apollo3 bootloader region | 48 KB | `ROMEM` ORIGIN 0x0000C000, `FLASH_BASEADDR` 0: 48 KB | `nsx-core/apollo3p/gcc/linker_script.ld:10`; `nsx-core/apollo3/gcc/linker_script.ld:10`; `mcu/apollo3p/regs/am_reg_base_addresses.h:37` | matches |
| D45 | Apollo4 bootloader region | 96 KB | `MCU_MRAM` ORIGIN 0x00018000, `MRAM_BASEADDR` 0: 96 KB | `nsx-core/apollo4p/gcc/linker_script.ld:10`; `nsx-core/apollo4l/gcc/linker_script.ld:10`; `mcu/apollo4p/regs/am_reg_base_addresses.h:77` | matches |
| D46 | No bootloader region on `nbl` | none | `MCU_MRAM` ORIGIN 0x00400000 | `nsx-core/apollo510/gcc/linker_script_nbl.ld:11` | matches |
| D47 | atomiq110 defaults to `nbl` | `nbl` | default gcc script `linker_script_nbl.ld`, whose `MCU_MRAM` starts at `RRAM_BASEADDR` 0x22000000 | `v5.2.25` `cmake/socs/atomiq110.cmake:58`; neuralspotx `src/neuralspotx/boards/atomiq110_fpga_turbo/memory.cmake:18`; `v5.2.25` `nsx-core/atomiq110/gcc/linker_script_nbl.ld:18` | matches |
| D48 | TCM left outside the gcc window on Apollo5 parts | 16 KB | `MCU_TCM` 507904 B (496 KB) against 512 KB; 245760 B (240 KB) against 256 KB on apollo330P and apollo510L | `nsx-core/{apollo510,apollo510b,apollo5b}/gcc/linker_script_sbl.ld:12`; `nsx-core/{apollo330P,apollo510L}/gcc/linker_script_sbl.ld:11`; `v5.2.25` `nsx-core/atomiq110/gcc/linker_script_nbl.ld:19` | matches |
| D49 | What occupies those 16 KB | a stack and heap reservation | nothing the program links: `.stack` and `.heap` are placed inside `MCU_TCM`, and the `STACK` and `HEAP` regions that would sit in the top 16 KB are commented out | `nsx-core/apollo510/gcc/linker_script_sbl.ld:14-15`, `:90-96`, `:126-138`; `nsx-core/apollo510/gcc/startup_gcc.c:167-168`, `:203` | differs |
| D50 | Apollo5 armclang stack and heap reservation | 20 KB | `MCU_TCM` 0x7B000 (492 KB), `ARM_LIB_HEAP` 4 KB at 0x2007B000, `ARM_LIB_STACK` 16 KB below 0x20080000: 20 KB; apollo330P `sbl`: 0x3B000 (236 KB) plus the same 20 KB | `nsx-core/apollo510/armclang/linker_script_sbl.sct:21`, `:26`, `:39`; `nsx-core/apollo330P/armclang/linker_script_sbl.sct:14`, `:20`, `:33` | matches |
| D51 | apollo4p gcc TCM reservation | none | `MCU_TCM` 393216 B (384 KB), the whole TCM | `nsx-core/apollo4p/gcc/linker_script.ld:11` | matches |
| D52 | apollo4p armclang reservation | 20 KB | `MCU_TCM` 0x5B000 (364 KB), heap 4 KB at 0x1005B000, stack 16 KB below 0x10060000: 20 KB | `nsx-core/apollo4p/armclang/linker_script.sct:17`, `:24`, `:30` | matches |
| D53 | apollo3p `STACKMEM` carved from SRAM | 4 KB | `STACKMEM` 0x10010000, LENGTH 4096; `RWMEM` starts at 0x10011000 | `nsx-core/apollo3p/gcc/linker_script.ld:11`, `:13` | matches |
| D54 | apollo3 flat `RWMEM` over TCM and SRAM | 384 KB | `RWMEM` ORIGIN 0x10000000, LENGTH 384K | `nsx-core/apollo3/gcc/linker_script.ld:11` | matches |
| D55 | apollo4p scripts link SSRAM0 only | SSRAM0 | `SHARED_SRAM` 0x10060000, 1048576 B, which is `SSRAM0_BASEADDR` and `SSRAM0_MAX_SIZE` | `nsx-core/apollo4p/gcc/linker_script.ld:12` | matches |
| D56 | apollo330P and apollo510L `nbl` and `itcm_sbl` scripts carry apollo510's sizes | apollo510's sizes | `MCU_MRAM` 4128768, `MCU_TCM` 507904, `SHARED_SRAM` 3145728 B in all four scripts, larger than the parts' 2048, 256 and 1792 KB | `nsx-core/{apollo330P,apollo510L}/gcc/linker_script_{nbl,itcm_sbl}.ld:11-13` | matches |
| D57 | Legacy neuralSPOT apollo3p SRAM window | 695 KB | legacy neuralSPOT is not among these sources | none | not checkable from these sources |
| D58 | nsx apollo3p SRAM window | 700 KB | `RWMEM` 716800 B (700 KB) | `nsx-core/apollo3p/gcc/linker_script.ld:11` | matches |
| D59 | Legacy neuralSPOT apollo510 and apollo4p scripts match nsx | match | legacy neuralSPOT is not among these sources | none | not checkable from these sources |
| D60 | armclang TCM below the gnu budget, Apollo5 | 4 KB | 492 against 496 KB; 236 against 240 KB on apollo330P | D48, D50 | matches |
| D61 | armclang TCM below the gnu budget, Apollo4 | 20 KB | 364 against 384 KB | D51, D52 | matches |

### Zephyr (`zephyr`)

| # | Fact | Appendix | Source | Provenance | Verdict |
| --- | --- | --- | --- | --- | --- |
| D62 | Apollo510 `DTCM_MAX_SIZE` | 0x7C000 | 0x7C000 (496 KB) | `am_apollo510.h:211` | matches |
| D63 | Apollo510 `MRAM_BASE_ADDR` | 0x410000 | 0x410000 | `am_apollo510.h:218` | matches |
| D64 | Apollo510 `MRAM_MAX_SIZE` | 0x3F0000 | 0x3F0000 (4032 KB) | `am_apollo510.h:219` | matches |
| D65 | Apollo3 `FLASH_LOAD_OFFSET` | 0xc000 | default 0xc000 when not building for MCUboot | `soc/ambiq/apollo3x/Kconfig.defconfig.apollo3_blue:40-45` | matches |
| D66 | Apollo3P flash node start | 0xc000 | `reg = <0x0000c000 0x1f4000>` | `dts/arm/ambiq/ambiq_apollo3p_blue.dtsi:109` | matches |
| D67 | Apollo4 flash node start | 0x18000 | `reg = <0x00018000 0x1e8000>` | `dts/arm/ambiq/ambiq_apollo4p.dtsi:89`; `dts/arm/ambiq/ambiq_apollo4p_blue.dtsi:103` | matches |
| D68 | Ambiq boards in Zephyr | 6 | 6: `apollo2_evb`, `apollo3_evb`, `apollo3p_evb`, `apollo4p_blue_kxr_evb`, `apollo4p_evb`, `apollo510_evb` | `boards/ambiq/` listing | matches |
| D69 | `apollo510_evb` DTCM | 496 KB | `dtcm` node `reg = <DTCM_BASE_ADDR DTCM_MAX_SIZE>`, 0x7C000 | `dts/arm/ambiq/ambiq_apollo510.dtsi:103`; `am_apollo510.h:211` | matches |
| D70 | `apollo510_evb` SRAM (`sram0` overridden) | 2048 KB | `sram0` `reg = <SSRAM_BASE_ADDR 0x200000>` | `boards/ambiq/apollo510_evb/apollo510_evb.dts:35-38` | matches |
| D71 | `apollo510_evb` `sram_no_cache` | 1 MB | `reg = <0x20280000 0x100000>` | same file `:40-45` | matches |
| D72 | `ambiq_dma_buff` offset inside `sram0` | 0x50000 | `CONFIG_SRAM_BASE_ADDRESS + CONFIG_SOC_AMBIQ_DMA_BUFF_LOCATION`, default 0x50000 | `soc/ambiq/apollo5x/shared_ram.ld:7`; `soc/ambiq/apollo5x/Kconfig:34-36` | matches |
| D73 | `apollo510_evb` MRAM window and origin | 4032 KB @ 0x410000 | `flash0` `reg = <MRAM_BASE_ADDR MRAM_MAX_SIZE>` | `dts/arm/ambiq/ambiq_apollo510.dtsi:89-92`; `am_apollo510.h:218-219` | matches |
| D74 | `apollo510_evb` ITCM | 256 KB | `ITCM_MAX_SIZE` 0x40000 | `am_apollo510.h:207`; `dts/arm/ambiq/ambiq_apollo510.dtsi:97` | matches |
| D75 | `apollo4p_evb` TCM (named `ITCM`) | 384 KB | 64 KB: `reg = <0x10000000 0x10000>`, named `ITCM` | `dts/arm/ambiq/ambiq_apollo4p.dtsi:66` | differs |
| D76 | `apollo4p_evb` SRAM | 2432 KB (three banks) | 2752 KB in one node at 0x10010000: `reg = <0x10010000 0x2b0000>` | `dts/arm/ambiq/ambiq_apollo4p.dtsi:73` | differs |
| D77 | `apollo4p_evb` MRAM window and origin | 1952 KB @ 0x18000 | 0x1e8000 (1952 KB) at 0x18000 | `dts/arm/ambiq/ambiq_apollo4p.dtsi:89` | matches |
| D78 | `apollo4p_blue_kxr_evb` TCM (named `ITCM`) | 64 KB | `reg = <0x10000000 0x10000>` | `dts/arm/ambiq/ambiq_apollo4p_blue.dtsi:80` | matches |
| D79 | `apollo4p_blue_kxr_evb` SRAM | 2752 KB | `reg = <0x10010000 0x2b0000>` | same file `:87` | matches |
| D80 | `apollo4p_blue_kxr_evb` MRAM | 1952 KB @ 0x18000 | `reg = <0x00018000 0x1e8000>` | same file `:103` | matches |
| D81 | `apollo3p_evb` TCM | 64 KB | `reg = <0x10000000 0x10000>` | `dts/arm/ambiq/ambiq_apollo3p_blue.dtsi:68` | matches |
| D82 | `apollo3p_evb` SRAM | 704 KB | `reg = <0x10010000 0xb0000>` | same file `:75` | matches |
| D83 | `apollo3p_evb` MRAM | 2000 KB @ 0xc000 | `reg = <0x0000c000 0x1f4000>` | same file `:109` | matches |
| D84 | `apollo3_evb` TCM | 64 KB | `reg = <0x10000000 0x10000>` | `dts/arm/ambiq/ambiq_apollo3_blue.dtsi:68` | matches |
| D85 | `apollo3_evb` SRAM | 320 KB | `reg = <0x10010000 0x50000>` | same file `:75` | matches |
| D86 | `apollo3_evb` MRAM | 976 KB @ 0xc000 | `flash0` is 1024 KB at 0 (`:91`); with `FLASH_LOAD_OFFSET` 0xc000 the ROM region is `FLASH_SIZE` − offset = 976 KB | `dts/arm/ambiq/ambiq_apollo3_blue.dtsi:91`; `include/zephyr/arch/arm/cortex_m/scripts/linker.ld:53-57`; D65 | matches |

## Appendix J

| # | Fact | Appendix | Source | Provenance | Verdict |
| --- | --- | --- | --- | --- | --- |
| J1 | apollo510/510b/5b TCM, heliaAOT | 512 KB | 507904 B (496 KB) on `apollo510_evb` and `apollo510b_evb` | helia-aot `helia_aot/platforms/platforms.py:498`, `:547` | differs (changed by AmbiqAI/helia-aot#540) |
| J2 | same, helia-profiler | 512 KB | 512 KB on apollo510, apollo510b, apollo5b | helia-profiler `src/helia_profiler/platform/soc.py:457`, `:498`, `:534` | matches |
| J3 | same, physical | 512 KB | 512 KB | D2 | matches |
| J4 | same, default gnu window | 507904 B | 507904 B in all three `sbl` scripts | D48 | matches |
| J5 | apollo510/510b/5b MRAM, heliaAOT | 4096 KB | 4128768 B (4032 KB) | `platforms.py:496`, `:545` | differs (changed by AmbiqAI/helia-aot#540) |
| J6 | same, helia-profiler | 4096 KB | 4096 KB | `soc.py:455`, `:496`, `:532` | matches |
| J7 | same, physical | 4096 KB | 4096 KB | D4 | matches |
| J8 | same, default gnu window (`sbl`) | 4128768 B | 4128768 B (4032 KB) in all three `sbl` scripts | `nsx-core/{apollo510,apollo510b,apollo5b}/gcc/linker_script_sbl.ld:11` | matches |
| J9 | atomiq110 TCM, heliaAOT | 496 KB | 496 KB | `platforms.py:593` | matches |
| J10 | same, helia-profiler | 496 KB | 496 KB | `soc.py:709` | matches |
| J11 | same, physical | 512 KB | 512 KB | D12 | matches |
| J12 | same, default gnu window | 507904 B | 507904 B | `v5.2.25` `nsx-core/atomiq110/gcc/linker_script_nbl.ld:19` | matches |
| J13 | atomiq110 MRAM, heliaAOT | 4096 KB | 4096 KB | `platforms.py:591` | matches |
| J14 | same, helia-profiler | 4096 KB | 4096 KB | `soc.py:707` | matches |
| J15 | same, physical (RRAM) | 4096 KB | 4096 KB | D14 | matches |
| J16 | same, default gnu window (`nbl`) | 4194304 B | 4194304 B | `v5.2.25` `nsx-core/atomiq110/gcc/linker_script_nbl.ld:18` | matches |
| J17 | atomiq110 ITCM, heliaAOT | 256 KB | 256 KB | `platforms.py:594` | matches |
| J18 | same, helia-profiler | 256 KB | 256 KB | `soc.py:710` | matches |
| J19 | same, physical | no header define | no header define | D16 | matches |
| J20 | same, default gnu window | 262144 B | 262144 B | `v5.2.25` `nsx-core/atomiq110/gcc/linker_script_nbl.ld:17` | matches |
| J21 | apollo330P / apollo510L TCM, heliaAOT | 256 KB | 245760 B (240 KB) on `apollo330mp_evb` and `apollo510l_evb` | `platforms.py:458`, `:525` | differs (changed by AmbiqAI/helia-aot#554) |
| J22 | same, helia-profiler | 240 KB | 240 KB | `soc.py:581`, `:651` | matches |
| J23 | same, physical | 256 KB | 256 KB | D6, D9 | matches |
| J24 | same, default gnu window | 245760 B | 245760 B | `nsx-core/{apollo330P,apollo510L}/gcc/linker_script_sbl.ld:11` | matches |
| J25 | apollo330P / apollo510L MRAM, heliaAOT | 2048 KB | 2031616 B (1984 KB) | `platforms.py:456`, `:523` | differs (changed by AmbiqAI/helia-aot#554) |
| J26 | same, helia-profiler | 1984 KB | 1984 KB | `soc.py:579`, `:649` | matches |
| J27 | same, physical | 2048 KB | 2048 KB | D8, D11 | matches |
| J28 | same, default gnu window | 2031616 B | 2031616 B | `nsx-core/{apollo330P,apollo510L}/gcc/linker_script_sbl.ld:10` | matches |
| J29 | apollo3p MRAM / SRAM, heliaAOT | 2048 / 704 KB | 2048 / 704 KB on `apollo3p_evb` and `apollo3_blue_plus_evb` | `platforms.py:365-366`, `:348-349` | matches |
| J30 | same, helia-profiler | 2000 / 700 KB | 2000 / 700 KB | `soc.py:364` | matches |
| J31 | same, physical | 2048 / 704 KB | 2048 / 704 KB | D28, D29 | matches |
| J32 | same, default gnu window | 2048000 / 716800 B | 2048000 / 716800 B | `nsx-core/apollo3p/gcc/linker_script.ld:10-11` | matches |
| J33 | apollo3 MRAM / RAM, heliaAOT | 1024 / 320 + 64 KB | 1024 / 320 + 64 KB on `apollo3_evb`, `apollo3_blue_evb`, `apollo3_blue_thin_evb` | `platforms.py:300-302`, `:316-318`, `:332-334` | matches |
| J34 | same, helia-profiler | none | no apollo3 SoC is registered | `soc.py` (the registered SoCs start at `:348` with apollo3p) | matches |
| J35 | same, physical | 1024 / 384 KB including TCM | 1024 / 384 KB | D31, D32 | matches |
| J36 | same, default gnu window | 976 / 384 KB flat | `ROMEM` 976K, `RWMEM` 384K | `nsx-core/apollo3/gcc/linker_script.ld:10-11` | matches |
| J37 | apollo4p / apollo4l MRAM, heliaAOT | 2000 KB | 2000 KB on all five Apollo4 boards | `platforms.py:385`, `:397`, `:409`, `:421`, `:433` | matches |
| J38 | same, helia-profiler | 2000 KB | 2000 KB | `soc.py:404`, `:429` | matches |
| J39 | same, physical | 2048 KB | 2048 KB | D21, D24 | matches |
| J40 | same, default gnu window | 1998848 B | 1998848 B (1952 KB) | `nsx-core/{apollo4p,apollo4l}/gcc/linker_script.ld:10` | matches |
| J41 | apollo4p SRAM, heliaAOT | 1024 KB | 1024 KB | `platforms.py:385` | matches |
| J42 | same, helia-profiler | 1024 KB | 1024 KB | `soc.py:404` | matches |
| J43 | same, physical | SSRAM0 1024 + SSRAM1 1024 + EXTRAM 384 KB | the same | D18 to D20 | matches |
| J44 | same, default gnu window | 1024 KB (SSRAM0) | 1048576 B (SSRAM0) | D55 | matches |
| J45 | same, resolution: `zephyr` budget | 2432 KB | 2752 KB | D76 | differs |
| J46 | `apollo510_evb` PSRAM, heliaAOT | 32168 KB (typo) | 32168 KB | `platforms.py:500` | matches |
| J47 | same, helia-profiler | 65536 KB on the SoC | 65536 KB on SoC apollo510 | `soc.py:462` | matches |
| J48 | same, resolution: board region | 65536 KB | 65536 KB from `nsx-psram` and from Zephyr | D36 | matches |
| J49 | PSRAM elsewhere, heliaAOT | none | only `apollo510_evb` declares PSRAM | `platforms.py:500` | matches |
| J50 | apollo330P / apollo510L clocks, heliaAOT | 96/192/250 | 96/192/250 MHz | `platforms.py:454`, `:520` | matches |
| J51 | same, helia-profiler | 96/250 | 96/250 MHz | `soc.py:589-590`, `:659-660` | matches |
| J52 | same, HAL | LP 96, HP1 192, HP2 250 | LP 96, HP1 192, HP2 250 MHz | `mcu/apollo330P/hal/am_hal_pwrctrl.h:218-220`; `mcu/apollo510L/hal/am_hal_pwrctrl.h:218-220` | matches |
| J53 | atomiq110 clocks, heliaAOT | 100/250/500 | 100/250/500 MHz | `platforms.py:587` | matches |
| J54 | same, helia-profiler | 25 (FPGA) | 25 MHz, one speed | `soc.py:721` | matches |
| J55 | same, HAL | 100/250/500 | ULP 100, LP 250, HP 500 MHz | `v5.2.25` `mcu/atomiq110/hal/am_hal_pwrctrl.h:228-230` | matches |
| J56 | same, resolution: board override | 25 | `ATOMIQ11X_FPGA` 25 (MHz); `NSX_SEGGER_CPUFREQ` 25000000 | `v5.2.25` `mcu/atomiq110/am_mcu_apollo.h:87`; `v5.2.25` `cmake/socs/facts/atomiq110.cmake:69` | matches |
| J57 | J-Link, helia-profiler SoC level | apollo4p `AMAP42KP-KBR`, apollo510b `AP510BFA-CBR`, apollo330P `Apollo330P_510L`, apollo510L `AP510L` | the same four strings | `soc.py:418`, `:519`, `:614`, `:671` | matches |
| J58 | J-Link, SDK facts | `AP510NFA-CBR` / `AP330MPA-CBR` / `AP510DLA-CBR` | the same, for apollo510, apollo330P, apollo510L | `cmake/socs/facts/apollo510.cmake:54`; `cmake/socs/facts/apollo330P.cmake:50`; `cmake/socs/facts/apollo510L.cmake:50` | matches |
| J59 | J-Link, neuralspotx board overrides | eight boards, including `AMA4B2KP-KBR`/`-KXR`, `AMA4B2KL-KXR`, `Apollo330P_510L` | eight `debug.cmake` files set `NSX_SEGGER_DEVICE`: `apollo330mP_evb`, `apollo4l_blue_evb`, `apollo4l_evb`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `apollo4p_evb`, `apollo4p_evb_disp_shield_rev2`, `atomiq110_fpga_turbo`, with the four named strings among them | neuralspotx `src/neuralspotx/boards/<board>/debug.cmake:4` (`:7` for `apollo330mP_evb` and the shield) | matches |
| J60 | J-Link names against SEGGER's device list | to be checked | SEGGER's list is not among these sources | none | not checkable from these sources |
| J61 | atomiq110 SWO trace clock, helia-profiler | core-clocked (25) | `swo_trace_clock_mhz` is unset, which means core-clocked; the core clock is 25 MHz | `soc.py:151-157`, `:721` | matches |
| J62 | same, SDK fact | 25 MHz (FPGA) | `NSX_SEGGER_CPUFREQ` 25000000 | `v5.2.25` `cmake/socs/facts/atomiq110.cmake:69` | matches |
| J63 | same, neuralspotx board override, hardware-measured | 48 MHz | `NSX_SEGGER_CPUFREQ` 48000000; the comment says the reset-default trace clock "measures 48 MHz" and was verified on hardware | neuralspotx `src/neuralspotx/boards/atomiq110_fpga_turbo/debug.cmake:6-17` | matches |
| J64 | atomiq110 NPU, heliaAOT | e2e hard-codes the Corstone U55 | the e2e build sets `ethos-u55-128` | helia-aot `tests/e2e/templates/CMakeLists.txt.j2:229`; `tests/e2e/gen/ethos_u_ops.py:20` | matches |
| J65 | same, helia-profiler | `ethos-u85-256` | `ethos-u85-256` | `soc.py:748` | matches |
| J66 | same, HAL NPU modes at `am_hal_pwrctrl.h:219-220` | ULP 100, HP 500 MHz | ULP 100, HP 500 MHz | `v5.2.25` `mcu/atomiq110/hal/am_hal_pwrctrl.h:219-220` (at `v5.2.24` the same enum is at `:226-227`) | matches |
| J67 | same, `nsx-npu` register base | 0x400E0000 | 0x400E0000 | `v5.2.25` `modules/nsx-npu/src/nsx_npu.c:25` | matches |
| J68 | same, IRQ | 117 | `NPU_IRQn = 117` | `v5.2.25` `modules/nsx-ambiqsuite/sdk/CMSIS/AmbiqMicro/Include/atomiq110.h:184`; `v5.2.25` `modules/nsx-npu/README.md:19` | matches |
| J69 | same, Vela configuration | `ethos-u85-256` | `vela --accelerator-config ethos-u85-256` | `v5.2.25` `modules/nsx-npu/README.md:56` | matches |
| J70 | same, MACs per cycle | 256 | the SDK gives only the configuration name, not a MAC count | none | not checkable from these sources |
| J71 | same, dedicated NPU SRAM | none | the atomiq110 header defines DTCM, SSRAM, HBLRAM, RRAM and a virtual region, and no NPU memory; a search of the SDK found no NPU memory define | `v5.2.25` `mcu/atomiq110/regs/am_reg_base_addresses.h:29-54` | matches |
| J72 | `apollo4p_evb` PSRAM, heliaAOT | none | none | `platforms.py:385` | matches |
| J73 | same, helia-profiler | 32768 KB | 32768 KB | helia-profiler `src/helia_profiler/platform/board.py:93` | matches |
| J74 | same, neuralspotx README: the plain EVB has no PSRAM; the Display Kit shield adds an APS25616N | no PSRAM on the plain EVB | the same; the statement is in the shield board's README, and `nsx-psram` agrees | neuralspotx `src/neuralspotx/boards/apollo4p_evb_disp_shield_rev2/README.md:7-9`; `nsx-psram/CMakeLists.txt:31-38` | matches |
| J75 | `apollo510l_evb`, heliaAOT | present | present | `platforms.py:518` | matches |
| J76 | `apollo510dL_evb`, helia-profiler | present | present | `board.py:183` | matches |
| J77 | one EVB (AP510DLEVB) for the Lite series | one board | a datasheet fact; neuralspotx has `apollo510dL_evb` and no `apollo510l_evb` | neuralspotx `src/neuralspotx/boards/` listing | not checkable from these sources |

## Disagreements

### Rows that differ

- **D35, Apollo4 board PSRAM.** The appendix gives 32768 KB to all five Apollo4 boards and questions only the plain `apollo4p_evb`. nsx-ambiq-sdk `v5.2.24` `modules/nsx-psram/CMakeLists.txt:31-38` says the plain and Blue apollo4l and apollo4p EVBs do not populate PSRAM, and stops at configure for any Apollo4 board except `apollo4p_evb_disp_shield_rev2`. #29 tracks the same correction.
- **D39, `apollo330mP_evb` PSRAM.** The appendix follows the SDK, and the board guide contradicts both. The board's BSP defines the PSRAM presence macro (`modules/nsx-ambiqsuite/sdk/boards/apollo330mP_evb/bsp/am_bsp.h:134`, `:136`), and `nsx-psram/CMakeLists.txt:130-137` builds the BA driver for the board with the 32 MB default (`:150-152`), which its comment calls conservative because the board has not been validated on hardware. The Apollo330 Plus EVB guide says PSRAM U14 is not populated on all revision 2.0 boards ([datasheets.md](datasheets.md) lines 300 and 313, QS-A330MP p8, p10, p30), and the owner statement at line 348 agrees. RFC 0002 lists the board's PSRAM as a pending data correction ([0002-migration.md](../rfcs/0002-migration.md) line 33). The catalogue should follow the guide and give the board no PSRAM. Unlike D40, `nsx-psram` configures a 32 MB device for this board without extra options. helia-profiler carries the same 32 MB (see the table below).
- **D40, `apollo510dL_evb` PSRAM.** The SDK treats this board as populated. Its BSP defines the PSRAM presence macro (`modules/nsx-ambiqsuite/sdk/boards/apollo510dL_evb/bsp/am_bsp.h:150`, `:152`), and `nsx-psram/CMakeLists.txt:60-64` says every staged Apollo5-class EVB carries an APS512-class PSRAM, with 32 MB as the default size (`:150-152`). The Apollo510 Lite EVB guide says the PSRAM footprint is unpopulated on all revision 2.0 boards ([datasheets.md](datasheets.md), QS-A510DL p8, p10, p30). The appendix's "none" agrees with the guide, and the catalogue should not follow the SDK here. `nsx-psram` stops at configure for this board until a driver is chosen explicitly (`:138-141`), so the SDK's claim does not reach a build by default.
- **Apollo3 Plus PSRAM (D33 and D34 match).** `nsx-psram` builds the 8 MB APS6404L driver for both `apollo3p_evb` and `apollo3p_evb_cygnus` (`nsx-psram/CMakeLists.txt:22-29`). Building the driver does not show that the part is fitted; #29 records the BSP evidence for each board.
- **D49, the 16 KB above the Apollo5 gcc window.** The size is right (D48), but the gcc scripts do not reserve it for the stack and heap. `.stack` and `.heap` are inside `MCU_TCM`, so the 496 KB window also holds the stack and heap, and the top 16 KB is in no linker region. The armclang scatter files do put the heap and stack at the top (D50). helia-aot's comment at `helia_aot/platforms/platforms.py:479-480` repeats the gcc description. No budget changes; only the explanation is wrong.
- **D75, D76 and J45, Zephyr `apollo4p_evb`.** At zephyr `d8be6be` the board has a 64 KB `ITCM` region and 2752 KB of SRAM at 0x10010000, not 384 KB of TCM and 2432 KB of SRAM, which would start at 0x10060000. The totals agree (2816 KB), but the split does not: a `zephyr` budget built from the appendix would offer 320 KB more TCM than Zephyr's `ITCM` region holds. No revision of `dts/arm/ambiq/ambiq_apollo4p.dtsi` reachable from `d8be6be` gives a 384 KB TCM. Since the TCM node was split out (`d873a1a335d`), every revision has `tcm` `<0x10000000 0x10000>` and `sram0` `<0x10010000 0x2b0000>`; before that, the file had one `sram0` `<0x10000000 0x2C0000>`. The appendix's split matches no Zephyr revision.
- **J1, J5, J21 and J25, heliaAOT's recorded Apollo5 sizes.** The appendix records heliaAOT before AmbiqAI/helia-aot#540 moved `apollo510_evb` and `apollo510b_evb` to the gnu window (496 KB DTCM, 4032 KB MRAM) and AmbiqAI/helia-aot#554 did the same for `apollo330mp_evb` and `apollo510l_evb` (240 KB, 1984 KB). The #28 decision has heliaAOT budget on-chip RAM at physical size and NVM from `usable_nvm()`, not from linker windows. J1 and J21 are therefore parity allow-list rows that the adoption changes: DTCM goes to the physical 512 KB and 256 KB. J25 is one too: MRAM goes to 1589248 B, the application NVM on the fitted parts. J5's 4128768 B is the value #28 keeps. J9 (atomiq110 DTCM 496 KB), J29 and J33 (Apollo3 MRAM 2048 and 1024 KB), J37 (Apollo4 MRAM 2000 KB) and J41 (apollo4p SRAM 1024 KB) record heliaAOT correctly, but they are #28 allow-list rows as well.

### Consumer values the sources contradict

These are current helia-aot (`1fd91daf`) and helia-profiler (`ed2f0a15`) values that disagree with nsx-ambiq-sdk, neuralspotx or Zephyr at the pinned revisions, or with a board guide recorded in [datasheets.md](datasheets.md), or that use a linker window where the physical size differs. The appendix records most of them correctly; they are listed here because they are the changes the adoption has to make.

| Consumer | Value | Sources say | Effect |
| --- | --- | --- | --- |
| helia-aot, all five Apollo4 boards (`platforms.py:385-433`); helia-profiler apollo4p and apollo4l (`soc.py:404`, `:429`) | MRAM 2000 KB | 2048 KB physical (D21, D24); 1952 KB gnu window (J40) | 2000 KB matches no source. #28 sets heliaAOT to usable NVM, 1998848 B (1952 KB), which on Apollo4 equals the gnu window. |
| helia-aot `apollo3p_evb`, `apollo3_blue_plus_evb` (`platforms.py:348`, `:365`); `apollo3_evb`, `apollo3_blue_evb`, `apollo3_blue_thin_evb` (`:300`, `:316`, `:332`) | MRAM 2048 KB and 1024 KB, the whole flash | flash includes the 48 KB bootloader region (D44); the gnu windows are 2048000 and 999424 B (J32, J36) | #28 sets heliaAOT to usable NVM, 2048000 B and 999424 B. |
| helia-aot `apollo510_evb` (`platforms.py:500`) | PSRAM 32168 KB | 65536 KB (D36) | The planner is offered 33368 KB less PSRAM than the board has. |
| helia-aot `apollo4p_evb`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb` (`platforms.py:385`, `:397`, `:409`); helia-profiler apollo4p (`soc.py:404`) | SRAM 1024 KB | physical SSRAM0 1024 + SSRAM1 1024 + EXTRAM 384 = 2432 KB (D18 to D20); 1024 KB is the gnu window (D55) | Under #28, heliaAOT budgets the 2432 KB physical total. |
| helia-profiler apollo3p (`soc.py:364`) | MRAM 2000 KB, SRAM 700 KB | physical 2048 KB flash and 704 KB SRAM (D28, D29); 2000 and 700 KB are the gnu window (J32) | The value is the linker window, not the physical size. |
| helia-profiler, five Apollo4 boards (`board.py:93`, `:104`, `:115`, `:128`, `:141`) | PSRAM 32768 KB | none populated (D35) | Tracked in #29. |
| helia-profiler `apollo330mP_evb` (`board.py:171-178` sets no `psram_kb`, so `registry.py:87-88` keeps the apollo330P value at `soc.py:583`) | PSRAM 32768 KB | `nsx-psram` agrees (D39); the board guide says none is fitted on revision 2.0 ([datasheets.md](datasheets.md), QS-A330MP p8, p10, p30) | Listed in RFC 0002's pending data corrections ([0002-migration.md](../rfcs/0002-migration.md) line 33). |
| helia-profiler AP4 family (`capabilities.py:281`) | PSRAM placement base 0x60000000 | Apollo4 MSPI0 aperture starts at 0x14000000 (`mcu/apollo4p/regs/am_reg_base_addresses.h:83`; `mcu/apollo4l/regs/am_reg_base_addresses.h:89`) | Outside D and J; raised in the issue discussion. Since `nsx-psram` refuses to configure on these boards (D35), a PSRAM placement there probably fails at build time before the base is used. Not traced through the profiler's build. |
| helia-profiler apollo330P and apollo510L (`soc.py:589-590`, `:659-660`) | clocks 96/250 MHz | the HAL also has HP1 at 192 MHz (J52) | An omitted operating point, not a wrong value. |
| helia-profiler atomiq110 (`soc.py:721`) | SoC clock 25 MHz | the HAL's MCU modes are 100/250/500 MHz (J55); 25 MHz is the FPGA build's clock (J56) | The value is right for the only atomiq110 board, but it sits on the SoC rather than the board. |
| helia-profiler apollo510b, apollo510L, apollo330P (`soc.py:519`, `:671`, `:614`) | J-Link `AP510BFA-CBR`, `AP510L`, `Apollo330P_510L` | SDK SoC facts `AP510NFA-CBR` (`cmake/socs/facts/apollo510b.cmake:52`), `AP510DLA-CBR`, `AP330MPA-CBR`; neuralspotx's `apollo330mP_evb` override agrees with the profiler | J-Link names are outside the drift test (appendix G). They are listed for completeness, and J60 still applies to them. |

Both consumers mix two kinds of size in one field, although each value matches a source. helia-aot uses the gnu window for the Apollo5 parts and atomiq110's DTCM, and the physical size for apollo3p (2048 and 704 KB). helia-profiler uses the physical size for apollo510, apollo510b and apollo5b (512 and 4096 KB) and the gnu window for apollo330P, apollo510L, atomiq110 and apollo3p.

## Not checkable from these sources

| Row | Fact | Where it could be checked |
| --- | --- | --- |
| D38 | `apollo5b_evb` PSRAM 32768 KB | no document for apollo5b exists in [datasheets.md](datasheets.md) either |
| D57, D59 | legacy neuralSPOT linker windows | a legacy neuralSPOT checkout at a named revision |
| J60 | J-Link names against SEGGER's device list | SEGGER's device database |
| J70 | 256 MACs per cycle for `ethos-u85-256` | Arm's Ethos-U85 or Vela documentation |
| J77 | one Apollo510 Lite EVB | the board guide, as recorded in [datasheets.md](datasheets.md) |
