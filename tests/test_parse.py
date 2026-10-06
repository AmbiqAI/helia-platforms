import pytest
import yaml

from helia_platforms import _parse
from helia_platforms.errors import FormatError


def load(text: str):
    return _parse.parse_yaml(text, "test.yaml")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("v: no", "no"),
        ("v: yes", "yes"),
        ("v: off", "off"),
        ("v: 1:30", "1:30"),
        ("v: 2026-10-05", "2026-10-05"),
        ("v: 1_000", "1_000"),
        ("v: 010", 10),
        ("v: 0x10", 16),
        ("v: 0o10", 8),
        ("v: -12", -12),
        ("v: 1.5", 1.5),
        ("v: 1e3", 1000.0),
        ("v: true", True),
        ("v: False", False),
        ("v: ~", None),
        ("v: null", None),
        ("v: 64K", "64K"),
    ],
)
def test_plain_scalars_follow_the_yaml_1_2_core_schema(text, expected):
    value = load(text)["v"]
    assert value == expected
    assert type(value) is type(expected)


@pytest.mark.parametrize(
    "text",
    [
        "v: !!int abc",
        "v: !!int 0x",
        "v: !!int ''",
        "v: !!int 1_000",
        "v: !!int ' 7 '",
        "v: !!bool abc",
        "v: !!float abc",
        "v: !!timestamp 2026-10-05",
        "v: !!timestamp abc",
        "v: !!binary aGk=",
        "v: !!set {a, b}",
        "v: !!omap [{a: 1}]",
        "v: !!pairs [{a: 1}]",
        "v: &x [1, *x]",
        pytest.param("v: " + "[" * 3000 + "]" * 3000, id="deep nesting"),
    ],
)
def test_unreadable_tagged_or_nested_values_are_format_errors(text):
    with pytest.raises(FormatError):
        load(text)


def test_an_explicit_int_tag_reads_a_core_schema_integer():
    assert load("v: !!int 0x10") == {"v": 16}


def test_duplicate_keys_are_rejected():
    with pytest.raises(FormatError, match="duplicate key 'a'"):
        load("a: 1\na: 2\n")


def test_nested_duplicate_keys_are_rejected():
    with pytest.raises(FormatError, match="duplicate key 'dtcm'"):
        load("memories:\n  dtcm: {size: 1}\n  dtcm: {size: 2}\n")


def test_non_scalar_keys_are_rejected():
    with pytest.raises(FormatError, match="must be a scalar"):
        load("? [a, b]\n: 1\n")


def test_merge_keys_are_not_special():
    assert load("a: &x {b: 1}\nc:\n  <<: *x\n") == {"a": {"b": 1}, "c": {"<<": {"b": 1}}}


def test_json_duplicate_keys_are_rejected():
    with pytest.raises(FormatError, match="duplicate key 'a'"):
        _parse.parse_json('{"a": 1, "a": 2}', "test.json")


def test_falls_back_to_safe_loader_without_libyaml(monkeypatch):
    monkeypatch.delattr(yaml, "CSafeLoader", raising=False)
    loader = _parse._loader_class()
    assert issubclass(loader, yaml.SafeLoader)
    assert yaml.load("v: 010\nw: no\n", Loader=loader) == {"v": 10, "w": "no"}


def test_parse_file_reads_json_by_suffix(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"schema_version": 1}')
    assert _parse.parse_file(path) == {"schema_version": 1}


def test_parse_file_reports_unreadable_files(tmp_path):
    path = tmp_path / "latin1.yaml"
    path.write_bytes(b"v: caf\xe9\n")
    with pytest.raises(FormatError, match=r"latin1\.yaml: cannot be read"):
        _parse.parse_file(path)
    with pytest.raises(FormatError, match="cannot be read"):
        _parse.parse_file(tmp_path)
