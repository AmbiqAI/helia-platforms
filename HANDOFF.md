# HANDOFF

Briefing for whoever picks this up next. Keep under ~2k tokens. Updated
2026-10-04.

## Goal

`helia-platforms`: one shared Python package holding Ambiq SoC and board
facts for heliaAOT, helia-profiler, helia-estimator (and `helia-npu`,
which consumes SoC definitions from here), with neuralspotx as a possible
later consumer. Phase now: specification and planning. No catalogue code
until the RFC revision and the blocking ADRs are accepted.

## Current state

Done, verified locally (nothing pushed, no commits yet):

- Repo skeleton: uv project (`uv_build`), `src/helia_platforms/` version
  stub and CLI, ruff + ty, pre-commit (gitleaks, ruff, uv-lock, ty,
  deferred-work marker hook in `scripts/check_todo_markers.py`), CI and release
  workflows, release-please config, templates, CODEOWNERS. All gates pass:
  ruff, ty, pytest, build, pre-commit.
- Design record: `docs/rfcs/0001-platform-catalogue.md` and appendix
  (imported from the teammate's heliaAOT "RFC 0005" draft, renumbered,
  unedited), `docs/rfcs/0001-platform-catalogue-review.md` (weaknesses,
  proposed changes, owner direction, ranking), `docs/adr/` (template,
  0001 docs layout), `docs/research/` (dated source inventories per repo).
- GitHub: project heliaPLATFORMS (#49, sibling layout: Status Backlog,
  Ready, In progress, In review, Done; Priority P0-P2; Size XS-XL), labels,
  repo settings, and issues #1-#21 created from the review's items, each on
  the board with priority and size. #1, #2 and #16 close on the first
  commit.

Not done: PyPI trusted publisher and the `pypi` environment (after the
publication ADR, #5, and the repo going public); the project's built-in
auto-add and close-to-Done workflows, which only the web UI can enable.

## Decisions so far (owner, 2026-10-04)

- helia-aot#278 (Evan Chen's Soc/Board redesign) is abstracted into this
  package and referenced from RFC 0001; 278 itself is left to its assignee.
- `helia-npu` owns NPU-driver detail only; SoC and board definitions live
  here and it consumes them.
- SoC is a specification; implementations (silicon, FPGA, FVP, RTL)
  realize all of it by default or a validated subset.
- Capabilities (MVE, FP16, NPU) are derived from facts, never declared.
  NPU is structured: vendor, family, model, MACs per cycle.
- Memories carry speed and port detail, not only size.
- No tool opinions (preferred memory order, alignment policy) in the
  package.
- Docs layout per ADR 0001; RFC numbering restarts at 0001 in this repo.
- Licence: the Ambiq Apollo SDK License, as heliaAOT.

## Next steps

1. Enable the project's auto-add and item-closed workflows in the web UI.
2. RFC revision PRs in the ranked order in the review (section 5), each
   on a `<issue#>-slug` branch closing its issue; P0 first: #3, #4, #5,
   #9, #10, then #6, #7, #8.
3. Profiler and estimator maintainer review (#15) before any schema code.

## Gotchas

- Local sibling clones drift: helia-aot local main was 45 commits behind
  origin; helia-profiler local was a feature branch several hundred commits
  behind origin/main and lacked `memory_map.py`, atomiq110 and apollo510L. Always
  check against `origin/main`. Authoritative neuralspotx and SDK checkouts
  are under `/Users/adam.page/Ambiq/neuralspotx/`, not the helia folder.
- The RFC appendix's line references are to moving branches; re-verify
  before citing. `docs/research/` notes mark what was and was not read.
- Repo is private; a public PyPI release before it is public would ship
  embargoed parts. See review item 3.1.
- release-please will not bump `uv.lock`; expect drift until an
  extra-file or lock refresh step is added.
- `scripts/check_todo_markers.py` is the only file a raw grep for bare
  markers will hit, by design.

## References

- Repo: https://github.com/AmbiqAI/helia-platforms (private)
- Board: https://github.com/orgs/AmbiqAI/projects/49
- Sibling boards: heliaAOT project #14, heliaPROFILER project #37 (Status:
  Backlog, Ready, In progress, In review, Done; Priority P0-P2; Size XS-XL)
- Related issues: helia-aot#278, helia-profiler#229 (closed), #133 phases
  (#176, #177, #179), #264, #284; helia-estimator #54, #55, #56, #60;
  neuralspotx#248

## Open questions

- Whether overlays carry an opaque per-tool `extensions:` map.
- neuralspotx direction: generator from this package, or upstream source.
- Hardware checks listed in issue draft 18.
