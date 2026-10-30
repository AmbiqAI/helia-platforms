# helia-platforms

`helia-platforms` is the shared catalog of Ambiq SoC and board facts (cores,
memories, clocks, NPU, debug-probe identifiers) consumed by heliaAOT,
helia-profiler and helia-estimator. Every value carries a provenance record:
the datasheet page, SDK file or measurement it came from, and who checked it.

- Import name: `helia_platforms`
- CLI entry point: `helia-platforms`

## Status

Alpha. The built-in data covers apollo3, apollo3p, apollo4l, apollo4p,
apollo510, apollo510b, apollo510L, apollo330P and atomiq110, with their parts
and boards; `helia-platforms list` prints what it holds. The file format, the
Python API and the CLI may change between 0.x releases.

Linker windows are not catalog content: they belong to an optional dataset of
link environments that ships separately.

## Install

```sh
pip install helia-platforms
```

or, in a uv project, `uv add helia-platforms`. Python 3.11 or later.

## Use

From the CLI:

```sh
helia-platforms list
helia-platforms show apollo510_evb               # every value with its provenance status
helia-platforms show apollo510_evb --provenance  # and the full record under each row
helia-platforms show my_board --overlay my_board.yaml
```

From Python:

```python
from helia_platforms import resolve

target = resolve("apollo510_evb")
target.soc.id  # "apollo510"
target.jlink_device  # "AP510NFA-CBR"
target.cpu_mhz()  # 96, at the default operating point
target.flash_load_address()  # 0x410000
target.placement_ranges()  # {"itcm": (0x0, 0x40000), ...}: base and size per region
```

A private catalog, such as a board of your own, loads over the built-in one
with `--overlay` on the CLI or `load_overlay` in Python.

## Upgrade notes

- apollo510b_evb's `jlink_device` is `AP510BFA-CBR`, the Apollo510B ordering
  number, which SEGGER lists as its own J-Link device. SEGGER added it in J-Link
  V8.94 (2025-12-10), so update an older J-Link, or pass the SDK's default
  `AP510NFA-CBR` yourself.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync --group dev && uv run pre-commit install && uv run pytest
```

In the repository:

- `docs/rfcs/`: design RFCs (the model and API are RFC 0002)
- `docs/adr/`: architecture decision records
- `docs/research/`: source inventories
- `HANDOFF.md`: current state of in-flight work

See `CONTRIBUTING.md` to contribute, and report security issues as described
in `SECURITY.md`.
