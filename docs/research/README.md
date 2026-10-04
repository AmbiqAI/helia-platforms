# Research notes

This directory holds dated source inventories for helia-platforms, the shared catalogue of Ambiq SoC and board facts for heliaAOT, helia-profiler, and helia-estimator. Each note records what one source (or a group of related sources) says about SoCs, boards, memories, clocks, capabilities, and name resolution, so that the catalogue can be reconciled against those sources rather than written from memory. The notes describe what each repo carries at a given revision. They are not sources of record for silicon figures, and values quoted in them keep the file they came from.

Every note names its exact revision (branch and commit) and read date in its front block, and lists the citations it re-checked, so the inventory can be re-run when a source moves. Several notes were read from stale or feature-branch checkouts; that is stated at the top of each affected note and should be resolved before reconciliation. Sections follow the same order in every note: What it is; Platform model; Registered entries; Consumers / name resolution; Facts it carries that the others do not; Tooling to mirror; Open questions.

| Note | Source | Revision | Read on |
| --- | --- | --- | --- |
| [heliaaot.md](heliaaot.md) | `AmbiqAI/helia-aot` | local `main` `e537d293` (45 commits behind `origin/main`) | 2026-10-04 |
| [helia-profiler.md](helia-profiler.md) | `AmbiqAI/helia-profiler` | `origin/main` `b195e29f` (local checkout is stale feature branch `feat/psram-clock-diagnostics` `ec23bac1`) | 2026-10-04 |
| [helia-estimator.md](helia-estimator.md) | `AmbiqAI/helia-estimator` (with workspace package `helia-npu`) | feature branch `s14-fvp-in-docker` `8cab17d` | 2026-10-04 |
| [neuralspotx-and-sdk.md](neuralspotx-and-sdk.md) | `AmbiqAI/neuralspotx`, `AmbiqAI/nsx-ambiq-sdk`, v5.2.24 snapshot, sdk audit mirror, legacy neuralspot | neuralspotx `main` `6afb7d2`; nsx-ambiq-sdk `main` `9d4463a`; snapshot `a07f152`; audit `a9f4ec2` | 2026-10-04 |
| [ambiqai-conventions.md](ambiqai-conventions.md) | `AmbiqAI/aitg-handbook`, local helia-sdlc, GitHub org via `gh` | aitg-handbook `main` `8ceb2a2`; helia-sdlc unversioned; GitHub as of read date | 2026-10-04 |
