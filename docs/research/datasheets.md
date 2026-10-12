# Ambiq SoC datasheets and EVB quick-start guides

| Field | Value |
| --- | --- |
| Source | Ambiq internal datasheet library (`soc/ap2` to `soc/ap5`, `evb/`) |
| Read on | 2026-10-04 |
| Method | pypdf text extraction with decryption of the permissions wrapper; layout extraction used for one table (the Cortex-M55 memory map and ordering table of the Apollo510 Lite and Apollo330 Plus datasheets) |
| Atomiq110 | No atomiq110 datasheet is present in the folder |

This note records what Ambiq's own datasheets and EVB quick-start guides say. The datasheets are the source of record for silicon and board numbers; this note is a page-cited summary of them. Catalog values should cite the document and PDF page given here, not another repo. Every citation is `<document key> p<N>`, where N is the PDF page index (1-based). For the datasheets the PDF page index matches the printed "Page N of M" footer. Document keys are defined in the inventory. Quotes are kept short and exact; anything that is arithmetic on a datasheet value is marked "computed".

## 1. Inventory

29 PDFs. SHA256 is the first 16 hex characters of the file hash, recomputed with `shasum -a 256` on the read date.

| Key | Path (under the source folder) | Document id, revision, date | Pages | SHA256 (16) |
| --- | --- | --- | --- | --- |
| DS-A510 | `soc/ap5/Apollo510-SoC-Datasheet.pdf` | DS-A510-1p1p0, 1.1.0, May 2026 | 302 | d73b34121df6cc09 |
| DS-A510 | `evb/Apollo510-SoC-Datasheet-v1_1_0.pdf` | duplicate of the above | 302 | d73b34121df6cc09 |
| DS-A510B | `soc/ap5/Apollo510B-SoC-Datasheet.pdf` | DS-A510B-1p1p0, 1.1.0, June 2026 | 266 | 892c109be268ab72 |
| DS-A510B | `evb/Apollo510B-SoC-Datasheet-v1_1_0.pdf` | duplicate of the above | 266 | 892c109be268ab72 |
| DS-A510LS | `soc/ap5/Apollo510-Lite-Series-Datasheet.pdf` | DS-A510LS-0p9p0, 0.9.0, July 2026 | 258 | 1cd7cfe5a1b60aeb |
| DS-A330PS | `soc/ap5/Apollo330-Plus-Series-DataSheet.pdf` | DS-A330PS-0p9p0, 0.9.0, July 2026 | 247 | 8793d3861a065c5d |
| DS-A4 | `soc/ap4/Apollo4-SoC-Datasheet.pdf` | DS-A4-1p5p0, 1.5.0, December 2025 | 230 | 326eecc05429c5e2 |
| DS-A4B | `soc/ap4/Apollo4-Blue-Datasheet.pdf` | DS-A4B-1p5p0, 1.5.0, December 2025 | 229 | e6e8b1144693eae5 |
| DS-A4P | `soc/ap4/Apollo4-Plus-SoC-Datasheet.pdf` | DS-A4P-1p6p0, 1.6.0, February 2025 | 247 | a16d4cd2bef867a0 |
| DS-A4BP | `soc/ap4/Apollo4-Blue-Plus-SoC-Datasheet.pdf` | DS-A4BP-1p8p0, 1.8.0, February 2025 | 258 | 6da2694a21e0ddde |
| DS-A4BP | `evb/Apollo4-Blue-Plus-SoC-Datasheet-v1_8_0.pdf` | duplicate of the above | 258 | 6da2694a21e0ddde |
| DS-A4L | `soc/ap4/Apollo4-Lite-Datasheet.pdf` | DS-A4L-0p9p1, 0.9.1, July 2023 | 185 | e9bc398995b17c69 |
| DS-A4BL | `soc/ap4/Apollo4-Blue-Lite-Datasheet.pdf` | DS-A4BL-0p9p0, 0.9.0, July 2023 | 189 | 72df1d74f61871d3 |
| DS-A3 | `soc/ap3/Apollo3-Blue-SoC-Datasheet.pdf` | DS-A3-1p3p0, 1.3.0, Feb 2024 (covers Apollo3 and Apollo3 Blue, includes Apollo3 Blue Thin) | 960 | c2337f251ab96a24 |
| DS-A3 | `evb/Apollo3-Blue-SoC-Datasheet-v1_3_0.pdf` | duplicate of the above | 960 | c2337f251ab96a24 |
| DS-A3P | `soc/ap3/Apollo3-Blue-Plus-SoC-Datasheet.pdf` | DS-A3P-1p3p0, 1.3.0, October 2022 | 1037 | 822a526ca108ff92 |
| DS-A3P | `evb/Apollo3-Blue-Plus-SoC-Datassheet-v1_3_0.pdf` (sic) | duplicate of the above | 1037 | 822a526ca108ff92 |
| DS-A2 | `soc/ap2/Apollo2-SoC-Datasheet.pdf` | A-SOCAP2-DSGA01EN v1.3, March 2023 (revision history p4) | 510 | 50a8493278e1ab44 |
| DA-A2 | `soc/ap2/Apollo2-SoC-Flash-Programming-Helper-Functions-Datasheet-Addendum.pdf` | DA-A2-1p1, 1.1, November 22, 2023 (p3) | 22 | 30a0cc6508d4399f |
| QS-A510 | `evb/Apollo510-EVB-Quick-Start-Guide-v2.1.pdf` | QS-A510-2p1, 2.1, November 2025; EVB revision 2.2 | 24 | 4350d3f28bf41a66 |
| QS-A510B | `evb/Apollo510B-EVB-Quick-Start-Guide-v1.1-2.pdf` | QS-A510B-1p1, 1.1, November 2025; EVB revision 2.0 | 26 | d3b5c54e7762ae7f |
| QS-A510DL | `evb/Apollo510-Lite-EVB-Quick-Start-Guide-v2.0.pdf` | QS-A510DL-2p0, 2.0, June 2026; EVB revision 2.0 | 32 | 268bf8b6ff2bebe1 |
| QS-A330MP | `evb/Apollo330-Plus-EVB-Quick-Start-Guide-v2.0.pdf` | QS-A330MP-2p0, 2.0, June 2026; EVB revision 2.0 | 32 | 3ed362a2ef243b7d |
| QS-A4P | `evb/Apollo4-Plus-EVB-Quick-Start-Guide.pdf` | QS-A4P-1p5, 1.5, December 2025; "All EVB Revisions" | 22 | c8b7a803582466ec |
| QS-A4PDK | `evb/Apollo4-Plus-Display-Kit-Quick-Start-Guide.pdf` | QS-A4PDK-1p2, 1.2, March 2023; shield board revision 1 | 19 | c304d267be211669 |
| QS-A4BP | `evb/Apollo4-Blue-Plus-KBR-EVB-rev1-Quick-Start-Guide-v1p4.pdf` | QS-A4BP_KBR-1p4, 1.4, December 2025; EVB revision 1.0 | 22 | def3e953943305f2 |
| QS-A4 | `evb/Apollo4-EVB-rev3-Quick-Start-Guide-v4p2.pdf` | QS-A4-4p2, 4.2, December 2025; EVB revision 3 | 21 | d91f289df8374f46 |
| QS-A4 | `evb/Apollo4-EVB-rev3-Quick-Start-Guide-v4p2-2.pdf` | duplicate of the above | 21 | d91f289df8374f46 |
| QS-A3BP | `evb/Apollo3-Blue-Plus-EVB-Quick-Start-Guide.pdf` | A-SOCA3P-QSGA01EN v1.2, September 14, 2022 (p3); EVB revision 1.0 | 17 | 4f7036fda707c8fe |

