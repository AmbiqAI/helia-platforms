# RFC 0002: migration and output changes

Status: Accepted, 2026-10-21 (drafted 2026-10-04). Part of [RFC 0002](0002-model-and-api.md),
kept in its own file for length. Terms are as defined in RFC 0002's
glossary.

Each consumer's outputs that change on adoption, and the parity test in
issue #13 that covers each. A parity test compares the consumer's current
data with the package's answer and allows only the differences on its
allow-list. The allow-list carries every change in this document,
including each pending data correction below, each with its reason.

Consumer facts at the revisions read on 2026-10-04, including runtime
dependencies, are in `docs/research/queries-*.md`.

## All consumers

| Output that changes | Parity test (#13) |
|---|---|
| None from the multicore model ([0002-multicore.md](0002-multicore.md)): every `core=` and `npu=` argument defaults to index 0, the primary application core and primary NPU, so single-core answers are unchanged | Every parity test below runs with the defaults |

## Pending data corrections

Pending verification, issue #14. Each row is a difference between a
consumer's current data and what the sources of record say. None is
applied until verified; each parity allow-list must carry the row with its
reason.

helia-profiler citations are at `ed2f0a15`; line numbers are in
`src/helia_profiler/platform/board.py` unless the row names another file.
"nsx-psram" is `modules/nsx-psram/` in nsx-ambiq-sdk
`v5.2.24`. Its `CMakeLists.txt:31-37` states that the plain and Blue
apollo4l and apollo4p EVBs do not populate PSRAM, and its `README.md:90-95`
names `apollo4p_evb_disp_shield_rev2` as the only supported Apollo4 board.

| Fact | Current data | Source says | Consumers affected | Source |
|---|---|---|---|---|
| `apollo4p_evb` PSRAM | helia-profiler 32 MB (line 93) | No PSRAM on the base board; the Display Kit is the only PSRAM source and fits only the non-Blue EVB. nsx-psram agrees | helia-profiler | research/datasheets.md section 7 (QS-A4P p10; QS-A4PDK p10, p12); nsx-psram |
| `apollo4p_blue_kbr_evb` PSRAM | helia-profiler 32 MB (line 128) | None listed, and the Display Kit is not compatible with the Blue EVB. nsx-psram agrees | helia-profiler | section 7 (QS-A4BP p10; QS-A4PDK p10); nsx-psram |
| `apollo4l_evb`, `apollo4l_blue_evb`, `apollo4p_blue_kxr_evb` PSRAM | helia-profiler 32 MB (lines 104, 115, 141) | Not populated, per nsx-psram. research/datasheets.md has no quick-start guide for these three boards | helia-profiler | nsx-psram |
| `apollo330mP_evb` PSRAM | helia-profiler 32 MB, inherited from `apollo330P` (`src/helia_profiler/platform/soc.py:583`) | The revision 2.0 guide and the owner statement say the part is not fitted. nsx-psram assumes it is fitted (`CMakeLists.txt:60-64`) and maps the board to the "BA" driver as unvalidated, with a conservative 32 MB default; that is the same figure as helia-profiler's, which does not state its own source. helia-profiler's `apollo330P` memory comment describes a "Rev1 EVB" (`src/helia_profiler/platform/soc.py:565`), so the difference is a board-revision question | helia-profiler | section 7 (QS-A330MP p8, p10, p30) and Owner statements in research/datasheets.md; nsx-psram `README.md:25`, `CMakeLists.txt:60-64, 130-137, 150-152` |
| `apollo3p_evb` PSRAM | helia-profiler 8 MB (line 67) | Not mentioned in the guide. The nsx-ambiq-sdk `v5.2.24` BSP sets `AM_BSP_MSPI_PSRAM_INST 0` but defines no PSRAM pins, only generic MSPI0, MSPI1 and MSPI2 pins; nsx-psram still builds its 8 MB APS6404L driver for the board. Under the rule below, the board's `population` carries no PSRAM, and the 8 MB moves to an add-on (an APS6404L on MSPI0) under RFC 0002's composed external memory ([0002-model-and-api.md](0002-model-and-api.md), "Board, external memory and add-ons") | helia-profiler | section 7 (QS-A3BP p7); nsx-ambiq-sdk `v5.2.24` `modules/nsx-ambiqsuite/sdk/boards/apollo3p_evb/bsp/am_bsp.h:118`, `bsp/am_bsp_pins.h:469-679`; nsx-psram `CMakeLists.txt:21-29` |
| apollo4p SSRAM | heliaAOT `apollo4p_evb`, `apollo4p_blue_kbr_evb` and `apollo4p_blue_kxr_evb` SRAM 1 MB; helia-profiler `sram_kb=1024` | 2048 kB SSRAM plus 384 kB extended SRAM plus 384 kB TCM | heliaAOT, helia-profiler | section 7 (DS-A4P p52, p58) |
| apollo3p MRAM and SRAM | helia-profiler `mram_kb=2000`, `sram_kb=700` | 2 MB flash; 704 KB main SRAM plus 64 KB TCM | helia-profiler | section 7 (DS-A3P p2, p82) |
| apollo510L and apollo330P NVM | helia-profiler `mram_kb=1984` (the SDK window from 0x00410000); heliaAOT `apollo330mp_evb` and `apollo510l_evb` MRAM 2031616 (`platforms.py:456` and `:523`, `ea5cd6c0`) | NVM-APPL on the fitted 510D Lite and 330M Plus ends at 0x00593FFF; NVM-M41 is reserved per part | heliaAOT, helia-profiler | section 7 and section 3 (DS-A510LS p33; DS-A330PS p33) |
| apollo510L and apollo330P clocks | helia-profiler lp 96, hp 250 | Two HP modes: HP1 192 MHz and HP2 250 MHz | helia-profiler | section 7 (DS-A510LS p46; DS-A330PS p46) |

Both Apollo3 Plus PSRAM decisions follow one rule: a board's `population`
records a part only where the board is wired for one, until a hardware
check (#19) confirms what is fitted. In nsx-ambiq-sdk
`v5.2.24`, the `apollo3p_evb_cygnus` BSP defines PSRAM pins on MSPI1
(`modules/nsx-ambiqsuite/sdk/boards/apollo3p_evb_cygnus/bsp/am_bsp_pins.h:966-1011`):
a PSRAM-only chip-select on pad 69, and data pins D0-D3 and a clock pin
that the BSP marks as shared with FLASH1. It also sets
`AM_BSP_MSPI_PSRAM_INST 1` (`bsp/am_bsp.h:118`). The `apollo3p_evb`
BSP names MSPI0 as the PSRAM instance but defines no PSRAM pins.

`apollo3p_evb_cygnus` therefore keeps its 8 MB (helia-profiler line 78)
and is not a pending correction. The PSRAM pin definitions show that the
board is wired for PSRAM, not that the part is fitted, so whether it is
fitted is a hardware question (#19).

An inference, not proof, supports treating `apollo3p_evb`'s MSPI0 as an
add-on interface. Its generic MSPI0 pins use pads 22 (D0) and 23 (D3)
(`am_bsp_pins.h:490, 514`), which the BSP also assigns to COM_UART TX and
RX (`am_bsp_pins.h:105, 113`). helia-profiler records that pads 22 and 23
are the J-Link virtual-COM UART that carries its `uart` transport
(`board.py:57-61`). A part on MSPI0 would therefore share the console UART
pads. The cygnus PSRAM pins are pads 51 to 54, 59 and 69, which do not
clash with its COM_UART pads 22 and 23 (the same lines in the cygnus BSP).

## heliaAOT

### Target names

The 15 registered targets at `ea5cd6c0` resolve as follows. A name is
either a catalog id or an alias; an alias resolves to a target whose
`id` differs from the name, and the name is kept in `Target.aliases`.

| heliaAOT name | Catalog entry | `target.id` | Artefact name |
|---|---|---|---|
| `apollo3_evb` | Board id (also a neuralspotx board id) | `apollo3_evb` | Unchanged |
| `apollo3_blue_evb` | Board id carried from heliaAOT; no neuralspotx board | `apollo3_blue_evb` | Unchanged |
| `apollo3_blue_thin_evb` | Board id carried from heliaAOT; no neuralspotx board | `apollo3_blue_thin_evb` | Unchanged |
| `apollo3p_evb` | Board id | `apollo3p_evb` | Unchanged |
| `apollo3_blue_plus_evb` | Alias of `apollo3p_evb` (a byte-identical copy today, RFC 0001 Architecture; #278 phase 4 retires it by alias) | `apollo3p_evb` | Unchanged: heliaAOT keeps the passed name (decided, below) |
| `apollo4p_evb`, `apollo4l_evb`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `apollo4l_blue_evb` | Board ids | same | Unchanged |
| `apollo330mp_evb` | Board id `apollo330mP_evb` (case differs only) | `apollo330mP_evb` | Unchanged after lowercasing |
| `apollo510_evb`, `apollo510b_evb` | Board ids | same | Unchanged |
| `apollo510l_evb` | Alias of `apollo510dL_evb` (one Lite EVB, the AP510DLEVB, RFC 0001 Architecture) | `apollo510dL_evb` | Unchanged: heliaAOT keeps the passed name (decided, below) |
| `atomiq110` | Soc id; bare Soc target | `atomiq110` | Unchanged |

Decided: when the user passes an alias, heliaAOT keeps printing and
keying artefacts by the name the user passed (lowercased), and records
`target.id` alongside it in `plan.json`. `apollo510l_evb` and
`apollo3_blue_plus_evb` stay accepted aliases of `apollo510dL_evb` and
`apollo3p_evb`, and their artefacts are not renamed. Composition aliases are not covered: they key
artefacts by `target.id` as RFC 0002 states, and no heliaAOT target today
is a composition.

Parity (#13, target names): every registered name resolves; either
`target.id.lower()` equals the name, or the name is in `target.aliases`
(case-insensitive) and is listed in the table above; artefact names equal
today's for every name.

### Budgets, capabilities and policy

| Output that changes | Parity test (#13) |
|---|---|
| Memory budgets come from the catalog for every module type: on-chip RAM is the physical region size from `target.memories()`, except `atomiq110`'s HBLRAM (see below the table), NVM is `target.usable_nvm()`, and external memories come from `target.external_memories()`; no link environment is a budget source (decided 2026-10-05, see #28). `usable_nvm()` subtracts the boot reservations and other cores' image slots of the selected boot configuration, because planning into them would overwrite the bootloader or radio firmware; it does not subtract stack and heap carve-outs. A plan within a physical RAM size can therefore exceed what a linker script or devicetree gives the program, for example the nsx default script's 496 KB of DTCM on Apollo510 or Zephyr's 2 MB `sram0` on `apollo510_evb` against 3 MB of SSRAM. The largest case is apollo4p: the nsx scripts link SSRAM0 only (`SHARED_SRAM`, 1048576 bytes, at nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/apollo4p/gcc/linker_script.ld:12`; RFC 0001 appendix D) against a 2432 KB SRAM budget. The budgets stay physical (accepted, decided 2026-10-05, see #28); heliaAOT should instead warn when a plan exceeds the SDK window of the selected link environment, using the optional link-environment dataset where it covers the target (#28) | Budget parity: per target and module type, budgets equal today's `platforms.py` figures at `ea5cd6c0` except the rows in Pending data corrections and in this table |
| `apollo510_evb` and `apollo510b_evb` DTCM changes from 507904 bytes (`platforms.py:498` and `:547`, `ea5cd6c0`; `MCU_TCM` in nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/apollo510/gcc/linker_script_sbl.ld:12` and `apollo510b/gcc/linker_script_sbl.ld:12`) to the physical 524288 (DTCM 512 KB, RFC 0001 appendix D) | Budget parity, allow-listed: RAM budgets are physical sizes (decided 2026-10-05, see #28) |
| `apollo330mp_evb` and `apollo510l_evb` DTCM changes from 245760 bytes (`platforms.py:458` and `:525`; `MCU_TCM` in nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/apollo330P/gcc/linker_script_sbl.ld:11` and `apollo510L/gcc/linker_script_sbl.ld:11`) to the physical 262144 (DTCM 256 KB, RFC 0001 appendix D) | Budget parity, allow-listed: RAM budgets are physical sizes (decided 2026-10-05, see #28) |
| `atomiq110` DTCM changes from 507904 bytes (`496 * 1024` at `platforms.py:593`; `MCU_TCM` in nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/atomiq110/gcc/linker_script_nbl.ld:19`) to the physical 524288 (DTCM 512 KB, RFC 0001 appendix D) | Budget parity, allow-listed: RAM budgets are physical sizes (decided 2026-10-05, see #28) |
| `apollo330mp_evb` and `apollo510l_evb` MRAM changes from 2031616 bytes (`platforms.py:456` and `:523`; the nsx window, which runs into NVM-M41) to 1589248 (1552 KB) | Budget parity, allow-listed: `usable_nvm()` with the `sbl` configuration the EVBs ship with (QS-A510DL p7, QS-A330MP p7), so the application starts at 0x00410000. NVM-APPL on the fitted 510D Lite and 330M Plus (AP510DLA-CBR, QS-A510DL p10; AP330MPA-CBR, QS-A330MP p10) ends at 0x00593FFF, above which is the 432 KB NVM-M41 radio slot (DS-A510LS p33; DS-A330PS p33). 0x00594000 - 0x00410000 = 1589248. Depends on the apollo510L and apollo330P NVM row in Pending data corrections (#14) |
| `apollo4p_evb`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `apollo4l_evb` and `apollo4l_blue_evb` MRAM changes from 2048000 bytes (`2000 * 1024` at `platforms.py:385`, `:397`, `:409`, `:421`, `:433`) to 1998848 (1952 KB) | Budget parity, allow-listed: `usable_nvm()` with the `sbl` configuration. `apollo4p_evb` and `apollo4p_blue_kbr_evb` ship SBL-provisioned (QS-A4P p10-11, QS-A4BP p10-11, research/datasheets.md section 2); the other three boards have no guide in the inventory and rest on RFC 0002's statement that Ambiq EVBs ship SBL-provisioned. The application starts at 0x18000 (AmbiqSuite Apollo4 linker scripts; nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/apollo4p/gcc/linker_script.ld:10`; RFC 0002 Boot configurations records the 0xC000 in `am_defines.py` as a conflict). 2048 KB of MRAM less 96 KB: 2097152 - 98304 = 1998848 |
| `apollo3_blue_plus_evb` and `apollo3p_evb` MRAM changes from 2097152 bytes (`2048 * 1024` at `platforms.py:348` and `:365`) to 2048000 (2000 KB) | Budget parity, allow-listed: `usable_nvm()` with the `sbl` configuration the Apollo3 Blue Plus EVB ships with (QS-A3BP p8, research/datasheets.md section 2). The application starts at 0xC000 (RFC 0002 Boot configurations; nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/apollo3p/gcc/linker_script.ld:10`). 2048 KB of flash less 48 KB: 2097152 - 49152 = 2048000 |
| `apollo3_evb`, `apollo3_blue_evb` and `apollo3_blue_thin_evb` MRAM changes from 1048576 bytes (`1024 * 1024` at `platforms.py:300`, `:316`, `:332`) to 999424 (976 KB) | Budget parity, allow-listed: `usable_nvm()` with the `sbl` configuration. These boards have no guide in the inventory and rest on RFC 0002's statement that Ambiq EVBs ship SBL-provisioned. The application starts at 0xC000 (nsx-ambiq-sdk `v5.2.24` `modules/nsx-core/src/apollo3/gcc/linker_script.ld:10`). 1024 KB of flash less 48 KB: 1048576 - 49152 = 999424 |
| `apollo4p_evb`, `apollo4p_blue_kbr_evb` and `apollo4p_blue_kxr_evb` SRAM changes from 1048576 bytes (`platforms.py:385`, `:397`, `:409`) to 2490368 (2432 KB), the sum of the physical SRAM-kind regions SSRAM0 1024 KB, SSRAM1 1024 KB and EXTRAM 384 KB (RFC 0001 appendix D); pending verification in the apollo4p SSRAM row of Pending data corrections (#14) | Budget parity, allow-listed: RAM budgets are physical sizes (decided 2026-10-05, see #28) |
| `apollo510_evb` PSRAM changes from 32168 KB (the literal `32168 * 1024` at `platforms.py:500`, `ea5cd6c0`) to 64 MB, hardware-measured (research/datasheets.md, Hardware-validated facts) | Budget parity, allow-listed with that reason |
| `apollo510b_evb` gains a PSRAM region (64 MB, same measurement) | Budget parity, allow-listed |
| Capabilities are derived; `BLE`, `USB` and `PSRAM` leave built-in lists. heliaAOT 0.33.0 removed all three from `SocCapability` and rejects them with "Declare PSRAM memory under platform.memories" (`helia_aot/platforms/defines.py:10-25` and `helia_aot/cli/defines.py:396-402` at `d31bf22`), so PSRAM is a memory budget only. `MCU` is a heliaAOT policy tag its adapter adds, not a derived capability | Capability parity: per target, the adapter's set equals today's list minus `BLE`, `USB` and `PSRAM` |
| `min_alignment` and `preferred_memory_order` come from heliaAOT tables keyed by `target.soc.id` | Policy-table parity: values per target unchanged |
| The nsx manifest SoC list uses neuralspotx spelling (`apollo510L`, not `apollo510l`) | Manifest parity: `compatibility.socs` equals `catalog.socs()` ids for the listed SoCs |

Two MRAM budgets do not change under `usable_nvm()`. `apollo510_evb` and
`apollo510b_evb` keep 4128768: 4 MB of NVM less the 64 KB NVM-SBL
partition (DS-A510 p35, DS-A510B p34), equal to `platforms.py:496` and
`:545` at `ea5cd6c0`. `atomiq110` keeps 4194304: its Soc `default_boot` is
the no-bootloader layout (RFC 0002 Boot configurations; decided 2026-10-05,
see #28), and it has no radio-core slot. The SDK defaults to nbl because its
only atomiq110 board is the FPGA, and keeps sbl scripts for future silicon
(nsx-ambiq-sdk `v5.2.24` `cmake/socs/atomiq110.cmake:20-23`).

`atomiq110` SRAM does not change either: it stays 3145728 (3072 KB of
SSRAM, `platforms.py:592` at `ea5cd6c0`). The catalog records HBLRAM on
atomiq110 as a physical region of 13312 KB at 0x60000000 (nsx-ambiq-sdk
`v5.2.24`
`modules/nsx-ambiqsuite/sdk/mcu/atomiq110/regs/am_reg_base_addresses.h:41-42`),
but the heliaAOT adapter leaves it out of the default budget (the
`memories` of `SocPlatform`) until its technology and CPU reach are
confirmed (#19). The FPGA has no HBLRAM, so `atomiq110_fpga` removes it.
Counting it as SRAM would raise the budget from 3 MB to 16 MB, which this
table does not allow-list.

### Custom definitions (`platform.*`)

| Today's field | Under RFC 0002 | Shim (one release) |
|---|---|---|
| `cpu` | Soc `core` and `core_options`. A known core string maps to its `Core`; unknown cores must state `core_options` explicitly | Maps known strings; rejects an unknown core without options, with a hint |
| `speeds` | Operating points | Maps each speed to an operating point |
| `memories` (sizes, no bases) | Regions require a base. With `based_on`, the shim takes bases from the base entry or rejects with a hint. Size-only regions are allowed only without `based_on`; such an entry has no addresses: `classify_address` returns None and address-dependent queries raise, per RFC 0002's MemoryRegion rule (RFC 0001 appendix E raised in `classify_address` too; RFC 0002 returns None) | Supplies bases or rejects |
| `capabilities` | Derived. A declared capability that contradicts the facts is rejected, after one release in which it only warns | Warns, then rejects |
| `preferred_memory_order`, `min_alignment` | heliaAOT's `extensions` entry (proposal) | Reads the old keys and warns |

## helia-profiler

| Output that changes | Parity test (#13) |
|---|---|
| PSRAM removed from the five Apollo4 boards (`apollo4p_evb`, `apollo4l_evb`, `apollo4l_blue_evb`, `apollo4p_blue_kbr_evb` and `apollo4p_blue_kxr_evb`) and from `apollo330mP_evb`, once verified (Pending data corrections). On `apollo3p_evb` the 8 MB moves from the board to an add-on (an APS6404L on MSPI0) under RFC 0002's composed external memory, so it appears only when that add-on is selected. `apollo3p_evb_cygnus` keeps its 8 MB; #19 asks whether the part is fitted | Memory parity: per board, physical regions equal today's `MemoryLayout` where it holds physical sizes, except the allow-listed rows; the linker-sized rows (apollo330P and apollo510L DTCM and MRAM, atomiq110 DTCM) are checked under capacity parity instead |
| `_BOARD_TO_AOT_PLATFORM` is deleted. `apollo510b_evb`, `apollo510dL_evb`, `apollo5b_evb` and `apollo330mP_evb`, proxied to `apollo510_evb` today (research/helia-profiler.md), plan against their own targets. `atomiq110_fpga_turbo` resolves to the built-in FPGA board target of that id, which carries Implementation `atomiq110_fpga` (#104), and heliaAOT plans against its reduced values (decided; a deliberate output change for that one target, replacing today's mapping to bare `atomiq110`). `apollo3p_evb_cygnus`, absent from the map today, gains a mapping to its own board target | heliaAOT-name parity: per board, the target hpx passes to heliaAOT, with these re-pointings allow-listed |
| `atomiq110_fpga_turbo`'s trace clock changes from 48 to 50 MHz. helia-profiler sets `swo_trace_clock_mhz=48` on its `atomiq110` `SocDef` (`platform/soc.py:735` at `062aff95`, added in `f71ea4a9`, AmbiqAI/helia-profiler#465) after neuralspotx's `debug.cmake:6-18` (`neuralspotx-v0.9.0`). The catalog's 50 MHz is `measured` by an ACPR sweep in the review of #133: at 1 Mbaud, SWO decodes only for ACPR+1 = 49 to 52, and neither 48 MHz at 1 Mbaud nor neuralspotx's 48 MHz at 1.92 Mbaud decodes any line, so helia-profiler's SWO output on this board is corrected | Trace-clock parity: per board, the SWO reference clock equals today's, except `atomiq110_fpga_turbo`, allow-listed from 48 to 50 MHz |
| The windows table is deleted; windows come from the optional dataset or the build's own script | Window parity: dataset windows equal today's `_MAPS` rows per SoC, toolchain and profile |
| Capacity checks (memory plan, matrix skips) read `target.budget(env)` for the build's link family and profile instead of `MemoryLayout`. Where `MemoryLayout` holds a gcc linker size today (apollo330P and apollo510L DTCM and MRAM, atomiq110 DTCM), the gnu value is unchanged. Where it holds a physical size, the check tightens to the window: apollo510 DTCM from 512 KB to the 496 KB of `MCU_TCM` in the gcc `sbl` script, and MRAM to the application window (AmbiqAI/helia-profiler#466) | Capacity parity: per board and link family, capacities equal today's `MemoryLayout` except allow-listed rows, each naming the window it now uses |
| `app_flash_load_addr` is replaced by `flash_load_address()` from the selected boot configuration | Boot parity: per board, the derived address equals today's value for the board's provisioning |
| `custom_socs` and `custom_boards` translate to overlays through a one-release shim | Custom-format parity: the shim's output resolves to the same facts as today's loader for the documented examples |

## helia-estimator with helia-npu

| Output that changes | Parity test (#13) |
|---|---|
| Codegen spellings in `helia_aot_codegen.py`: `apollo510` resolves to the bare Soc target, not `apollo510_evb` (the estimator calls `resolve_board("apollo510")` where it wants the board). `ap510` matches the built-in shorthand `AP510` case-insensitively and raises `AmbiguousPlatform` with candidates. `apollo510_eb` raises `UnknownPlatform`; it is not a shorthand, so it may become a built-in alias if wanted. The estimator maps its own spellings in its adapter. The `at110*` prefix rule is not reproduced; `at110` is a built-in alias of `atomiq110` (#68) | Name parity: every spelling the estimator uses resolves, through the adapter, to the target it maps to today, or is listed here |
| `origin` mapping: `golden` becomes `origin: builtin`; `derived` becomes `origin: overlay` with `based_on` the built-in Soc; `custom` becomes `origin: overlay` without `based_on`. Value status maps `confirmed` to the package status that matches its source (`datasheet`, `sdk` or `measured`), `fitted` to `fitted`, `unverified` to `unverified` | Provenance parity: per value, the mapped status and source equal today's record |
| The NPU clock per mode comes from the npu-0 clock domain point of each system operating point (`target.npu_mhz(mode)`) | Clock parity: per mode, the clock equals today's `npu_clock_hz` |
| `soc_overrides` becomes a Soc overlay; a `null` memory removal becomes `memories_removed`. Corstone-320 becomes an `fvp` Implementation with `model` and its own `memories`: its generic SRAM stands in for SSRAM, and its DDR for HBLRAM, PSRAM and RRAM, through `stands_in_for` (per research/queries-helia-estimator.md; [ADR 0007](../adr/0007-fvp-memory-maps.md)) | Override parity: today's override examples produce the same `SocDefinition` projection |

## neuralspotx

| Output that changes | Parity test (#13) |
|---|---|
| Shield board ids (`apollo4p_evb_disp_shield_rev2` and the others) become compositions and keep resolving, to a board target whose `id` is the base board and whose `aliases` keep the shield id | Board-id parity: every neuralspotx board id resolves to a target whose `id` equals it, except compositions, which resolve to board plus add-ons; `atomiq110_fpga_turbo` resolves to an implementation target, not a board |
| Exact-case Soc and board ids are unchanged | Id parity: every non-composition neuralspotx board id and every SoC fact-file id is a catalog id, exact case; the catalog may also hold ids neuralspotx lacks (`apollo3_blue_evb`, `apollo3_blue_thin_evb`) |

## Custom definitions in every tool

Custom SoC and board keys that are not facts of the new model move, with a
one-release shim in each tool that reads the old key and warns:
`jlink_device` on a custom SoC moves to the Part or Board override;
`preferred_memory_order` and `min_alignment` move to the tool's
`extensions` entry (proposal). If open question 4 rejects `extensions`,
each tool keeps a sidecar file keyed by catalog id instead. Covered by
each tool's custom-format parity test in #13.

## Relationship to helia-aot#278

| #278 phase | Where it lands |
|---|---|
| 0: `resolve_platform` stops mutating the registry (#331) | heliaAOT, unchanged; the package's immutable catalog removes the class of bug for adopters. |
| 1: Soc/Board split, `NpuSpec`, ISA derivation | This package. `SocPlatform` stays heliaAOT's flattened view, built by an adapter. |
| 2: `platform.soc:` config surface | heliaAOT accepts the overlay format (`platform.overlay`) and a `platform.soc:` shorthand that builds a one-entry overlay. |
| 3: NPU variant cross-check | heliaAOT, reading `NpuInstance.npu.accelerator_config` from here. |
| 4: aliases and family shorthands | This package's resolver. |

Changes relative to #278's model: an implementation layer between Soc and
Board (bring-up FPGA and FVP as implementations, the FPGA on a Board of
category `fpga`, and the J-Link device per part), capabilities
derived from `CoreOptions` rather than a cpu-string table,
`preferred_memory_order` and `min_alignment` removed from the shared
model, memory regions with technology, attachment and characterization,
operating points instead of a speeds list, ordered cores and accelerators
with an explicit access matrix instead of one cpu string, provenance on
every fact, an
immutable catalog with overlays instead of registration, and overlays
may add aliases (#278 allowed built-in aliases only), still never
shadowing a built-in id or alias.
