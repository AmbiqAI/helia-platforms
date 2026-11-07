# 0007. Model an FVP's memories as its own list, not as substitutions

Date: 2026-10-07
Status: Accepted; amended 2026-10-29 (#68) and 2026-11-06 (#93)

## Amendment, 2026-11-06: no port on an access entry (#93)

`Access.port` left the model on #93: which memory a compiler serves over
which NPU port is the consumer's choice, and the IP's port classes with
their per-port limits are `NpuInstance.axi_ports`. So the field-path
example in point 5 reads `access.<master>@<target>.guidance`, and the
example in point 3 of an FPGA stating its own path limits
(`atomiq110_fpga`'s scaled-down NPU-to-SSRAM FIFO) no longer exists in
the data: those limits were a fit, not a cited capture, and came out
with #93. Point 3's rule itself, that any kind may write `access`, stands.

## Context

[RFC 0002](../rfcs/0002-model-and-api.md) lets an FVP Implementation
describe its model's memories as `substitutions` against its Soc. Each
substitution names a region the model provides, the Soc regions it
`replaces`, and its own size and base; the replaced regions are removed,
and the substitute does not count as an added memory (RFC 0002 at
`af7482b`, `docs/rfcs/0002-model-and-api.md:264-272`). `Subset` carries
the mapping and `Substitution` has the fields `replaces`, `size`, `base`,
`characterization` and `provenance` (`:781-782`); the semantic rules allow
substitutions only on kind `fvp` (`:852-853`). [ADR
0002](0002-schema-format-and-runtime.md) section 2.4 lists the mapping as
keyed by the region the model provides and `replaces` as a list keyed by
value, and [ADR 0004](0004-schema-and-catalogue-versions.md) point 1 sorts
`Substitution.replaces` in the digest projection.

The case substitutions were written for is the Corstone-320 FVP standing
in for atomiq110. helia-npu's target file
(`AmbiqAI/helia-estimator` at `5991d9f1`,
`packages/helia-npu/src/helia_npu/targets/atomiq110-fvp-corstone-320.yaml:13-22`)
lists the Soc features the model implements (`ssram`, `tcm`, `hblram`,
`psram`, `rram` among them) and says how each is emulated: one FVP DDR
region behind timing adapter 1 stands in for `hblram`, `psram` and `rram`,
and the FVP SRAM behind timing adapter 0 stands in for `ssram`. RFC 0002's
migration plan describes the same mapping as many-to-one substitutions
([0002-migration.md](../rfcs/0002-migration.md), helia-estimator table).

The first implementation of substitutions (issue #56) left two gaps that
the format could not close:

1. A substitute had no `technology` or `attachment`, which every
   `MemoryRegion` requires, nor `executable`, `writeable` or `cacheable`.
   That implementation copied them from the first region the substitute
   replaced. The RFC does not say so, and the copy is wrong when the
   replaced regions differ, as `hblram`, `psram` and `rram` do.
2. A substitute had no access entries. The access entries of the regions
   it replaced were removed with them, and an Implementation could not
   write `access`, so no core or NPU reached a substitute.

On 2026-10-07 the repository owner decided that an FVP is modelled apart
from the silicon and declares its own memories, rather than deltas
against the Soc. ADR 0002 and ADR 0004 are Accepted and therefore
immutable, so this record carries the decision and supersedes the parts
of them that describe substitutions.

## Decision

1. **An FVP declares its whole memory list.** `Implementation.memories`, a
   mapping of region name to `MemoryRegion` like `Soc.memories`, exists in
   the file format, the model and the JSON Schema. It is allowed only when
   `kind` is `fvp` and is an error on any other kind. When it is present
   it is the complete memory list of the realized Soc, in the order the
   FVP writes it: no Soc region is inherited, and a region with the name of
   a Soc region replaces that region whole. This is an exception to rule 2
   of ADR 0002 section 2.5 (a collection merges by key) for this one key.
   Combining `memories` with `subset.memories_removed`,
   `subset.memories_resized` or `subset.memories_rebased` is an error.
   Without `memories`, an FVP inherits the Soc's regions as any other
   Implementation does.
2. **`stands_in_for` names the Soc regions a model region emulates.** A
   region in an FVP's `memories` may carry `stands_in_for: [<Soc region
   names>]`, a list keyed by value. The Corstone-320's DDR region carries
   `stands_in_for: [hblram, psram, rram]`. Each listed name must be a
   region of the Soc and must not also be a region of the FVP's own list,
   and each Soc region appears in at most one `stands_in_for`. A region
   whose name equals a Soc region's name represents that region and needs
   no `stands_in_for`. `stands_in_for` is an error anywhere else: on a
   Soc's regions, and on any Implementation that is not an FVP (which
   cannot write `memories`). `MemoryRegion.stands_in_for` is a tuple of
   names, empty by default.
3. **Access follows the list.** An inherited Soc `access` entry whose
   target is a Soc region absent from the FVP's list is dropped, as
   `memories_removed` drops it; an entry whose target is present by name
   is kept. `Implementation.access` adds entries and merges with the
   inherited ones by (`master`, `target`), replacing an inherited entry
   with the same pair. An entry the FVP
   writes for a Soc region it does not list is a reference error, as for
   any removed region. The Soc's `default_access` applies to the realized
   Soc as usual. Amended for #68: `access` was allowed only when `kind` is
   `fvp`; any kind may now write it, so an FPGA can state its own path
   limits (`atomiq110_fpga`'s scaled-down NPU-to-SSRAM FIFO).
4. **Substitutions are removed.** `Substitution` and `Subset.substitutions`
   leave the file format, the model and the committed JSON Schema. Clock
   caps and the subset limits are unchanged.
5. **Provenance.** FVP regions and access entries carry provenance as any
   Implementation fact does, by the rules of [ADR
   0003](0003-provenance-record.md) section 3; no record is taken from the
   Soc, even for a region with a Soc region's name. Field paths
   follow ADR 0003 section 2:
   `fact:implementation:<id>:memories.<name>.size`,
   `memories.<name>.stands_in_for.<Soc region>` (the item ends the path)
   and `access.<master>@<target>.port`.
6. **`dram` technology.** `MemoryRegion.technology` and
   `MemoryDevice.technology` gain the value `dram`, so a model's DDR region
   can say what it is. The owner chose this on 2026-10-07; the other values
   are unchanged.
7. **Queries.** On an FVP target, `Target.region(name)` also accepts a Soc
   region name that a region's `stands_in_for` lists, and returns the
   region that stands in for it, so a tool asking for `hblram` on the
   Corstone-320 target gets the DDR region. The resolver (issue #58)
   implements this rule; the realized Soc that `Catalog._realized()`
   returns holds only the FVP's regions.

This record supersedes, in ADR 0002 section 2.4, the collection "an FVP
Implementation's `substitutions` (keyed by the region the model
provides)" and the value list "a substitution's `replaces`"; an FVP's
`memories` is a mapping keyed by region name, and `stands_in_for` is a
list keyed by value. It supersedes, in ADR 0004 point 1, the item
`Substitution.replaces` in the lists keyed by value: the digest
projection sorts `MemoryRegion.stands_in_for` instead, and projects
`Implementation.memories` as a mapping and `Implementation.access` as a
list sorted by (`master`, `target`), like the Soc's.

## Consequences

- An FVP region states its own `technology`, `attachment` and access, so
  neither gap above needs a convention. The Corstone-320 becomes one
  `fvp` Implementation whose memories are its model regions.
- An FVP restates the regions it keeps by name, because none is
  inherited. That costs a few lines per FVP and makes the realized list
  readable in one place.
- A reference from inherited Soc data to a region the FVP does not list,
  such as a boot configuration's `app_start` in `rram`, is reported after
  realization, as after `memories_removed`; the FVP removes or redeclares
  those boot configurations. The owner chose this strict rule over letting
  such references resolve to a stand-in.
- RFC 0002 and its migration plan describe the FVP memory map and link
  here; the resolver (issue #58) must implement the query rule in point 7.
