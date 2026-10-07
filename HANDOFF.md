# HANDOFF

Briefing for whoever picks this up next. Keep under ~2k tokens. Updated
2026-10-07.

## Goal

`helia-platforms`: one shared Python package holding Ambiq SoC and board
facts for heliaAOT, helia-profiler, helia-estimator and `helia-npu`, with
neuralspotx as a possible later consumer. The model and API are RFC 0002;
the export and pages are RFC 0003.

## Current state

Merged on `main`:

- Design record: RFC 0001 (imported) and its review; RFC 0002 with its
  companions (`0002-multicore.md`, `0002-private-silicon.md`,
  `0002-migration.md`); RFC 0003. All RFCs are still Draft (#75).
- ADRs 0001 to 0006, all Accepted (#50): docs layout, file format and
  runtime, provenance record, versions, publication and embargo, drift
  snapshots.
- The loader (#48, PR #49): the ADR 0002 file format, YAML 1.2 reader,
  structural stage, `based_on` and Implementation merges with per-value
  provenance, frozen model, `load_overlay()`, the committed JSON Schema,
  and `helia-platforms validate` and `export --schema`.
- Tooling: ruff, ty, pytest, pre-commit (gitleaks, uv-lock, deferred-work
  markers, local paths), all run in CI; CODEOWNERS per data path and a
  fact-change PR template (#17).

Not yet: built-in data (`src/helia_platforms/data/` does not exist), the
resolver and `Target`, `builtin()`, the provenance validator, the export,
the snapshots, and anything a consumer can call. `helia_platforms` exports
only `__version__`.

## Next steps

The ordered plan, with each step's dependencies, is the roadmap issue #79
(issues #56 to #78). In short:

1. Stage 1, in parallel: #56 (clock caps, FVP substitutions), #57
   (remaining semantic rules), #60 (`builtin()`), #69 part 1
   (distribution file lists), #71 (snapshot extractor).
2. #58 (resolver and `Target`), #61 (provenance validator and register),
   #59 (`identity()` and digest).
3. #63 (first built-in data: apollo510), then the other Socs (#64 to #68).
4. #72 (`check-sources`), #73 (link environments), #74 (export), #13
   (parity tests), then publication (#77) and consumer adoption (#78).

## Decisions (owner)

- Unreleased hardware never enters this repository; private silicon is
  side-loaded (entry points, `HELIA_PLATFORMS_PATH`). The export filter is
  defence in depth.
- No tool policy, no energy data in the package. Tools key their policy by
  canonical id.
- Capabilities are derived from structural facts, never declared.
- A Soc is a specification; an FPGA or FVP is an Implementation, not a
  board. Board `category` is engineering, evaluation or custom.
- RAM budgets are physical region sizes; NVM is `usable_nvm()` after boot
  reservations and other cores' image slots (#28).
- heliaAOT keeps the alias the user passed and records the canonical id.
- RFC 0003 defers the resolved `targets` export; publishable outputs come
  only from `builtin(include_plugins=False)` with no overlays.
- Roadmap PRs: each issue is committed and opened as a PR when its checks
  pass; apage224 reviews and merges.

## Open owner decisions

- Data conflicts found while writing built-in data (#63 to #68).
- Accepting RFC 0002 and RFC 0003 (#75).
- Whether the link-environment dataset ships in the wheel (RFC 0002 open
  question 2; #73).
- The distribution path, public first or PyPI from the private repository
  (ADR 0005 point 2; #77).
- Document ids for the internal atomiq110 specification (ADR 0003 open
  question 1; #68).
- Hardware questions with no owner (#19); facts-versus-policy sign-off
  from the profiler maintainers (#15); neuralspotx direction (#18).

## Gotchas

- Local sibling clones drift. Read consumer and SDK sources at the
  revisions the docs cite (`git show <rev>:<path>`), never a working tree.
- Line references in RFC 0001's appendix are to moving branches; re-verify
  before citing. `docs/research/` notes mark what was and was not read.
- The repository is private; a PyPI release before ADR 0005's audit could
  ship material that is not cleared (ADR 0005 points 2 and 3).
- Datasheets are the source of record and contradict consumer data in
  several places (PSRAM on Apollo4 EVBs, apollo4p SSRAM, apollo3p sizes,
  Lite and 330 Plus NVM and clocks): `docs/rfcs/0002-migration.md`,
  "Pending data corrections".
- Boot layout is a choice, not one fact: Apollo510 datasheets partition a
  64 KB SBL region, Lite and 330 Plus parts ship SBL-provisioned without
  it in the datasheet, and AmbiqSuite's Apollo4 `am_defines.py` disagrees
  with its linker scripts.

## References

- Repository: https://github.com/AmbiqAI/helia-platforms (private)
- Project board: https://github.com/orgs/AmbiqAI/projects/49
- Related: helia-aot#278, helia-profiler#459, helia-profiler#465
