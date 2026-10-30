# Contributing

## Issue first

Every change starts from an issue. Open one using the task template before
writing code, and make sure every pull request closes an issue (`Closes #N` in
the PR body).

## Branches

Name branches `<issue#>-slug`, for example `12-add-apollo510-memories`.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/). The commit
type drives release notes and version bumps through release-please:

- `feat:` new capability
- `fix:` bug fix
- `docs:`, `test:`, `refactor:`, `chore:`, `ci:` for everything else
- `!` after the type, or a `BREAKING CHANGE:` footer, for breaking changes

## Fact changes

A pull request that changes anything under `src/helia_platforms/data/` (the
built-in catalog, the source register `sources.yaml` or the release
allow-list `unverified.yaml`) or under `snapshots/` uses the fact-change
template, `.github/PULL_REQUEST_TEMPLATE/fact-change.md`, instead of the
default one. The template asks for the provenance record of each changed
fact, as ADR 0003 defines it, for the checks of ADR 0003 section 4, and
for confirmation that the change adds no unreleased hardware, tool policy or
energy data. Select it with `gh pr create --template fact-change.md`, or by
adding `?quick_pull=1&template=fact-change.md` to the GitHub compare URL.

The `fact-changes` CI job enforces ADR 0003 section 4 on every pull request.
It loads the built-in data at the merge base and at the head, both from git
and with the head's loader, and compares them by fact path. A value that
changed must resolve to a record that changed in `status`, `source` (as a
set) or `verified_on`, or, between two `unverified` records, in `notes`. A
`derived` record must change when a `fact:` input it names changes. New fact
paths are exempt. A list of plain values, such as `peripherals`,
`alternate_bases` or `modes`, is compared as a set. A changed list needs a
changed list record, except that an added item may instead carry a record of
its own. The order of `cores`, `npus` and `accelerators` is a fact, because
index 0 is primary, so moving an item both revisions keep needs a changed
record too. Run it locally against `main` with:

```sh
uv run python scripts/check_fact_changes.py --base origin/main
```

It exits 2 when either revision's data does not load with the head's loader,
for example when a pull request adds a rule the merge base's data breaks.
Split such a pull request: first the data change that satisfies the rule,
then the rule.

To review a data change, run `uv run helia-platforms show <id> --provenance`
on the pull request's branch. It prints every resolved value of the target with
the record it resolves to.

`.github/CODEOWNERS` gives each data file and directory, the schema
directory and the snapshot directory its own entry.

## Local setup

```sh
uv sync --group dev
uv run pre-commit install
```

Pre-commit hooks are required. They run ruff, ty, gitleaks, the uv lock
check, the deferred-work marker check, and the local-path check on every
commit. Run them across the whole tree with:

```sh
uv run pre-commit run --all-files
```

CI runs the same command. The gitleaks hook scans only staged changes, so
that command, in CI or locally with nothing staged, gives it nothing to scan.
The check-merge-conflict hook looks for conflict markers only while a merge or
rebase is in progress, which is never the case in CI, so it checks nothing there
either.

## Deferred work

Deferred-work markers must be traceable. Write `TODO(#123): <one line>` with a
real issue number, or `TODO(verify)` for a claim that still needs a source of
record. Untagged markers are rejected by the `todo-markers` hook. The hook
skips `tests/test_check_todo_markers.py`, because that file is made of marker
examples.

## Local paths

The repository is meant to be public, so committed text must not contain
local filesystem paths: home directories (`/Users/<name>`, `/home/<name>`,
and their Windows, WSL `/mnt/<drive>` and `\\wsl$\<distro>`, Cygwin and Git
Bash forms), macOS temporary directories, and cloud-sync folders such as
iCloud Drive or OneDrive. Such a path resolves on one machine only. Cite other
repositories by name and revision instead, for example `AmbiqAI/helia-aot` at
`57a80e7c`. The `local-paths` hook rejects these paths, including symlink
targets, paths glued to a single-dash option such as `-I` or `-isystem`, and
JSON-escaped forms such as `\/Users\/<name>`; `scripts/check_local_paths.py`
holds the exact forms. A path inside a remote URL (`http`, `https`, `ftp`,
`sftp`, `ssh`, `git` or `s3`, optionally prefixed with `git+`) is fine, unless
it is in the query string or the host is `localhost`, `127.0.0.1`, `[::1]` or
`0.0.0.0`. Under any other scheme, `file://` and editor URLs included, the
path is rejected.

For the rare line where the path is itself the subject, add a
`local-paths: ignore` comment to that line; it silences the whole line.
The hook skips `tests/test_check_local_paths.py` entirely, because that
file is made of local-path examples, so review changes to it by hand.

## Source snapshots

`snapshots/` holds the values extracted from nsx-ambiq-sdk, neuralspotx and
Zephyr with hal_ambiq ([ADR 0006](docs/adr/0006-drift-test-snapshots.md)). They
are generated, never edited by hand. The pins are the SDK tag of each Soc and
the Zephyr revision the committed files record; the hal_ambiq commit follows
from Zephyr. neuralspotx is a consumer, so its snapshot stays at
`neuralspotx-v0.9.0` and is never refreshed; the neuralspotx parity test reads
`tests/parity/neuralspotx/boards.json`, frozen from it (#18). The extractor fetches only those commits from GitHub, into
`~/.cache/helia-platforms/upstream` unless `--cache` names another directory.

```sh
# Check that the committed snapshots regenerate byte for byte
uv run --group extract scripts/extract_snapshots.py extract --check
# Refresh: an nsx-ambiq-sdk tag and a Zephyr main commit by full SHA
uv run --group extract scripts/extract_snapshots.py extract \
    --sdk <tag> --zephyr <40-hex SHA>
```

The refresh prints the values that changed, with addresses in hex; put that
summary in the pull request description. `snapshots/exceptions.yaml` lists the
disagreements `check-sources` accepts, each with a reason and an issue.

The link-environment dataset, `src/helia_platforms/data/link_environments.json`,
is generated from the snapshots and the catalog's public Socs and boards, as
`snapshots/link-environments.yaml` directs (#73). Regenerate it in the same pull
request as a snapshot refresh or a data change that moves a region; CI fails
while it is stale.

```sh
uv run python scripts/generate_link_environments.py          # regenerate
uv run python scripts/generate_link_environments.py --check  # what CI runs
```

## Checks

Before opening a pull request, make sure these pass:

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv build
```
