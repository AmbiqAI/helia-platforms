# helia-platforms

`helia-platforms` is the shared catalog of Ambiq SoC and board facts (cores,
memories, clocks, NPU, debug-probe identifiers) consumed by heliaAOT,
helia-profiler and helia-estimator. Linker windows are not catalog content:
the design ([RFC 0002](docs/rfcs/0002-model-and-api.md)) places them in an
optional generated dataset of link environments that ships separately.

- Import name: `helia_platforms`
- CLI entry point: `helia-platforms`

## Status

Planning. This repository ships the toolchain and an importable stub only. It
contains no catalog data or catalog code yet.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync --group dev && uv run pre-commit install && uv run pytest
```

Check the CLI:

```sh
uv run helia-platforms --version
```

## Where things live

- `docs/rfcs/`: design RFCs
- `docs/adr/`: architecture decision records
- `docs/research/`: source inventories
- `HANDOFF.md`: current state of in-flight work

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report security issues as described in
[SECURITY.md](SECURITY.md).
