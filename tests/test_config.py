"""Tests for mcp_patterns.config."""

import pytest

from mcp_patterns.config import (
    ConfigError, ServerConfig, get_bool, get_float, get_int, get_str,
)


def test_get_str_required_present():
    assert get_str("A", required=True, env={"A": "hi"}) == "hi"


def test_get_str_optional_default():
    assert get_str("A", "def", env={}) == "def"


def test_get_str_blank_is_missing():
    assert get_str("A", "def", env={"A": "   "}) == "def"


def test_get_str_required_missing_raises():
    with pytest.raises(ConfigError):
        get_str("A", required=True, env={})


def test_get_int_parses_and_defaults():
    assert get_int("N", env={"N": "42"}) == 42
    assert get_int("N", 7, env={}) == 7


def test_get_int_bad_raises():
    with pytest.raises(ConfigError):
        get_int("N", env={"N": "x"})


@pytest.mark.parametrize("val", ["1", "true", "YES", "on", "t"])
def test_get_bool_truthy(val):
    assert get_bool("B", env={"B": val}) is True


@pytest.mark.parametrize("val", ["0", "false", "NO", "off", "f"])
def test_get_bool_falsy(val):
    assert get_bool("B", env={"B": val}) is False


def test_get_bool_bad_raises():
    with pytest.raises(ConfigError):
        get_bool("B", env={"B": "maybe"})


def test_get_float():
    assert abs(get_float("F", env={"F": "3.14"}) - 3.14) < 1e-9


def test_server_config_from_env():
    cfg = ServerConfig.from_env(env={
        "MCP_SERVER_NAME": "demo", "MCP_LOG_LEVEL": "DEBUG",
        "MCP_REQUEST_TIMEOUT_S": "60", "MCP_USE_SYNTHETIC_DATA": "false",
    })
    assert cfg.server_name == "demo"
    assert cfg.log_level == "DEBUG"
    assert cfg.request_timeout_s == 60
    assert cfg.use_synthetic_data is False


def test_server_config_defaults_and_required():
    assert ServerConfig.from_env(env={"MCP_SERVER_NAME": "x"}).request_timeout_s == 30
    with pytest.raises(ConfigError):
        ServerConfig.from_env(env={})
