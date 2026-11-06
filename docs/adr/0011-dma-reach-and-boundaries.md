# 0011. Record DMA reach as access entries from memory controllers, and DMA boundaries on regions and devices

Date: 2026-11-06
Status: Proposed

## Context

The Apollo5 datasheets state three kinds of DMA fact. "A DMA transfer must
not cross a DTCM 4 kB boundary" and "must not cross the MRAM0-MRAM1 boundary
at address 0x600000" (DS-A510 1.1.0 p22; ERR014 on p29); crossing the
DTCM-SSRAM0, SSRAM0-SSRAM1 or SSRAM1-SSRAM2 boundary during an MSPI DMA
hangs the device (ERR018, p96). "MSPI module can autonomously transfer data
between the external device and internal memory or NVM" (p98), while "the
APBDMA does not have the capability to transfer from memory to memory"
(p22). The SDK's PSRAM drivers split every DMA at 1 kB of device address
(`eDMABoundary = AM_HAL_MSPI_BOUNDARY_BREAK1K`, nsx-ambiq-sdk `v5.2.26`) to
respect the device's page and tCEM limits.

heliaAOT's weight-prefetch schedule (helia-aot RFC 0005) plans transfers
from these facts: the boundary of the destination region, the engine that
reaches each memory, and the granule of the external device. RFC 0002's
model has no place for them: an `Access` master is a core, NPU or
accelerator, `MemoryRegion` has no transfer constraint, and
`MemoryCharacterization.max_beats` is the Ethos-U burst split, not a DMA
break. The owner deferred the GPU and display controller as bus masters
(#88); a DMA engine inside a memory controller is not an accelerator either.

## Decision

1. A memory controller name may be an `Access` master. The entry states
   that the controller's DMA engine moves data between the devices on that
   controller and the target region. A peripheral that is not a memory
   controller is rejected as a master. `default_access` grants nothing to
   such a master, and the access-coverage rule and `memories(core=)` keep
   reading core masters only. `requires_awake`, `guidance` and
   `characterization` mean what they mean for any master.
2. `MemoryRegion` and `MemoryDevice` gain an optional `dma_boundary`, a
   size. A single DMA transfer does not cross an address that is a whole
   multiple of it, counted from the region's base or from the device's
   address 0. The region's value binds every DMA master that reaches it;
   the device's is the split the SDK driver applies to the device side of
   a transfer. Each value carries its own provenance record. A boundary
   given as an absolute address is written as its offset from the base:
   the MRAM0-MRAM1 boundary at 0x600000 is `mram` `dma_boundary: 2M`.
3. "No memory-to-memory DMA" is not a field. A consumer that finds no DMA
   master reaching two on-die regions has no engine to name; the datasheet
   sentence lives in this record and in the records' notes.

## Consequences

- apollo510, apollo510b, apollo510L and apollo330P record `dtcm`
  `dma_boundary: 4K` and, where the datasheet states them, `ssram` 1M and
  `mram` 2M, with entries from each MSPI controller to `dtcm`, `ssram` and
  `mram`. APS512XX, APS256XXN and APS6404L record `dma_boundary: 1K` as an
  `sdk` fact. Apollo4 and Apollo3 datasheets state no boundary rule, so
  their regions carry none.
- heliaAOT reads `target.reachable("mspi0", "dtcm")` and
  `target.region("dtcm").dma_boundary` instead of its own Apollo5 table;
  the transfer cost stays a helia-profiler measurement.
- The deep-sleep rule ("a DMA operation cannot be performed to or from DTCM
  when the CPU is in deep sleep", p22) waits for power-domain names (RFC
  0002 open question 5) before it becomes `requires_awake` on these
  entries; until then it is in the records' notes.
- `derives_from` does not compare `dma_boundary`; a derived Soc writes its
  own values with its own datasheet pages, as apollo510b does for its
  regions.
