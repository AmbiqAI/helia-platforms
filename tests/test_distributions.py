"""File-list test for the built wheel and sdist (ADR 0005, point 1).

A published PyPI file cannot be replaced, so a stray file in either
distribution must fail here first. The catalogue half of the test waits for
the loader and export (#69).
"""

import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "helia_platforms"

# The five sdist paths listed in ADR 0005, Context (plus the sdist's own directory prefix).
SDIST_TOP_LEVEL = {"PKG-INFO", "pyproject.toml", "README.md", "LICENSE.md", "src"}
# Newer uv versions keep the unnormalised pyproject.toml beside the rewritten one.
SDIST_TOOL_FILES = {"pyproject.toml.orig"}
WHEEL_DIST_INFO = {
    "licenses/LICENSE.md",
    "WHEEL",
    "entry_points.txt",
    "METADATA",
    "RECORD",
}


def _tracked_package_files() -> set[str]:
    """Return the git-tracked files of the package, relative to ``src/``."""
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout to know which package files are tracked")
    out = subprocess.run(
        ["git", "ls-files", "-z", f"src/{PACKAGE}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout
    files = {Path(p).relative_to("src").as_posix() for p in out.split("\0") if p}
    assert files, "git ls-files found no package files"
    return files


@pytest.fixture(scope="module")
def dist_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    out = tmp_path_factory.mktemp("dist")
    # Output is left uncaptured so pytest shows uv's diagnostics if the build fails.
    subprocess.run([uv, "build", "--out-dir", str(out)], cwd=ROOT, check=True)
    return out


def _version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def _only(dist_dir: Path, pattern: str) -> Path:
    (path,) = dist_dir.glob(pattern)
    return path


def test_wheel_file_list(dist_dir: Path) -> None:
    with zipfile.ZipFile(_only(dist_dir, "*.whl")) as zf:
        names = {n for n in zf.namelist() if not n.endswith("/")}
    package_files = {n for n in names if n.startswith(f"{PACKAGE}/")}
    dist_info = names - package_files

    # `helia_platforms/data/**` (#60) is tracked, so it is expected like any other package file.
    assert package_files == _tracked_package_files()
    assert {n.split("/", 1)[0] for n in dist_info} == {f"{PACKAGE}-{_version()}.dist-info"}
    assert {n.split("/", 1)[1] for n in dist_info} == WHEEL_DIST_INFO


def test_sdist_file_list(dist_dir: Path) -> None:
    with tarfile.open(_only(dist_dir, "*.tar.gz")) as tf:
        members = [m.name for m in tf.getmembers() if not m.isdir()]
    prefixes = {n.split("/", 1)[0] for n in members}
    assert len(prefixes) == 1
    (prefix,) = prefixes
    names = {n.removeprefix(f"{prefix}/") for n in members}
    assert {n.split("/", 1)[0] for n in names} - SDIST_TOOL_FILES == SDIST_TOP_LEVEL
    assert {n for n in names if n.startswith("src/")} == {
        f"src/{p}" for p in _tracked_package_files()
    }
