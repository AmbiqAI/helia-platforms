<!--
Provenance: imported on 2026-10-04 from 0005-platform-ssot-appendix.md
(dated 2026-09-30), the appendix to the draft heliaAOT RFC 0005.
Renumbered to accompany RFC 0001 in this repository. Text unchanged except
this header, the RFC link and the dated amendment note that opens section C. Line references inside are to the revisions
named in the first paragraph and will drift; re-verify before relying on one.
-->

# RFC 0005 appendix: implementation notes

Companion to [RFC 0001](0001-platform-catalogue.md). The RFC states the design;
this appendix holds the verified detail the adoption PRs and the
helia-profiler review work from: where every symbol goes, every reader that
changes, every number and its source, and the derived change lists. Line
references are to heliaAOT `main`, helia-profiler `origin/main`
(`2d0096c0`), neuralspotx `origin/main` (`b930d59`), `nsx-ambiq-sdk`
`v5.2.24`/`v5.2.25`, and zephyr `d8be6be` (v4.4.0-1273) with hal_ambiq
`c03d2f9`, as read on 2026-09-30. The RFC reached this form after a first
review and four rounds of independent code-level audits (twelve reviews in
all); each round's findings were verified against the code before being
folded in.

## A. The four sources today

| Source | Shape | What it carries |
|---|---|---|
| heliaAOT `helia_aot/platforms/platforms.py:254-544` | 15 `SocPlatform` literals, board-named | cpu, speeds, memory sizes, capabilities, preferred memory order, alignment |
| helia-profiler `src/helia_profiler/platform/` | 9 `SocDef` + 13 `BoardDef` dataclasses | core tier, core, MVE, memory sizes, clock domains, J-Link device, SWO/RTT, NPU string; memory bases and flash addresses in `capabilities.py`; verified linker windows in `memory_map.py`; profiler policy alongside |
| neuralspotx `src/neuralspotx/boards/<board>/board.yaml` | one YAML per board | soc, tier, `sdk_provider`, core, float ABI, ABI string, toolchains (the `cpu` block is a copy of the SDK's) |
| nsx-ambiq-sdk `cmake/socs/facts/<soc>.cmake` + `modules/nsx-core/src/<soc>/{gcc,armclang}/` | 11 CMake fact files; one to four linker scripts per SoC and toolchain | series, core, arch class, DSP/MVE/FPU, PMU tier, ABI flags, compile definitions, SEGGER device / flash address / trace clock; linker `MEMORY` windows |

The profiler's name map: `_BOARD_TO_AOT_PLATFORM`
(`engines/helia_aot/compile.py:55-68`) sends `apollo330mP_evb`,
`apollo510dL_evb` and `apollo510b_evb` to heliaAOT's `apollo510_evb`
(`compile.py:63,66-67`), although heliaAOT has `apollo330mp_evb`,
`apollo510l_evb` and `apollo510b_evb`. hpx re-applies its own capacities
after planning and raises on overflow
(`stages/plan_memory.py:264-276,338-341`). `hpx analyze` passes the raw
board name (`evaluation/engine_analysis.py:72`), which heliaAOT case-folds
to `apollo330mp_evb`, so the two hpx commands disagree with each other.
heliaAOT's `platform.h.j2:96-117` (Zephyr module type) picks the TCM
section macros by matching the start of the platform name; the e2e harness
derives fp16 support from `TARGET_CPU`
(`tests/e2e/templates/CMakeLists.txt.j2:167-171,186-195`). Issue #229 names
`platform/` as a "future shared-package seam"; `placement.py:5` and
`tests/test_package_layout.py:283-284` keep it importable on its own.

## B. Entities

```
CoreDef      cortex-m4, cortex-m55  (ids: the profiler's CoreArch)
             arch_class, isa, pmu_tier (the profiler's PmuTier: dwt | pmu)
NpuDef       ethos-u85-256
             vendor, kind, macs_per_cycle, vela_accelerator_config
SocDef       apollo3, apollo3p, apollo4p, apollo4l, apollo510, apollo510b,
             apollo5b, apollo330P, apollo510L, atomiq110
             series, core_tier, core -> CoreDef, description,
             fpu: none|fpv4-sp-d16|fpv5-sp-d16, fpu_dp, mve: none|int|fp,
             has_dcache, npu: NpuInstance | None,
             memories: tuple[MemoryRegion], clocks: tuple[ClockDomain],
             jlink_device (default), swo_trace_clock_mhz,
             c_define, cmsis_header, ssram_full_power_enum,
             has_radio_subsystem,
             zephyr_tcm_sections: (bss_section, data_section) | None,
             helia_aot: {capabilities, preferred_memory_order, min_alignment},
             aliases, origin, registered_name
NpuInstance  npu -> NpuDef, clocks: tuple[ClockSpeed], base_address, irq;
             vela_accelerator_config passes through to the NpuDef
MemoryRegion name (e.g. dtcm, ssram0, ssram1), kind
             (mram|sram|dtcm|itcm|psram|nvm|hblram), size, base,
             executable, writeable, external, provenance
LinkWindow   (board, linker_profile, link_family) -> per region:
             origin, length, app_window, section_attributable,
             window_provenance, app_provenance; source_tag
BoardDef     soc -> SocDef, tier (evb|fpga|custom), is_fpga,
             external memories (board-level MemoryRegion: psram, nvm),
             clocks override, swo_trace_clock_mhz override,
             jlink_device override, starter_profile_board, description,
             helia_aot override, aliases
```

- `SocPlatform.speeds` is the `cpu` clock domain's MHz list (board override
  first).
- `app_flash_load_addr(board, profile)` is an accessor over the windows
  table (the MRAM window's origin: `0x410000` on Apollo5 `sbl`, `0xC000` on
  Apollo3, `0x18000` on Apollo4, `0x22000000` on atomiq110 `nbl`), not a
  stored field; the profiler's `rtt_scan_ranges` is not a package field
  (section C).
