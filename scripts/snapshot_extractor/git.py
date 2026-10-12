"""Fetch committed revisions of the upstream repositories into a local cache.

Each checkout is a shallow, blobless fetch of one commit with a sparse work tree
of the paths a source reads. Files are read only from a work tree that ``git
status`` reports clean at that commit, so the input is always a commit's content.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from snapshot_extractor import ExtractError

_SHA = re.compile(r"[0-9a-f]{40}")
_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ADVICE": "0"}


def _url(repository: str) -> str:
    return f"https://github.com/{repository}.git"


def _git(*args: str, cwd: Path | None = None) -> str:
    command = ["git", "-c", "advice.detachedHead=false", "-c", "core.autocrlf=false", *args]
    result = subprocess.run(
        command, cwd=cwd, env=_ENV, capture_output=True, text=True, errors="replace", check=False
    )
    if result.returncode != 0:
        raise ExtractError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def resolve(repository: str, revision: str) -> str:
    """The commit SHA ``revision`` (a tag, a branch or a full SHA) names upstream now."""
    if _SHA.fullmatch(revision):
        return revision
    refs: dict[str, str] = {}
    for line in _git("ls-remote", _url(repository), revision, f"{revision}^{{}}").splitlines():
        sha, ref = line.split("\t")
        refs[ref] = sha
    for ref in (f"refs/tags/{revision}^{{}}", f"refs/tags/{revision}", f"refs/heads/{revision}"):
        if ref in refs:
            return refs[ref]
    raise ExtractError(f"{repository} has no tag or branch {revision!r}")


@dataclass(frozen=True)
class Checkout:
    """A clean sparse work tree of ``repository`` at ``commit``."""

    repository: str
    revision: str
    commit: str
    root: Path

    def read(self, path: str) -> str:
        """The text of a file in the sparse work tree, undecodable bytes replaced."""
        try:
            return (self.root / path).read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            raise ExtractError(f"{self.repository}@{self.revision}: cannot read {path}") from exc

    def blob(self, path: str) -> str | None:
        """The text of any file at the commit, fetched on demand; ``None`` if absent."""
        try:
            data = _git("cat-file", "blob", f"{self.commit}:{path}", cwd=self.root)
        except ExtractError:
            return None
        return data

    def source(self) -> dict[str, str]:
        """The ``metadata.sources`` entry for this checkout (ADR 0006 section 2)."""
        return {"commit": self.commit, "repository": self.repository, "revision": self.revision}


def fetch(cache: Path, repository: str, revision: str, commit: str) -> Checkout:
    """Fetch ``commit`` without checking anything out; ``Checkout.blob`` reads from it."""
    if not _SHA.fullmatch(commit):
        raise ExtractError(f"{commit!r} is not a full commit SHA")
    root = cache / repository.replace("/", "__") / commit
    if not (root / ".git").is_dir():
        root.mkdir(parents=True, exist_ok=True)
        _git("init", "-q", cwd=root)
        _git("remote", "add", "origin", _url(repository), cwd=root)
    try:
        _git("cat-file", "-e", f"{commit}^{{commit}}", cwd=root)
    except ExtractError:
        _git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", commit, cwd=root)
    return Checkout(repository, revision, commit, root)


def checkout(
    cache: Path, repository: str, revision: str, commit: str, paths: Sequence[str]
) -> Checkout:
    """Fetch ``commit`` and check out the gitignore-style ``paths`` patterns."""
    root = fetch(cache, repository, revision, commit).root
    _git("sparse-checkout", "set", "--no-cone", *paths, cwd=root)
    _git("checkout", "-q", "--force", "--detach", commit, cwd=root)
    head = _git("rev-parse", "HEAD", cwd=root).strip()
    if head != commit:
        raise ExtractError(f"{repository}: checked out {head}, expected {commit}")
    if _git("status", "--porcelain", "--untracked-files=all", cwd=root).strip():
        raise ExtractError(f"{repository}: the work tree at {root.name} is not clean")
    return Checkout(repository, revision, commit, root)
