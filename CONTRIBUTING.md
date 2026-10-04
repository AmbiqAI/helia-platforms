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
check, and the deferred-work marker check on every commit. Run them across the
whole tree with:

```sh
uv run pre-commit run --all-files
```

## Deferred work

Deferred-work markers must be traceable. Write `TODO(#123): <one line>` with a
real issue number, or `TODO(verify)` for a claim that still needs a source of
record. Untagged markers are rejected by the `todo-markers` hook.

## Checks

Before opening a pull request, make sure these pass:

```sh
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv build
```
