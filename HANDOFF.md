# HANDOFF

Briefing for whoever picks this up next. Keep under ~2k tokens, and keep
in it only what changes rarely: the live state (open PRs, the next issue,
what is blocked) is the status section of the roadmap issue #79.

## Goal

`helia-platforms`: one shared Python package holding Ambiq SoC and board
facts for heliaAOT, helia-profiler, helia-estimator and `helia-npu`, with
neuralspotx as a possible later consumer. The model and API are RFC 0002
(with `0002-multicore.md`, `0002-private-silicon.md`,
`0002-migration.md`); the export and pages are RFC 0003.

## Where things live

- **Plan and live status:** #79. It lists every remaining issue in order
  with its dependencies, and its status section names the open PRs and
  the next issue to start.
- **Decisions:** accepted ones are ADRs in `docs/adr/`. Smaller owner
  decisions about one issue are comments on that issue.
- **Built-in data (#63 to #68):** each issue carries the owner's decisions,
  the datasheet verification sign-off, and, in collapsed comments, the full
  research proposal (draft YAML with provenance records) and the page-quote
  verification table. The decisions override the proposal where they
  differ. Read all of them before writing a data file.
- **Datasheets:** Ambiq PDFs are not in this repository. The owner holds a
  local copy; ask for its path and never commit it. The SHA256 prefixes in
  `docs/research/datasheets.md` confirm the copy is the one the notes
  cite.
- **Source inventories:** `docs/research/`, each dated and pinned to a
  revision.

## How to work

- One issue per change, on a branch `<issue#>-slug` (CONTRIBUTING.md).
  Roadmap issues are committed and opened as a PR when their checks pass;
  apage224 reviews and merges. No tool attribution in commits or PRs.
- Before starting an issue, check that the issues it depends on are merged
  (`gh pr list`, #79).
- Accepted ADRs are not rewritten: a small change is a dated amendment
  section under the status line, a larger one a new ADR that supersedes
  the affected part (`docs/adr/README.md`).
- Hosted Copilot has reviewed only the PRs that requested it as a
  reviewer (Evan's do at creation; #160 to #164 did not until asked);
  request it when the PR opens.
- Every built-in value carries an ADR 0003 provenance record; a value with
  no source of record is `unverified` with an allow-list entry and an
  issue. Where sources disagree, ask the owner before writing the value.

## Decisions (owner)

- Unreleased hardware never enters this repository; private silicon is
  side-loaded (entry points, `HELIA_PLATFORMS_PATH`). The export filter is
  defence in depth.
- The package states facts with their sources; what to do with them is
  the consumer's (ADR 0010). The loader rejects data that cannot be
  parsed, references what does not exist or contradicts itself, and keeps
  built-in data complete and unshadowable; it rejects nothing because a
  consumer might misuse it. A query that applies a filter takes it as a
  named parameter. No tool policy, no
  energy data. Tools key their policy by canonical id, and
  `Catalog.lineage()` walks an overlay entry's `based_on` chain so a
  derived Soc finds its base's policy (#134).
- Linker windows are the consumers' (#73). The package gives
  `Target.application_ranges()`, each region less boot reservations and
  other cores' image slots; helia-profiler intersects it with its own
  windows. No `LinkEnvironment`, `budget()` or `windows` command.
- Which memory an NPU serves over which port is the compiler's choice
  (#93): `NpuInstance.axi_ports` gives the IP's port classes and per-port
  limits, and access entries carry no port. Values fitted to make a model
  match captures stay in the tool that fits them (#131).
- Capabilities are derived from structural facts, never declared.
- A Soc is a specification; an FPGA or FVP is an Implementation, not a
  board. An FVP declares its own memory map (ADR 0007).
- RAM budgets are physical region sizes; NVM is `usable_nvm()` after boot
  reservations and other cores' image slots (#28).
- heliaAOT keeps the alias the user passed and records the canonical id.
- RFC 0003 defers the resolved `targets` export; publishable outputs come
  only from `builtin(include_plugins=False)` with no overlays. The export
  writes entries already merged, so it carries no `based_on` (#134,
  owner decision 2026-11-07).
- A region's optional `dma_boundary` says a single DMA transfer does not
  cross a whole multiple of it from the region's base (ADR 0011, #153).
- Releases go to PyPI from this private repository; the owner's data audit
  is the only review before upload (ADR 0005, amended 2026-10-29).

## Gotchas

- Local sibling clones drift. Read consumer and SDK sources at the
  revisions the docs cite (`git show <rev>:<path>`), never a working tree.
- Line references in RFC 0001's appendix are to moving branches; re-verify
  before citing. `docs/research/` notes mark what was and was not read.
- Merging the release-please PR tags the release and publishes to PyPI at
  once: the `pypi` environment has no manual gate, and the repository
  variable `HELIA_PLATFORMS_PYPI_PUBLISH` (`true`) is the only switch. A
  PyPI version cannot be replaced.
- A key the format reads but ignores is marked `Deprecated` in
  `_format.py` (`Access.port` until #159): the loader warns, drops it and
  keeps it out of the source hash, so the fact-change gate can load the
  merge base's data with the head's loader.
- Datasheets are the source of record and contradict consumer data in
  several places (`docs/rfcs/0002-migration.md`, "Pending data
  corrections"); each difference needs a row in the parity allow-lists of
  #13.
- No datasheet states the Apollo3 or Apollo4 application start or SBL
  size; those come from SDK sources at pinned revisions.

## References

- Repository: https://github.com/AmbiqAI/helia-platforms (private)
- Project board: https://github.com/orgs/AmbiqAI/projects/49
- Related: helia-aot#278, helia-profiler#459, helia-profiler#465,
  helia-estimator#190 (the first consumer, on a git pin)
