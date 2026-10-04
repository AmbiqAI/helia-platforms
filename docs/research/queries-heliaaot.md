# heliaAOT: question surface

- **Source:** helia-aot checkout (GitHub `AmbiqAI/helia-aot`)
- **Revision:** `origin/main` `ea5cd6c0`
- **Read on:** 2026-10-04
- **Method:** query-surface read by a gatherer against `origin/main` (`ea5cd6c0`). Spot checks at the end were run with `git show origin/main:<path> | sed -n 'N,Mp'`.

This note records what heliaAOT code asks of a platform today. It complements [heliaaot.md](heliaaot.md), which inventories the model itself from an older local checkout. The "fact or tool policy" column is this note's classification, not a label the source carries.

## Public surface

All under `helia_aot/platforms/`.

| Symbol | Kind | What it exposes |
| --- | --- | --- |
| `SocCapability` | enum | `MCU`, `DSP`, `USB`, `BLE`, `MVE`, `PSRAM`, `FP16`, `NPU` |
| `MemoryType` | enum | `MRAM`, `SRAM`, `DTCM`, `ITCM`, `DRAM`, `PSRAM`; properties `readable`, `writeable`, `executable`, `is_init_ram`; methods `init_const_qualifier()`, `to_qualifiers()` |
| `SocPlatform` | frozen dataclass | `name`, `cpu`, `min_alignment`, `speeds`, `memories` (`{MemoryType: bytes}`), `capabilities`, `preferred_memory_order` |
| `SocPlatform.supports_fp16` | property | True when `FP16` is declared, or when `cpu == cortex-m55` as a fallback; rejects `FP16` on non-FP16 cpus |
| `SocPlatform.supports_npu` | property | True when `NPU` is in `capabilities` |
| `register_platform` | function | Process-global registration; `KeyError` on a case-insensitive duplicate |
| `get_platform` | function | Case-insensitive lookup; returns the canonical name |
| `resolve_platform` | function | Registered name: only `memories` merges, run-locally; other overrides are ignored with a warning. Unregistered name: all seven fields required, else `ConfigValueError` listing the YAML and CLI spellings |
| `list_platform_names`, `list_platforms` | functions | Enumeration |
| `_canonical_platform_name` | private function | `casefold` |
| `PLATFORM_REGISTRY`, `_BUILTIN_PLATFORM_NAMES` | module state | Registry and built-in name set |

### Registered names on `origin/main` (15)

`apollo3_blue_evb`, `apollo3p_evb`, `apollo3_evb`, `apollo3_blue_plus_evb`, `apollo3_blue_thin_evb`, `apollo4p_evb`, `apollo4l_evb`, `apollo4p_blue_kbr_evb`, `apollo4p_blue_kxr_evb`, `apollo4l_blue_evb`, `apollo330mp_evb`, `apollo510_evb`, `apollo510b_evb`, `apollo510l_evb`, `atomiq110`.

### State of related work

| Item | State on `origin/main` |
| --- | --- |
| Issue #331 (custom platforms leaked across runs) | Fixed by PR #334 (2026-08-31): custom platforms are run-local |
| Issue #278 items (Soc/Board split, `NpuSpec`, aliases, `platform.soc`) | Not implemented; no branch for it |
| Memory sizes in `platforms.py` | Carry linker-window figures with linker-script comments (example: `245760` with comment `MCU_TCM`) |
| `targets.json` example for `apollo330mp_evb` | MRAM 2031616, SRAM 1835008, DTCM 245760 bytes; speeds 96/192/250; capabilities MCU, DSP, MVE, FP16, BLE, USB; `min_alignment` 16; `supports_fp16` true (source: `targets.json` export as reported by the gatherer) |
| Docs export schema | `export_schema_version` 1 at `repo_tools/docs_export.py:81` (see Citation checks) |
| Runtime dependencies relevant to helia-platforms | `pyproject.toml:50-51` declares `typer>=0.16.0` and `pyyaml>=6.0.0` (read with `git show ea5cd6c0:pyproject.toml`) |

## Question table

