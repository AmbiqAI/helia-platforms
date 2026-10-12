# helia-platforms

`helia-platforms` is the shared catalog of Ambiq SoC and board facts (cores,
memories, clocks, NPU, debug-probe identifiers) consumed by heliaAOT,
helia-profiler and helia-estimator. Linker windows are not catalog content:
the design ([RFC 0002](docs/rfcs/0002-model-and-api.md)) places them in an
optional generated dataset of link environments that ships separately.

- Import name: `helia_platforms`
- CLI entry point: `helia-platforms`

## Status

Pre-release; nothing is published yet. The runtime is in place: the file
format and its JSON Schema, the frozen model, `load_overlay` and `builtin()`
with side-loaded private catalogs, the structural and semantic validation, the
catalog digest, and the CLI's `validate` and `export --schema` commands. The
built-in data is still an empty stub (`src/helia_platforms/data/names.yaml`),
and the resolver that consumers will query (RFC 0002) is not written yet.

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
