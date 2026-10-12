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
- Accepted ADRs are never edited. A change to an accepted decision is a new
  ADR that supersedes the affected part (ADR 0007 and ADR 0008 do this).
- Every built-in value carries an ADR 0003 provenance record; a value with
  no source of record is `unverified` with an allow-list entry and an
  issue. Where sources disagree, ask the owner before writing the value.

## Decisions (owner)

- Unreleased hardware never enters this repository; private silicon is
  side-loaded (entry points, `HELIA_PLATFORMS_PATH`). The export filter is
  defence in depth.
- No tool policy, no energy data in the package. Tools key their policy by
  canonical id.
- Capabilities are derived from structural facts, never declared.
- A Soc is a specification; an FPGA or FVP is an Implementation, not a
  board. An FVP declares its own memory map (ADR 0007, proposed in #82).
- RAM budgets are physical region sizes; NVM is `usable_nvm()` after boot
  reservations and other cores' image slots (#28).
- heliaAOT keeps the alias the user passed and records the canonical id.
- RFC 0003 defers the resolved `targets` export; publishable outputs come
  only from `builtin(include_plugins=False)` with no overlays.

## Gotchas

- Local sibling clones drift. Read consumer and SDK sources at the
  revisions the docs cite (`git show <rev>:<path>`), never a working tree.
- Line references in RFC 0001's appendix are to moving branches; re-verify
  before citing. `docs/research/` notes mark what was and was not read.
- The repository is private; a PyPI release before ADR 0005's audit could
  ship material that is not cleared (ADR 0005 points 2 and 3).
- release-please bumps the version in `pyproject.toml` but not the
  project's own entry in `uv.lock`, so `uv sync --locked` (CI) and the
  uv-lock hook fail on a release PR until `uv lock` is run on its branch.
- Datasheets are the source of record and contradict consumer data in
  several places (`docs/rfcs/0002-migration.md`, "Pending data
  corrections"); each difference needs a row in the parity allow-lists of
  #13.
- No datasheet states the Apollo3 or Apollo4 application start or SBL
  size; those come from SDK sources at pinned revisions.

## References

- Repository: https://github.com/AmbiqAI/helia-platforms (private)
- Project board: https://github.com/orgs/AmbiqAI/projects/49
- Related: helia-aot#278, helia-profiler#459, helia-profiler#465
