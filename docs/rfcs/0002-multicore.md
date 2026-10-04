# RFC 0002: multiple cores and accelerators

Status: Draft, 2026-10-04. Part of [RFC 0002](0002-model-and-api.md),
kept in its own file for length; it is as normative as the RFC. Terms are
as defined in RFC 0002's glossary.

## Why

Ambiq parts already ship with more than one core. The Apollo510 Lite and
Apollo330 Plus series pair the Cortex-M55 application core with a
Cortex-M4 radio core: their memory maps carry "Radio subsystem TCM RAM
(64 kB)" and an NVM region "NVM for Cortex-M4 Firmware" (NVM-M41), and
the datasheets note that "Factory-installed Cortex-M4 firmware reduces the
amount of available NVM" (DS-A510LS p2, p33; DS-A330PS p2, p33; recorded
in [research/datasheets.md](../research/datasheets.md) sections 2 and 4).
The Apollo4 Blue Lite has a BLE radio ("Bluetooth 5.1 Low Energy",
DS-A4BL p2) whose controller incorporates a dedicated Arm Cortex-M0
(DS-A4BL p84).

The model must also describe, without changing what single-core consumers
call today, generic shapes such as a SoC with an application core, a DSP
core and an NPU, or a SoC with two application cores and two NPUs.

## Cores

`Soc.cores` is an ordered tuple of `CoreInstance`:

| Field | Meaning |
|---|---|
| `id` | Unique within the Soc: `cm55_0`, `radio_m4`, `dsp_0` |
| `role` | `application`, `radio`, `dsp` or `other` |
| `core` | The `Core` IP block |
| `options` | `CoreOptions` for this instance |
| `clock_domain` | The clock domain the core runs in |
| `programmable_by` | `customer`, `vendor` or `either`; `None` for a core with no loadable image |

Index 0 is always the primary application core. Every single-core
convenience on `Target` (`core`, `core_options`, `isa()`, `memories()`,
`flash_load_address()`, `budget()`) means core 0 unless `core=` says
otherwise.

`Core` widens beyond Arm: `Core.arch` may be a non-Arm ISA (for example an
Xtensa DSP core), and `has_dsp_extension` and `pmu` are read as that IP's
facts. Derived ISA features are per core: `isa(core=)` computes them from
that core's `Core` and `options`.

## Accelerators

`Soc.npus` is an ordered tuple of `NpuInstance`, index 0 primary. Each has
an `id`, its `npu` IP, `axi_width_bits`, base address, IRQ, `driven_by`
(the id of the core that programs it) and `clock_domain`. `Target.npu` is
the convenience for index 0. Other accelerators (a GPU, a display
controller) follow the same pattern in `Soc.accelerators`, a tuple of
`AcceleratorInstance` (id, kind, IP name, `driven_by`, `clock_domain`,
base address, IRQ); this RFC models no further detail for them.

## Memory reachability

Regions keep one global address (`MemoryRegion.base`) by default, because
Ambiq parts use a unified address space. A region may list
`alternate_bases` where the silicon aliases it at more than one address.

Reachability is an explicit access matrix, never inferred from the address
space. `Soc.access` is a tuple of `Access` entries keyed by (master id,
target), where a master is a core, NPU or accelerator id and the target is
a region name or a memory controller name (a `Soc.peripherals` entry such
as `mspi0`):

| Field | Meaning |
|---|---|
| `master`, `target` | The key |
| `access` | `direct` or `none` |
| `requires_awake` | Power domains that must be on for the access |
| `guidance` | `preferred`, `allowed` or `discouraged`, with `reason` |
| `address` | Optional per-master address, for a part where a master sees the region at a different address |
| `port` | Optional NPU AXI port class: `0` (Vela `Sram`, Arm `AXI_SRAM`) or `1` (Vela `Dram`, `AXI_EXT`), the estimator's vocabulary per [research/queries-helia-estimator.md](../research/queries-helia-estimator.md); replaces `NpuInstance.memory_ports` |
| `characterization` | Optional latency, bandwidth and port facts, each with provenance (no energy data); for this master it overrides the region's characterization |
| `provenance` | Required on built-ins |

No entry means not reachable or not known; the package never infers one.
A region private to one core has one entry.

External memory is reached through its interface. An entry whose target is
a memory controller applies, for the master it names, to every device a
Board, AddOn or FPGA Implementation populates on an interface using that
controller; the
devices inherit the entry explicitly, not by address. `memories(core=)`
and `budget(env, core=)` include an external region when that core has an
entry for its interface's controller. An interface whose
controller has no Soc-level entries draws a validation warning that its
devices are unreachable.

`Soc.default_access` is a declared shorthand that keeps single-core
built-ins short: `{master: <core 0 id>, access: direct, scope: on_die}`
expands to a `direct` entry from core 0 to every on-die region and memory
controller that has no explicit entry for core 0, excluding any region or
controller that has an entry for another core (a region another core owns,
such as the radio subsystem TCM, is never granted to core 0 by default).
It is a fact with provenance, not inference, and explicit entries for core
0 override it; entries for other masters never remove core 0's default.
NPU and accelerator entries are always explicit.

