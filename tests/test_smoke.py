import pytest

import helia_platforms
from helia_platforms.cli import main


def test_version_is_string() -> None:
    assert isinstance(helia_platforms.__version__, str)


def test_main_no_args_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert capsys.readouterr().out.strip() == helia_platforms.__version__


def test_main_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == helia_platforms.__version__
