## Summary

<!-- Which facts change, and why? Name what prompted the change: a datasheet
revision, a measurement, a snapshot refresh, an issue. -->

Closes #

<!-- The PR title carries the commit type (ADR 0004 section 2). `fix(data):`
corrects a value; `fix(data)!:` removes a collection member; `feat(data)!:`
removes a built-in id or alias; `feat(data):` adds an entry, or renames a
built-in id and keeps the old id as an alias; `chore(data):` changes only
provenance, the source register or allow-list, or refreshes snapshots with no
fact change. A PR that spans several takes the type with the largest bump. -->

## Changed facts

<!-- One block per changed value, or one per group when a single record
covers the group. `record_at` is the field path of the group or value that
holds the record the value resolves to, or `entry` for the entry's own record.

Source references use ADR 0003 section 2's canonical spellings:
  doc:<key>@<revision>:p<page>[-<page>]
  repo:<repository>@<revision>:<path>[:<line>[-<line>]][#<symbol>]
    (revision: a full 40-hex commit SHA, or a tag the source register lists)
  meas:<target id>/<method>/<YYYY-MM-DD>
  url:https://<host>/<path>
  fact:<entity kind>:<id>:<field path>

Each status needs at least: datasheet a doc:; sdk a repo:; measured a meas:
and a repo: or url: record of the method and result; fitted the meas:
references it was fitted to, their evidence, and a repo: or doc: reference to
the fit procedure; derived one reference per input, with the arithmetic in
notes. An unverified record has no verified_on or verified_by, and its notes
say why it is unverified. -->

```yaml
- fact: fact:<entity kind>:<id>:<field path>
  old: <value at the merge base, or "new">
  new: <value at head, or "removed">
  record_at: <field path, or "entry">
  status: <datasheet | sdk | measured | fitted | derived | unverified>
  source:
    - <reference>
  verified_on: <YYYY-MM-DD, the date the value was compared with its source>
  verified_by: <GitHub login, or @AmbiqAI/<team>>
  notes: <optional>
```

## Provenance checks (ADR 0003 section 4)

<!-- The `fact-changes` CI job checks the first, second and fourth boxes,
and loading the catalog (pytest) checks the cycle, unverified-gate and
register rules. The author still confirms each box and the reviewer checks
the rename and snapshot boxes by hand. -->

- [ ] Every changed value resolves to a record that differs from the merge
      base's in `status`, `source` (compared as a set) or `verified_on`.
      Between two `unverified` records, a change to `notes` also counts. A
      change to `verified_by` alone never counts, nor does a change to
      `notes` alone on any other status.
- [ ] Where a group record covers a changed value, this PR changes the group
      record or adds a record for that value.
- [ ] Any fact moved to a new path is listed above under its old and new
      paths. The changed-record check exempts new fact paths, so only review
      catches a value changed together with a rename.
- [ ] For every changed fact that a `derived` record names as a `fact:`
      input, that `derived` record also changes, even if the derived value
      does not. No `fact:` input chain forms a cycle.
- [ ] No value in a built-in entry resolves to `unverified`, and no
      `derived` value has a `fact:` input that resolves to `unverified`,
      unless `unverified_allowed` in `unverified.yaml` lists it with a reason
      and an issue. Entries whose fact this PR removes or verifies are
      removed from that list.
- [ ] Every cited document, repository and tag is in the source register
      (`sources.yaml`), and each newly cited tag is recorded there with its
      40-hex commit SHA.
- [ ] Each `sdk` record that cites a snapshotted repository (nsx-ambiq-sdk,
      neuralspotx, zephyr, hal_ambiq) cites a `revision` that the committed
      snapshots hold (ADR 0006).

## Catalog scope

<!-- No check can tell whether hardware is released, and no CI job checks
the other two rules yet. The author confirms each box and the reviewer
checks it again. -->

- [ ] No entry this PR adds describes unreleased hardware. The rule covers
      every entity kind, including a new board or add-on for a released SoC
      (ADR 0005 point 1), and `release_status: public` does not satisfy it
      on its own.
- [ ] No built-in entry carries tool policy: no tool section, no
      `extensions` map and no setting such as `preferred_memory_order`
      (RFC 0002 principle P1). Each tool keeps its policy, keyed by
      canonical id.
- [ ] No entry carries energy data, such as energy per cycle or per bit;
      the estimator's energy coefficients stay in helia-estimator (RFC 0002,
      the `MemoryRegion` paragraph of the Soc section).

## Snapshot refresh (ADR 0006)

<!-- Delete this section unless the PR regenerates files under snapshots/. -->

- New pins:
- Extractor summary of changed values:
- Consumer maintainers asked to review (for a window, flash load address,
  trace clock or other value a consumer reads):

- [ ] The extractor regenerated the snapshots; none was edited by hand.
- [ ] Each disagreement `check-sources` reports is fixed in this PR or has an
      exceptions-list entry with a reason and an issue.

## Validation

- [ ] `uv run pre-commit run --all-files` passes
- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run ty check` passes
- [ ] `uv run pytest` passes
- [ ] `uv build` succeeds
- [ ] Docs updated where behavior or data changed
