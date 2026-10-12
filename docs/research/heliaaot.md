# heliaAOT platform model: source inventory

> Superseded for consumer facts by [queries-heliaaot.md](queries-heliaaot.md), read against `origin/main`; this note was read from a stale checkout.

- **Source:** helia-aot checkout (GitHub `AmbiqAI/helia-aot`)
- **Revision:** local `main` at `e537d293`
- **Read on:** 2026-10-04
- **Method:** Inventory from a read of the local checkout; ten citations re-checked against `e537d293` on 2026-10-04 (results under Open questions, "Citation checks").

> **Stale checkout.** Local `main` at `e537d293` is **45 commits behind `origin/main`** (`git status -sb` on 2026-10-04 reports `## main...origin/main [behind 45]`). Every path, line number, and value below describes `e537d293`, not current upstream. Re-run this inventory against `origin/main` before reconciling the catalog with it. The checkout also has an untracked `HANDOFF.md`.

## What it is

heliaAOT is the ahead-of-time compiler that turns LiteRT models into C modules for Ambiq targets. Its platform model is a flat, in-code registry of SoC/board entries used by the memory planner, operator selection, code templates, and docs export.

| Item | Value | Source |
| --- | --- | --- |
| Platform type | `SocPlatform` (frozen dataclass with pydantic `Field`s) | `helia_aot/platforms/defines.py:129-130` |
| Registry | `register_platform(...)` into `_PLATFORM_REGISTRY`; read-only view `PLATFORM_REGISTRY` | `helia_aot/platforms/platforms.py:245` |
| Registered entries | 15 literals | `helia_aot/platforms/platforms.py:254-544` |
| Name resolution | `resolve_platform(platform_cfg)` | `helia_aot/platforms/platforms.py:144-241` |
| Config surface | `PlatformArgs` | `helia_aot/cli/defines.py:265-286` (see Citation checks) |
| Board vs SoC split | None. One type per entry; entry names are board-style (`*_evb`) except `atomiq110` | `platforms.py` |

## Platform model (types, fields, data files)

### `SocPlatform` fields

| Field | Type | Default | Notes | Source |
| --- | --- | --- | --- | --- |
| `name` | `str` | required | Unique platform name | `defines.py:142` |
| `min_alignment` | `int` | required | Validated as a positive power of two at config load | `defines.py:143`, validator follows |
| `cpu` | `str` | `"cortex-m4"` | CPU architecture string | `defines.py:144` |
| `speeds` | `list[int]` | `[]` | Clock speeds in MHz | `defines.py:145` |
| `memories` | `dict[MemoryType, int]` | `{}` | Sizes in bytes | `defines.py:146` |
| `capabilities` | `list[SocCapability]` | `[]` | Capability flags | `defines.py:147` |
| `preferred_memory_order` | `list[MemoryType]` | `[]` | Planner placement preference | `defines.py:148-150` |

| Derived property | Source |
| --- | --- |
| `supports_fp16` | `defines.py:172` |
| `supports_npu` | `defines.py:212` |

### Other types

| Type | Values | Source |
| --- | --- | --- |
| `ModuleType` | `neuralspot`, `zephyr`, `cmake`, `nsx`, `cmsis_pack` | `helia_aot/defines.py` |
| Per-module-type memory budgets or link families | None exist | n/a |

### Data files

| File | Content | Source |
| --- | --- | --- |
| None for platforms | All entries are Python literals | `platforms.py` |
| `docs/src/data/generated/targets.json` | Generated target list | `repo_tools/docs_export.py` |
| `docs/src/data/generated/config-schema.json` | Generated config schema | `repo_tools/docs_export.py` |
| `docs/src/data/generated/cli.json` | Generated CLI reference | `repo_tools/docs_export.py` |
| `docs/src/data/generated/residency-example.json` | Generated residency example | `repo_tools/docs_export.py` |

## Registered entries (table)

Values are the repo's literals as read at `e537d293`. They are heliaAOT's planner inputs, not verified silicon figures. Sizes: KB = 1024 bytes as written in the literals (for example `4096 * 1024`).

