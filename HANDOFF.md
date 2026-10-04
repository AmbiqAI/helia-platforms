# HANDOFF

Briefing for whoever picks this up next. Keep under ~2k tokens. Updated
2026-10-04.

## Goal

`helia-platforms`: one shared Python package holding Ambiq SoC and board
facts for heliaAOT, helia-profiler, helia-estimator (and `helia-npu`,
which consumes SoC definitions from here), with neuralspotx as a possible
later consumer. Phase now: specification and planning. The architecture deliverable is
RFC 0002 (the model and the API the package exposes), built on
helia-aot#278 with the owner's changes. No catalogue code until RFC 0002
and the blocking ADRs are accepted.

## Current state

Done:

- Repo skeleton: uv project (`uv_build`), `src/helia_platforms/` version
  stub and CLI, ruff + ty, pre-commit (gitleaks, ruff, uv-lock, ty,
  deferred-work marker hook in `scripts/check_todo_markers.py`), CI and release
  workflows, release-please config, templates, CODEOWNERS. All gates pass:
  ruff, ty, pytest, build, pre-commit.
- Design record: `docs/rfcs/0001-platform-catalogue.md` and appendix
  (imported from the teammate's heliaAOT "RFC 0005" draft, renumbered,
  unedited), `docs/rfcs/0001-platform-catalogue-review.md` (weaknesses,
  proposed changes, owner direction, ranking), `docs/adr/` (template,
  0001 docs layout), `docs/research/` (dated source inventories per repo,
  issue 278 verbatim, and `queries-*.md` question-surface inventories).