| Question in plain words | API used today | Caller file:line | What it does with the answer | Fact or tool policy |
| --- | --- | --- | --- | --- |
| Does the target support MVE? | `SocCapability.MVE in platform.capabilities` | `aot/operators/conv_2d/kernels.py:180,197,206,238,264,340,349,442,532` | Kernel selection | Fact (ISA) |
| Does the target support MVE or DSP? | Capability membership | `aot/operators/depthwise_conv_2d/kernels.py:112,153,156,345,404,408` | Kernel selection | Fact (ISA) |
| Which capabilities does the target have? | `platform.capabilities` | `aot/operators/average_pool_2d.py:85,96,98` | Kernel gate | Fact (ISA) |
| Does the target support MVE? | Capability membership | `aot/operators/batch_matmul.py:171,188`; `fully_connected.py:499`; `svdf.py:109` | Kernel selection and size computation | Fact (ISA) |
| Does the platform satisfy a kernel's requirements? | `set(kernel.capabilities) & set(platform.capabilities)` | `aot/operators/kernel_record.py:72-73` | Filters applicable kernels | Fact (ISA); intersection rule is tool policy |
| Is fp16 native? | `platform.supports_fp16` | `aot/operators/dequantize.py:131,157` | Chooses the cast path | Fact, with a cpu-name fallback |
| May fp16 be used? | `supports_fp16` | `aot/operators/operator.py:744` | Gate | Fact, with a cpu-name fallback |
| Should fp16 code be generated? | `supports_fp16` | `aot/handlers/module_handler.py:123` | Codegen | Fact, with a cpu-name fallback |
| Is fp16 supported, for the record? | `supports_fp16` | `aot/module_requirements.py:35,51,94`; `aot/plan.py:287` | Schema and `plan.json` | Fact |
| Does the platform declare an NPU? | `supports_npu`, gated by `require_platform_npu` | `aot/operators/ethosu_operator.py:98` | `ConfigValueError` if absent | Presence is a fact; the gate is tool policy |
| What tensor alignment does the NPU need? | None (hard-coded 16 bytes) | `aot/operators/ethosu_operator.py:152` as reported (see Citation checks) | Tensor alignment | Fact not modelled |
| Which memories exist, how large, in what order? | `platform.memories`, `preferred_memory_order` | `aot/plan.py:162-165` | Planner budgets | Sizes: fact (linker windows); order: tool policy |
| Is ITCM available? | `MemoryType.ITCM in platform.memories` | `aot/handlers/operator_handler.py:212`; `aot/operators/operator.py:369` | `code_placement` gate | Fact |
| What is the alignment floor, which pools, in what order? | `min_alignment`, `memories`, `preferred_memory_order` | `memory/planner.py:209,240,248,278-292` | Planner | Alignment and order: tool policy; sizes: fact |
| Which cpu string should be emitted? | `platform.cpu.lower()` | `aot/handlers/module_handler.py:292` | Codegen flags | Fact |
| What name and cpu go in messages? | `name`, `cpu` | `aot/operators/ethosu_operator.py:101`; `operator.py:747` | Error text | Identity |
| What are all the fields? | All fields | `cli/main.py:75,93-104` | `target-info` display | Mixed |
| What cpu and capabilities go in the plan? | `cpu`, `capabilities` | `aot/plan.py:285-286` | `plan.json` export | Fact |

### Module types and templates

| Item | Location | Platform question asked |
| --- | --- | --- |
| `ModuleType` | `helia_aot/defines.py` | `neuralspot`, `zephyr`, `cmake`, `nsx`, `cmsis_pack` |
| Logging and `PUT_IN_*` macros per module type | `helia_aot/aot/templates/platform.h.j2` | Which section macro to emit |
| Zephyr DTCM section | `platform.h.j2` lines about 96-113 | `platform_name.startswith('apollo510')` or `'apollo330'` gives `__dtcm_bss_section`; `startswith('apollo3')` or `'apollo4'` gives `__itcm_section` |
| NSX compatibility list | `helia_aot/aot/templates/nsx/nsx-module.yaml.j2` | Static `compatibility.socs`: `apollo3p`, `apollo4p`, `apollo4l`, `apollo510`, `apollo510l`, `apollo510b`, `apollo5b`, `apollo330P`, `atomiq110`. `apollo510l` is lowercase and does not match neuralspotx's `apollo510L`. Toolchains `arm-none-eabi-gcc`, `armclang` (see Citation checks). NPU block on the `has_ethos_u` flag |

## Overlay and custom-definition surface

| Surface | Detail |
| --- | --- |
| `PlatformArgs` | `helia_aot/cli/defines.py:301`. Fields: `name` (default `apollo510_evb`), `cpu`, `speeds`, `memories`, `capabilities`, `preferred_memory_order`, `min_alignment` |
| Spellings | YAML `platform.*` and CLI `--platform.*` |
| Registered-name override | Only `memories` merges, run-locally; other fields ignored with a warning |
| Full custom definition | All seven fields required for an unregistered name |
| Docs | `docs/src/content/docs/guide/targets.mdx` teaches registered-name override and full custom definition |
| SoC selector | No `platform.soc` |