| Name | Lines | CPU | Speeds (MHz) | MRAM | SRAM | DTCM | ITCM | PSRAM | Capabilities | Align |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `apollo3_evb` | 254-268 | M4 | 48, 96 | 1 MB | 320 KB | 64 KB | - | - | MCU, DSP | 4 |
| `apollo3_blue_evb` | 270-284 | M4 | 48, 96 | 1 MB | 320 KB | 64 KB | - | - | MCU, DSP, BLE | 4 |
| `apollo3_blue_thin_evb` | 286-300 | M4 | 48, 96 | 1 MB | 320 KB | 64 KB | - | - | MCU, DSP, BLE | 4 |
| `apollo3_blue_plus_evb` | 302-316 | M4 | 48, 96 | 2 MB | 704 KB | 64 KB | - | - | MCU, DSP, BLE | 4 |
| `apollo3p_evb` | 319-333 | M4 | 48, 96 | 2 MB | 704 KB | 64 KB | - | - | MCU, DSP, BLE | 4 |
| `apollo4p_evb` | 340-350 | M4 | 96, 192 | 2 MB | 1 MB | 384 KB | - | - | MCU, DSP, USB | 4 |
| `apollo4p_blue_kbr_evb` | 352-362 | M4 | 96, 192 | 2 MB | 1 MB | 384 KB | - | - | MCU, DSP, USB, BLE | 4 |
| `apollo4p_blue_kxr_evb` | 364-374 | M4 | 96, 192 | 2 MB | 1 MB | 384 KB | - | - | MCU, DSP, USB, BLE | 4 |
| `apollo4l_evb` | 376-386 | M4 | 96, 192 | 2 MB | 1 MB | 384 KB | - | - | MCU, DSP | 4 |
| `apollo4l_blue_evb` | 388-398 | M4 | 96, 192 | 2 MB | 1 MB | 384 KB | - | - | MCU, DSP, BLE | 4 |
| `apollo330mp_evb` | 404-425 | M55 | 96, 192, 250 | 2 MB | 1.75 MB | 256 KB | - | - | MCU, DSP, MVE, FP16, BLE, USB | 16 |
| `apollo510_evb` | 437-460 | M55 | 96, 250 | 4 MB | 3 MB | 512 KB | 256 KB | 32168 KB (sic) | MCU, USB, PSRAM, DSP, MVE, FP16 | 16 |
| `apollo510l_evb` | 463-483 | M55 | 96, 192, 250 | 2 MB | 1.75 MB | 256 KB | - | - | MCU, DSP, MVE, FP16, USB | 16 |
| `apollo510b_evb` | 485-507 | M55 | 96, 250 | 4 MB | 3 MB | 512 KB | 256 KB | - | MCU, DSP, MVE, FP16, BLE, USB | 16 |
| `atomiq110` | 529-544 | M55 | 100, 250, 500 | 4 MB | 3 MB | 496 KB | 256 KB | - | MCU, DSP, MVE, FP16, NPU | 16 |

Notes on specific literals:

| Entry | Note | Source |
| --- | --- | --- |
| `apollo510_evb` PSRAM | Literal is `32168 * 1024`, which is 32168 KB, not 32 MB (32768 KB). Kept as written | `platforms.py:447` |
| `apollo510_evb` | Only entry that lists `PSRAM` in `preferred_memory_order` and as a capability | `platforms.py:449`, `platforms.py:453` |
| Apollo3 series | Code comment: SRAM is main SRAM only and excludes DTCM; DTCM is modelled separately | `platforms.py:247-252` |
| `atomiq110` | Code comment: DTCM 496 KB because the part's `MCU_TCM` region is 507904 bytes; HBLRAM has no heliaAOT memory type and is left out; no DRAM pool; clock points follow the Atomiq110 platform guide | `platforms.py:510-527` |

## Consumers / name resolution

### Field consumers

