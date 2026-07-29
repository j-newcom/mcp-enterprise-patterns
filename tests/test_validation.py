"""Tests for mcp_patterns.validation."""

import pytest

from mcp_patterns.validation import (
    optional_str, require, require_enum, require_int, require_str,
)
from mcp_patterns.errors import ValidationError


def test_require():
    assert require({"a": 5}, "a") == 5
    with pytest.raises(ValidationError):
        require({}, "a")
    with pytest.raises(ValidationError):
        require({"a": None}, "a")


def test_require_str():
    assert require_str({"s": "hi"}, "s") == "hi"
    assert require_str({"s": "  hi  "}, "s") == "hi"
    with pytest.raises(ValidationError):
        require_str({"s": 5}, "s")
    with pytest.raises(ValidationError):
        require_str({"s": ""}, "s")
    with pytest.raises(ValidationError):
        require_str({"s": "abcdef"}, "s", max_len=3)


def test_require_int_coercion_and_ranges():
    assert require_int({"n": 5}, "n") == 5
    assert require_int({"n": "7"}, "n") == 7
    with pytest.raises(ValidationError):
        require_int({"n": "x"}, "n")
    with pytest.raises(ValidationError):
        require_int({"n": 0}, "n", minimum=1)
    with pytest.raises(ValidationError):
        require_int({"n": 99}, "n", maximum=10)


@pytest.mark.parametrize("val", [True, False])
def test_require_int_rejects_bool(val):
    # bool is a subclass of int in Python — must be rejected explicitly
    with pytest.raises(ValidationError):
        require_int({"n": val}, "n")


def test_require_enum():
    assert require_enum({"t": "850"}, "t", ["850", "856"]) == "850"
    with pytest.raises(ValidationError):
        require_enum({"t": "999"}, "t", ["850", "856"])


def test_optional_str():
    assert optional_str({}, "s", "def") == "def"
    assert optional_str({"s": None}, "s", "def") == "def"
    assert optional_str({"s": "x"}, "s") == "x"
