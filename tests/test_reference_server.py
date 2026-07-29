"""Integration test for the reference server (all patterns wired together)."""

import io
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "examples", "reference_server"))

from mcp_patterns.config import ServerConfig
import server as refserver


def _server():
    reg = refserver.build_server(ServerConfig(server_name="ref-test", log_level="ERROR"))
    reg._logger.handlers[0].stream = io.StringIO()
    return reg


def test_get_inventory_ok():
    r = _server().dispatch("get_inventory", {"sku": "SKU-1001"})
    assert r["ok"] is True and r["data"]["on_hand"] == 240


def test_unknown_sku_not_found():
    r = _server().dispatch("get_inventory", {"sku": "NOPE"})
    assert r["ok"] is False and r["error"]["code"] == "not_found"


def test_missing_arg_validation_error():
    r = _server().dispatch("get_inventory", {})
    assert r["ok"] is False and r["error"]["code"] == "validation_error"


def test_check_reorder():
    reg = _server()
    assert reg.dispatch("check_reorder", {"sku": "SKU-1002", "threshold": 20})["data"]["needs_reorder"] is True
    assert reg.dispatch("check_reorder", {"sku": "SKU-1001", "threshold": 20})["data"]["needs_reorder"] is False


def test_supplier_normalized():
    r = _server().dispatch("get_supplier_status", {"supplier": "globex"})
    assert r["ok"] is True and r["data"]["risk_score"] == 68


def test_lists_three_tools():
    assert len(_server().list_tools()) == 3
