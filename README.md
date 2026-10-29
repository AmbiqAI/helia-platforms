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
catalog digest, the provenance checks, the resolver that consumers query
(RFC 0002), and the CLI's `list`, `show`, `validate` and `export --schema`
commands. The
built-in data grows one Soc family per data issue (#63 to #68);
`helia-platforms list` prints what it holds.

## Upgrade notes

- apollo510b_evb's `jlink_device` is `AP510BFA-CBR`, the Apollo510B ordering
  number, which SEGGER lists as its own J-Link device. SEGGER added it in J-Link
  V8.94 (2025-12-10), so update an older J-Link, or pass the SDK's default
  `AP510NFA-CBR` yourself.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync --group dev && uv run pre-commit install && uv run pytest
```

Look at the catalog from the CLI:

```sh
uv run helia-platforms list
uv run helia-platforms show apollo510_evb               # every value with its provenance status
uv run helia-platforms show apollo510_evb --provenance  # and the full record under each row
uv run helia-platforms show my_board --overlay my_board.yaml
```

## Where things live

- `docs/rfcs/`: design RFCs
- `docs/adr/`: architecture decision records
- `docs/research/`: source inventories
- `HANDOFF.md`: current state of in-flight work

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report security issues as described in
[SECURITY.md](SECURITY.md).