Duplicates, checked by comparing SHA256 lines and by diffing the extracted text (identical apart from the `SOURCE:` line):

| `evb/` copy | Same file as | SHA256 (16) |
| --- | --- | --- |
| `Apollo510-SoC-Datasheet-v1_1_0.pdf` | `soc/ap5/Apollo510-SoC-Datasheet.pdf` | d73b34121df6cc09 |
| `Apollo510B-SoC-Datasheet-v1_1_0.pdf` | `soc/ap5/Apollo510B-SoC-Datasheet.pdf` | 892c109be268ab72 |
| `Apollo3-Blue-Plus-SoC-Datassheet-v1_3_0.pdf` | `soc/ap3/Apollo3-Blue-Plus-SoC-Datasheet.pdf` | 822a526ca108ff92 |
| `Apollo3-Blue-SoC-Datasheet-v1_3_0.pdf` | `soc/ap3/Apollo3-Blue-SoC-Datasheet.pdf` | c2337f251ab96a24 |
| `Apollo4-Blue-Plus-SoC-Datasheet-v1_8_0.pdf` | `soc/ap4/Apollo4-Blue-Plus-SoC-Datasheet.pdf` | 6da2694a21e0ddde |
| `Apollo4-EVB-rev3-Quick-Start-Guide-v4p2-2.pdf` | `evb/Apollo4-EVB-rev3-Quick-Start-Guide-v4p2.pdf` | d91f289df8374f46 (byte-identical, not only identical text) |

That leaves 23 distinct documents. DS-A510LS and DS-A330PS are revision 0.9.0 (preliminary); DS-A4L and DS-A4BL are also pre-1.0.

## 2. Boot and NVM partitioning by family

### Apollo510 and Apollo510B

| Fact | Value | Source |
| --- | --- | --- |
| NVM-SBL | 0x00400000-0x0040FFFF, "NVM reserved for Secure Boot Loader (64 kB)" | DS-A510 p35; DS-A510B p34 |
| NVM0-APPL | 0x00410000-0x005FFFFF, "NVM0 for application (1.94 MB)" | DS-A510 p35; DS-A510B p34 |
| NVM1-APPL | 0x00600000-0x007FFFFF, "NVM1 for application (2 MB)" | DS-A510 p35; DS-A510B p34 |
| Boot Loader ROM | 0x02000000-0x0201FFFF, 128 kB | DS-A510 p35; DS-A510B p34 |
| Boot ROM role | "initiates the secure boot flow, if enabled" | DS-A510 p29; DS-A510B p28 |
| SBL is factory-installed | an erratum workaround "is implemented in the pre-installed SBL" | DS-A510 p60; DS-A510B p58 |
| Boot flow | "Secure Boot (SBR+SBL) always runs in Secure Execution Mode" | DS-A510 p53; DS-A510B p51 |
| SBL SWO | SBL uses GPIO28 as SWO output (1 Mbaud) during boot | DS-A510 p85; DS-A510B p91 |

### Apollo510 Lite series and Apollo330 Plus series

Both datasheets carry the same Cortex-M55 memory map (Table 4) on p33. There is no NVM-SBL row. The code region 0x00000000-0x003BFFFF is reserved, so there is no ITCM.

| Fact | Value | Source |
| --- | --- | --- |
| RS TCM RAM | 0x003C0000-0x003CFFFF, "Radio subsystem TCM RAM (64 kB)" | DS-A510LS p33; DS-A330PS p33 |
| NVM-APPL | starts at 0x00400000; end address per variant (table below); "NVM for Cortex-M55/System Software" | DS-A510LS p33; DS-A330PS p33 |
| NVM-M41 | from the end of NVM-APPL to 0x005FFFFF; "NVM for Cortex-M4 Firmware" | DS-A510LS p33; DS-A330PS p33 |
| Reserved | 0x00600000 upward (printed as "0x00600000 - 0x01FFFFF", digit missing in the source) | DS-A510LS p33; DS-A330PS p33 |
| Boot Loader ROM | 0x02000000-0x0201FFFF, 128 kB | DS-A510LS p33; DS-A330PS p33 |
| Boot ROM role | "initiates the secure boot flow, if enabled" | DS-A510LS p26; DS-A330PS p26 |
| SBL SWO | SBL uses GPIO28 as SWO output (1 Mbaud) during boot | DS-A510LS p86; DS-A330PS p86 |
| M4 firmware footnote | "Factory-installed Cortex-M4 firmware reduces the amount of available NVM" | DS-A510LS p2, p254; DS-A330PS p2, p243 |