- `docs/rfcs/0002-model-and-api.md` (Draft): glossary, principles,
  entity model (Core, Npu, Soc, Implementation, Part, Board, AddOn,
  MemoryDevice, BootConfig; LinkEnvironment optional, outside the core
  model), derived capabilities, resolver (compositions, shorthands; a Soc
  id always resolves to the bare Soc), overlay semantics (syntax deferred
  to ADR #7), release status, question surface, API, changes relative to
  RFC 0001. Companion docs: `0002-multicore.md` (multicore model),
  `0002-private-silicon.md` (side-loading), `0002-migration.md` (#278
  mapping and the
  per-consumer migration and output changes, pending data corrections
  (#14) and parity tests (#13). `docs/rfcs/README.md` indexes the RFCs.
- Commits on `main`: repo bootstrap and design record. Branch
  `22-rfc-0002-model-and-api` carries RFC 0002 and the consumer research;
  review rounds 1 to 4 and the multicore section are committed and pushed
  (0a63a1f). The owner decisions below on FPGA, energy, private silicon
  and local paths are applied locally, not yet committed.
- Open PRs: #24 (RFC 0002 and research) and #25 (CLI on typer). Issues
  #22 (RFC 0002) and #23 (typer) are In review on the board.
  helia-profiler#459 filed for its typer upper cap.
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
- Boot layout is named boot configurations (sbl, nbl, custom) with a
  default per Soc, replaceable by an Implementation, with board
  provisioning recorded; flash address derived. Documented reservations
  (SBL partition) are facts; radio firmware is a core's image slot, not a
  reservation; link windows are not in the core model (optional generated
  SDK dataset).
- External memory is composed: board interfaces, default population per
  board revision, add-ons (shields, daughter boards) bringing devices.
- Board stage is eb, evb or custom; Parts carry silicon revision. An FPGA
  is a reduced Implementation of the Soc, resolvable directly (built-in
  `atomiq110_fpga_turbo`), carrying its own probe, boot and memory
  interface facts; heliaAOT plans against its reduced values.
- Licence: the Ambiq Apollo SDK License, as heliaAOT.
- CLI uses typer (as heliaAOT does), not argparse; typer stays a core
  dependency.
- heliaAOT keeps the name the user passed for aliases (`apollo510l_evb`,
  `apollo3_blue_plus_evb`) and records the canonical id alongside.
- No energy data in the package or its notes; energy coefficients stay in
  helia-estimator.
- Unreleased SoCs never enter this repo: side-loaded from private packages
  (entry points) or `HELIA_PLATFORMS_PATH`; the embargo filter is defence
  in depth.
- Notes cite repositories by name and revision, never local filesystem
  paths; a pre-commit check enforces it (see #26).
- Multicore and heterogeneous SoCs: ordered `cores` and `npus` (index 0
  primary), an explicit access matrix (never inferred), NVM image slots
  owned by cores, system operating points over clock domains; every query
  defaults to core 0 and npu 0. No unreleased parts named in the docs.
  Detail in `docs/rfcs/0002-multicore.md`.

## Next steps

1. Commit and push the owner-decision edits to PR #24; owner approval,
   then merge (it absorbs #3, #8, #9, #10). Merge PR #25 after its review.
   Implement #26 (local-path check).
2. After RFC 0002 merges: ADRs #5 (publication and embargo), #6
   (provenance), #7 (schema format, including the full overlay syntax),
   #12 (schema version vs catalogue version); then #11 drift snapshots and
   #13 parity tests, using RFC 0002's migration tables as the change list.
3. Profiler and estimator maintainer review (#15) before any schema code.
4. Enable the project's auto-add and item-closed workflows in the web UI.

## Gotchas

- Local sibling clones drift: helia-aot local main was 45 commits behind
  origin; helia-profiler local was a feature branch several hundred commits
  behind origin/main and lacked `memory_map.py`, atomiq110 and apollo510L. Always
  check against `origin/main`. Authoritative neuralspotx and SDK checkouts
  are under the neuralspotx workspace checkout, not the helia folder.
- The RFC appendix's line references are to moving branches; re-verify
  before citing. `docs/research/` notes mark what was and was not read.
- Repo is private; a public PyPI release before it is public would ship
  embargoed parts. See review item 3.1.
- release-please will not bump `uv.lock`; expect drift until an
  extra-file or lock refresh step is added.
- `scripts/check_todo_markers.py` is the only file a raw grep for bare
  markers will hit, by design.

- Datasheets (source of record; see `docs/research/datasheets.md`)
  contradict current catalogue data:
  no PSRAM on the base apollo4p_evb (Display Kit only); PSRAM unpopulated
  on apollo330mP_evb and apollo510dL_evb rev 2.0; Apollo510B has a BLE
  controller. Board revision changes what is populated. apollo510_evb and
  apollo510b_evb PSRAM is 64 MB, hardware-validated 2026-07-05 (nsx-psram
  CMakeLists.txt:60-125); BSP macro names are driver families, not sizes.
- Boot layout is not one fact: Apollo510/510B datasheets partition a 64 KB
  SBL region; Lite and 330 Plus datasheets do not, yet their EVB parts ship
  SBL-provisioned; Apollo3/4 secure boot is OTP-enabled with app addresses
  only in the SDK (and AmbiqSuite's Apollo4 `am_defines.py` disagrees with
  its linker scripts). Lite/330 Plus reserve the top of NVM (NVM-M41,
  Cortex-M4 radio firmware; 16/288/432 KB by variant), which the SDK's
  default apollo510L and apollo330P windows appear to overlap. Modelling
  decided (see Decisions).

## References

- Repo: https://github.com/AmbiqAI/helia-platforms (private)
- Board: https://github.com/orgs/AmbiqAI/projects/49
- Sibling boards: heliaAOT project #14, heliaPROFILER project #37 (Status:
  Backlog, Ready, In progress, In review, Done; Priority P0-P2; Size XS-XL)
- Related issues: helia-aot#278, helia-profiler#229 (closed), #133 phases
  (#176, #177, #179), #264, #284; helia-estimator #54, #55, #56, #60;
  neuralspotx#248

## Open questions

- Whether to adopt the proposed `extensions:` map (RFC 0002 open
  question 4).
- Which environments the optional link-environment dataset covers and how
  it is versioned (RFC 0002 open question 2).
- neuralspotx direction: generator from this package, or upstream source.
- Hardware checks: issue #19 (Hardware questions needing an owner).
