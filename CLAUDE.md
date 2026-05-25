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

**Important:** Genesis does **not** call any LLM API server-side. Code generation runs on the **host LLM** (Claude Desktop, Cursor, etc.). Genesis only assembles a prompt and accepts the resulting code back through `register_tool`.

### Data flow for tool creation

```
User asks Claude to make a tool
  → host LLM calls meta_tools.create_tool(description)
      → generator.build_generation_prompt()        # returns a prompt STRING; no API call
  → host LLM reads the prompt, generates Python code locally
  → host LLM calls meta_tools.register_tool(code=...)
      → validator.validate()                        # 8 checks, fail-fast
      → write generated_tools/<name>.py
      → loader.load_tool_file()                     # importlib dynamic load
      → registry.register()                         # in-memory + tools_manifest.json
```

The trust boundary is `register_tool`: any string that passes `validator.validate()` is loaded into the live server process.

### Key files

| File | Responsibility |
|---|---|
| `genesis/server.py` | Entry point. Low-level MCP server with dynamic dispatch. |
| `genesis/meta_tools.py` | The 6 built-in meta-tools (`create_tool`, `register_tool`, `list_tools`, `delete_tool`, `update_tool`, `describe_tool`). `META_TOOL_SCHEMAS` is read by server at boot. |
| `genesis/generator.py` | Builds the natural-language prompt that the host LLM consumes. **No API calls.** |
| `genesis/validator.py` | AST-based checks: syntax, imports, forbidden calls, forbidden names (reflection), structure, schema, uniqueness, side effects. |
| `genesis/registry.py` | In-memory `{name: ToolEntry}` dict. Persists to `tools_manifest.json`. |
| `genesis/loader.py` | `importlib.util` dynamic loading. Raises `LoadError` on all failure modes. |
| `genesis/config.py` | Singleton config loaded from `config.yaml`. Also calls `load_dotenv` for future-compat, but no subsystem reads env vars in v0.1. |

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
3. Forbidden calls (`eval`, `exec`, `compile`, `__import__`, `os.system`, `subprocess.*`, etc.)
4. Forbidden names / reflection primitives (`__builtins__`, attribute access to dunder names like `__import__` / `__globals__`, calls to `getattr` / `globals` / `locals` / `vars`) — added in v0.1 to close F-01 / F-02
5. Required structure (`TOOL_SCHEMA` + `handler`)
6. JSON Schema validity of `TOOL_SCHEMA`
7. Name uniqueness against registry
8. No top-level side effects

### Config

`config.yaml` is the single source of truth for the import allowlist, paths, and server identity. Never read YAML directly in subsystems — always go through `genesis.config.get_config()`.

### Security posture (v0.1)

The validator is the entire trust boundary — there is no sandbox. v0.1 is local, single-user only. See `README.md` "Security Notes" and `SECURITY_FIXES_v0_1.md` for what is and is not blocked, and what is deferred to v0.2.
