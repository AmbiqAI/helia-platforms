# 0012. Record the D-cache line, the DMA address alignment of a controller mode, and the power states that block DMA

Date: 2026-11-17
Status: Proposed

## Context

heliaAOT plans DMA transfers from external memory into on-die memory and the
cache maintenance around them (`helia_aot/platforms/transfer.py` in
AmbiqAI/helia-aot at `main`). ADR 0011 gave it each region's DMA boundary. It
still keeps three hand tables, because helia-platforms 0.2.0 has no field
for the facts in them (#175):

- `DCACHE_LINES`: the Cortex-M55 D-cache line, 32 bytes, the unit of cache
  maintenance. The catalog records only `CoreOptions.dcache_kb`, the size an
  implementer chose.
- `DMA_GRANULES`: 4 bytes for PSRAM on apollo510, apollo510b, apollo510L and
  apollo330P, because "the HAL takes a word-aligned device address in HEX
  DDR mode". The rule is in the Apollo510 MSPI HAL:
  `am_hal_mspi_nonblocking_transfer` and `am_hal_mspi_highprio_transfer`
  return `AM_HAL_STATUS_INVALID_OPERATION` when the MSPI's device
  configuration is `AM_HAL_MSPI_FLASH_HEX_DDR_CE0` or `_CE1` and the
  transfer's device address is not a multiple of 4 (hal_ambiq `3d7044ea`,
  `mcu/apollo510/hal/mcu/am_hal_mspi.c:3886-3894` and `:4689-4697`). The
  HAL keys the rule on the controller's mode, not on the PSRAM part, and
  states no alignment rule for the transfer count.
- `SOC_NOTES`: "DMA to DTCM is forbidden in deep sleep" for the Apollo510
  family. The datasheets say "A DMA operation cannot be performed to or from
  DTCM when the CPU is in deep sleep or the DTCM location is powered down"
  (DS-A510 1.1.0 p22, ERR014 on p29; DS-A510B 1.1.0 p21 and p28), and the
  Apollo510 Lite and Apollo330 Plus datasheets say the same of TCM (DS-A510LS
  0.9.0 p21, DS-A330PS 0.9.0 p21). heliaAOT's table says no restriction is
  recorded for apollo330P, which DS-A330PS p21 contradicts. ADR 0011 left
  this rule unmodelled and quoted it in record notes.

## Decision

Each fact is recorded on the entity its source attributes it to, with its
own provenance record, and the catalog states only what the source states
(ADR 0010).

1. **D-cache line.** `Core` gains an optional `dcache_line`, the IP's L1
   data cache line in bytes. Arm fixes it for the IP (TRM-M55 r1p1-02 p198,
   "It has a cache line size of 32 bytes"), while the implementer chooses
   whether an instance has the cache and how large it is (`dcache_kb`).
   Absent means none is recorded. The loader rejects a value that is not a
   power of two, 0 included: Armv8-M's CCSIDR.LineSize encodes the line as
   a power of two words (TRM-M55 p69), so no other value can be read back
   from a core. `Target.dcache_line(core=0)` returns the IP's line, and
   `None` where the IP records none or the instance's `dcache_kb` is 0 (a
   source states that instance has no D-cache).
2. **DMA address alignment.** `Soc` gains an optional
   `dma_address_alignment`, a map from an interface mode (`hex-ddr`, the
   spelling `MemoryInterface.modes` and `MemoryDevice.modes` use) to bytes:
   a DMA transfer through any of the Soc's memory controllers running in
   that mode starts at a device address that is a multiple of the value.
   It is a Soc fact because the source is the Soc's HAL, which applies it to
   every MSPI instance; it is keyed by mode because the HAL keys it by the
   device configuration. A mode without an entry has no stated alignment,
   and a value of 0 is rejected, as ADR 0011 rejects a boundary of 0. A
   non-power-of-two value is not rejected, because it contradicts no other
   fact. `Target.dma_address_alignment(region)` gives the value for an
   external region: the Soc's entry for the one mode the region's interface
   and device share (either side's modes where the other lists none).
   With no shared mode, or with several, it returns `None`, because which
   mode the driver runs is the driver's choice; a consumer that knows the
   mode reads `target.soc.dma_address_alignment` itself. It returns `None`
   for an on-die region and raises for a name that is no region.
3. **Power states that block DMA.** `MemoryRegion` gains an optional
   `dma_blocked_when`, a non-empty list from the closed vocabulary
   `cpu_deep_sleep`: no DMA transfer to or from the region can be performed
   while the Soc's application core (core 0, the CPU the datasheet
   describes) is in deep sleep. As with ADR 0011's boundary, the value
   covers the DMA masters the source names, and the record's notes say
   which; the Apollo5 notes name none. A region the source does not name
   carries nothing, and absent means not stated, not "no restriction". The
   "location is powered down" half of the sentence holds for any memory
   and is not recorded. A new state is added to the vocabulary when a
   source states one.

The values are facts, not heliaAOT's rules over them. Whether to offer DMA
from a source, how to round a transfer, and when to clean or invalidate the
cache stay with the consumer.

## Consequences

- `cortex-m55` records `dcache_line: 32` (TRM-M55 p198, p69), so every
  M55 Soc's core 0 returns 32. `cortex-m4` and `cortex-m0` record none.
- apollo510 and apollo510b record `dma_address_alignment: {hex-ddr: 4}`.
  apollo510b cites the same HAL, because nsx-ambiq-sdk builds it against
  `mcu/apollo510` (`cmake/socs/apollo510b.cmake:12-13` at `v5.2.27`) and
  Zephyr at `8f62a4ab` lists no apollo510b (`soc/ambiq/soc.yml`). apollo510L and apollo330P record none: neither
  hal_ambiq at `3d7044ea` nor nsx-ambiq-sdk `v5.2.27` carries their MSPI
  HAL as source, and their EVBs populate no MSPI device. apollo510_evb and
  apollo510b_evb's `psram0` therefore return 4.
- `dtcm` on apollo510, apollo510b, apollo510L and apollo330P records
  `dma_blocked_when: [cpu_deep_sleep]`. `itcm` and the radio core's
  `rs_tcm` carry nothing, because the datasheets do not name them, and
  Apollo3, Apollo4 and atomiq110 regions carry nothing, because their
  datasheets were not read for the rule. This replaces ADR 0011's
  consequence that the deep-sleep rule is only quoted in notes.
- The source register gains `zephyrproject-rtos/hal_ambiq`, cited at the
  revision the snapshots hold (ADR 0006).
- `derives_from` compares neither new field, as with `dma_boundary`.
- heliaAOT can drop `DCACHE_LINES`, `DMA_GRANULES` and `SOC_NOTES` for
  `target.dcache_line()`, `target.dma_address_alignment(region.name)` over
  `target.external_memories()`, and `target.region(name).dma_blocked_when`.