| Field | Consumers (paths under `helia_aot/` unless noted) |
| --- | --- |
| `.name` | `cli/main.py` (see Citation checks), `aot/operators/operator.py` (cited as :113; actual use found at :650), template `aot/templates/platform.h.j2:96-117` (string-prefix dispatch on `apollo510`, `apollo330`, `apollo3`, `apollo4`) |
| `.cpu` | `cli/main.py`, `operator.py` (cited as :113; actual use found at :650) |
| `.speeds` | `cli/main.py` |
| `.memories` | `cli/main.py`, `memory/planner.py`, `memory/hill_climb_planner.py`, `operators/batch_matmul.py`, `repo_tools/docs_export.py` |
| `.capabilities` | `cli/main.py`; operators `batch_matmul`, `svdf`, `average_pool_2d`, `conv_2d/kernels.py`, `depthwise_conv_2d/kernels.py`, `transpose_conv/defines.py`, `ethosu_operator.py`, `dequantize.py`, `module_requirements.py` |
| `.preferred_memory_order` | `cli/main.py`, `memory/planner.py` |
| `.min_alignment` | `cli/main.py`, `memory/planner.py`, `memory/hill_climb_planner.py`, `cli/defines.py` |
| `supports_fp16` | `operator.py`, `dequantize.py`, `module_requirements.py`, `module_handler.py`, `repo_tools/docs_export.py` |
| `supports_npu` | `ethosu_operator.py`, `repo_tools/docs_export.py` |
| `TARGET_CPU` (derived from platform) | `tests/e2e/templates/CMakeLists.txt.j2:167-195` branches on it |

### Name resolution

| Case | Behaviour | Source |
| --- | --- | --- |
| Registered name | Returned from the registry; any other `platform_cfg` fields are ignored and a warning lists them | `platforms.py:144-241` |
| Unregistered name | A run-local `SocPlatform` is built from `PlatformArgs` fields | `platforms.py:144-241` |
| Default name | `PlatformArgs.name` defaults to `apollo510_evb` | `cli/defines.py` (`PlatformArgs`) |
| Aliases | None at this revision; family-aware aliases are proposed in issue #278 | GitHub |

## Facts it carries that the others do not

| Fact | Where |
| --- | --- |
| Per-entry `min_alignment` (4 on M4 entries, 16 on M55 entries), enforced power of two | `defines.py:143` plus validator; `platforms.py` |
| `preferred_memory_order` per entry (planner placement policy) | `platforms.py` |
| Capability flags `BLE`, `USB`, `PSRAM`, `FP16`, `NPU` per board-style entry | `platforms.py` |
| Board-variant names not present elsewhere: `apollo3_evb`, `apollo3_blue_evb`, `apollo3_blue_thin_evb`, `apollo3_blue_plus_evb`, `apollo330mp_evb` (lower-case `mp`), `apollo510l_evb` | `platforms.py` |
| No performance, power, or energy data per platform anywhere in the repo | n/a |

## Tooling to mirror

| Area | Setting | Source |
| --- | --- | --- |
| Python | `requires-python >=3.11` | `pyproject.toml` |
| Lint | ruff line-length 120, select `E4, E7, E9, F, I` | `pyproject.toml` |
| Types | ty, environment `python = .venv`, `python-version = 3.11` | `pyproject.toml` |
| Tests | pytest `testpaths = tests`, `addopts = -ra --maxfail=1 -q` | `pyproject.toml` |
| pre-commit | pre-commit-hooks v6.0.0; gitleaks v8.30.1; ruff v0.11.12; local ty v0.0.78 (blocking); local `todo-markers` (rejects untagged deferred-work markers) | `.pre-commit-config.yaml` |
| Workflows | `ci.yml`, `build-wheel.yml`, `build-binaries.yml`, `release.yml` (release-please), `docs.yml`, `docs-site.yml`, `release-model-e2e.yml`, `runner-probe.yml` | `.github/workflows/` |
| Release | `.release-please-manifest.json` present | repo root |
| Ownership | No CODEOWNERS | repo root |
| Design records | RFCs in `mkdocs/rfcs/`: `0002-arena-model-hardening.md`, `0003-operator-capabilities-interning.md` (confirmed present on 2026-10-04) | `mkdocs/rfcs/` |

