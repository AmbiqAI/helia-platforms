## Summary

<!-- Which facts change, and why? Name what prompted the change: a datasheet
revision, a measurement, a snapshot refresh, an issue. -->

Closes #

<!-- The PR title carries the commit type (ADR 0004 section 2):
`fix(data):` for a corrected value, `fix(data)!:` for a removed collection
member, `feat(data):` for a new entry, and `chore(data):` for a change to
provenance only, to the source register or allow-list, or for a snapshot
refresh that changes no fact. -->

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

<!-- No CI job runs these checks yet. Until one does, the author confirms
each box and the reviewer checks it again. -->

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