Worked example of the shape (provenance is recorded per SoC; this is not a
statement about any part): an NPU may reach the application core's DTCM,
but the access keeps that core's power domain on and competes with it, so
the entry reads `{master: npu_0, target: dtcm, access: direct,
requires_awake: [<application core domain>], guidance: discouraged,
reason: "keeps the application core domain awake"}`.

An Implementation that removes a region, controller, core or accelerator
removes the access entries that name it. Removing a memory controller makes
any Board, AddOn or Implementation population on that controller's interfaces a validation
error, not a warning: the hardware to attach the device does not exist.

## Image slots and boot

Per-part NVM reservations become `ImageSlot`s owned by a core:
`ImageSlot` = `core`, `region`, `offset`, `size`, `supplier` (`vendor` or
`customer`), provenance. On the Apollo510 Lite and Apollo330 Plus parts,
NVM-M41 is the radio core's slot, sized per variant (16, 288 or 432 KB,
DS-A510LS p33, DS-A330PS p33), supplier `vendor` by default. That the
slot is flashable by the customer is recorded as an owner statement until
a document confirms it. `usable_nvm(core=)` subtracts the slots of other
cores and the boot reservations.

A boot configuration gives one application start per programmable core:
`BootConfig.app_start` maps core id to (region, offset). A single
(region, offset) is shorthand for core 0. `flash_load_address(core=)`
reads that core's start from the selected configuration.

## Clock domains and operating points

`Soc.clock_domains` lists `ClockDomain`s, each with its own named points
(`DomainPoint`: name, MHz, HAL mode). An `OperatingPoint` is a system
operating point: it couples domains by naming one point per domain. This
generalises today's CPU plus NPU coupling. `OperatingPoint.hal_mode` is the
system mode where the HAL has one; the profiler reads per-domain HAL mode
names from `DomainPoint.hal_mode`.

`OperatingPoint` stores no MHz of its own. `target.cpu_mhz(point=None,
core=0)` and `target.npu_mhz(point=None, npu=0)` read the domain point of
that core or NPU. In overlays, `cpu_mhz` and `npu_mhz` on an operating
point are shorthand that expands to points in the core-0 and npu-0
domains. An Implementation may add or replace domain points through
`Implementation.clock_domains` (an FPGA running at 25 MHz). Clock caps
(`max_cpu_mhz`, `max_npu_mhz`) apply to the core-0 and npu-0 domains;
`Subset.max_domain_mhz` caps any domain by id.

## Queries

| Query | Meaning |
|---|---|
| `isa(core=0)` | Derived ISA features of that core |
| `memories(core=0)` | Regions with a `direct` access entry for that core, plus external regions whose interface controller it has an entry for |
| `placement_ranges(core=0)` | (base, size) of the regions that core reaches |
| `flash_load_address(core=0)`, `usable_nvm(core=0)` | From the selected boot configuration and that core's slots |
| `budget(env, core=0)` | Only regions that core can reach |
| `operating_points(domain=None)`, `operating_point(name=None, *, domain=None)` | System points, or one domain's points |
| `cpu_mhz(point=None, core=0)`, `npu_mhz(point=None, npu=0)` | That core's or NPU's clock in a system operating point |
| `npu_clocks(npu=0)` | That NPU's clock per system operating point |
| `cores(role=None)`, `npus()`, `accelerators()` | System inventory |
| `reachable(master, target)` | The `Access` entry (for an external region, its controller's), or `None` |
| `classify_address(address, master=0)` | The region at that address as the master sees it; `alternate_bases` classify to the same region |

`core=` and `npu=` take an index or an id. heliaAOT names a platform and
gets core 0 and npu 0 implicitly; `platform.core` and `platform.npu` are
future additive options. Placement and budget for a core ignore regions it
cannot reach. Partitioning work across cores or NPUs is tool policy.

## Validation

The multicore validation rules are listed once, in RFC 0002 under
"Overlays, validation, export, CLI".

## Example overlay

Shape only: a generic SoC with an application core, a DSP core and an
NPU. Ids and values are illustrative. Core `options`, memories, clock
domains and power-domain names are elided or placeholders (see RFC 0002
open question 5).

```yaml
socs:
  example_hetero:
    cores:
      - {id: app_0, role: application, core: cortex-m55, clock_domain: app, programmable_by: customer}
      - {id: dsp_0, role: dsp, core: example-xtensa-dsp, clock_domain: dsp, programmable_by: customer}
    npus:
      - id: npu_0
        npu: {vendor: arm, family: ethos-u, model: u85, macs_per_cycle: 256}
        driven_by: app_0
        clock_domain: npu
    default_access: {master: app_0, access: direct, scope: on_die}
    access:
      - {master: app_0, target: dsp_tcm, access: none}
      - {master: npu_0, target: dtcm, access: direct, requires_awake: [app_power], guidance: discouraged, reason: keeps the app core domain awake}
      - {master: npu_0, target: ssram, access: direct, guidance: preferred, port: 0}
      - {master: npu_0, target: mspi0, access: direct, guidance: allowed, port: 1}
      - {master: dsp_0, target: dsp_tcm, access: direct}
```
