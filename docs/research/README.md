# Research notes

This directory holds dated source inventories for helia-platforms, the shared catalog of Ambiq SoC and board facts for heliaAOT, helia-profiler, and helia-estimator. Each note records what one source (or a group of related sources) says about SoCs, boards, memories, clocks, capabilities, and name resolution, so that the catalog can be reconciled against those sources rather than written from memory. The notes describe what each repo carries at a given revision. They are not sources of record for silicon figures, and values quoted in them keep the file they came from.

Every note records its source, exact revision (branch and commit), read date and method first, then uses sections suited to its source; most also list the citations they re-checked, so the inventory can be re-run when a source moves. Several notes were read from stale or feature-branch checkouts; that is stated at the top of each affected note and should be resolved before reconciliation. Notes cite repositories by name and revision, never local filesystem paths; a pre-commit check enforces this (see #26). The `queries-*` notes record the question surface (what each consumer's code asks of a platform today) rather than the model itself.

The "Superseded by" column marks inventory notes that a `queries-*` note, read against `origin/main`, supersedes: `heliaaot.md` for all consumer facts, because its checkout was stale; `helia-estimator.md` and `helia-profiler.md` where the two conflict.

| Note | Source | Revision | Read on | Superseded by |
| --- | --- | --- | --- | --- |
| [heliaaot.md](heliaaot.md) | `AmbiqAI/helia-aot` | local `main` `e537d293` (45 commits behind `origin/main`) | 2026-10-04 | [queries-heliaaot.md](queries-heliaaot.md) for consumer facts (stale checkout) |
| [helia-profiler.md](helia-profiler.md) | `AmbiqAI/helia-profiler` | `origin/main` `b195e29f` (local checkout is stale feature branch `feat/psram-clock-diagnostics` `ec23bac1`) | 2026-10-04 | [queries-helia-profiler.md](queries-helia-profiler.md) where they conflict |
| [helia-estimator.md](helia-estimator.md) | `AmbiqAI/helia-estimator` (with workspace package `helia-npu`) | feature branch `s14-fvp-in-docker` `8cab17d` | 2026-10-04 | [queries-helia-estimator.md](queries-helia-estimator.md) where they conflict |
| [neuralspotx-and-sdk.md](neuralspotx-and-sdk.md) | `AmbiqAI/neuralspotx`, `AmbiqAI/nsx-ambiq-sdk`, v5.2.24 snapshot, sdk audit mirror, legacy neuralspot | neuralspotx `main` `6afb7d2`; nsx-ambiq-sdk `main` `9d4463a`; snapshot `a07f152`; audit `a9f4ec2` | 2026-10-04 | |
| [ambiqai-conventions.md](ambiqai-conventions.md) | `AmbiqAI/aitg-handbook`, local helia-sdlc, GitHub org via `gh` | aitg-handbook `main` `8ceb2a2`; helia-sdlc unversioned; GitHub as of read date | 2026-10-04 | |
| [helia-aot-278.md](helia-aot-278.md) | AmbiqAI/helia-aot issue 278 (verbatim) | issue as of 2026-09-26 | 2026-10-04 | |
| [queries-heliaaot.md](queries-heliaaot.md) | `AmbiqAI/helia-aot` question surface | `origin/main` `ea5cd6c0` | 2026-10-04 | |
| [queries-helia-profiler.md](queries-helia-profiler.md) | `AmbiqAI/helia-profiler` question surface | `origin/main` `b195e29f` | 2026-10-04 | |
| [queries-helia-estimator.md](queries-helia-estimator.md) | `AmbiqAI/helia-estimator` (with `helia-npu`) question surface | `origin/main` `5991d9f1` | 2026-10-04 | |
| [queries-neuralspotx-zephyr.md](queries-neuralspotx-zephyr.md) | `AmbiqAI/neuralspotx`, `AmbiqAI/nsx-ambiq-sdk`, heliaAOT Zephyr path, question surface | neuralspotx `main` `6afb7d2`; nsx-ambiq-sdk `9d4463a`; heliaAOT `origin/main` `ea5cd6c0` | 2026-10-04 | |
| [datasheets.md](datasheets.md) | Ambiq SoC datasheets and EVB quick-start guides, Ambiq internal datasheet library (29 PDFs, 23 distinct); page-cited summary of the source of record (the PDFs themselves) | per-document revision and SHA256 in the note's inventory | 2026-10-04 | |
| [ambiqsuite.md](ambiqsuite.md) | SWS AmbiqSuite: boot linker variants, provisioning tools, board BSP external memories | see note | 2026-10-04 | |
| [appendix-verification.md](appendix-verification.md) | RFC 0001 appendix D and J, each number checked against `AmbiqAI/nsx-ambiq-sdk`, `AmbiqAI/neuralspotx`, Zephyr with hal_ambiq, `AmbiqAI/helia-aot` and `AmbiqAI/helia-profiler` | nsx-ambiq-sdk `v5.2.24` and `v5.2.25`; neuralspotx `b930d59`; zephyr `d8be6be`; hal_ambiq `c03d2f9`; helia-aot `1fd91daf`; helia-profiler `ed2f0a15` | 2026-10-05 | |