| Variant | NVM-APPL | NVM-APPL size (computed) | NVM-M41 | NVM-M41 size (computed) | Datasheet note on M41 |
| --- | --- | --- | --- | --- | --- |
| Apollo510 Lite / Apollo330 Plus | 0x00400000-0x005FBFFF | 2032 KB | 0x005FC000-0x005FFFFF | 16 KB | none |
| Apollo510B Lite / Apollo330B Plus | 0x00400000-0x005B7FFF | 1760 KB | 0x005B8000-0x005FFFFF | 288 KB | "BLE-only code" |
| Apollo510D Lite / Apollo330M Plus | 0x00400000-0x00593FFF | 1616 KB | 0x00594000-0x005FFFFF | 432 KB | "Bluetooth Dual Mode: BR/EDR+ BLE" |

Row labels: the plain extraction and the layout extraction of p33 both label the rows "(510 Lite)", "(510B Lite)", "(510D Lite)" in DS-A510LS and "(330 Plus)", "(330B Plus)", "(330M Plus)" in DS-A330PS. Both labelings were confirmed.

### Apollo4 family

| Datasheet | Secure boot is OTP-enabled ("SECBOOTONRST configuration in OTP") | Secure Boot section | Points to | Application start address |
| --- | --- | --- | --- | --- |
| DS-A4 | p70 | p93 | "Apollo4 Family Security User's Guide" p94 | not stated |
| DS-A4B | p62 | p86 | "Apollo4 Family Security User's Guide" p87 | not stated |
| DS-A4P | p70 | p94 | "Apollo4 Family Security User's Guide" p95 | not stated |
| DS-A4BP | p67 | p92 | "Apollo4 Family Security User's Guide" p93 | not stated |
| DS-A4L | p60 | p82 | "separate Security document(s)" p82 | not stated |
| DS-A4BL | p57 | p80 | "separate Security document(s)" p80 | not stated |

The Apollo4 datasheets also state the following:

- The boot ROM transfers control once "a valid reset vector is establish at offset zero in the NVM" (DS-A4P p70; same text in DS-A4 p70, DS-A4L p60, DS-A4BL p57).
- The memory map is the Arm architecture-level map only: 0x00000000-0x1FFFFFFF is "Internal NVM (NVM)" (DS-A4P p60; DS-A4 p60; DS-A4B p52; DS-A4BP p57; DS-A4L p50; DS-A4BL p47).
- None of the six datasheets reserves an SBL region or gives a boot ROM address. The strings 0xC000 and 0x18000 do not appear in any Apollo4 or Apollo3 datasheet.

### Apollo3 Blue, Apollo3 Blue Plus, Apollo2

| Fact | Apollo3 Blue (DS-A3) | Apollo3 Blue Plus (DS-A3P) | Apollo2 (DS-A2) |
| --- | --- | --- | --- |
| Boot Loader ROM | 0x08000000-0x08000FFF (4 kB), "Execute Only Boot Loader and Flash Helper Functions" p78 | same range p82 | same range p68 |
| Flash map | 0x00000000-0x000FFFFF p78 | 0x00000000-0x001FFFFF p82 | 0x00000000-0x000FFFFF p68 |
| Secure boot enablement | OTP SECBOOTONRST p169; BOOTLOADER register (0x400201A0) fields SECBOOTONRST, SECBOOT, SECBOOTFEATURE p147; INFO0 SECBOOT field p857 | same text p177; register p151-152; INFO0 p932 | no secure boot or SECBOOT text in the datasheet; INFO0 SECURITY word has BOOTLOADER_AT_RESET p506; DA-A2 p17 mentions "a secure boot loader in flash instance 0" |
| Bootloader visibility at 0x00000000 | BOOTLOADERLOW field, "ADDR0 = 0x1 - Bootloader code at 0x00000000" p148 | p152 | BOOTLOADERLOW register at 0x400201A0 p120 |
| Hand-off | "valid reset vector ... at offset zero in the flash memory" p169 | p177 | p126 |
| Application start address | not stated | not stated | not stated |

### EVB guides on provisioning

| Guide | Ships with | Examples linked at | SBL UART pins | Override pin | Source |
| --- | --- | --- | --- | --- | --- |
| QS-A510 | SBL and INFO0 pre-programmed; default boot non-secure | 0x410000 | UART0 on GPIO30 and GPIO55; 115200 bps; 5 s timeout | GPIO93, Button 0 (SW2) | p7, p12 |
| QS-A510B | SBL and INFO0 pre-programmed; default boot non-secure | 0x410000 | UART1 on GPIO12 and GPIO14; 115200 bps; 5 s timeout | GPIO46, Button 0 (SW2) | p7, p13 |
| QS-A510DL | "preprogrammed with a Secure Bootloader" and uninitialised INFO0 | 0x410000 | not stated | not stated | p7, p13 |
| QS-A330MP | "preprogrammed with a Secure Bootloader" and uninitialised INFO0 | 0x410000 | not stated | not stated | p7, p13 |
| QS-A4P | SBL and INFO0 pre-programmed; default boot non-secure | not stated | UART on GPIO47 and GPIO60; 115200 bps; 3 s timeout | GPIO18, BTN0/SW1 | p10-11 |
| QS-A4PDK | same as QS-A4P | not stated | UART on GPIO47 and GPIO60; 115200 bps; 3 s timeout | GPIO18, BTN0/SW1 | p13 |
| QS-A4BP | SBL and INFO0 pre-programmed; default boot non-secure | not stated | UART on GPIO47 and GPIO60; 115200 bps; 3 s timeout | GPIO18, BTN0/SW1 | p10-11 |
| QS-A4 | SBL and INFO0 pre-programmed; default boot non-secure | not stated | UART on GPIO47 and GPIO60; 115200 bps; 3 s timeout | GPIO18, BTN0/SW1 | p10 |
| QS-A3BP | SBL and INFO0 pre-programmed | not stated | UART on GPIO22 and GPIO23; baud not stated | GPIO16, BTN1 | p8 |

