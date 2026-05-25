import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure fixtures are importable for loader tests
FIXTURES = Path(__file__).parent / "fixtures"


# ── Registry tests ────────────────────────────────────────────────────────────

def _make_registry():
    # Always return a fresh Registry, bypassing the singleton
    from genesis.registry import Registry
    return Registry()


def _dummy_handler(arguments: dict) -> dict:
    return {"status": "success", "data": None, "message": ""}


def _make_entry(name: str = "echo_message", tool_type: str = "generated"):
    from genesis.registry import ToolEntry
    return ToolEntry(
        name=name,
        description="Test tool.",
        schema={"name": name, "description": "Test tool.", "inputSchema": {"type": "object", "properties": {}, "required": []}},
        handler=_dummy_handler,
        file_path=Path("generated_tools") / f"{name}.py",
        created_at="2026-05-21T00:00:00Z",
        tool_type=tool_type,
    )


def test_register_and_get():
    reg = _make_registry()
    entry = _make_entry("my_tool")
    reg.register(entry)
    assert reg.get("my_tool") is entry


def test_unregister():
    reg = _make_registry()
    reg.register(_make_entry("my_tool"))
    assert reg.unregister("my_tool") is True
    assert reg.get("my_tool") is None
    assert reg.unregister("my_tool") is False


def test_names():
    reg = _make_registry()
    reg.register(_make_entry("tool_a"))
    reg.register(_make_entry("tool_b", tool_type="meta"))
    assert reg.names() == {"tool_a", "tool_b"}


def test_list_filter_all():
    reg = _make_registry()
    reg.register(_make_entry("gen_tool", tool_type="generated"))
    reg.register(_make_entry("meta_tool", tool_type="meta"))
    result = reg.list(filter="all")
    assert len(result) == 2
    types = {r["type"] for r in result}
    assert types == {"generated", "meta"}


def test_list_filter_generated():
    reg = _make_registry()
    reg.register(_make_entry("gen_tool", tool_type="generated"))
    reg.register(_make_entry("meta_tool", tool_type="meta"))
    result = reg.list(filter="generated")
    assert all(r["type"] == "generated" for r in result)


def test_list_filter_meta():
    reg = _make_registry()
    reg.register(_make_entry("gen_tool", tool_type="generated"))
    reg.register(_make_entry("meta_tool", tool_type="meta"))
    result = reg.list(filter="meta")
    assert all(r["type"] == "meta" for r in result)


def test_manifest_round_trip(tmp_path):
    from genesis.registry import Registry
    from unittest.mock import patch

    reg = Registry()
    entry = _make_entry("weather_tool")
    entry.file_path = tmp_path / "weather_tool.py"
    reg.register(entry)

    manifest_path = tmp_path / "tools_manifest.json"

    mock_config = MagicMock()
    mock_config.paths.manifest_file = manifest_path

    with patch("genesis.registry.get_config", return_value=mock_config):
        reg.save_manifest()
        assert manifest_path.exists()

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "weather_tool"

        loaded = reg.load_manifest()
        assert loaded[0]["name"] == "weather_tool"


def test_manifest_missing_file(tmp_path):
    from genesis.registry import Registry
    from unittest.mock import patch

    reg = Registry()
    mock_config = MagicMock()
    mock_config.paths.manifest_file = tmp_path / "nonexistent_manifest.json"

    with patch("genesis.registry.get_config", return_value=mock_config):
        result = reg.load_manifest()
        assert result == []


# ── Loader tests ──────────────────────────────────────────────────────────────

def test_loader_valid_tool():
    from genesis.loader import load_tool_file
    schema, handler = load_tool_file(FIXTURES / "valid_tool.py")
    assert schema["name"] == "echo_message"
    assert callable(handler)
    result = handler({"message": "hello"})
    assert result["status"] == "success"


def test_loader_missing_file():
    from genesis.loader import load_tool_file, LoadError
    with pytest.raises(LoadError, match="not found"):
        load_tool_file(Path("nonexistent_tool.py"))


def test_loader_bad_imports_file():
    """bad_imports.py has subprocess — it will load (loader doesn't validate),
    but its imports execute. We just ensure loader doesn't crash on import-level issues
    that aren't syntax errors; validation is the validator's job."""
    from genesis.loader import load_tool_file
    # bad_imports.py imports subprocess which IS available in the test env;
    # loader should succeed — validator would have caught it before writing to disk
    schema, handler = load_tool_file(FIXTURES / "bad_imports.py")
    assert schema["name"] == "bad_imports_tool"


def test_loader_inline_bad_module(tmp_path):
    """Tool file with a runtime error during module load."""
    from genesis.loader import load_tool_file, LoadError
    bad = tmp_path / "crash_tool.py"
    bad.write_text("""
raise RuntimeError("module load error")

TOOL_SCHEMA = {"name": "x", "description": "x", "inputSchema": {"type": "object", "properties": {}, "required": []}}

def handler(arguments: dict) -> dict:
    return {"status": "success", "data": None, "message": ""}
""", encoding="utf-8")
    with pytest.raises(LoadError, match="module load error"):
        load_tool_file(bad)
