# AmbiqSuite: boot layout and board external memories

Source: AmbiqSuite (internal SWS repository) (SWS AmbiqSuite)
Revision: stable b015b860da
Read on: 2026-10-04
Method: gatherer read of linker scripts, tools/ and boards/*/bsp. File:line
references as reported; spot-check before citing in the catalogue.

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
| apollo510L_fpga_turbo and one further FPGA board | APS25616N | IS25WX064 / ATXP032 | yes |

- Shields are separate board directories ({evb}_disp_shield_rev{N}), each
  with a full BSP. There is no add-on or daughter-board mechanism.
- FPGA realizations exist as boards for apollo510L and one further unreleased SoC in
  addition to atomiq110.

## Conflicts to resolve

| Item | Source A | Source B |
|---|---|---|
| apollo510_evb PSRAM device | BSP: APS25616BA | Resolved: 64 MB, hardware-validated 2026-07-05 on apollo510_evb and apollo510b_evb (nsx-ambiq-sdk `modules/nsx-psram/CMakeLists.txt:60-125` (last changed in a1a0df1)). `APS25616BA` names the 1.2 V "BA" driver family, not the capacity; neither BSP macros nor part markings are evidence of size |
| apollo330mP_evb PSRAM | BSP declares APS25616N | rev 2.0 guide and owner: not populated |
| apollo4p_evb PSRAM | profiler: 32 MB | guides and AmbiqSuite: only on the display shield board |

Capacities inferred from part names are not evidence. The apollo510 and
apollo510b EVB PSRAM is settled by hardware measurement; apollo330mP_evb
tracks apollo510b_evb for the driver choice by product-team guidance but is
not validated, and apollo510dL_evb is undecided.