The QS-A510DL and QS-A330MP guides do not state the SBL UART or override pins. They refer to the README in `tools\apollo510L_scripts` and `tools\apollo330_scripts` instead (p13).

### Reading (interpretation, not a datasheet statement)

The following reads the tables above:

- **Apollo510 and Apollo510B.** The 64 kB SBL region at 0x00400000 is part of the documented die partitioning. Application code starts at 0x00410000 because the datasheet says so.
- **Apollo510 Lite and Apollo330 Plus.** The datasheets reserve no SBL region: NVM-APPL starts at 0x00400000. Even so, the EVB guides say the fitted parts ship with a secure bootloader and link examples at 0x410000, and the datasheets say the SBL drives GPIO28 at boot. On these parts the SBL and its 64 KB offset are therefore a provisioning property of the fitted part, not a fact of the documented partitioning.
- **Apollo3 and Apollo4.** Secure boot is enabled through OTP. The application start addresses that software uses (0xC000, 0x18000) do not appear in the datasheets. They come from SBL provisioning, documented elsewhere.
- **Radio firmware on Lite and 330 Plus.** The NVM-M41 reservation differs by part (16, 288 or 432 KB). Usable application NVM is therefore a per-part fact, not a per-family fact.

## 3. Discrepancy with the SDK (needs hardware confirmation)

nsx-ambiq-sdk `main` `9d4463a` uses the `sbl` script as the default gcc linker profile for apollo510L and apollo330P (`cmake/socs/apollo510L.cmake:29`, `cmake/socs/apollo330P.cmake:29`; the default profile is chosen in `cmake/nsx_toolchain_flags.cmake:47-76`).

| SDK file | Region | SDK value | Datasheet says | Overlap (computed) |
| --- | --- | --- | --- | --- |
| `modules/nsx-core/src/apollo510L/gcc/linker_script_sbl.ld:10` | `MCU_MRAM` | ORIGIN 0x00410000, LENGTH 2031616 (0x1F0000), so it ends at 0x00600000 | NVM-APPL ends at 0x005FBFFF / 0x005B7FFF / 0x00593FFF (DS-A510LS p33) | 16 KB (510 Lite), 288 KB (510B Lite), 432 KB (510D Lite) of NVM-M41 |
| `modules/nsx-core/src/apollo330P/gcc/linker_script_sbl.ld:10` | `MCU_MRAM` | same as above | same pattern (DS-A330PS p33) | 16 KB (330 Plus), 288 KB (330B Plus), 432 KB (330M Plus) of NVM-M41 |
| both files, lines 11-12 | `MCU_TCM`, `SHARED_SRAM` | TCM 0x20000000 + 240 KB; SRAM 0x20080000 + 1835008 (1.75 MB) | DTCM 256 kB at 0x20000000; System SRAM 1.75 MB at 0x20080000 | none |

On the Apollo510 Lite EVB (fitted part AP510DLA-CBR, QS-A510DL p10) the default window runs 432 KB into the region the datasheet assigns to Cortex-M4 firmware. The same holds for the Apollo330 Plus EVB (AP330MPA-CBR, QS-A330MP p10). This is an overlap on paper. It matters only if an image actually grows past the NVM-APPL end address. Both datasheets are preliminary (revision 0.9.0), and nobody has observed the overlap on hardware.

There is one more mismatch, outside the default profile. The `itcm` profile scripts (`apollo510L/gcc/linker_script_itcm_sbl.ld:10-13`, `apollo330P/gcc/linker_script_itcm_sbl.ld:10-13`) and the `nbl` scripts (`apollo510L/gcc/linker_script_nbl.ld:10-13`, `apollo330P/gcc/linker_script_nbl.ld:10-13`) declare the following:

- an ITCM of 256 KB at 0x00000000
- MRAM of 4128768 bytes
- TCM of 507904 bytes
- SRAM of 3 MB

These match the Apollo510 map (DS-A510 p35), not the Lite or 330 Plus map, where 0x00000000-0x003BFFFF is reserved and NVM is 2 MB (DS-A510LS p33; DS-A330PS p33).

## 4. SoC facts

### Core and clocks

| SoC | Core, max MHz | Operating modes | FPU / MVE | Caches | Crystals | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Apollo510 | Cortex-M55, 250 | LP 96, HP 250 (TurboSPOT) | "Helium (MVE) vector integer, floating point"; scalar half, single, double | 64 kB I / 64 kB D | 48 MHz, 32.768 kHz | DS-A510 p2, p21, p23 |
| Apollo510B | Cortex-M55, 250 | LP 96, HP 250 | Helium (MVE); scalar double/single/half | 64 kB I / 64 kB D | 48 MHz, 32.768 kHz | DS-A510B p2, p20, p22 |
| Apollo510 Lite series | Cortex-M55, 250 | LP 96, HP1 192 (HFRC), HP2 250 (PLL) | Helium (MVE); scalar half, single, double | 32 kB I / 32 kB D | 48 MHz, 32.768 kHz | DS-A510LS p2, p20, p46 |
| Apollo330 Plus series | Cortex-M55, 250 | LP 96, HP1 192 (HFRC), HP2 250 (PLL) | Helium (MVE); scalar half, single, double | 32 kB I / 32 kB D | 48 MHz, 32.768 kHz | DS-A330PS p2, p20, p46 |
| Apollo4 | Cortex-M4F, 192 | 96 LP, 192 TurboSPOT | FPU; no MVE | 64 kB NVM cache | 32 MHz, 32.768 kHz | DS-A4 p2, p52, p58 |
| Apollo4 Blue | Cortex-M4F, 192 | 96, 192 TurboSPOT | FPU | 64 kB NVM cache | 32 MHz, 32.768 kHz | DS-A4B p2, p44, p50 |
| Apollo4 Plus | Cortex-M4F, 192 | 96, 192 TurboSPOT | FPU | 64 kB NVM cache | 32 MHz, 32.768 kHz | DS-A4P p2, p52, p58 |
| Apollo4 Blue Plus | Cortex-M4F, 192 | 96, 192 TurboSPOT | FPU | 64 kB NVM cache | 32 MHz, 32.768 kHz | DS-A4BP p2, p49, p55 |
| Apollo4 Lite | Cortex-M4F, 192 | 96, 192 TurboSPOT | FPU | 64 kB NVM cache | 32 MHz, 32.768 kHz | DS-A4L p2, p42, p48 |
| Apollo4 Blue Lite | Cortex-M4F, 192 | 96, 192 TurboSPOT | FPU | 64 kB NVM cache | 32 MHz, 32.768 kHz | DS-A4BL p2, p39, p45 |
| Apollo3 Blue | Cortex-M4F, 96 | 48 nominal, 96 TurboSPOT | FPU | 16 KB 2-way | 32.768 kHz | DS-A3 p2 |
| Apollo3 Blue Plus | Cortex-M4F, 96 | 48 nominal, 96 TurboSPOT | FPU | 16 KB 2-way | 32.768 kHz | DS-A3P p2 |
| Apollo2 | Cortex-M4F, 48 | up to 48; no TurboSPOT text | FPU | 16 kB 2-way | 32.768 kHz | DS-A2 p38-40 |

