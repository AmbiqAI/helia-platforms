from typer.testing import CliRunner

import helia_platforms
from helia_platforms.cli import app

runner = CliRunner()


def test_version_is_string() -> None:
    assert isinstance(helia_platforms.__version__, str)


def test_no_args_prints_version() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert helia_platforms.__version__ in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert helia_platforms.__version__ in result.output