## Open questions

### GitHub state (from the prior read; not re-queried except where noted)

| Item | State | Note |
| --- | --- | --- |
| #278 "Platform model redesign: Soc/Board split, typed NPU spec, family-aware name aliases" | OPEN, `priority:P2` (also `enhancement`, `refactor`), assignee `evanchen11` (Evan Chen) | State, title, assignee, labels re-confirmed with `gh` on 2026-10-04. Project placement (heliaAOT #14 In progress; AITG Roadmap; AITG Handbook) and parent `aitg-handbook#3` are from the prior read |
| #544 named `memory.reserve` | OPEN | Related |
| #539 Apollo510 memories overstate DTCM/MRAM | CLOSED | May be fixed upstream after `e537d293`; the table above reflects the stale checkout |
| #331 `resolve_platform` registry leak | CLOSED | |
| #321 Atomiq110 memory provenance | CLOSED | |
| #265 NPU capability gate | CLOSED | |
| #346 FP16 listing on M55 | CLOSED | |
| #320 Atomiq110 rename | CLOSED | |
| #318 ITCM placement routing | CLOSED | |

### Questions

| # | Question |
| --- | --- |
| 1 | Which of the 45 upstream commits touch `helia_aot/platforms/`? The entry table may already differ on `origin/main` (for example after #539). |
| 2 | Is the `apollo510_evb` PSRAM literal `32168 * 1024` intended? helia-profiler (origin/main `b195e29f`) carries `psram_kb=65536` for SoC `apollo510`; the two sources disagree. |
| 3 | MRAM and SRAM literals differ from helia-profiler for the same parts (heliaAOT 2 MB vs profiler `mram_kb=2000` on Apollo3P/4P/4L; heliaAOT 704 KB vs profiler `sram_kb=700` on Apollo3P). Which source is authoritative? |
| 4 | How will #278's Soc/Board split map the six board variants that exist only here (see Facts) onto the catalog? |
| 5 | `platform.h.j2` dispatches on name prefixes; the catalog needs a family field that keeps this working for `atomiq110` (no matching prefix). |

### Citation checks (2026-10-04, against `e537d293`)

| Citation given | Result |
| --- | --- |
| `platforms/defines.py:129-170` for `SocPlatform` fields | Partial match. Class starts at 129; fields at 142-150; 151-170 is the `min_alignment` validator. Derived properties are outside the range: `supports_fp16` at 172, `supports_npu` at 212. |
| `platforms/platforms.py:254-544` for the 15 literals | Match. `apollo3_evb` opens at 254; `atomiq110` closes at 544. |
| `platforms/platforms.py:144-241` for `resolve_platform` | Match. `def resolve_platform` at 144; body ends at 241. |
| `cli/defines.py:248-285` for `PlatformArgs` | Mismatch. 248-264 is the end of `MemoryArgs`. `PlatformArgs` is at 265-286 (`min_alignment` field on 286). |
| `cli/main.py:71-78` per-field consumers | Mismatch. Platform fields are used at line 75 (list table: `name`, `cpu`, `capabilities`) and 94-103 (detail view: `cpu` 94, `speeds` 95, `capabilities` 96, `memories` 99-100, `preferred_memory_order` 102, `min_alignment` 103). |
| `aot/templates/platform.h.j2:96-117` prefix dispatch | Match. Prefix tests at 96, 98, 111, 113. |
| `platforms.py` PSRAM literal `32168 KB` | Match at line 447. |
| `aot/operators/operator.py:113` for `.name` and `.cpu` | Mismatch. Line 113 is a class docstring. `self.platform.name` and `self.platform.cpu` are used at line 650. |
| Local `main` 45 commits behind `origin/main` | Match. |
| Issue #278 state, title, assignee, `priority:P2` | Match (via `gh`). |