### Memory

| SoC | ITCM | DTCM / TCM | System SRAM | NVM | Source |
| --- | --- | --- | --- | --- | --- |
| Apollo510 | 256 kB at 0x00000000 | 512 kB DTCM at 0x20000000 | 3 MB at 0x20080000 | 4 MB (0x00400000-0x007FFFFF, of which 64 kB is SBL) | DS-A510 p35, p298 |
| Apollo510B | 256 kB at 0x00000000 | 512 kB DTCM at 0x20000000 | 3 MB at 0x20080000 | 4 MB | DS-A510B p34, p263 |
| Apollo510 Lite series | none | unified I/D TCM 256 kB at 0x20000000 | 1.75 MB at 0x20080000; 0x20040000-0x2007FFFF reserved | 2 MB less NVM-M41 (section 2) | DS-A510LS p33 |
| Apollo330 Plus series | none | unified I/D TCM 256 kB at 0x20000000 | 1.75 MB at 0x20080000; 0x20040000-0x2007FFFF reserved | 2 MB less NVM-M41 | DS-A330PS p33 |
| Apollo4 | none | 384 kB data TCM | 1024 kB SSRAM plus up to 480 kB extended SRAM | 2 MB | DS-A4 p52, p58 |
| Apollo4 Blue | none | 384 kB | 1024 kB SSRAM plus 480 kB extended | 2 MB | DS-A4B p44, p50 |
| Apollo4 Plus | none | 384 kB | 2048 kB SSRAM plus 384 kB extended | 2 MB | DS-A4P p52, p58 |
| Apollo4 Blue Plus | none | 384 kB | 2048 kB SSRAM plus 384 kB extended | 2 MB | DS-A4BP p49, p55 |
| Apollo4 Lite | none | 384 kB | 1024 kB SSRAM; no extended RAM listed | 2 MB | DS-A4L p42, p48 |
| Apollo4 Blue Lite | none | 384 kB | 1024 kB SSRAM; no extended RAM listed | 2 MB | DS-A4BL p39, p45 |
| Apollo3 Blue | none | 64 KB TCM at 0x10000000 | 320 KB main at 0x10010000 (0x10010000-0x1005FFFF) | 1 MB flash | DS-A3 p78 |
| Apollo3 Blue Plus | none | 64 KB TCM at 0x10000000 | 704 KB main at 0x10010000 (0x10010000-0x100BFFFF) | 2 MB flash | DS-A3P p2, p82 |
| Apollo2 | none | none | 256 KB at 0x10000000 | 1 MB flash | DS-A2 p68 |

The Apollo4 datasheets give no SSRAM or TCM base address. DS-A4P p73 places DAXI data accesses (SSRAM, extended SRAM, MSPI) "at 0x10060000 - 0x1FFFFFFF".

### Radio, graphics, display

| SoC | Radio | GPU / display | Source |
| --- | --- | --- | --- |
| Apollo510 | none ("No Connectivity") | 2.5D GPU 96/250 MHz, display controller, MIPI DSI | DS-A510 p2, p298 |
| Apollo510B | BLE 5.4; Bluetooth Low Energy Controller is section 12 (48 MHz MCU, 64 KB SRAM, 512 KB NVM) | 2.5D GPU, display controller, MIPI DSI | DS-A510B p2, p4, p81, p263 |
| Apollo510 Lite | none ("No Connectivity"); NVM-M41 is still 16 KB | 2.5D GPU 96 MHz, display controller, MIPI DSI and QSPI | DS-A510LS p2, p33, p254 |
| Apollo510B Lite | BLE 5.4 | as above | DS-A510LS p2, p254 |
| Apollo510D Lite | BLE 5.4 and Bluetooth Classic (dual mode) | as above | DS-A510LS p2, p254 |
| Apollo330 Plus | none ("No Connectivity") | no GPU or display controller listed | DS-A330PS p2, p243 |
| Apollo330B Plus | BLE 5.4 | none listed | DS-A330PS p2, p243 |
| Apollo330M Plus | BLE 5.4 and Bluetooth Classic; 802.15.4, Thread and Matter footnoted "Planned for future OTA update" | none listed | DS-A330PS p2, p243 |
| Apollo4, Apollo4 Plus | none | GPU, display controller, MIPI DSI 1.2 two lanes | DS-A4 p2, p52; DS-A4P p2, p52 |
| Apollo4 Blue, Apollo4 Blue Plus | "Bluetooth Low Energy 5.4 compatible radio with up to 5.1 feature support" | GPU, display controller, MIPI DSI 1.2 single lane | DS-A4B p2, p44; DS-A4BP p2, p49 |
| Apollo4 Lite | none | GPU; display up to 390x390 over MSPI, no MIPI DSI listed | DS-A4L p2, p42 |
| Apollo4 Blue Lite | "Bluetooth 5.1 Low Energy" | GPU; display over MSPI | DS-A4BL p2, p39 |
| Apollo3 Blue, Apollo3 Blue Plus | "Integrated Bluetooth 5 low-energy controller" | none | DS-A3 p2; DS-A3P p2 |
| Apollo3 (AMAP31KK) | none ("non-BLE configuration") | none | DS-A3 p954 |
| Apollo2 | none | none | DS-A2 p38-40 |

