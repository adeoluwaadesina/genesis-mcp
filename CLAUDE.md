# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run the MCP server
python -m genesis.server

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_validator.py -v
```

## Architecture

Genesis MCP is a self-extending MCP server. The key design: it uses the **low-level `mcp.Server` class** (not `FastMCP`) so that `list_tools` and `call_tool` are implemented as dynamic handlers that read from the in-memory registry at call time. This is what makes hot-loading possible without a server restart.

### Data flow for `create_tool`

```
User prompt → meta_tools.create_tool()
  → generator.generate_tool()       # calls Anthropic API with strict system prompt
  → validator.validate()            # 7 checks, fail-fast
  → write generated_tools/<name>.py
  → loader.load_tool_file()         # importlib dynamic load
  → registry.register()            # in-memory + tools_manifest.json
```

### Key files

| File | Responsibility |
|---|---|
| `genesis/server.py` | Entry point. Low-level MCP server with dynamic dispatch. |
| `genesis/meta_tools.py` | The 5 built-in tools. `META_TOOL_SCHEMAS` dict is read by server at boot. |
| `genesis/generator.py` | Anthropic API call → raw code string. Retries once on validation failure. |
| `genesis/validator.py` | AST-based checks: syntax, imports, forbidden calls, structure, schema, uniqueness, side effects. |
| `genesis/registry.py` | In-memory `{name: ToolEntry}` dict. Persists to `tools_manifest.json`. |
| `genesis/loader.py` | `importlib.util` dynamic loading. Raises `LoadError` on all failure modes. |
| `genesis/config.py` | Singleton config loaded from `config.yaml` + `.env`. |

### Tool file contract

Every generated tool must have:
- Module-level `TOOL_SCHEMA` dict (with `name`, `description`, `inputSchema`)
- Module-level `def handler(arguments: dict) -> dict` function
- Return value: `{"status": "success"|"error", "data": ..., "message": "..."}`
- No top-level side effects

### Cross-platform rules

- `pathlib.Path` everywhere — no raw string paths
- `Path.home()` for home directory — no `~` shell expansion
- `encoding="utf-8"` on every `open()` call — Windows defaults to cp1252

### Validator check order (fail-fast)

1. AST syntax parse
2. Import allowlist (see `config.yaml`)
3. Forbidden calls (`eval`, `exec`, `os.system`, `subprocess.*`, etc.)
4. Required structure (`TOOL_SCHEMA` + `handler`)
5. JSON Schema validity of `TOOL_SCHEMA`
6. Name uniqueness against registry
7. No top-level side effects

### Config

`config.yaml` is the single source of truth for model, import allowlist, and paths. Never read env vars or YAML directly in subsystems — always go through `genesis.config.get_config()`.
