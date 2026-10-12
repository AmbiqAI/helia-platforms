# AmbiqSuite: boot layout and board external memories

Source: AmbiqSuite (internal SWS repository) (SWS AmbiqSuite)
Revision: stable b015b860da
Read on: 2026-10-04
Method: gatherer read of linker scripts, tools/ and boards/*/bsp. File:line
references as reported; spot-check before citing in the catalog.

## Boot layout

AmbiqSuite ships both a no-bootloader (nbl) and a secure-bootloader (sbl)
linker variant per SoC. Examples default to sbl.

| SoC | nbl app origin | sbl app origin | Example |
|---|---|---|---|
| Apollo3 | 0x00000000 | 0x0000C000 | per-family example scripts |
| Apollo4 | 0x00000000 | 0x00018000 | boards/common4/examples/graphics/nemagfx_enhanced_stress_test/linker_script.sbl.ld:10 (LENGTH 1998848) |
| Apollo510 | 0x00400000 (LENGTH 4194304) | 0x00410000 (LENGTH 4128768) | boards/common5/examples/graphics/nemagfx_enhanced_stress_test/linker_script.{nbl,sbl}.ld |
| Apollo510L | 0x00400000 (LENGTH 2097152) | 0x00410000 | tests/testcases/apollo510L/nemagfx_tests/nemagfx_enhanced_stress_test_cases/linker_script.nbl.ld:10 |

- Provisioning tools per family under tools/apollo{3,4,510,510L}_scripts:
  create_info0.py (INFO0 generation), create_cust_image_blob.py (images
  for the Ambiq SBL), uart_wired_update.py, sbl_updates/ (field updates of
  the Ambiq SBL) per tools/apollo510_scripts/README.txt:14-26.
- tools/apollo3_scripts and apollo4_scripts am_defines.py set
  AM_SECBOOT_DEFAULT_NONSECURE_MAIN = 0xC000; Apollo4 linker scripts use
  0x18000.
- The Apollo510L nbl script runs to 0x00600000, so AmbiqSuite, like
  nsx-ambiq-sdk, does not reserve the NVM-M41 radio firmware region the
  Lite datasheet shows (see datasheets.md section 3).
- Not found: a documented procedure to run an nbl image on a part whose
  SBL is provisioned. The gatherer's summary asserted an INFO0 bypass but
  its evidence did not show one; treat as unverified.

## Board external memories

BSPs declare the driver and interface for external memories
unconditionally; a declaration means the board supports the device, not
that it is populated.

| Board dir | PSRAM device | NOR / NAND | eMMC |
|---|---|---|---|
| apollo510_evb | APS25616BA | IS25WX064 | yes |
| apollo330mP_evb | APS25616N (octal DDR) | IS25WX064 | yes |
| apollo510L_eb | APS25616N (MSPI) + APS12804O (IOM 4) | IS25WX064 | yes |
| apollo4p_evb_disp_shield_rev1 | APS12808L | ATXP032 | no |
| apollo4p_evb_disp_shield_rev2 | APS25616N | IS25WX064 | no |
| apollo4l_evb_disp_shield, apollo4l_blue_evb_disp_shield, apollo4b_evb_disp_shield | APS25616N / APS12808L | varies | no |
| apollo3p_evb | none | none | no |
| apollo5b_eb_revb | APS25616N | TC58CYG0 (NAND) | yes |
| apollo510L_fpga_turbo and one further FPGA BSP | APS25616N | IS25WX064 / ATXP032 | yes |

- Shields are separate board directories ({evb}_disp_shield_rev{N}), each
  with a full BSP. There is no add-on or daughter-board mechanism.
- FPGA realizations have board directories (BSPs) for apollo510L and one
  further unreleased SoC in addition to atomiq110. RFC 0002 models each as
  an Implementation of kind `fpga`, not as a board.

## atomiq110 FPGA (`boards/atomiq110_fpga_turbo`)

Read at the revision above (stable b015b860da) by a gatherer; paths are
repository-relative; the gatherer gave the BSP files by name, and their
`boards/atomiq110_fpga_turbo/bsp/` directory follows AmbiqSuite's layout.
Not spot-checked in this pass.

| Fact | Source |
|---|---|
| The board directory exists, `FAMILY` atomiq110 | `boards/atomiq110_fpga_turbo/board-defs.mk:1-3` |
| `ATOMIQ11X_FPGA` must be set to the loaded FPGA image's designated frequency in MHz (12 and 48 given as examples); the default is 25 MHz; FPGA HFRC rates derive from 50 MHz divisions. The clock is therefore a property of the FPGA image loaded, matched by a firmware build define | `mcu/atomiq110/am_mcu_apollo.h:63-64` (image frequency rule and examples), `:70-71` (50 MHz divisions), `:86` (default 25) |
| The BSP sets the FPGA clock at initialisation | `boards/atomiq110_fpga_turbo/bsp/am_bsp.c:210-218` |
| "FPGA supports only IOM0 and 1" | `boards/atomiq110_fpga_turbo/bsp/am_bsp.c:1177-1179` |
| J-Link device `ATOMIQ110`; flash addresses the same as silicon | `tools/atomiq110_scripts/jlink-ota.txt:24` (device), 34 and 38 (addresses) |
| Memory map: DTCM 0x20000000 (512 KB), SSRAM 0x21000000 (3 MB), RRAM 0x22000000 (4 MB), HBLRAM 0x60000000 | `mcu/atomiq110/regs/am_reg_base_addresses.h:28-47` |
| External memory declared by the BSP: PSRAM APS25616N, MSPI NOR IS25WX064 on MSPI2, NAND on MSPI0 | `boards/atomiq110_fpga_turbo/bsp/am_bsp.h:135-152` |

- The FPGA uses the same addresses as the atomiq110 register header; there
  is no rebasing of SSRAM or RRAM relative to silicon.
- Not documented: the bitstream, the FPGA platform, or a carrier board
  model. Whether HBLRAM at 0x60000000 is on-die or external on the FPGA is
  not stated.
- Owner statement (2026-10-04, not a document): the FPGA mirrors atomiq110
  at roughly one tenth of the silicon clock; it runs at 25 MHz, possibly
  50 MHz; the clock can be adjusted after flashing.

## Conflicts to resolve

| Item | Source A | Source B |
|---|---|---|
| apollo510_evb PSRAM device | BSP: APS25616BA | Resolved: 64 MB, hardware-validated 2026-07-05 on apollo510_evb and apollo510b_evb (nsx-ambiq-sdk `modules/nsx-psram/CMakeLists.txt:60-125` (last changed in a1a0df1)). `APS25616BA` names the 1.2 V "BA" driver family, not the capacity; neither BSP macros nor part markings are evidence of size |
| apollo330mP_evb PSRAM | BSP declares APS25616N | rev 2.0 guide and owner: not populated |
| apollo4p_evb PSRAM | profiler: 32 MB | guides and AmbiqSuite: only on the display shield board |
| atomiq110 FPGA PSRAM interface | `am_bsp.h` references IOM2 for PSRAM | `am_bsp.c:1177-1179`: the FPGA supports only IOM0 and IOM1 |
| atomiq110 J-Link device spelling | AmbiqSuite `jlink-ota.txt:24`: `ATOMIQ110` | neuralspotx `boards/atomiq110_fpga_turbo/debug.cmake`: `Atomiq110`; no source says J-Link matches names case-insensitively (issue #19) |

Capacities inferred from part names are not evidence. The apollo510 and
apollo510b EVB PSRAM is settled by hardware measurement; apollo330mP_evb
tracks apollo510b_evb for the driver choice by product-team guidance but is
not validated, and apollo510dL_evb is undecided.