### Corrections to first-pass readings

- Apollo510B does have a BLE controller: TOC section 12 "Bluetooth Low Energy Controller (BLEC)" (DS-A510B p4, p81).
- Apollo510 Lite and Apollo330 Plus system SRAM is at 0x20080000, not 0x20040000. 0x20040000-0x2007FFFF is reserved (DS-A510LS p33; DS-A330PS p33).
- The NVM-M41 sizes are 16, 288 and 432 KB by variant, not 256 KB (DS-A510LS p33; DS-A330PS p33).

## 5. Ordering parts

| Part number | Family | Package | Radio | Source |
| --- | --- | --- | --- | --- |
| AP510NFA-CBR | Apollo510 | 225-pin BGA, 6.6 x 6.6, commercial | none | DS-A510 p2, p298 |
| AP510NFA-IBR | Apollo510 | 225-pin BGA, industrial | none | DS-A510 p2, p298 |
| AP510NFA-CCR | Apollo510 | 182-pin WLCSP, 4.9 x 4.7 | none | DS-A510 p2, p298 |
| AP510BFA-CBR | Apollo510B | 153-pin WFBGA, 5.6 x 5.6 | BLE 5.4 | DS-A510B p2, p263; QS-A510B p8 |
| AP510NLA-CCR | Apollo510 Lite | 110-pin CSP | none | DS-A510LS p254 |
| AP510NLA-CBR | Apollo510 Lite | 169-pin BGA | none | DS-A510LS p254 |
| AP510BLA-ICR | Apollo510B Lite | 110-pin CSP, industrial only | BLE 5.4 | DS-A510LS p254 |
| AP510DLA-CCR | Apollo510D Lite | 110-pin CSP | BLE 5.4, BT Classic | DS-A510LS p254 |
| AP510DLA-CBR, AP510DLA-IBR | Apollo510D Lite | 169-pin BGA | BLE 5.4, BT Classic | DS-A510LS p254 |
| AP330NPA-CCR | Apollo330 Plus | 110-pin CSP | none | DS-A330PS p243 |
| AP330NPA-IBR | Apollo330 Plus | 169-pin BGA, industrial only | none | DS-A330PS p243 |
| AP330BPA-CCR, AP330BPA-ICR | Apollo330B Plus | 110-pin CSP | BLE 5.4 | DS-A330PS p243 |
| AP330MPA-CCR | Apollo330M Plus | 110-pin CSP | BLE 5.4, Matter/Thread | DS-A330PS p243 |
| AP330MPA-IBR | Apollo330M Plus | 169-pin BGA, industrial only | BLE 5.4, Matter/Thread | DS-A330PS p243 |
| AMAP42KK-KBR | Apollo4 | 146-pin BGA | none | DS-A4 p224 |
| AMA4B2KK-KBR | Apollo4 Blue | 131-pin BGA | BLE | DS-A4B p223 |
| AMAP42KP-KBR | Apollo4 Plus | 146-pin BGA, 5.0 x 5.0 | none | DS-A4P p241 |
| AMA4B2KP-KBR, AMA4B2KP-KXR | Apollo4 Blue Plus | 131-pin BGA, 4.7 x 4.7 (same text for both) | BLE | DS-A4BP p252 |
| AMAP42KL-KBR | Apollo4 Lite | 146-pin BGA, 5.0 x 5.0 | none | DS-A4L p182 |
| AMA4B2KL-KXR | Apollo4 Blue Lite | 131-pin BGA, 4.7 x 4.7 | BLE | DS-A4BL p186 |
| AMA3B2KK-KBR | Apollo3 Blue Plus | 108-pin BGA | BLE | DS-A3P p1032 |
| AMA3B1KK-KBR-B0 | Apollo3 Blue | 81-pin BGA | BLE | DS-A3 p954 |
| AMA3B1KK-KCR-B0, AMA3B1KK-KCR-TB | Apollo3 Blue | 66-pin CSP / WLCSP | BLE | DS-A3 p954 |
| AMA3B1KK-KQR | Apollo3 Blue | 64-pin QFN | BLE | DS-A3 p954 |
| AMAP31KK-KBR, AMAP31KK-KCR | Apollo3 (non-BLE) | 81-pin BGA / 66-pin WLCSP | none | DS-A3 p954 |
| AMAPH1KK-KCR, AMAPH1KK-KCR-TB | Apollo2 | 49-pin WLCSP | none | DS-A2 p509 |
| AMAPH1KK-KBR | Apollo2 | 64-pin BGA | none | DS-A2 p509 |

The documents disagree with each other on ordering in three places:

- **Lite and 330 Plus ordering tables.** These tables (layout-extracted to confirm the commercial and industrial columns) do not list AP510BLA-CBR, AP510BLA-CCR, AP330NPA-CBR, AP330BPA-CBR or AP330MPA-CBR. The package-drawing pages do name them (DS-A510LS p198, p200; DS-A330PS p188, p190).
- **Apollo330 Plus EVB part.** The Apollo330 Plus EVB fits AP330MPA-CBR (QS-A330MP p8, p10), but that part is not in the DS-A330PS ordering table.
- **Apollo4 EVB rev3 part.** QS-A4 lists the fitted part as AMAP42KK-KCR-B2 (p9) but its own ordering table gives AMAP42KK-KBR-B2 (p20).

