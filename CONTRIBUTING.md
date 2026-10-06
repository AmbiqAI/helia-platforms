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

## Deferred work

Deferred-work markers must be traceable. Write `TODO(#123): <one line>` with a
real issue number, or `TODO(verify)` for a claim that still needs a source of
record. Untagged markers are rejected by the `todo-markers` hook.

## Local paths

The repository is meant to be public, so committed text must not contain
local filesystem paths: home directories (`/Users/<name>`, `/home/<name>`,
and their Windows, WSL `/mnt/<drive>`, Cygwin and Git Bash forms), macOS temporary
directories, and cloud-sync folders such as iCloud Drive or OneDrive. Such a
path resolves on one machine only. Cite other repositories by name and revision instead, for
example `AmbiqAI/helia-aot` at `57a80e7c`. The `local-paths` hook rejects
these paths, including symlink targets; `scripts/check_local_paths.py` holds
the exact forms. A path inside a remote URL (`http`, `https`, `ftp`, `sftp`,
`ssh`, `git` or `s3`, optionally prefixed with `git+`) is fine; under any
other scheme, `file://` and editor URLs included, it is not.

For the rare line where the path is itself the subject, add a
`local-paths: ignore` comment to that line; it silences the whole line.
The hook skips `tests/test_check_local_paths.py` entirely, because that
file is made of local-path examples, so review changes to it by hand.
Known gaps in what the hook catches are tracked in #44.

## Checks

Before opening a pull request, make sure these pass:

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv build
```