- `zephyr_tcm_sections` is `("__dtcm_bss_section", "__dtcm_data_section")`
  on Apollo5 parts, `("__itcm_section", "__itcm_section")` on
  Apollo3/Apollo4 (their Zephyr devicetrees name the TCM region `"ITCM"`,
  `ambiq_apollo4p.dtsi:67`), and `None` on atomiq110, which reproduces
  `platform.h.j2:96-117`.
- Derived properties: `supports_fp16` is true iff `mve == fp` (the only
  fp16-arithmetic signal: FPv4 on the M4 only converts, and the SDK builds
  the M55 with `fpv5-sp-d16`, `cmake/nsx_toolchain_flags.cmake:208`; ATfE
  uses `fp-armv8-fullfp16-sp-d16`); `supports_fp32` is `fpu != none`;
  `supports_fp64` is `fpu_dp`, the CMSIS device header's `__FPU_DP` (1 on
  the M55 parts, 0 on the M4 parts); `supports_npu` is `npu is not None`.
- Boards, the union of both catalogs: from helia-profiler `apollo3p_evb`,
  `apollo3p_evb_cygnus`, `apollo4p_evb`, `apollo4l_evb`, `apollo4l_blue_evb`,
  `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `apollo510_evb`,
  `apollo510b_evb`, `apollo5b_evb`, `apollo330mP_evb`, `apollo510dL_evb`,
  `atomiq110_fpga_turbo`; from heliaAOT `apollo3_evb`, `apollo3_blue_evb`,
  `apollo3_blue_thin_evb` (SoC `apollo3`; neuralspotx also ships
  `apollo3_evb`). heliaAOT's `apollo3_blue_plus_evb` and `apollo3p_evb` are
  identical entries (`platforms.py:302-333`); `apollo3_blue_plus_evb`
  becomes an alias of `apollo3p_evb`. `apollo510l_evb` becomes an alias of
  `apollo510dL_evb`: Ambiq sells one Apollo510 Lite evaluation board, the
  AP510DLEVB, fitted with the Apollo510D Lite (AP510DLA; BLE 5.4 and
  Bluetooth Classic); the SoC entry `apollo510L` covers the series' three
  parts (AP510NLA, AP510BLA, AP510DLA), which share the core, clocks
  (96 / 192 / 250 MHz) and memories (2 MB NVM, 2 MB SRAM as 1792 KB SSRAM +
  256 KB DTCM). neuralspotx's `apollo2_evb`, `apollo3_evb_cygnus` and
  `apollo4p_evb_disp_shield_rev2` are not in the catalog: neither tool
  supports them, and neuralspotx is not a consumer.
- `ethos-u55-128` is the Corstone-300 FVP configuration heliaAOT's e2e
  harness uses (`CMakeLists.txt.j2:227-239`), not a SoC, and is not in the
  catalog.
- Seed rule for the `helia_aot` section of a board heliaAOT has no literal
  for: `min_alignment` 4 on M4 and 16 on M55; `preferred_memory_order`
  DTCM → SRAM → MRAM (ITCM never, PSRAM only where declared: today only
  `apollo510_evb`); `capabilities` MCU, DSP, plus MVE when `mve != none`,
  FP16 when `mve == fp`, NPU when an NPU is present, PSRAM when the board
  has a PSRAM region.

## C. Facts and policy, by symbol

**Amendments (2026-11-07).** The owner signed the table off on #15 as
amended by helia-profiler's position of the same day, read against profiler
main `6231cd2e` under [ADR 0010](../adr/0010-facts-not-policy.md) and the
owner decision on #73 (linker windows stay in the consumers). The table
below is kept as written; these amendments take precedence over it, and
over every other passage of this appendix (sections B, D, E, F, G and I)
and of RFC 0001 that puts `LinkWindow`, `linked_memory_map`, a `windows`
command or `app_flash_load_addr(board, profile)` over a windows table into
the package. RFC 0002's "Link environments" text and ADR 0006 section 4
still describe the dataset; #73 amends them.

- *Flash address row.* `_FAMILY_APP_FLASH_LOAD_ADDR` and
  `_SOC_APP_FLASH_LOAD_ADDR` no longer exist; `capabilities.py` reads
  `memory_map.mram_app_origin`. The catalog side is
  `Target.flash_load_address()`, derived from boot configurations, not a
  windows table. The profiler keeps recipe precedence, its explicit
  override and its refusal of an unknown address.
- *RTT scan ranges.* Profiler policy over the catalog's apertures and the
  profiler's own windows, not "the package's windows".
- *Address tables and `soc_placement_ranges`.* The catalog supplies sourced
  physical regions (`placement_ranges()`) and, for the pre-build fit check,
  the ranges an application may occupy in each region after the boot
  reservations and other cores' image slots (`application_ranges()`, #73),
  which keep the gaps and tell an unknown region from an empty one. On the
  `apollo330mP_evb` and `apollo510dL_evb` boards, whose fitted parts carry
  a 432 KB radio firmware slot, MRAM is `[0x00410000, 0x00594000)`: the
  physical range intersected with the nsx window would wrongly include
  the slot. Other parts of those Socs carry a 16 KB or 288 KB slot and give
  their own end. The profiler
  keeps its logical-placement mapping. No family, FPGA or script-derived
  address is copied wholesale, and no window enters the catalog.
- *`memory_map.py`.* Stays in the profiler in full: `LinkFamily`,
  `LinkedRegionWindow`, `_MAPS`, `_window`, `linked_memory_map`,
  `classify_address`, the family window constants and `mram_app_origin`.
  The profiler will regenerate the windows from the nsx-ambiq-sdk it
  resolves, with source hashes and a drift check; that generator is not
  written yet (#73). `classify_address` consumes those windows.
- *Placement enums.* Physical region kinds may map to catalog regions;
  `Placement`, `ArenaRole`, `Placement.region` and `_PLACEMENT_REGION` stay
  in the profiler as tool choices ("TCM means DTCM; ITCM never holds
  weights", scratch and constant overrides).
- *`MemoryLayout`.* Still present; it is replaced by the catalog's
  `application_ranges()` intersected with the profiler's windows, not by
  catalog windows.
- *SoC facts and clocks.* As the table says. `ClockDomain.default` is the
  profiler's choice for an omitted option. The profiler's `SocDef` has
  `has_mve` and no explicit FPU field; the catalog answers both through
  `Target.isa()`.
- *Board facts.* `starter_profile_board` and `profile_source_board` select
  NSX metadata and stay in the profiler. `ble_reset_gpio_pin` is BSP wiring
  and moves to the catalog once sourced (#157); whether the profiler holds
  it low stays with the profiler. Channel and measurement GPIO defaults
  stay.
- *Custom builders and registry.* Only factual overlay loading migrates;
  the profiler's config keys, policy parsing, hints and
  `_reject_unknown_keys` stay in its compatibility adapter. No mixed
  builder moves wholesale.
- *Counters and capabilities.* Capture decisions, pass planning and the
  capability wrappers stay in the profiler. Arm PMU event ids are sourced
  facts of the core IP and move to the catalog once sourced (#158). The
  profiler will read PMU and cache presence from the catalog
  (`Target.isa().has_pmu` and `pmu_kind`; the cache sizes are per core
  instance, `CoreInstance.options.icache_kb` and `dcache_kb`, which
  `Target.core_options` gives for core 0 and `Target.cores()` for each
  core. The application core's sizes are sourced on apollo510, apollo510b,
  apollo510L and apollo330P, and recorded but unverified on atomiq110
  (#68); the Lite parts' radio core records an 8 KB I-cache. They are
  absent on purpose elsewhere: apollo4p and apollo4l's 64 KB cache is an
  NVM cache (#66), and apollo3 and apollo3p's 16 KB cache is the flash
  cache) rather than inferring them from the Soc family.
- *Symbols the table omits.* `CoreArch`, `PmuTier`, `ClockDomain.speed`
  and `speed_names`, `SocDef.clock_domain` and `cpu_clock` map to catalog
  queries. `PlatformRegistry`, `_freeze_registry`, `_SOCS`, `_BOARDS` and
  `_register_board` map to catalog registration with profiler policy
  attached. The capability record classes, the timer and attach predicates
  and the reset tokens stay profiler wrappers. `DEFAULT_*_GPIO_PIN`, the
  custom-field validators, `_PLACEMENT_SIZE_FIELD` and the family window
  constants stay in the profiler. The `platform/__init__.py` exports remain
  the profiler's compatibility surface.

The facts named above that move once sourced are data issues, not rules:
#157 (the BLE reset pin) and #158 (PMU event ids and cache presence).

| Symbol (today) | Where it goes | Why |
|---|---|---|
| `SocDef` fields: core, MVE/FPU, memories, clocks, `c_define`, `cmsis_header`, `swo_trace_clock_mhz`, `ssram_full_power_enum`, `has_radio_subsystem` | package | silicon, SDK or HAL facts, all drift-testable |
| `SocDef.app_flash_load_addr` (with `_FAMILY_APP_FLASH_LOAD_ADDR`, `_SOC_APP_FLASH_LOAD_ADDR`, `resolve_app_flash_load_addr`) | package, as the accessor `app_flash_load_addr(board, profile)` over the windows table; readers `stages/flash.py:50-51`, `stages/flash_power.py:52`, `target/probe/flash.py` | equals the default script's MRAM origin (`NSX_SEGGER_PF_ADDR`) for every SoC; a stored copy would be a second thing to keep in sync |
| `SocDef.rtt_scan_ranges` (`soc.py:386-732`: `(0x10000000, 0x100000)` on M4 parts, the DTCM window on M55 parts) | profiler, as a rule over the package's windows; reader `transport/rtt.py:733` | hpx's choice of where to scan for the RTT control block, not a chip fact |
| `SocDef.jlink_device`, `SocDef.swo_trace_clock_mhz`, `SocDef.clocks` | package, board override + SoC default; profiler reads `jlink_device_for(board)`, `swo_trace_clock_for(board)`, `clocks_for(board)`. Where no silicon board exists to measure the trace clock, the SoC value is `None` (core-clocked) | board realizations differ (FPGA); the J-Link name is package-specific |
| `SocDef.family` | package as `core_tier` (readers: `plan_memory.py:401-475`, `validation/matrix.py:233`, `capabilities.py`); new `series` from the SDK | two different groupings |
| `SocDef.capabilities` property, `requires_attached_probe_for_cycles`, `has_full_pmu`, `profiling_backends`, `profiling_domains` (`soc.py:269-324`) | profiler, as functions of `SocDef` | policy; the first imports `build_soc_capabilities` |
| `SocDef.pmu_max_ops`, `SocDef.has_usb` | profiler tables keyed by SoC id; for custom SoCs, resolved through the `based_on` chain or the entry's `profiler` section | capture-buffer sizing; driver support |
| `SocDef.has_mve`, `SocDef.npu` (Vela string) | package exposes `has_mve` and `NpuInstance.vela_accelerator_config` as compatibility accessors | readers compare them (`engines/cmsis_nn.py:61`, `stages/preflight.py:378-410`) |
| `capabilities.py` address tables (`:271-369`) and `soc_placement_ranges` (`soc.py:761-779`) | package, folded into regions and windows; `placement_ranges(soc, board)` | facts |
| `memory_map.py` (`LinkFamily`, `LinkedRegionWindow`, `_MAPS`, `_window`, `linked_memory_map`, `classify_address`) | package, as `LinkWindow`, `linked_memory_map(soc, board, profile, family)`, `classify_address` | verified facts with provenance |
| `memory_map.py` `link_family_for_toolchain` / `_LINK_FAMILY_BY_TOOLCHAIN` | profiler | maps hpx toolchain names (`vocab.Toolchain`) |
| `placement.py` `Placement`, `MemoryRegion` enum, `ArenaRole` | package, enum renamed `PlacementRegion`; `helia_profiler.placement` re-exports | `memory_map.py:75` imports them |
| `placement.py` slack constants | profiler | policy |
| `soc.py` `MemoryLayout` | removed; `plan_memory.py:45,55-61` (`_REGION_FIELDS`) reads window lengths by region kind instead | regions replace it |
| `soc.py` `MemoryRange`, `ClockSpeed`, `ClockDomain`, `PerfTier`, `SocOrigin`, `_register_soc` | package | |
| `BoardDef` fields: `soc`, `is_fpga`, `starter_profile_board`, `description`, `psram_kb` | package (`psram_kb` becomes an external region; `apollo510dL_evb`'s 0 becomes no region) | board facts |
| `BoardDef.channel`, `default_*_gpio_pin`, `ble_reset_gpio_pin` | profiler board-policy record keyed by board id (readers: `config/__init__.py:836-859`, `firmware/__init__.py:181,322`, `firmware/context.py:410,449`, `firmware/project.py:244-252`, `cli/inspect_cmds.py:169`, `console/presentation.py:124`) | measurement wiring and support tier |
| `registry.py` `build_platform_registry`, `get_soc`, `get_board`, `list_*` | package | |
| `registry.py` `get_soc_for_board` (folds `board.psram_kb` into a SoC copy, `:83-92`) | removed; every caller (11 source files outside `platform/`, entering at `stages/resolve_platform.py:38`, plus 9 test files) takes `(soc, board)` | PSRAM is a board region |
| `registry.py` GPIO default lookups (`:95-134`) | profiler, reading its policy record | |
| `custom.py` builders, `_reject_unknown_keys` | package (overlay v2); profiler keeps a v1→v2 shim | |
| `custom.py`'s `ConfigError` (`:23`) | package raises `helia_platforms.PlatformError`; the profiler wraps it in `ConfigError` with a hint | the package cannot import `helia_profiler.errors` |
| `SocOrigin`, `is_builtin`, `registered_name`, `based_on` | package | provenance; `memory_bases_like` is removed because `based_on` copies regions |
| `counters.py`, `SocCapabilities` builders, plan-memory family tables | profiler | policy |

Naming mechanics: ids are the SDK/NSX spellings and are matched
case-insensitively. `aliases` exist for genuine renames:
`apollo3_blue_plus_evb → apollo3p_evb`, `apollo510l_evb → apollo510dL_evb`.
`resolve_board("atomiq110")` returns `atomiq110_fpga_turbo` because the
SoC has one board; a SoC with several boards raises and lists them.
heliaAOT's registry keys and `SocPlatform.name` are the lowercase form; its
`_canonical_platform_name` delegates alias and SoC-id resolution to the
package. `_BOARD_TO_AOT_PLATFORM` is deleted; hpx's
`engine.config.platform_name` override (`compile.py:96-99`, documented)
survives as an escape hatch.

## D. Memory: physical regions, windows, sources

Physical regions and their sources:

| SoC | Regions (KB) | Source |
|---|---|---|
| apollo510 (also apollo510b, apollo5b, which have no headers of their own) | ITCM 256, DTCM 512, SSRAM 3072, MRAM 4096 | `mcu/apollo510/regs/am_reg_base_addresses.h` |
| apollo330P / apollo510L | DTCM 256, SSRAM 1792, MRAM 2048 | `am_reg_base_addresses.h` |
| atomiq110 | DTCM 512, SSRAM 3072, RRAM 4096 (kind `mram`), HBLRAM 13312; ITCM 256 | header; ITCM has no header define and comes from the linker script |
| apollo4p | TCM 384, SSRAM0 1024, SSRAM1 1024, EXTRAM 384, MRAM 2048 | header |
| apollo4l | TCM 384, SSRAM0 1024, MRAM 2048 | header (SSRAM1/EXTRAM are 0) |
| apollo3p | TCM 64, SRAM 704 (768 − TCM), flash 2048 | `am_reg_base_addresses.h` for TCM; `hal/am_hal_flash.h:71,86-87` for SRAM and flash |
| apollo3 | TCM 64, SRAM 320 (384 − TCM), flash 1024 | same headers |

Board external regions: PSRAM on `apollo3p_evb`/`_cygnus` (8192),
the five Apollo4 boards (32768, but see the reconciliation row for the
plain `apollo4p_evb`), `apollo510_evb`/`apollo510b_evb` (65536),
`apollo5b_evb`/`apollo330mP_evb` (32768), none on `apollo510dL_evb` and
`atomiq110_fpga_turbo`; NVM 8192 on `apollo510_evb` (the profiler's
`nvm_kb`; no reader today).

**nsx / neuralSPOT (`gnu`, `armlink`).** Windows are what the SDK's linker
script gives the program. Sources of difference from the physical size,
verified in the scripts:
- the secure-bootloader region at the start of MRAM (64 KB on Apollo5 `sbl`,
  48 KB on Apollo3, 96 KB on Apollo4; none on `nbl`, which atomiq110 defaults
  to);
- a stack/heap reservation at the top of TCM on Apollo5 parts (16 KB in the
  gcc scripts, 20 KB in the armclang scatter files; apollo4p: none in gcc,
  20 KB in armclang);
- a 4 KB `STACKMEM` carved from SRAM on apollo3p; on apollo3 the script is
  one flat 384 KB `RWMEM` covering TCM and SRAM;
- bank selection: the apollo4p scripts link SSRAM0 only.
- The SDK's `nbl` and `itcm_sbl` scripts for apollo330P/apollo510L carry
  apollo510's sizes (an upstream bug the profiler already works around), so
  only the default `sbl` profile is verified for those parts.
- Legacy neuralSPOT's apollo3p script gives 695 KB of SRAM where nsx gives
  700; the `neuralspot` module type uses the nsx window and accepts the
  5 KB overstatement. Its apollo510 and apollo4p scripts match nsx.
- nsx modules built with armclang have 4 KB (Apollo5) or 20 KB (Apollo4)
  less TCM than the `gnu` budget; accepted and documented.

**Zephyr (`zephyr`).** Zephyr generates its linker script from the
devicetree, and its Ambiq devicetrees already carry the SDK's reservations:
the Apollo510 SoC file takes its sizes from hal_ambiq's `am_apollo510.h`
(`DTCM_MAX_SIZE 0x7C000`, `MRAM_BASE_ADDR 0x410000`, `MRAM_MAX_SIZE
0x3F0000`), Apollo3 applies `FLASH_LOAD_OFFSET 0xc000`, and the Apollo3P
and Apollo4 flash nodes start at `0xc000` / `0x18000`. Stacks and heap are
Kconfig-sized sections inside the regions. Zephyr ships six Ambiq boards,
and the `zephyr` rows exist only for those (from the board and SoC
devicetrees in the Zephyr tree):

| Board | TCM | SRAM | MRAM (window @ origin) | ITCM |
|---|---|---|---|---|
| apollo510_evb | DTCM 496 | 2048 (`sram0` overridden; 1 MB `sram_no_cache` carved; `soc/ambiq/apollo5x/shared_ram.ld` places a NOLOAD `ambiq_dma_buff` section at offset `0x50000` *inside* `sram0`, sized by the drivers that use it, not a further carve-out) | 4032 @ 0x410000 | 256 |
| apollo4p_evb | 384 (named `ITCM`) | 2432 (three banks) | 1952 @ 0x18000 | — |
| apollo4p_blue_kxr_evb | 64 (named `ITCM`) | 2752 | 1952 @ 0x18000 | — |
| apollo3p_evb | 64 | 704 | 2000 @ 0xc000 | — |
| apollo3_evb | 64 | 320 | 976 @ 0xc000 | — |
| apollo2_evb | not in the catalog | | | |

heliaAOT budget wiring: a `SocPlatform` carries `budgets: {gnu: ...,
zephyr: ...}`; its `memories` is the `gnu` budget.
`resolve_platform(cfg, module_type=None)` returns the registered object for
`neuralspot`, `nsx`, `cmake`, `cmsis_pack` and `None`, and a copy with
`memories = budgets["zephyr"]` for `zephyr`; a board with no `zephyr`
budget uses `gnu` with a warning. `target-info` and `targets.json` print
every budget.

## E. Custom definitions (overlay v2) and the v1 shim

The package parses one YAML shape: `socs:`/`boards:` maps, `based_on`
(copies every field of the base, tool sections included, then applies the
entry's keys), regions keyed by name with `size` and optional `base`
(required for built-ins), `remove: [psram]` to drop an inherited region,
`helia_aot:`/`profiler:` sections handed to the tool that owns them,
unknown keys rejected with a suggestion. An entry whose regions have no
`base` has no windows: `classify_address` and `linked_memory_map` raise a
clear error for it, and heliaAOT budgets it by its regions for every link
family. An id that shadows a built-in is rejected. A from-scratch SoC must
give `series` and `core_tier`.

hpx's v1→v2 shim maps every `CustomSocField`, `CustomMemoryField` and
`CustomBoardField` key: `memory.*_kb` → regions (bases from the `based_on`
chain); SoC-level `psram_kb`/`nvm_kb` → board regions; `has_mve: true` →
`mve: fp` on M55 and rejected on M4 (allowed today); `family` →
`core_tier`, with `series` from `based_on`; `pmu_tier` → validated against
the core; `description` → `SocDef.description`; `pmu_max_ops`, `channel`,
`rtt_scan_ranges`, the GPIO pins and `ble_reset_gpio_pin` → `profiler:`;
`app_flash_load_addr` → the custom entry's MRAM window origin, and
`app_flash_load_addr: null` → accepted, no window, and flashing refuses as
today. Two v1 behaviours change and are documented:
`based_on` now inherits `swo_trace_clock_mhz`, `has_usb`,
`ssram_full_power_enum` and `has_radio_subsystem`, and a custom SoC can no
longer replace a built-in id.

heliaAOT's `PlatformArgs` without `overlay` builds a run-local
`SocPlatform` exactly as today (no package entry; `capabilities` declared
directly, one budget for every module type). With `platform.overlay`, the
entries come from the file, and hpx passes its own overlay through so a
custom board reaches heliaAOT. The `SocCapability` enum keeps `BLE` and
`USB` (deprecated) so existing user configs still validate; built-ins never
set them; `PSRAM` is set when the board has a PSRAM region.

## F. Query API and CLI

`resolve_board(name)`, `resolve_soc(name)`, `get_core/get_npu`,
`list_cores/list_npus/list_socs/list_boards`, `boards_for(soc)`,
`socs_with(core=..., mve=..., npu=...)`, `linked_memory_map(soc, board,
profile, family)`, `placement_ranges(soc, board)`, `classify_address`,
`jlink_device_for(board)`, `swo_trace_clock_for(board)`,
`clocks_for(board)`, `app_flash_load_addr(board, profile)`,
`load_overlay(path)`. No I/O at import time.

CLI: `helia-platforms list [socs|boards|cores|npus]`, `show <id>`,
`windows <board> [--profile --family]`, `validate <overlay.yaml>` and
`check-sdk` (the drift test, runnable locally).

## G. The SDK drift test

Superseded by [ADR 0006](../adr/0006-drift-test-snapshots.md), which
compares the catalog with committed snapshots of the SDK, neuralspotx
and Zephyr. The table below is kept as imported.

The package's CI checks out `nsx-ambiq-sdk` at the tags neuralspotx pins
(`registry.lock.yaml`: `v5.2.24`, and `v5.2.25` for atomiq110) and compares:

| Package field | SDK key | Rule |
|---|---|---|
| `series` | `NSX_SOC_SERIES` | equal |
| `core`, `core.arch_class` | `NSX_SOC_CORE`, `NSX_SOC_ARCH_CLASS` | equal |
| `mve != none`, `fpu != none` | `NSX_SOC_HAS_MVE`, `NSX_SOC_HAS_FPU` | equal |
| `fpu` | `NSX_FPU` | `fpv4-sp-d16` on M4; the M55 files carry `""` and are not compared |
| `fpu_dp` | `__FPU_DP` in `CMSIS/AmbiqMicro/Include/<soc>.h` | equal |
| `core.pmu_tier` | `NSX_SOC_PMU_TIER` | `dwt` ↔ `none`, `pmu` ↔ `armv8m` |
| `supports_npu` | `npu` in `NSX_SOC_CAPABILITIES` | equal |
| `c_define` | `NSX_SOC_COMPILE_DEFINITIONS` | member |
| `app_flash_load_addr(board, default)` (the MRAM window origin) | `NSX_SEGGER_PF_ADDR` | equal |
| `swo_trace_clock_for(board) or clocks_for(board)` default MHz | `NSX_SEGGER_CPUFREQ` (the TPIU trace clock) | equal on silicon boards; boards with a neuralspotx `debug.cmake` override compare against that override |
| `gnu` windows, default profile | `MEMORY` blocks of `modules/nsx-core/src/<soc>/gcc/<default>.ld` | equal |
| physical regions | the headers in section D | equal where a define exists |

Excluded until reconciled: `jlink_device` (RFC decision 12). Not compared:
`core_tier`, `clocks` (the SDK carries only the trace clock), `executable`
(the SDK's `rwx` flags differ between apollo4p and apollo4l). The `zephyr`
windows are checked against a Zephyr revision the package pins; the rows
above were read at zephyr `d8be6be` (v4.4.0-1273) with hal_ambiq
`c03d2f9`.

## H. Version pins and co-development

The profiler pins heliaAOT in `pyproject.toml:47`,
`engines/helia_aot/compile.py:42-43` and
`src/helia_profiler/data/compatibility-baseline-v1.json` (fingerprint
asserted by `tests/test_package_layout.py`), echoed by
`tests/test_compatibility.py`, three docs pages and `uv.lock`. `uv lock`
strips the profiler's `x-release-please-version` marker from `uv.lock`
(its AGENTS.md); Phase 3 step 1 restores it.

Co-development: `uv run --with-editable ../helia-platforms <cmd>` (an
ephemeral overlay; a plain `uv pip install -e` is undone by the next
`uv run`); `uv.lock` is never re-locked against a path.

## I. Phase details

### Phase 1 — create the package and publish 0.1.0

1. `AmbiqAI/helia-platforms`, public: uv project, `src/helia_platforms/`,
   Python ≥3.11, setuptools, ruff/ty/pytest, release-please
   (`bump-minor-pre-major`), PyPI trusted publisher.
2. Move the symbols in section C; cut the five policy properties,
   `pmu_max_ops` and `has_usb`; add `series`, `description`, `fpu`, `mve`,
   `has_dcache`, `zephyr_tcm_sections`, regions, `LinkWindow` (nsx rows
   from `_MAPS`, Zephyr rows from the Zephyr tree), `NpuDef`, `NpuInstance`,
   board overrides, the `helia_aot` section (from heliaAOT's literals, seed
   rule for the rest), `aliases`; rename the placement enum.
3. Overlay v2 parser, `PlatformError`, and the CLI.
4. Validators (ids and aliases unique across entities; every reference
   resolves; regions inside physical bounds and non-overlapping; FP16 only
   with MVE-FP; MVE only on Armv8.1-M; catalog snapshot) and the SDK
   drift test.
5. Reconcile the data (section J).
6. helia-profiler maintainers sign off on section C.
7. Tag 0.1.0, publish to PyPI.

### Phase 2 — heliaAOT

1. Dependency `helia-platforms>=0.1,<0.2`; re-lock `uv.lock`.
2. `platforms/platforms.py`: replace the literals with an adapter that
   builds one `SocPlatform` per board (lowercase name, `soc` id in NSX
   spelling, `budgets`, `memories` = `gnu`). `resolve_platform` gains an
   optional `module_type` passed from `converter.py:180`;
   `_canonical_platform_name` delegates aliases and SoC ids to the package.
   Public names (`platforms/__init__.py`, `api_manifest.json`) unchanged;
   `SocPlatform` gains `soc` and `budgets`.
3. One PR. Regenerate `targets.json` (gains `budgets`; bump its
   `export_schema_version` and extend `docs/scripts/render-generated.mjs`),
   `residency-example.json`, `residency-example-placed.json`,
   `config-schema.json` and `cli.json` (for `platform.overlay`), and update
   `guide/memory-reports.mdx:67`; the diffs are the change list and the PR
   description explains each line. Derived from the RFC's rules, the list
   is:
   - budgets (`gnu`): apollo510/510b DTCM 512→496 KB, MRAM 4096→4032;
     apollo330mp/apollo510l DTCM 256→240, MRAM 2048→1984; apollo3p MRAM
     2048→2000, SRAM 704→700; apollo3 boards MRAM 1024→976; apollo4p/4l
     MRAM 2000→1952; atomiq110 unchanged;
   - budgets (`zephyr`), new column, for the five catalog boards Zephyr
     supports (section D);
   - PSRAM: apollo510 32168→65536 KB; new PSRAM memory on apollo3p_evb,
     the five Apollo4 boards, apollo510b_evb and apollo330mp_evb, with the
     PSRAM capability, not in `preferred_memory_order`; NVM 8192 on
     apollo510_evb (no `MemoryType`, so not exported);
   - clocks: atomiq110 100/250/500→25 MHz (FPGA board);
   - capabilities: BLE and USB removed everywhere;
   - targets: `apollo5b_evb`, `apollo3p_evb_cygnus`, `apollo510dl_evb`,
     `atomiq110_fpga_turbo` added; `atomiq110`, `apollo3_blue_plus_evb`
     and `apollo510l_evb` become aliases and leave the listing (they still
     resolve); the residency examples move with the apollo510_evb `gnu`
     DTCM budget (479928→463544 and 524032→507648 bytes);
   - plan JSON (`<prefix>_plan.json`, documented in `guide/options.mdx`,
     not snapshot-checked): `platform.capabilities` loses BLE/USB and gains
     PSRAM where added; `placement` budgets move with the `gnu` numbers;
   - HBLRAM 13312 on atomiq110 (no `MemoryType`, so not exported);
   - `templates/nsx/nsx-module.yaml.j2:44-53`: the dead `apollo510l` entry
     becomes `apollo510L` (neuralspotx matches SoC ids exactly), and the
     list is generated from the catalog's SoC ids; it stays unconditional,
     as `tests/unit/aot/test_ethos_u_driver_contract.py:210-213` requires,
     so no module's compatibility narrows;
   - `TargetChips.astro` gains the `apollo5` stem, placed after `apollo510`.
4. `platform.h.j2:96-117` reads `zephyr_tcm_sections`. e2e harness: pass
   an F16 flag from `supports_fp16` (`test_e2e.py:605`; both CMake sites).
   `ethosu_operator.py:105`'s hint names `atomiq110_fpga_turbo`.
5. `PlatformArgs` gains `platform.overlay`.
6. Tests: `tests/unit/platforms/*` (incl. `test_platform_resolution.py:34-37`
   and `:294-296`, which pin `atomiq110` as a key and identity of the
   resolved object), `tests/unit/aot/test_ethos_u_platform_gating.py:73`,
   `tests/unit/aot/test_ethos_u_driver_contract.py:202-213`. Docs:
   `guide/targets.mdx` (capabilities list, names),
   `getting-started/targets.mdx` excerpt, README excerpts, AGENTS.md §16
   (the lowercase rule is unchanged; one sentence is added: "canonical ids
   come from `helia-platforms`").
7. Release heliaAOT.

### Phase 3 — helia-profiler

1. Dependency `helia-platforms>=0.1,<0.2`; raise the heliaAOT pins and their
   echoes to the Phase 2 release; restore the release-please marker in
   `uv.lock`.
2. `platform/` keeps policy only: `capabilities_for(soc)`,
   `profiling_backends/domains`, the board-policy record, `pmu_max_ops` and
   `has_usb` tables, `link_family_for_toolchain`, slack constants,
   `counters.py`. hpx's capacity checks (`stages/plan_memory.py:255-262,
   653-654`, `engines/helia_aot/compile.py:160-161`,
   `validation/matrix.py:228-229`) read the default-profile window of the
   selected link family (`gnu` or `armlink`). **hpx output change:** today
   `SocDef.memory` holds physical sizes on Apollo5 (512/4096 KB) and 2000 KB
   MRAM on Apollo4, so those checks tighten to 496/4032 and 1952 KB (and
   492 KB DTCM under armclang). Every `get_soc_for_board` caller takes
   `(soc, board)`; `jlink_device` readers (capture, terminal transport,
   inspect commands, session, probe resolution, lifecycle, flash stages,
   fixture target, validation matrix) use `jlink_device_for(board)`;
   `swo_trace_clock_mhz` readers (`transport/swo.py:210`,
   `capture/terminal_transport.py:159`) use `swo_trace_clock_for(board)`;
   `rtt_scan_ranges` (`transport/rtt.py:733`) comes from the profiler's
   rule over the windows; flash stages use `app_flash_load_addr(board,
   profile)`; `soc.family` readers use `core_tier`; `board.channel` readers use the
   policy record; `soc.core`/`pmu_tier` comparisons keep their enums.
3. Delete `_BOARD_TO_AOT_PLATFORM`; `analyze_for_engine` resolves the board
   through the registry and accepts `target.overlay`. **Output change:**
   `apollo330mP_evb`, `apollo510dL_evb` and `apollo510b_evb` compile
   against their own heliaAOT targets; `apollo5b_evb` gains one.
4. NSX emission sites are unchanged (canonical ids are the NSX spellings),
   except `firmware/project.py:85`, which gains `.lower()` to match
   neuralspotx's module ids (`nsx-board-apollo330mp-evb`).
5. `target.overlay` and the v1→v2 shim with a logged deprecation; docs.
6. `test_package_layout.py`: a rule that `platform/` may import
   `helia_platforms`. Rewritten tests: `test_platform.py`,
   `test_memory_map.py`, `test_jlink.py`, `test_verify_placement.py`,
   `test_flash_stage.py`, `test_power.py`, `test_plan_memory.py`,
   `test_probe_cli.py`, `test_session.py`, `test_config.py`,
   `test_firmware.py`, `test_aot_placement_rulesets.py`,
   `test_helia_aot_adapter.py`, `test_aot_manifest.py`,
   `test_rtt_reader.py`, `test_validation_matrix.py`,
   `contracts/test_board_resolution.py`, `contracts/test_window_matrix.py`,
   `contracts/test_firmware_render_snapshots.py`,
   `contracts/test_reset_ownership.py`,
   `contracts/test_transport_selection.py`.
7. CI and docs: nothing renames.

### Phase 4 — 1.0 and follow-ups

1. Tag 1.0.0 once both consumers are on the package; consumers move to
   `>=1.y,<2`.
2. hpx fixture code that hard-codes `apollo510_evb`, `lp` and 96 MHz
   (`fixture_target.py:21`, `fixture_operator_timing.py:13-14`,
   `fixture.py:313`) reads the registry.
3. `tests/e2e_zephyr` gains a map-file assertion so the `zephyr` window rows
   are checked by a real build.

## J. Data reconciliation

| Fact | heliaAOT | helia-profiler | physical | default gnu window | resolution |
|---|---|---|---|---|---|
| apollo510/510b/5b TCM | 512 KB | 512 KB | 512 KB | 507904 B = 496 KB | region 512; gnu budget 496 |
| apollo510/510b/5b MRAM | 4096 KB | 4096 KB | 4096 KB | 4128768 B = 4032 KB (`sbl`) | region 4096; gnu budget 4032 |
| atomiq110 TCM | 496 KB | 496 KB | 512 KB | 507904 B = 496 KB | region 512; gnu budget 496 |
| atomiq110 MRAM | 4096 KB | 4096 KB | 4096 KB (RRAM) | 4194304 B = 4096 KB (`nbl` default) | unchanged |
| atomiq110 ITCM | 256 KB | 256 KB | no header define | 262144 B | region 256 from the linker |
| apollo330P / apollo510L TCM | 256 KB | 240 KB | 256 KB | 245760 B = 240 KB | region 256; gnu budget 240 |
| apollo330P / apollo510L MRAM | 2048 KB | 1984 KB | 2048 KB | 2031616 B = 1984 KB | region 2048; gnu budget 1984 |
| apollo3p MRAM / SRAM | 2048 / 704 KB | 2000 / 700 KB | 2048 / 704 KB | 2048000 / 716800 B = 2000 / 700 KB | regions 2048 / 704; gnu budget 2000 / 700 |
| apollo3 MRAM / RAM | 1024 / 320 + 64 KB | — | 1024 / 384 KB incl. TCM | 976 KB / 384 KB flat | regions 1024, TCM 64, SRAM 320; gnu budget 976 / 320 + 64 |
| apollo4p / apollo4l MRAM | 2000 KB | 2000 KB | 2048 KB | 1998848 B = 1952 KB | region 2048; gnu budget 1952; today's 2000 matches neither |
| apollo4p SRAM | 1024 KB | 1024 KB | SSRAM0 1024 + SSRAM1 1024 + EXTRAM 384 KB | 1024 KB (SSRAM0) | regions per bank; gnu budget SSRAM0; zephyr 2432 |
| apollo510_evb PSRAM | 32168 KB (typo) | 65536 KB on the SoC | board fact | not linked | board region 65536 KB per the profiler's hardware note; confirm on the EVB datasheet |
| PSRAM elsewhere | none | see section D | board facts | not linked | board regions; heliaAOT gains PSRAM on those targets |
| apollo330P / apollo510L clocks | 96/192/250 | 96/250 | HAL: LP 96, HP1 192, HP2 250 | | 96/192/250 |
| atomiq110 clocks | 100/250/500 | 25 (FPGA) | HAL: 100/250/500 | | SoC 100/250/500; board override 25 |
| J-Link | | SoC-level: apollo4p `AMAP42KP-KBR`, apollo510b `AP510BFA-CBR`, apollo330P `Apollo330P_510L`, apollo510L `AP510L` | SDK facts: `AP510NFA-CBR` / `AP330MPA-CBR` / `AP510DLA-CBR`; neuralspotx board overrides on eight boards, incl. `AMA4B2KP-KBR`/`-KXR` (apollo4p Blue), `AMA4B2KL-KXR` (apollo4l Blue), `Apollo330P_510L` (apollo330mP_evb) | | board overrides from neuralspotx; SoC defaults from the profiler; check all against SEGGER's device list before drift-testing |
| SWO trace clock, atomiq110 | | core-clocked (25) | SDK fact 25 MHz (FPGA); neuralspotx board override 48 MHz, hardware-measured | | SoC `None`; board override 48 |
| atomiq110 NPU | e2e hard-codes the Corstone U55 | `"ethos-u85-256"` | HAL `am_hal_pwrctrl.h:219-220`: NPU modes ULP 100 MHz, HP 500 MHz; `nsx-npu`: base `0x400E0000`, IRQ 117, Vela `ethos-u85-256` (256 MACs/cycle); no dedicated NPU SRAM anywhere in the SDK | | `NpuDef ethos-u85-256`; `NpuInstance` clocks 100/500, base, IRQ 117; no `sram_kb` field |
| apollo4p_evb PSRAM | none | 32768 KB | neuralspotx's board README: the plain EVB has no populated PSRAM; only its Display Kit shield variant adds an APS25616N | | check the EVB; if unpopulated, `apollo4p_evb` loses its PSRAM region |
| `apollo510l_evb` vs `apollo510dL_evb` | present | present | one EVB (AP510DLEVB) for the Lite series | | one board, alias |

## K. Validation detail

- Package: validators and the SDK drift test in CI, against both SDK tags
  and the pinned Zephyr revision.
- heliaAOT: the tests in Phase 2 step 6; `repo_tools.docs_export --check`;
  snapshot baselines regenerated only for the listed changes; the e2e matrix
  on `apollo4p_blue_kbr_evb` and `apollo510_evb`; `tests/e2e_zephyr` builds
  (budget assertion in Phase 4).
- helia-profiler: the rewritten tests in Phase 3 step 6; hardware
  validation on `apollo510_evb` and `apollo330mP_evb`.
