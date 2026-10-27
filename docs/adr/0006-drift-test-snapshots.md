# 0006. Check the catalogue against committed source snapshots

Date: 2026-10-05
Status: Accepted; amended 2026-10-27 (#18)

## Amendment, 2026-10-27: neuralspotx is a consumer (#18)

neuralspotx consumes this catalog, so it is no longer a source. Comparing the
catalog with a neuralspotx revision generated from it would compare the
catalog with itself. From this amendment:

- `check-sources` compares nothing from `snapshots/neuralspotx.json`. Its
  board rows below (the board's Soc, `toolchains`, the `debug.cmake`
  overrides, the board's default scripts) are removed. The trace clock and
  flash load address it checked against the SDK facts are compared once
  per Soc instead: `flash_load_address()` of the Soc target against
  `NSX_SEGGER_PF_ADDR`.
- The neuralspotx snapshot stays at `neuralspotx-v0.9.0`, the last revision
  before neuralspotx consumed the catalog, and is never refreshed. The
  extractor still regenerates it there, so step 1 checks it. It is the
  consumer data of a parity test under #13 (`tests/test_parity.py`).
- The SDK tag per Soc is the `revision` the committed SDK snapshot records,
  not neuralspotx's `soc_families`. A refresh passes `--sdk <tag>`, which
  applies to every Soc in the extractor's SoC-to-header map; the weekly
  step 2 extracts the newest `v*` tag.
- `SdkFacts.build.toolchains` is removed from the format: which toolchains a
  build supports is neuralspotx's policy.
- A citation of neuralspotx at a pinned pre-adoption revision stays valid
  evidence (ADR 0003).

## Context

RFC 0001 makes `nsx-ambiq-sdk` the authority for firmware builds and this
package the authority for tools, with CI checking the overlap at the SDK
tags neuralspotx pins and the `zephyr` windows at a pinned Zephyr revision
([RFC 0001, Authority](../rfcs/0001-platform-catalogue.md#authority);
[appendix G](../rfcs/0001-platform-catalogue-appendix.md#g-the-sdk-drift-test)
lists the compared fields and the exclusions). [Review item
3.2](../rfcs/0001-platform-catalogue-review.md#32-the-drift-test-needs-private-sources-from-a-public-ci)
proposed committed snapshots because the SDK and neuralspotx were private
and a public CI could not check them out without a token. RFC 0002 keeps
the comparison as the CLI's `check-sources`, "against the committed SDK and
Zephyr snapshots" ([Overlays, validation, export,
CLI](../rfcs/0002-model-and-api.md#overlays-validation-export-cli)); moves
linker windows into an optional link-environment dataset that an extractor
regenerates ([Link environments](../rfcs/0002-model-and-api.md#link-environments));
and derives the flash load address from named [boot
configurations](../rfcs/0002-model-and-api.md#boot-configurations). Its
migration plan holds that dataset to window parity with the profiler's
`_MAPS` rows ([0002-migration.md](../rfcs/0002-migration.md), helia-profiler
table).

The private-source premise of item 3.2 does not hold today. On 2026-10-05,
`gh repo view --json visibility` reports `AmbiqAI/nsx-ambiq-sdk`,
`AmbiqAI/neuralspotx`, `zephyrproject-rtos/zephyr` and
`zephyrproject-rtos/hal_ambiq` as public; this repository is private. CI
can check out all four without a token, so the choice between live
checkouts and snapshots rests on other grounds: whether PR CI should depend
on the network and on upstream state, whether a source change is reviewed
as data, and whether upstream drift is noticed.

A fact read from a working tree cannot be reproduced. RFC 0001 appendix D's
`apollo4p_evb` Zephyr row (TCM 384 KB, SRAM 2432 KB) matches neither
committed revision: zephyr `d8be6be`, the revision appendix G names, and
`8f62a4ab` both give a 64 KB `tcm` and a 2752 KB `sram0` at `0x10010000`
(`dts/arm/ambiq/ambiq_apollo4p.dtsi:64-73`, which the board does not
override).

The pins chain. neuralspotx `neuralspotx-v0.8.1` pins `nsx-ambiq-sdk` per
SoC family: `v5.2.24` for the apollo2, apollo3, apollo4 and apollo5
families, `v5.2.25` for atomiq110
(`src/neuralspotx/data/registry.lock.yaml:314,333,363,393,435`). Zephyr
`8f62a4ab` pins hal_ambiq `3d7044ea` (`west.yml:159-160`).

The sources need care to read (nsx-ambiq-sdk `v5.2.24`, neuralspotx
`neuralspotx-v0.8.1`, zephyr `8f62a4ab`, hal_ambiq `3d7044ea`):

- Facts files use multi-line `set()` lists and quoted empty values
  (`cmake/socs/facts/apollo510.cmake:29,34-45`). The default script per
  toolchain is chosen in an `if`/`else` in two forms: a
  `_nsx_linker_script_default` passed to `nsx_select_linker_script`
  (`cmake/socs/apollo510.cmake:23,28`), and a direct
  `set(NSX_LINKER_SCRIPT ...)` (`cmake/socs/apollo3p.cmake:21,24`).
- gcc `MEMORY` blocks contain commented-out regions
  (`modules/nsx-core/src/apollo510/gcc/linker_script_sbl.ld:14-15`) and `K`
  suffixes (`modules/nsx-core/src/apollo3/gcc/linker_script.ld:10`).
  armclang scatter files declare stack and heap as `EMPTY` regions, one
  with a negative length
  (`modules/nsx-core/src/apollo510/armclang/linker_script_sbl.sct:26,39`).
- Register headers give sizes as C expressions, and
  `modules/nsx-ambiqsuite/sdk/mcu/apollo4l/regs/am_reg_base_addresses.h:51-68`
  keeps Apollo4P's SSRAM1 definitions inside `#if 0`.
- neuralspotx overrides SoC debug facts per board
  (`src/neuralspotx/boards/atomiq110_fpga_turbo/debug.cmake:17` sets the
  measured 48 MHz trace clock, #30).
- Zephyr `reg` cells are hal_ambiq macros
  (`dts/arm/ambiq/ambiq_apollo510.dtsi:97`; hal_ambiq
  `dts/apollo510/am_apollo510.h:211`), boards override SoC nodes
  (`boards/ambiq/apollo510_evb/apollo510_evb.dts:44-46`), and Apollo3 sets
  its load address as a Kconfig default under `if !BOOTLOADER_MCUBOOT`
  (`soc/ambiq/apollo3x/Kconfig.defconfig.apollo3_blue:40-43`).

## Decision

### 1. Committed snapshots, verified against live sources off the PR path

Commit snapshots of the extracted source facts. Check the catalogue against
them on every PR, and check them against the live sources only when they or
the extractor change, and weekly. The extractor reads only committed
revisions, checked out or archived at the commit SHA, never a working tree.

| When | Job | Network |
|---|---|---|
| Every PR and push to `main` | `check-sources` compares the catalogue with the snapshots; the link-environment dataset is regenerated from them and must equal the committed dataset | none |
| PRs that change the snapshots, the extractor, `uv.lock` (which pins the extractor's dependencies, `pcpp` among them) or the built-in data | The extractor re-runs at each recorded `commit`; its output must equal the committed files byte for byte, and each `#<symbol>` reference in a snapshotted repository must name a single definition (section 3); built-in data changes run only this reference check. A job-level condition on the changed paths, not a workflow path filter, skips it otherwise, so it can be a required check | public checkouts, no token |
| Weekly | Step 1 re-extracts at each recorded `revision` and fails if a tag now resolves to another commit or the extractor breaks. Step 2 extracts neuralspotx `main`, the SDK tags that revision's lock names, and Zephyr `main`, and diffs the result against the snapshots | public checkouts, no token |

The weekly job reports to one tracking issue. A step 1 failure, or a
step 2 diff whose hash differs from the last one posted, adds a comment
that mentions the snapshot directory's code owners; earlier comments are
never edited. GitHub disables scheduled workflows in a public repository
after 60 days without repository activity, so once this repository is
public the job may need re-enabling after a quiet period.

Reason: the PR check is hermetic and fast, and its result depends only on
the commit. An upstream change reaches the catalogue only as a reviewed
diff of extracted values. The regeneration check rejects a hand-edited
snapshot, and the weekly run reports upstream drift within a week without
failing unrelated PRs.

Rejected: live checkouts on every PR, because each result would depend on
the network and on upstream state, an upstream change would surface as an
unrelated PR failing rather than as a reviewed diff, and a `v5.2.24` working
tree alone is about 200 MB. Snapshots alone, because nothing would notice a
moved tag, a hand edit or a new upstream release.

A private source, should one appear (a private SDK branch, or private
silicon under [0002-private-silicon.md](../rfcs/0002-private-silicon.md)),
is extracted in the private package's repository and checked there with the
same extractor and `check-sources --snapshots <dir>`. No snapshot of a
private source enters this repository. Without `--snapshots`,
`check-sources` reads the checkout's `snapshots/` directory; the snapshots
are not shipped in the wheel.

### 2. Format: one JSON file per source repository

Recommendation: `snapshots/nsx-ambiq-sdk.json`, `snapshots/neuralspotx.json`
and `snapshots/zephyr.json`, at stable paths. Each file holds every revision
the pins name. The SDK file is keyed by SoC, and each SoC block names the
tag it was read at. The other two are keyed by board, and the neuralspotx
file also has a `soc_families` key. Reason: a pin bump edits a file in
place, so the review shows the values that moved, and atomiq110's separate
SDK tag is one field rather than a second file.

Rejected: one file per source and revision, because a pin bump becomes a
new file and its review a whole-file read. One file per SoC, because an SDK
tag bump touches every file and repeats the metadata. YAML, because a
generated file gains nothing from it and needs dumper settings to be
deterministic; the catalogue's own format is ADR 0002 (#7)'s decision and
does not bind this one.

Normalisation:

- `json.dumps(sort_keys=True, indent=2, ensure_ascii=True)` plus a final
  newline, with the extractor's dependencies pinned by `uv.lock`. Identical
  input gives identical bytes, so regeneration is checked by plain byte
  equality, and the file carries no extraction date.
- C, linker and devicetree values are evaluated to JSON integers (casts and
  `UL` dropped, `K` and `M` multiplied out, macros expanded). None of them
  is a hex string, so each has one spelling; `check-sources` and the
  extractor's summary print addresses in hex.
- CMake values stay as written: lists of unquoted strings in source order,
  comments stripped. `set(NSX_FPU "")` is `[""]`, distinct from an absent
  key, and `"0x00410000"` and `TRUE` stay strings that the comparison parses.
- Each group records the repo-relative path it was read from, never a line
  number, so an unrelated upstream edit does not change the snapshot.
- A small source unit is recorded whole (every `set()` of a facts file,
  every region of every script, every integer define of
  `am_reg_base_addresses.h`), so a new comparison seldom needs a refresh.
  Large headers contribute named defines only.

Metadata: `extractor_version` (an integer, bumped when the output changes
for unchanged input; not the package version) and `sources`, one entry per
repository and revision with `repository`, `revision` (as pinned: tag or
commit) and `commit` (the full SHA). The Zephyr file lists hal_ambiq as a
second source.

Example, abridged; the file itself puts every key on its own line:

```json
{
  "metadata": {
    "extractor_version": 1,
    "sources": [
      {"commit": "a9f4ec25a162f6f3700623feb691423bb5a51132", "repository": "AmbiqAI/nsx-ambiq-sdk", "revision": "v5.2.24"},
      {"commit": "aefce2ca858795e783c76726ebe7d14d9d4bde7c", "repository": "AmbiqAI/nsx-ambiq-sdk", "revision": "v5.2.25"}
    ]
  },
  "socs": {
    "apollo510": {
      "cmsis": {"path": "modules/nsx-ambiqsuite/sdk/CMSIS/AmbiqMicro/Include/apollo510.h", "values": {"__FPU_DP": 1}},
      "facts": {"path": "cmake/socs/facts/apollo510.cmake", "values": {"NSX_FPU": [""], "NSX_SEGGER_PF_ADDR": ["0x00410000"], "NSX_SOC_SERIES": ["apollo5"]}},
      "linker": {
        "gcc": {
          "default": "linker_script_sbl.ld",
          "path": "modules/nsx-core/src/apollo510/gcc",
          "scripts": {"linker_script_sbl.ld": {"MCU_MRAM": {"length": 4128768, "origin": 4259840}, "MCU_TCM": {"length": 507904, "origin": 536870912}}}
        }
      },
      "registers": {"path": "modules/nsx-ambiqsuite/sdk/mcu/apollo510/regs/am_reg_base_addresses.h", "values": {"DTCM_BASEADDR": 536870912, "DTCM_MAX_SIZE": 524288}},
      "revision": "v5.2.24"
    }
  }
}
```

### 3. What is extracted, and what is compared

The extractor reads only the paths below, so nothing else in the source
trees reaches a snapshot. Each source is extracted for every id it ships,
apollo2 and `apollo2_evb` included; an id the catalogue lacks is reported
unless the exceptions list names it.

| Source | Keyed by | Extracted |
|---|---|---|
| `nsx-ambiq-sdk` | SoC family, at the tag the committed snapshot records (amended: no longer neuralspotx's `soc_families`) | every `set()` of `cmake/socs/facts/<soc>.cmake`; the default script per toolchain from `cmake/socs/<soc>.cmake`; every gcc `MEMORY` region and armclang execution region of every script in `modules/nsx-core/src/<soc>/`, with `EMPTY` regions recorded as the range they occupy (`base - length` to `base` for a negative length) and `empty: true`; every integer define of `modules/nsx-ambiqsuite/sdk/mcu/<dir>/regs/am_reg_base_addresses.h` outside `#if 0`, and the flash and SRAM size defines of `hal/am_hal_flash.h` on Apollo3 parts; the processor-configuration defines of `modules/nsx-ambiqsuite/sdk/CMSIS/AmbiqMicro/Include/<header>.h`, `__FPU_DP` among them |
| neuralspotx (frozen at `neuralspotx-v0.9.0`; parity data only, see the amendment) | board; `soc_families` | `board.soc`, `toolchains` and `cpu` from `src/neuralspotx/boards/<board>/board.yaml`; every `set()` of its `debug.cmake`; the default script per toolchain from its `memory.cmake`, the selection a neuralspotx board build uses; the SDK revision per SoC family from `src/neuralspotx/data/registry.lock.yaml`, which selects the tags above |
| Zephyr with hal_ambiq | board in `boards/ambiq/` (six at `8f62a4ab`) | each memory node's label and `reg` base and size; the `zephyr,flash`, `zephyr,sram`, `zephyr,itcm` and `zephyr,dtcm` chosen nodes; the `FLASH_LOAD_OFFSET` default of the SoC's `Kconfig.defconfig` files for a build without MCUboot |

The SoC-to-header map (`<dir>`, `<header>`) is hand-written in the
extractor's source and reviewed with it: apollo510b and apollo5b have no
headers of their own and read apollo510's. Each group's `path` records the
header actually read.

Parser scope: CMake `set()` and the two default-script forms above, with no
other CMake evaluation; gcc `MEMORY` blocks and scatter execution regions;
object-like C defines with arithmetic, skipping `#if 0`; Kconfig `default`
lines and the `if !BOOTLOADER_MCUBOOT` guard. Devicetrees are read with
`python-devicetree` from the pinned Zephyr commit
(`scripts/dts/python-devicetree`) after preprocessing with `pcpp`, a
pure-Python C preprocessor pinned in `uv.lock`, so includes, node merges by
path and board overrides resolve without a compiler (open question 2).

The comparison uses RFC 0002's field names; spelling maps live in the
comparison code, not in the snapshot. It widens appendix G with
`has_dsp_extension`, `abi` and `float_abi`, `toolchains` and the board's
Soc, and replaces appendix G's "gnu windows equal" row with the containment
and dataset rows.

| Catalogue fact | Snapshot value | Rule |
|---|---|---|
| `Soc.series` | `NSX_SOC_SERIES` | equal |
| core 0 `Core.id`, `Core.arch` | `NSX_SOC_CORE`, `NSX_SOC_ARCH_CLASS` | equal after the spelling map (`armv7e_m` is `armv7e-m`, `armv8_1m` is `armv8.1-m`) |
| `Core.pmu` | `NSX_SOC_PMU_TIER` | `dwt` is `none`; `armv8m` is `armv8m` |
| `Core.has_dsp_extension`; `CoreOptions.mve`, `fpu` not `none` | `NSX_SOC_HAS_DSP`, `NSX_SOC_HAS_MVE`, `NSX_SOC_HAS_FPU` | equal |
| `CoreOptions.fpu` | `NSX_FPU` | equal where not empty (the Cortex-M55 files set `""`) |
| `CoreOptions.fpu_dp` | CMSIS `__FPU_DP` | equal |
| `Soc.npus` not empty | `npu` in `NSX_SOC_CAPABILITIES` | equal |
| `SdkFacts.c_define` | `NSX_SOC_COMPILE_DEFINITIONS` | member |
| `SdkFacts.build.abi`, `float_abi` | `NSX_ABI_FLAGS`, `NSX_FLOAT_ABI` | equal |
| `SdkFacts.trace_clock_mhz` | `NSX_SEGGER_CPUFREQ` of the facts file | equal after the snapshot's value, a string in Hz, is converted to MHz (`"48000000"` is 48) |
| `flash_load_address()` of the Soc target, under its `default_boot` | `NSX_SEGGER_PF_ADDR` | equal |
| `MemoryRegion.base`, `size` | register defines, through a per-SoC map of region to define expression | equal where a define exists |
| every extracted linker and devicetree region | the catalogue's physical regions | lies inside one contiguous, gap-free run of them |
| an `sdk` record that cites a snapshotted repository (nsx-ambiq-sdk, neuralspotx, zephyr, hal_ambiq) | the snapshots | cites a `revision` the snapshots hold: a tag by name, a commit as the exact full SHA; a reference matches a snapshot's `revision` field only |
| a `#<symbol>` reference in such a record | the source at that revision | names a single definition (checked by the extract jobs, which hold the source trees) |
| the link-environment dataset | the snapshots | regenerates byte for byte (section 4) |

A region may span adjoining physical regions: apollo3's gcc `RWMEM` covers
TCM and SRAM, and Zephyr's apollo4p `sram0` (`0x10010000`, 2752 KB) covers
the rest of TCM, SSRAM0, EXTRAM and SSRAM1. The containment rule flags the
apollo330P and apollo510L `nbl` and `itcm_sbl` scripts, which carry
apollo510's sizes (RFC 0001 appendix D): their `MCU_TCM` is 507904 bytes in
gcc and 503808 in armclang, against a 256 KB DTCM
(`modules/nsx-ambiqsuite/sdk/mcu/apollo510L/regs/am_reg_base_addresses.h:43`).
A disagreement passes only when an exceptions list beside the snapshots
names it, with a reason and an issue, in the manner of the parity
allow-lists of #13.

Recorded but deliberately not compared:

- `jlink_device` against `NSX_SEGGER_DEVICE` and its eight board overrides,
  until the spellings are reconciled with SEGGER's device database (RFC
  0001, Authority; RFC 0002 records two spellings for atomiq110).
- Clocks and operating points, because the SDK carries only the trace clock.
- `MemoryRegion.executable`, because the scripts' `rwx` flags differ
  between apollo4p and apollo4l (RFC 0001 appendix G).
- External memories, which the SDK scripts do not link; the board guides
  are their source of record (research/datasheets.md).
- Physical regions with no header define, such as atomiq110's ITCM, whose
  provenance names another source.
- Probe settings with no catalogue field (`NSX_SEGGER_SWOFREQ`,
  `NSX_SEGGER_IF_SPEED`).

### 4. Refresh, and the link-environment dataset

A refresh is a PR made by running the extractor with new pins: an
nsx-ambiq-sdk tag (`--sdk`) and a Zephyr `main` commit by full SHA, from
which the hal_ambiq commit follows (amended; neuralspotx is not refreshed). The pins are the `revision` fields of the
committed snapshots; there is no separate pin file. The first snapshots pin
`neuralspotx-v0.8.1` and the Zephyr `main` head current when the extractor
is implemented (`8f62a4ab` today). The PR carries the regenerated
snapshots, the extractor's summary of changed values in its description,
and, in the same PR, the catalogue, provenance and dataset changes that
`check-sources` then requires, or exception entries with an issue each.
Snapshots are never edited by hand.

Review: one approving review from a code owner of the snapshot directory
(per-directory owners are #17; until then `.github/CODEOWNERS` names the
same owners, `@apage224` and `@evanchen11`, for every path). When a changed value is one a consumer reads (a
window, a flash load address, a trace clock), a maintainer of that consumer
also reviews. A fact sourced from a snapshot carries an `sdk` provenance
record, as ADR 0003 (#6) defines it, citing the upstream repository at the snapshot's
`revision`, so a refresh that changes a value also changes its provenance.
`check-sources` fails when an `sdk` record that cites a snapshotted
repository (nsx-ambiq-sdk, neuralspotx, zephyr, hal_ambiq) cites a
`revision` the snapshots do not hold; `sdk` records citing other sources,
such as AmbiqSuite, are exempt.

The link-environment dataset is generated from the snapshots, never from a
source tree, and committed under `link-environments/`. Whether and how the
dataset ships is not decided; its versioning is RFC 0002 open question 2
and ADR 0004 (#12) open question 2. gcc scripts become `gnu` environments,
armclang scatter files `armlink` environments with `EMPTY` regions as
carve-outs, and Zephyr boards `zephyr` environments with the Kconfig load offset applied.
`LinkEnvironment.revision` is the commit in the snapshot's metadata. A
hand-written mapping lists which (SoC, toolchain, profile) and Zephyr
boards become environments and maps linker region names to catalogue
region names; it leaves out the apollo330P and apollo510L `nbl` and
`itcm_sbl` scripts until upstream fixes them. Window parity (#13) then runs
against the generated dataset.

## Consequences

Easier: PR CI needs no network and gives one answer per commit. Every
upstream change that reaches the catalogue arrives as a reviewed diff
naming the commit it came from. Window figures have one input and are
generated rather than copied. A private package reuses the extractor and
`check-sources` against its own snapshots.

Harder: the extractor is code this repository maintains, with parsers for
CMake, gcc `MEMORY`, scatter regions, C defines and Kconfig defaults, plus
the devicetree toolchain. An upstream format change breaks it on the weekly
run or on a refresh, not on PRs. The snapshots lag upstream by up to a week
for detection, and for as long as nobody bumps a pin. Addresses in the JSON
are decimal.

To follow: the extractor, the snapshots, `check-sources` and the three CI
jobs, under #11; a `.gitattributes` line `snapshots/*.json text eol=lf`, so
a checkout with CRLF conversion keeps the bytes regeneration compares; the
exceptions list, starting with the apollo330P and apollo510L scripts; the
snapshot directory's CODEOWNERS entry (#17). On acceptance this record
replaces RFC 0001 appendix G's table and review item 3.2's sentence "The
Zephyr comparison can stay live", and RFC 0002 links here from `check-sources` and Link
environments.

## Open questions

1. Whether the weekly job should open a refresh PR itself, which needs a
   workflow token with write access, instead of commenting on the tracking
   issue.
2. Whether `pcpp` preprocesses the Ambiq devicetrees as the C preprocessor
   in Zephyr's build does. If not, the extractor needs a pinned compiler
   preprocessor instead.
