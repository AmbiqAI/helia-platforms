# 0008. Mark a Soc's memory controllers in a list of their own

Date: 2026-10-07
Status: Accepted; amended 2026-10-28 (#66)

## Amendment, 2026-10-28: a subset can remove only the controller (#66)

The Apollo4 Blue Plus maps "The three MSPI modules", but "MSPI1 is not
pinned out on the Apollo4 Blue Plus KBR package" (DS-A4BP p118). `peripherals_removed` would say the block is gone. The owner
decided on 2026-10-27, reviewing #126, to add `memory_controllers_removed`, in
a Soc delta and an Implementation subset. It removes a name from the inherited
`memory_controllers` and drops the inherited access entries that name it,
and leaves `peripherals` as it is. The second paragraph of the Decision
below is replaced to that extent; `peripherals_removed` still also removes
the name from `memory_controllers`.

## Context

RFC 0002 makes a memory controller a valid `Access` target, and
`docs/rfcs/0002-multicore.md` expands `default_access` over every on-die
region and memory controller. ADR 0002 gives a Soc only `peripherals`, a
list of names (section 2.4), so nothing says which peripherals are memory
controllers. An Apollo510 lists IOM0-7, MSPI0-3, SDIO0-1, UART0-1 and
more (CMSIS `apollo510.h` in nsx-ambiq-sdk `v5.2.24`). Treating every
peripheral as a controller would grant core 0 access entries to UARTs;
listing only controllers in `peripherals` would leave an FPGA unable to
say that IOM2 and above are absent. The owner decided on 2026-10-07 to list
every peripheral and mark the controllers separately (#57, #63).

## Decision

A Soc gains `memory_controllers`, a list of names keyed by value in the
sense of ADR 0002 section 2.4, alongside `peripherals`. Each name must also
be in `peripherals`. Only regions and memory controllers may be `Access`
targets or `default_access` grants, and a Board's or Implementation's
interface `controller` must be a memory controller of the Soc as realized.

There is no `memory_controllers_removed`. `peripherals_removed`, in a Soc
delta or an Implementation subset, also removes the name from the inherited
`memory_controllers` and drops the inherited access entries that name it; a
name the delta itself writes in `memory_controllers` stays and is reported
by the reference check. This is an exception to ADR 0002 section 2.5 rule 3
for this one list.

Each name is a fact; its provenance path ends at the name
(`memory_controllers.<name>`, ADR 0003 section 2). In the digest projection
of ADR 0004 point 1, `memory_controllers` is sorted like the other value
lists.

## Consequences

- The access matrix and its expansion cover only what can hold memory, and
  `peripherals` can describe the whole Soc.
- Every built-in Soc must mark its controllers; a controller left off the
  list cannot carry an interface.
- ADR 0002 section 2.4's list of value lists and section 2.5 rule 3, and
  ADR 0004 point 1's list of sorted value lists, are read together with
  this record.
