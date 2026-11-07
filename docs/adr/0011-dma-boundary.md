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
rule. The Apollo3 Blue, Apollo3 Blue Plus and Apollo4 Plus datasheets
(DS-A3 1.3.0, DS-A3P 1.3.0, DS-A4P 1.6.0) state no such rule; atomiq110's
sources were not read for one.

Two neighbouring questions stay outside the catalog under ADR 0010. Which
engine moves bytes between two memories is a consumer's rule over facts
the catalog already states: an external region sits behind a memory
controller, whose DMA moves it, and the datasheets say "the APBDMA does
not have the capability to transfer from memory to memory" (p22). The
split an SDK driver applies to the device side of a transfer
(`eDMABoundary`) is the SDK's setting, and its cost is a measurement.

## Decision

`MemoryRegion` gains an optional `dma_boundary`, a size, with its own
provenance record.

- **Meaning.** A single DMA transfer does not cross an address that is a
  whole multiple of `dma_boundary` counted from the region's `base`: the
  edges are `base + k * dma_boundary`, not addresses aligned to it. The
  two differ where the base is not itself a multiple. Apollo510's SSRAM
  starts at 0x20080000, and ERR018's edges are at 0x20180000 and
  0x20280000, so `ssram` carries `dma_boundary: 1M` and a consumer that
  aligned addresses to 1M instead would plan transfers across those
  edges. A boundary the datasheet gives as an absolute address is written
  as its offset: the MRAM0-MRAM1 boundary at 0x600000 is `mram`
  `dma_boundary: 2M`. The field says nothing about a transfer that runs
  from one region into the next; where a source states such an edge (ERR018
  names DTCM-SSRAM0), the record's notes carry it.
- **Masters.** The value is stated for the DMA masters the source names;
  the record's `notes` say which, and a consumer with another master reads
  them. A rule the source states for one master is not inferred for
  others.
- **Absent and zero.** A region without the field has no stated boundary;
  the catalog infers none, and a consumer does not read "none" as "no
  constraint" without its own reason. A value of 0 names no address and
  is rejected at load, as a slot of size 0 is.
- **Rebasing.** A region an overlay or an FPGA implementation rebases keeps
  its offset, so its edges move with the base. A record written for the
  silicon's absolute edge is then only as true as the new base makes it;
  the overlay owner checks it.

## Consequences

- apollo510, apollo510b, apollo510L and apollo330P record `dtcm`
  `dma_boundary: 4K`, and apollo510 and apollo510b also `ssram` 1M and
  `mram` 2M. The 510L and 330P 0.9.0 datasheets state the TCM rule in the
  SoC overview without naming the radio core's `rs_tcm`, which carries
  none. Apollo3, Apollo4 and atomiq110 regions carry none, the first two
  because their datasheets state no rule and atomiq110 because none was
  looked for.
- heliaAOT reads `target.region("dtcm").dma_boundary` instead of a table
  of its own and computes edges from the base; its engine rule and
  helia-profiler's transfer-cost calibration stay where they are.
- The deep-sleep rule ("a DMA operation cannot be performed to or from
  DTCM when the CPU is in deep sleep", p22) is not modelled; it is quoted
  in the records' notes.
- `derives_from` does not compare `dma_boundary`; a derived Soc writes its
  own values with its own datasheet pages, as apollo510b does for its
  regions.
