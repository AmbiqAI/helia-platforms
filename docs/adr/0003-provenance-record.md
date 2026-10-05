# 0003. Record provenance per fact with a closed status vocabulary

Date: 2026-10-05
Status: Proposed

## Context

In RFC 0001 only `MemoryRegion` (`provenance`) and `LinkWindow`
(`window_provenance`, `app_provenance` and a `source_tag`) carry
provenance (RFC 0001 appendix, entity listing); no other fact has a
record. The review of RFC 0001 (items 1.1 and 2.1) asks for one record
type attachable to any fact or group of facts, with the status vocabulary
`datasheet`, `sdk`, `measured`, `fitted`, `derived` and `unverified`, and a
release that rejects `unverified` unless allow-listed. Item 3.4 (#17) adds
that a changed value whose provenance did not change is rejected. RFC 0002
adopts this as principle P4 (RFC 0002 at `c3d3e78`, :82) and a
`Provenance` dataclass (`status`, `source`, `verified_on`, `verified_by`,
`notes`; :721), pending this record.

helia-estimator already keeps per-value provenance in `helia-npu`
(`packages/helia-npu/src/helia_npu/socs/atomiq110.yaml` at `5991d9f1`): a
record on each memory with `status` (`confirmed`, `fitted` or
`unverified`), free-text `source`, `reviewed_by`, `reviewed_on`, `notes`,
and a `fields` map of per-value records that override it (lines 37-55 for
`ssram`). Its sources are prose, for example "Atomiq110 SoC specification"
with no revision or page (line 52), so no tool can check them. The
datasheet inventory (`docs/research/datasheets.md`) cites every value as a
document key plus PDF page, with the key's document id and revision in the
inventory table.

## Decision

### 1. The record

| Field | Meaning | Required |
|---|---|---|
| `status` | One value from the vocabulary below. | Always |
| `source` | One or more source references in the canonical spellings of section 2. | Every status except `unverified`, where it is optional |
| `verified_on` | ISO date (`YYYY-MM-DD`) on which `verified_by` last compared the value with its source. Not the source's own date. | Every status except `unverified`, where it is forbidden: a date would read as a verification |
| `verified_by` | GitHub login of the person who checked, or an organisation team (`@AmbiqAI/<team>`). | As `verified_on`; who made an estimate goes in `notes` |
| `notes` | Free text: the arithmetic of a derived value, what a fitted value stands in for, why a value is unverified. Never parsed and never used by a gate. | Optional |

| Status | Meaning | Example |
|---|---|---|
| `datasheet` | Stated in a vendor document of record: an Ambiq datasheet, addendum, EVB quick-start guide or specification, or an Arm technical reference manual. | Apollo510 NVM-SBL at 0x00400000-0x0040FFFF: `doc:DS-A510@1.1.0:p35` (research/datasheets.md section 2) |
| `sdk` | Read from software that builds firmware for the part, at a pinned revision: nsx-ambiq-sdk, AmbiqSuite, Zephyr and its hal_ambiq module, neuralspotx. Consumer tool data (heliaAOT `targets.json`, the profiler registry) is not an `sdk` source; a value copied from it is `unverified` until traced. | Apollo510 trace clock 96 MHz: `repo:AmbiqAI/nsx-ambiq-sdk@v5.2.24:cmake/socs/facts/apollo510.cmake#NSX_SEGGER_CPUFREQ` (line 57) |
| `measured` | Observed on hardware or a model by a named method on a named target. | apollo510_evb PSRAM capacity 64 MB, confirmed by an XIP address-aliasing test on 2026-07-05: `meas:apollo510_evb/xip-alias/2026-07-05` and `repo:AmbiqAI/nsx-ambiq-sdk@v5.2.24:modules/nsx-psram/CMakeLists.txt:106-110` (added by AmbiqAI/nsx-ambiq-sdk#38) |
| `fitted` | A parameter chosen so that a model reproduces measurements; it stands in for a quantity, it does not state it. | atomiq110 SSRAM read latency 120 ns, fitted to FPGA PMU captures and RTL runs (`atomiq110.yaml:32,38-46` at `5991d9f1`). The example illustrates the status; the record itself migrates as `unverified` (section 5). |
| `derived` | Computed from other sourced values; `source` names every input. | Apollo510 NVM0-APPL size 0x1F0000, computed from 0x00410000-0x005FFFFF: `doc:DS-A510@1.1.0:p35`, with the arithmetic in `notes` |
| `unverified` | No checked source. The default for an overlay value with no record (RFC 0002 at `c3d3e78`, :462). | atomiq110 HBLRAM read latency 88 ns, an architect estimate (`atomiq110.yaml:59,77` at `5991d9f1`) |

Reports that summarise a group (`Target.provenance()`, which RFC 0002 at
`c3d3e78`, :795, defines as the worst status per group) use this order,
worst first:
`unverified`, `fitted`, `sdk`, `measured`, `datasheet`. A software
convention can disagree with the silicon (RFC 0002 at `c3d3e78`,
:288-291, records AmbiqSuite's Apollo4 `am_defines.py` against its linker
scripts), and a measurement
covers only the sample measured, while the datasheet is the source of
record (`docs/research/datasheets.md`). A `derived` value ranks as the
worst of its inputs: a `fact:` input by its own status, `doc:` as
`datasheet`, `meas:` as `measured`, `repo:` and `url:` as `sdk`. The
order exists for reports; the release gate in section 4 distinguishes
only `unverified`.

The CLI prints the status beside every value in `helia-platforms show
<id>`, and the full record with `--provenance`. The existing `--sources`
flag keeps its RFC 0002 meaning (at `c3d3e78`, :833), the entry's source label (for example
`builtin` or `overlay:<path>`), which is not the provenance `source`.

### 2. Source references

`source` holds a list of references from a closed set of kinds. Each kind
has one canonical spelling. The validator checks form and register
presence only; it never opens a document or a repository:

| Kind | Canonical spelling | The validator checks |
|---|---|---|
| Document | `doc:<key>@<revision>:p<page>[-<page>]` | The key and revision are in the source register; the pages are within the document. A page is the 1-based PDF page index, as in `docs/research/datasheets.md`. |
| Repository | `repo:<repository>@<revision>:<path>[:<line>[-<line>]][#<symbol>]` | The repository is in the source register; the revision is a tag, by name, or a full 40-hex commit SHA, never a branch or an abbreviated SHA; the path is repository-relative and contains no `:` or `#`. `#<symbol>` names the single definition of that symbol in the file (a CMake `set`, a C `#define`, an enumerator). For a snapshotted repository, ADR 0006 (#11)'s extract jobs check that the definition exists exactly once; the validator does not. |
| Measurement | `meas:<target id>/<method>/<YYYY-MM-DD>` | The target id resolves; the method is a lowercase slug; the date is not after `verified_on`. A `measured` or `fitted` record also carries at least one `repo:` or `url:` reference to a record of the method and result (a script, log, capture or written account). |
| URL | `url:https://<host>/<path>` | The scheme is https and the URL carries no credentials. Use it for public pages only; an internal document is cited with `doc:`. |
| Catalogue fact | `fact:<entity kind>:<id>:<field path>` | The fact exists. The entity kind is the singular of an ADR 0002 (#7) top-level key (`core`, `soc`, `implementation`, `part`, `board`, `addon`, `memory_device`). The field path is dot-separated; a keyed collection is addressed by its key (`fact:soc:atomiq110:memories.hblram.characterization.read_latency_ns`), and a collection keyed by a pair by `<first>@<second>` (`access.<master>@<target>`). A `derived` record uses it for inputs that are catalogue facts; an `unverified_allowed` entry may name a group path, which covers every value in the group. |

Each status needs at least these kinds: `datasheet` a `doc:`; `sdk` a
`repo:`; `measured` a `meas:` and its evidence; `fitted` the `meas:`
references it was fitted to, their evidence, and a `repo:` or `doc:`
reference to the fit procedure; `derived` one reference per input.

The source register is one committed data file with two top-level keys:
`documents` (key, document id, revision, date, page count, SHA256), which
is the inventory of `docs/research/datasheets.md` as data, and
`repositories` (name, URL). A GitHub repository is named `owner/name`; any
other repository gets a bare registered name and the register records the
system that hosts it (AmbiqSuite in SWS: `repo:AmbiqSuite@<40-hex SHA>:<path>`;
`docs/research/ambiqsuite.md` records only the abbreviated `b015b860da`).
Its file location follows ADR 0002 (#7).

### 3. Granularity, defaults and inheritance

A record attaches to an entry, to any group inside it (a memory region, a
`characterization` block, a boot configuration), or to a single value. A
value's provenance is the nearest record that encloses it: its own, else
the innermost enclosing group's, else the entry's. This is the
estimator's group record with `fields` overrides, generalised. The keys
on ADR 0002 (#7)'s closed non-fact list (`id`, `aliases`,
`release_status`, `default_board`, `derives_from`, `extensions`,
`based_on`, `provenance`) take no record.

```yaml
# Illustrative; the syntax, including a per-value record, is ADR 0002 (#7)'s.
socs:
  apollo510:
    sdk:
      trace_clock_mhz: 96
      provenance:          # covers every value in `sdk` that has no record of its own
        status: sdk
        source: ["repo:AmbiqAI/nsx-ambiq-sdk@v5.2.24:cmake/socs/facts/apollo510.cmake#NSX_SEGGER_CPUFREQ"]
        verified_on: 2026-10-05
        verified_by: <login>
```

Every value in a built-in entry must resolve to a record; a missing record
is a validation error, and `unverified` must be written out. In an overlay
a value with no record resolves to `unverified`. Inheritance follows RFC
0002 (at `c3d3e78`, :561-563): with `based_on`, and when an
Implementation inherits from its Soc, an unchanged value keeps the record
it resolved to in the base, whatever group records the new entry declares.
A changed, resized or removed value takes the new entry's nearest record,
or `unverified` where it has none. `Target` returns each value with the
record it resolved to in the entry that declared it.

### 4. Release and change rules

- **`unverified` gate.** A required check on every pull request to
  `main`, release-please's release pull request included, rejects any
  value in a built-in entry that resolves to `unverified`, and any
  `derived` value with a `fact:` input that resolves to `unverified`,
  unless the value is on the release allow-list `unverified_allowed`. It
  runs there because a job in `release.yml` could block only the upload,
  not the tag. No tag, private or public, is exempt: the allow-list
  records known gaps, and deferring the gate would move the whole backlog
  to the public cutover. `unverified_allowed` is one committed file, owned
  through CODEOWNERS (#17), at the location ADR 0002 (#7) gives. Each
  entry is a `fact:` reference, a reason and an issue (`#N`). The
  validator also rejects an entry whose fact is gone or no longer
  `unverified`, so the list cannot go stale.
- **A changed value needs a changed record (#17).** CI loads the built-in
  catalogue at the pull request's merge base and at its head and compares
  the declared facts, keyed by fact path. A value that differs must
  resolve to a record that differs from the base's in `status`, `source`
  (compared as a set) or `verified_on`; a `verified_on` equal to the date
  of the CI run (UTC) also passes. A change to `notes` or `verified_by`
  alone does not count. When the record covers a group, changing one value
  in it requires changing the group record or adding a record for that
  value. New fact paths are exempt, so a rename combined with a value
  change escapes this check. Changing a record without changing a value
  is allowed: that is a re-verification.
- **`derived` inputs.** A `derived` record lists every input in `source`:
  a `fact:` reference for an input that is a catalogue fact, any other
  kind for an input that is not. `notes` states the computation. As a
  separate check, a pull request that changes a fact named by a `fact:`
  input must also change the record of every `derived` value that names
  it, even when the derived value itself is unchanged.

### 5. helia-estimator mapping

| helia-estimator | helia-platforms |
|---|---|
| `status: confirmed` | `datasheet`, `sdk` or `measured`, chosen by the kind of the source: a document, a repository, or a measurement |
| `status: fitted` | `fitted` |
| `status: unverified` | `unverified` |
| `source` (free text) | Canonical references; the original text is kept in `notes` |
| `reviewed_by`, `reviewed_on` | `verified_by`, `verified_on` |
| `notes` | `notes` |
| Record on a memory, with `fields` overrides | A group record on the region or its `characterization`, with per-value records |

A `confirmed` or `fitted` record whose source text cannot be written as
canonical references migrates as `unverified`, with the text in `notes`.
It needs an entry in both lists: in `unverified_allowed`, so the migration
pull request passes the gate, and in the parity allow-list of #13, because
its status differs from the mapped estimator status that the parity test
expects (RFC 0002 migration at `c3d3e78`, `0002-migration.md:110`).
At `5991d9f1` this covers every `confirmed` record in `atomiq110.yaml`,
each of which cites "Atomiq110 SoC specification" without a revision or
page (lines 52-54, 65-69), and both `fitted` records, SSRAM (lines 38-41)
and RRAM (lines 102-103), whose measurements name no evidence location or
revision.

### Rejected alternatives

- One record per entry with a `source_tag` (RFC 0001): cannot give a
  value a status that differs from its neighbours (review 2.1).
- The estimator's three statuses: `confirmed` hides whether a value rests
  on a datasheet, an SDK or a measurement, which matters when those
  sources disagree.
- Free-text `source`: no validator can tell whether a revision or page
  was given.
- A structured mapping per source reference instead of a string: longer
  per value and harder to search, with no extra checking, because the set
  of kinds is closed.
- A separate `inputs` field for `derived`: a sixth field used by one
  status, when `source` already holds a list.
- An allow-list flag on each record: spreads release exceptions across the
  data instead of one reviewed file.
- Branch names as revisions: they move (review section 4).

## Consequences

- The validator checks each reference's form and that its document or
  repository is in the register; it cannot check that the source states
  the value. ADR 0006 (#11) compares `sdk` values, and `datasheet` values
  such as region bases against register defines, with snapshots taken at
  its own pinned revisions.
- A record over a large group is cheap to write but makes every change
  inside the group touch it, and a re-verification of the group sets
  `verified_on` for every value in it. Authors are pushed toward records
  at the level where sources differ.
- atomiq110's estimator-sourced values arrive as `unverified` until the
  estimator owners supply document ids, revisions and pages for the
  specification they cite. Those values need `unverified_allowed`
  entries in the migration pull request itself, since the gate runs on
  every pull request to `main`.
- A provenance-only change is a `chore(data):` change that ships with the
  next release, and `catalogue_digest` excludes provenance (ADR 0004
  (#12)).
- The source register is new data to maintain; a datasheet revision means
  a new register row and re-verified records.
- On acceptance, RFC 0002's glossary entry "provenance status" and P4
  (at `c3d3e78`, :70 and :82) drop "proposal pending ADR #6" and link
  here; the
  fact-change pull request template (#17) asks for the record.

## Open questions

1. Do the internal documents the estimator cites (the Atomiq110 SoC
   specification, the AT110 memory latency table) have document ids,
   revisions and pages, and may their ids appear in a repository that will
   later be public (ADR 0005 (#5))?
2. Which organisation team stands for the estimator's "Ambiq hardware
   review" as `verified_by`?
3. Should `unverified_allowed` entries expire at a catalogue version, or is the
   issue reference enough?
