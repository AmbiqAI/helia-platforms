# 0011. Record the DMA boundary of a memory region

Date: 2026-11-06
Status: Proposed

## Context

The Apollo5 datasheets state address boundaries a DMA transfer must not
cross: "A DMA transfer must not cross a DTCM 4 kB boundary" and "must not
cross the MRAM0-MRAM1 boundary at address 0x600000" (DS-A510 1.1.0 p22;
ERR014 on p29), and an MSPI DMA that crosses the DTCM-SSRAM0, SSRAM0-SSRAM1
or SSRAM1-SSRAM2 boundary hangs the device (ERR018, p96). A tool that
plans DMA transfers into these regions, such as heliaAOT's weight-prefetch
schedule (helia-aot RFC 0005), produces code that hangs if it does not
know them. RFC 0002's `MemoryRegion` has no transfer constraint, and
`MemoryCharacterization.max_beats` is the Ethos-U burst split, not a DMA
rule.

Two neighbouring questions stay outside the catalog under ADR 0010. Which
engine moves bytes between two memories is a consumer's rule over facts
the catalog already states: an external region sits behind a memory
controller, whose DMA moves it, and the datasheets say "the APBDMA does
not have the capability to transfer from memory to memory" (p22). The
split an SDK driver applies to the device side of a transfer
(`eDMABoundary`) is the SDK's setting, and its cost is a measurement.

## Decision

`MemoryRegion` gains an optional `dma_boundary`, a size. A single DMA
transfer does not cross an address that is a whole multiple of it,
counted from the region's base, whichever DMA master performs it. A
boundary the datasheet gives as an absolute address is written as its
offset from the base: the MRAM0-MRAM1 boundary at 0x600000 is `mram`
`dma_boundary: 2M`. The value carries its own provenance record. A region
without the field has no stated boundary; the catalog infers none.

## Consequences

- apollo510, apollo510b, apollo510L and apollo330P record `dtcm`
  `dma_boundary: 4K`, and apollo510 and apollo510b also `ssram` 1M and
  `mram` 2M. Apollo4 and Apollo3 datasheets state no boundary rule, so
  their regions carry none.
- heliaAOT reads `target.region("dtcm").dma_boundary` instead of a table
  of its own; its engine rule and helia-profiler's transfer-cost
  calibration stay where they are.
- The deep-sleep rule ("a DMA operation cannot be performed to or from
  DTCM when the CPU is in deep sleep", p22) is not modelled; it is quoted
  in the records' notes.
- `derives_from` does not compare `dma_boundary`; a derived Soc writes its
  own values with its own datasheet pages, as apollo510b does for its
  regions.