## Name resolution

| Aspect | Behaviour |
| --- | --- |
| Matching | `casefold` only |
| Aliases | None |
| `list-targets` output | Canonical lowercase names |
| `plan.json` identity | Prints `cpu`, not `name` |

## Workarounds for missing model facts

| Workaround | Where | Missing fact it stands in for |
| --- | --- | --- |
| Name-prefix dispatch for Zephyr section macros | `aot/templates/platform.h.j2` | SoC family and memory section names |
| 50+ e2e YAML files hard-code targets `apollo510_evb` or `apollo4p` | e2e tests | No family or default-target notion |
| Memory sizes hand-extracted from linker scripts | `platforms/platforms.py` | Linker-window facts with provenance |
| Hard-coded 16-byte tensor alignment | `aot/operators/ethosu_operator.py` (cited as line 152; see Citation checks) | NPU alignment requirement |
| Zephyr e2e uses Zephyr board id `apollo510_evb`, equal to the nsx board id | `tests/e2e_zephyr` | Zephyr board id mapping |
| Zephyr e2e pins Zephyr v4.3.0 (`3568e1b6`) and zephyr-sdk 0.17.4 | `tests/e2e_zephyr/tools/zephyr_deps.py` | Not a missing fact; recorded because devicetree sizes depend on this pin |

## Open points

| Point | Status |
| --- | --- |
| `apollo510l` vs `apollo510L` in `nsx-module.yaml.j2` | Mismatch with neuralspotx exact-case matching; impact on module discovery not read in this pass |
| `nsx-module.yaml.j2` lists `apollo5b` and `apollo330P` but heliaAOT has no `apollo5b_*` registered name | How the static list was derived not read in this pass |
| #278 design (Soc/Board, `NpuSpec`, aliases) | Not implemented; no branch |
| Per-kernel line lists in the question table | Only the lines in Citation checks were re-read |

## Citation checks

Run on 2026-10-04 against `origin/main` `ea5cd6c0`.

| Citation given | Result | Detail |
| --- | --- | --- |
| `aot/operators/kernel_record.py:72-73` | Match | 72 `if self.capabilities:`; 73 `if not (set(self.capabilities) & set(op.platform.capabilities)):` |
| `aot/operators/ethosu_operator.py:98` | Match | `if self.attributes.require_platform_npu and not self.platform.supports_npu:` |
| `aot/operators/ethosu_operator.py:101` | Match | Error f-string uses `self.platform.name` and `self.platform.cpu` |
| `aot/operators/ethosu_operator.py:152` (16-byte alignment) | Mismatch | 152 is `output_params: list[dict[str, Any]] = [`. `alignment_hint = 16` appears at 94, 129, 132, 135; the docstring states the 16-byte requirement at 49-52 |
| `aot/plan.py:162-165` | Match | 162 builds `budgets` from `platform.memories[memory] for memory in platform.preferred_memory_order`; 163-165 the constraints branch |
| `aot/handlers/module_handler.py:292` | Match | `cpu = (platform.cpu if platform is not None else "cortex-m4").lower()` |
| `cli/defines.py:301` | Match | `class PlatformArgs(_ConfigBase):` |
| `repo_tools/docs_export.py:81` | Partial | `EXPORT_SCHEMA_VERSION = 1` is at 80; 81 is `SCHEMA_VERSION_KEY = "export_schema_version"` |
| `aot/templates/platform.h.j2` about 96-113 | Match | Prefix tests at 96, 98, 111, 113 |
| `aot/operators/conv_2d/kernels.py:180,197,206` | Match | Each line tests `SocCapability.MVE` against `op.platform.capabilities` |
| `aot/operators/operator.py:369,744,747` | Match | 369 ITCM membership; 744 `supports_fp16` gate; 747 name and cpu in message |
| `nsx/nsx-module.yaml.j2` `compatibility.socs` | Match | List at 45-53; `apollo510l` at 49 |
| `nsx/nsx-module.yaml.j2` toolchains | Partial | 55-57 list `arm-none-eabi-gcc`, `armclang`, and also `atfe` |
| Zephyr v4.3.0, `3568e1b6`, sdk 0.17.4 | Match | `tests/e2e_zephyr/tools/zephyr_deps.py:193-194,228` |
| Registered-name count (first given as 17, including `apollo330p_evb` and `apollo330l_evb`) | Corrected | `git show ea5cd6c0:helia_aot/platforms/platforms.py` registers 15 platforms (15 `= register_platform(` assignments besides the function definition); neither `apollo330p_evb` nor `apollo330l_evb` is registered. List and count above corrected |