## 6. EVBs

### Identity

| Board | Guide | Board revision | EVB part number | SDK board dir named in guide | SoC fitted | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Apollo510 EVB | QS-A510-2p1 | 2.2 | AP510EVB | `apollo510_evb` | AP510NFA-CBR | p1, p6, p7, p8, p23 |
| Apollo510B EVB | QS-A510B-1p1 | 2.0 | AP510BEVB | `apollo510b_evb` | AP510BFA-CBR | p1, p6, p7, p8, p25 |
| Apollo510 Lite EVB | QS-A510DL-2p0 | 2.0 | AP510DLEVB | `apollo510dL_evb` | AP510DLA-CBR | p1, p6, p7, p8, p31 |
| Apollo330 Plus EVB | QS-A330MP-2p0 | 2.0 | AP330MPEVB | `apollo330mP_evba` (sic) | AP330MPA-CBR | p1, p6, p7, p8, p31 |
| Apollo4 Plus EVB | QS-A4P-1p5 | all revisions (1 to 3); ordering table lists 3 | AMAP4PEVB | `apollo4p_evb` | AMAP42KP-KBR | p1, p6, p7, p10, p21 |
| Apollo4 Plus Display Kit | QS-A4PDK-1p2 | shield revision 1, on AMAP4PEVB revision 2 or later | AMAP4PDISP | `apollo4p_evb_disp_shield_rev2` | AMAP42KP-KBR (on the EVB) | p1, p6, p9, p10 |
| Apollo4 Blue Plus (KBR) EVB | QS-A4BP_KBR-1p4 | 1.0 | AMA4BPEVB | `apollo4p_blue_kbr_evb` | AMA4B2KP-KBR | p1, p6, p7, p10, p21 |
| Apollo4 EVB | QS-A4-4p2 | 3 | AMAP4EVB | `apollo4b_bga_evb` | AMAP42KK-KCR-B2 (Apollo4, not Plus; see section 5) | p1, p6, p7, p9, p20 |
| Apollo3 Blue Plus EVB | A-SOCA3P-QSGA01EN v1.2 | 1.0 | AMA3B2EVB | none given (scripts in `tools\apollo3_blue_scripts`) | AMA3B2KK-KBR | p5, p7, p8 |

### Hardware

| Board | External memory on the base board | On add-ons | Debug, SWO | Radio hardware | Source |
| --- | --- | --- | --- | --- | --- |
| Apollo510 EVB | Hex PSRAM APS512XXN-AOB4BI-WBRZ (features list) or APS512XXB-AOB5NI-WA (parts diagram); octal flash IS25WX064-JHL; 8 GB eMMC IS21EF08G-JCLI. Capacities of the PSRAM and flash are not stated in this guide | none described | on-board Segger J-Link (J16) | none | p8, p10, p16 |
| Apollo510B EVB | Hex PSRAM APS512XXN-AOB4BI-WBRZ; 8 GB eMMC IS21EF08G-JCLI; no octal flash | none described | on-board J-Link (J16) | PCB trace antenna; RF switch for BLE PHY testing | p8, p10, p17 |
| Apollo510 Lite EVB | 8 GB eMMC IS21EF08G-JCLI. PSRAM footprint U14 (APS512XXN-AOB4BI-WBRZ) "Not populated" on all revision 2.0 boards because of a "PSRAM scan window issue at 1.2 V supply" | none described | on-board J-Link (J16); SWO Viewer used in BLE test | PCB trace antenna; RF switch | p8, p10, p27, p30 |
| Apollo330 Plus EVB | 8 GB eMMC IS21EF08G-JCLI. PSRAM U14 not populated on all revision 2.0 boards (same issue) | none described | on-board J-Link (J16) | PCB trace antenna; RF switch | p8, p10, p27, p30 |
| Apollo4 Plus EVB | No PSRAM, flash or eMMC listed; high-speed connector J8 "for interfacing to displays and/or high-speed memory" | Display Kit (next row) | Segger J-Link; topside on board revision 3, back side on 1 and 2; SWO defaults to J13 | RF switch "for BLE PHY testing" is listed although the fitted part is non-Blue | p10, p12, p19 |
| Apollo4 Plus Display Kit | n/a | 256 Mb (32 MB, computed) HexSPI PSRAM APS256XXN; 64 Mb (8 MB, computed) octal flash IS25WX064; 4 GB eMMC THGBMNG5D1LBAIT. GPIO34 selects MSPI0 hex to PSRAM only, or MSPI0/MSPI1 octal to PSRAM and flash. "only compatible with the (non-blue) Apollo4 Plus EVB" | on the EVB | n/a | p10, p11, p12 |
| Apollo4 Blue Plus (KBR) EVB | None listed; J8 high-speed connector | none described | J-Link SWO Viewer device "AMA4B2KP-KBR", SWO clock 1000 kHz; SWO defaults to J13 | PCB (MIFA) antenna; RF switch | p7, p10, p19 |
| Apollo4 EVB (rev 3) | None listed | none described | Segger J-Link; SWO defaults to J13 | RF switch for BLE PHY testing listed | p9, p10, p18 |
| Apollo3 Blue Plus EVB | None listed; FTDI USB-to-SPI interface | none described | Segger J-Link; debugger-in and debugger-out ports | PCB (MIFA) antenna; RF switch J1 | p7 |

## 7. Catalog corrections implied

| Current belief | Datasheet or guide says | Source |
| --- | --- | --- |
| `apollo4p_evb` PSRAM 32 MB (helia-profiler `psram_kb=32768`) | No PSRAM on the base board. The Display Kit is the only PSRAM source in these documents and fits only the non-Blue AMAP4PEVB | QS-A4P p10; QS-A4PDK p10, p12 |
| `apollo4p_blue_kbr_evb` PSRAM 32 MB (helia-profiler) | No PSRAM listed, and the Display Kit is not compatible with the Blue EVB | QS-A4BP p10; QS-A4PDK p10 |
| `apollo330mP_evb` PSRAM 32 MB (helia-profiler, inherited from SoC `apollo330P`) | Not populated on revision 2.0 | QS-A330MP p8, p10, p30 |
| `apollo510dL_evb` no PSRAM (helia-profiler `psram_kb=0`) | Agrees: footprint unpopulated on revision 2.0 | QS-A510DL p8, p10, p30 |
| `apollo3p_evb` PSRAM 8 MB (helia-profiler `psram_kb=8192`) | Not mentioned in the guide. Unverified, not disproved | QS-A3BP p7 |
| `apollo510_evb` PSRAM 64 MB (helia-profiler) or 32168 KB (heliaAOT) and NVM 8 MB (helia-profiler `nvm_kb=8192`) | The "NVM" is the IS25WX064-JHL octal NOR flash, which QS-A4PDK describes as 64 Mb. The PSRAM is APS512XX-family, but no document in the folder states its capacity, so 64 MB is consistent with the part list but not confirmed | QS-A510 p8, p10; QS-A4PDK p12 |
| `apollo510b_evb` PSRAM 64 MB (helia-profiler, inherited) | APS512XXN-AOB4BI-WBRZ fitted; capacity not stated; no octal flash | QS-A510B p8, p10 |
| `apollo5b_evb` | No guide or datasheet in the folder | inventory |
| heliaAOT's planned PSRAM addition to `apollo330mp_evb` (as reported for this read; the plan was not found in the other research notes) | Not supported by the revision 2.0 guide | QS-A330MP p8, p30 |
| helia-profiler `apollo510L` and `apollo330P` `mram_kb=1984` (0x1F0000, the SDK window from 0x00410000) | NVM-APPL on the fitted 510D Lite / 330M Plus ends at 0x00593FFF: 1616 KB from 0x00400000, or 1552 KB from 0x00410000 (computed) | DS-A510LS p33; DS-A330PS p33 |
| helia-profiler `apollo510L` and `apollo330P` clocks lp 96, hp 250 | Two HP modes: HP1 192 MHz (HFRC) and HP2 250 MHz (PLL). heliaAOT `apollo330mp_evb` already lists 96, 192, 250 | DS-A510LS p46; DS-A330PS p46 |
| `apollo4p` SRAM 1 MB (heliaAOT `apollo4p_evb`; helia-profiler `sram_kb=1024`) | 2048 kB SSRAM plus 384 kB extended SRAM plus 384 kB TCM | DS-A4P p52, p58 |
| helia-profiler `apollo3p` `mram_kb=2000`, `sram_kb=700` | 2 MB flash; 704 KB main SRAM plus 64 KB TCM | DS-A3P p2, p82 |
| Board identity is the board name only | Board revision changes fitted memory (Apollo510 Lite and Apollo330 Plus revision 2.0 drop PSRAM; the Apollo4 Plus EVB guide spans revisions 1 to 3). The catalog needs a board revision field | QS-A510DL p30; QS-A330MP p30; QS-A4P p6, p12 |

## 8. Gaps

| Gap | Effect |
| --- | --- |
| No atomiq110 datasheet | atomiq110 numbers cannot be sourced from this folder |
| No Apollo4 Family Security User's Guide (referenced by DS-A4 p94, DS-A4B p87, DS-A4P p95, DS-A4BP p93) | Apollo4 SBL layout and application start address remain unsourced |
| No Apollo5 or Apollo510 Lite security documentation, and no SBL documentation for the Lite and 330 Plus parts | The 0x410000 offset on those parts rests on the EVB guides alone |
| No apollo5b documents | `apollo5b` and `apollo5b_evb` cannot be checked |
| No guides for Apollo4 Lite, Apollo4 Blue Lite, Apollo4 Blue Plus KXR, Apollo4 Blue, Apollo3 Blue, Apollo3, or Apollo2 EVBs | Board facts for those catalog entries are unsourced |
| J-Link device names | Confirmed in a guide only for the Apollo4 Blue Plus KBR EVB ("AMA4B2KP-KBR", QS-A4BP p7). Other `jlink_device` values in the catalog are unverified |
| PSRAM capacity of the APS512XX parts | Not stated in any document in the folder |
| Fitted crystal values | Each datasheet states its crystal oscillator frequencies (section 4), but no EVB guide states which crystals are fitted |
| Preliminary revisions | DS-A510LS and DS-A330PS are 0.9.0; DS-A4L 0.9.1; DS-A4BL 0.9.0 |

## Owner statements (2026-10-04)

Recorded from Adam Page in planning discussion, not from a document. They
carry provenance status "owner statement" until a document confirms them.

| Statement | Effect on the catalog |
|---|---|
| The Apollo510 EVB has PSRAM and NOR flash populated. | Confirms the parts named in the Apollo510 EVB guide are fitted; capacities still need a document. |
| The Apollo330 Plus EVB does not come with PSRAM populated. | Agrees with the rev 2.0 guide. |
| On Apollo4 the display shield adds PSRAM, and users may add daughter boards with PSRAM or NOR. | External memories must be composable from add-ons, not fixed per board. |

## Hardware-validated facts

| Fact | Evidence | Provenance status |
|---|---|---|
| apollo510_evb and apollo510b_evb PSRAM is 64 MB (APS512-class, hex DDR on MSPI0, BA driver) | BA driver reports 65536 KB; XIP aliasing shows distinct data at +32 MB and a live address near +64 MB; validated 2026-07-05; nsx-ambiq-sdk `modules/nsx-psram/CMakeLists.txt:60-125` (last changed in a1a0df1) | measured |

## Additional datasheet facts cited by RFC 0002

| Fact | Source | Provenance status |
|---|---|---|
| Apollo510 MSPI0 XIP aperture is 0x60000000-0x6FFFFFFF (256 MB) | DS-A510 p36 (system memory map) and p98 (MSPI section) | datasheet |
| Apollo4 Blue Lite BLE controller incorporates a dedicated Arm Cortex-M0 | DS-A4BL p84 | datasheet |
