# Genesis MCP — Build Handover & Architecture Document

> **⚠️ HISTORICAL DOCUMENT — DOES NOT REFLECT SHIPPED ARCHITECTURE**
>
> This handover captures the **original design intent** (pre-scaffold,
> May 2026). During the build the code-generation path pivoted: Genesis no
> longer makes server-side Anthropic API calls. The host LLM (Claude
> Desktop, Cursor) generates code and posts it back via `register_tool`.
> References below to `generator.generate_tool()`, the `anthropic`
> dependency, `ANTHROPIC_API_KEY`, and "Anthropic API costs per tool"
> describe the design that was **not** built.
>
> Authoritative current sources:
> - `CLAUDE.md` — current architecture, data flow, validator order
> - `README.md` "Security Notes" — trust model and validator scope
> - `SECURITY_FIXES_v0_1.md` — security fixes applied vs deferred
>
> This document is preserved for historical context (rationale, decision
> log, original phasing) and is not updated as the codebase evolves.

---

**Audience:** Claude Code (consuming this to plan, scaffold, and build)
**Author of spec:** Adeoluwa Adesina (planning phase, via Claude chat)
**Status:** Pre-scaffold. Greenfield project.
**Language:** Python 3.11+
**License:** Open source (MIT recommended)

---

## 1. Project Summary

**Genesis MCP** is a self-extending Model Context Protocol (MCP) server. It ships with a small set of built-in meta-tools — most importantly `create_tool` — that allow an AI assistant (or human user) to generate, register, and use new MCP tools at runtime, without restarting the server or writing code manually.

The core insight: building MCP tools today requires developer skill (SDK setup, schema design, server registration, hot reload). Genesis collapses that workflow into a single conversation: describe the tool you want, Genesis writes it, validates it, and registers it live.

**One-line pitch:** *An MCP server with one tool — the tool that creates other tools.*

---

## 2. Goals & Non-Goals

### Goals (v1)
- Ship a working MCP server that runs locally via stdio transport.
- Provide a `create_tool` meta-tool that turns a natural-language description into a working, registered MCP tool.
- Persist generated tools to disk so they survive restarts.
- Validate generated code (syntax, banned imports, schema correctness) before registration.
- Hot-load new tools into the running server (no restart required).
- Provide meta-tools for managing generated tools: `list_tools`, `delete_tool`, `update_tool`, `describe_tool`.
- Be runnable by a non-developer following the README.
- Compatible with Claude Desktop and Cursor out of the box.

### Non-Goals (v1)
- Full sandboxing / container isolation. (v1 uses an import allowlist; v2 can add subprocess or Docker isolation.)
- A GUI. (CLI + AI client only.)
- Multi-user / hosted deployment. (Local only in v1.)
- Tool marketplace / sharing. (v2 idea.)
- Support for transports other than stdio. (v2 can add SSE/HTTP.)

---

## 3. Target User

- **Primary:** AI-curious builders and developers who want custom tools for their AI workflows but don't want to write MCP server code from scratch.
- **Secondary:** Non-technical users running Claude Desktop who want to extend it with personal tools (note-saving, currency conversion, weather, etc.).
- **Tertiary:** Open-source contributors who will fork, extend, and publish their own variants.

---

## 4. Architecture Overview

### 4.1 High-level flow

```
User (in Claude Desktop / Cursor)
        │
        ▼
   MCP Client
        │  (stdio)
        ▼
┌───────────────────────────────────────┐
│         Genesis MCP Server            │
│                                       │
│  ┌─────────────────────────────────┐  │
│  │   Meta-Tools (built-in)         │  │
│  │   - create_tool                 │  │
│  │   - list_tools                  │  │
│  │   - delete_tool                 │  │
│  │   - update_tool                 │  │
│  │   - describe_tool               │  │
│  └─────────────────────────────────┘  │
│                                       │
│  ┌─────────────────────────────────┐  │
│  │   Generated Tools (dynamic)     │  │
│  │   - get_weather                 │  │
│  │   - save_note                   │  │
│  │   - convert_currency            │  │
│  │   - ... (user-created)          │  │
│  └─────────────────────────────────┘  │
│                                       │
│  ┌─────────────────────────────────┐  │
│  │   Subsystems                    │  │
│  │   - Generator (LLM-powered)     │  │
│  │   - Validator                   │  │
│  │   - Registry (in-mem + disk)    │  │
│  │   - Hot-loader                  │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
        │
        ▼
   Disk: generated_tools/*.py
         tools_manifest.json
```

### 4.2 Component responsibilities

| Component | File | Responsibility |
|---|---|---|
| Server core | `genesis/server.py` | MCP server entry point. Uses official `mcp` Python SDK. Boots, registers all tools, exposes via stdio. |
| Meta-tools | `genesis/meta_tools.py` | The 5 built-in tools (create/list/delete/update/describe). |
| Generator | `genesis/generator.py` | Calls Anthropic API with a strict system prompt to convert a NL description into code + schema. |
| Validator | `genesis/validator.py` | AST parse, import allowlist check, JSON Schema validation, handler signature check. |
| Registry | `genesis/registry.py` | Tracks loaded tools in memory and on disk (`tools_manifest.json`). |
| Hot-loader | `genesis/loader.py` | `importlib`-based dynamic loading of new tool files into the live server. |
| Template | `genesis/templates/tool_template.py` | The canonical structure every generated tool must follow. |
| Config | `genesis/config.py` | Loads `config.yaml` (import allowlist, API key env var name, paths). |

### 4.3 Key design decisions

| Decision | Rationale |
|---|---|
| Tools stored as **plain Python files** in `generated_tools/`, not a database | Transparency, editability, version-controllable, shareable. Critical for open-source ethos. |
| **LLM-powered generation** (not templates) | Users describe tools in messy natural language; templates would be too rigid. |
| **Strict tool template** | Predictable structure → trivial validation, loading, debugging. |
| **stdio transport** | Standard MCP. Works with Claude Desktop, Cursor, most clients out of the box. |
| **Import allowlist** (not full sandbox) for v1 | Sufficient safety for local use; full sandbox is v2 scope. Documented as "run at your own risk". |
| **Single-process** for v1 | Simplicity. Subprocess isolation per tool is v2. |
| **Anthropic API for generation** | Best-in-class for code generation following strict templates. API key supplied by user in `.env`. |

---

## 5. The Tool Template (canonical structure)

Every generated tool MUST conform to this exact structure. The validator rejects anything that doesn't.

```python
# Auto-generated by Genesis MCP
# Tool: <tool_name>
# Description: <one-line description>
# Generated: <ISO timestamp>

TOOL_SCHEMA = {
    "name": "<tool_name>",
    "description": "<one-line description>",
    "inputSchema": {
        "type": "object",
        "properties": {
            # ... param definitions ...
        },
        "required": [...]
    }
}

def handler(arguments: dict) -> dict:
    """
    <docstring>
    """
    # ... generated logic ...
    return {
        "status": "success" | "error",
        "data": <result>,
        "message": <optional human-readable note>
    }
```

**Rules:**
- Module-level `TOOL_SCHEMA` dict (required).
- Module-level `handler(arguments: dict) -> dict` function (required).
- No other top-level code execution (imports allowed, no side effects on import).
- Return value MUST be a dict with at least `status` and `data` keys.

---

## 6. Meta-Tools Specification

### 6.1 `create_tool`

**Description:** Generates a new MCP tool from a natural language description and registers it live.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "description": "Natural language description of the tool to create. Should explain what the tool does, what inputs it takes, and what it returns."
    },
    "name_hint": {
      "type": "string",
      "description": "Optional suggested name (snake_case). If omitted, Genesis will infer from the description."
    }
  },
  "required": ["description"]
}
```

**Behaviour:**
1. Call the Generator with the description.
2. Validator runs on the generated code.
3. If invalid: return error with details, do NOT register.
4. If valid: write file to `generated_tools/<name>.py`, update manifest, hot-load.
5. Return success with the new tool's name, schema, and file path.

**Return:**
```json
{
  "status": "success",
  "data": {
    "tool_name": "get_weather",
    "file_path": "generated_tools/get_weather.py",
    "schema": { ... },
    "ready": true
  },
  "message": "Tool 'get_weather' created and registered. You can now use it."
}
```

### 6.2 `list_tools`

**Description:** Lists all user-generated tools.

**Input schema:** `{}` (no params)

**Return:** Array of `{name, description, created_at, file_path}`.

### 6.3 `delete_tool`

**Description:** Removes a generated tool from the server and disk.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"}
  },
  "required": ["name"]
}
```

**Behaviour:** Unregisters from live server, deletes file, updates manifest. Returns confirmation. Cannot delete built-in meta-tools.

### 6.4 `update_tool`

**Description:** Modifies an existing generated tool by providing a new description (regenerates) or by patching specific behavior.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "new_description": {"type": "string"}
  },
  "required": ["name", "new_description"]
}
```

**Behaviour:** Regenerates the tool with the new description, validates, replaces the old file, re-registers. Keeps the same tool name.

### 6.5 `describe_tool`

**Description:** Returns the full schema and source code of a specific tool. Useful for debugging.

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"}
  },
  "required": ["name"]
}
```

**Return:** `{name, description, schema, source_code, file_path, created_at}`.

---

## 7. Generator: The LLM Prompt

The Generator calls Anthropic's API (Claude Sonnet 4.6 or current best model). The system prompt is critical and must be strict.

### Generator system prompt (use as-is or refine)

```
You are a code generator for Genesis MCP. Your only job is to produce a single Python file
that defines exactly ONE MCP tool, following the strict template below.

Your output MUST be valid Python code, with no markdown fences, no commentary, no explanation —
ONLY the raw code of the tool file.

The tool file MUST follow this exact structure:

```python
# Auto-generated by Genesis MCP
# Tool: <tool_name>
# Description: <one-line description>
# Generated: <ISO timestamp will be inserted by Genesis>

<imports — ONLY from the allowlist>

TOOL_SCHEMA = {
    "name": "<tool_name>",
    "description": "<one-line description>",
    "inputSchema": {
        "type": "object",
        "properties": { ... },
        "required": [...]
    }
}

def handler(arguments: dict) -> dict:
    """<docstring>"""
    # logic
    return {"status": "success", "data": ..., "message": "..."}
```

ALLOWED IMPORTS (whitelist — anything not on this list will be rejected):
- requests
- json
- datetime
- pathlib
- os.path (read-only operations)
- re
- math
- typing
- urllib.parse

FORBIDDEN:
- subprocess, os.system, eval, exec, compile, __import__
- shutil (file deletion/moving)
- socket, ftplib, telnetlib
- Any networking other than `requests` for HTTPS

RULES:
1. The handler function MUST accept a single `arguments: dict` parameter.
2. The handler function MUST return a dict with `status`, `data`, and `message` keys.
3. On error, return {"status": "error", "data": null, "message": "<error description>"}.
4. Wrap external API calls in try/except.
5. Validate inputs at the start of `handler`.
6. Tool name MUST be snake_case.
7. Description must be one sentence, plain language.
8. inputSchema MUST be valid JSON Schema.

Now generate the tool based on this user description:
<USER DESCRIPTION HERE>
```

### Generator implementation notes

- Use `anthropic` Python SDK.
- Model: `claude-sonnet-4-5-20250929` or latest available; configurable via `config.yaml`.
- Temperature: `0` (deterministic, no creativity).
- Max tokens: 2000.
- Strip any accidental markdown fences from the response before validation.
- Retry once on validation failure with the error message appended to the prompt.

---

## 8. Validator Rules

Run in this order. Fail fast.

1. **Syntax check** — `ast.parse(code)`. Reject on `SyntaxError`.
2. **Import check** — Walk the AST, collect all `Import` and `ImportFrom` nodes. Reject if any imported module is not in the allowlist.
3. **Forbidden names** — Walk AST for `Call` nodes referencing `eval`, `exec`, `compile`, `__import__`, `os.system`, `subprocess.*`. Reject if found.
4. **Required structure** — Module must have:
   - A module-level `TOOL_SCHEMA` dict assignment.
   - A module-level `def handler(arguments: dict) -> dict:` function.
5. **Schema validity** — `TOOL_SCHEMA` must be a valid JSON Schema with required keys: `name`, `description`, `inputSchema`. Use `jsonschema` library.
6. **Name uniqueness** — `TOOL_SCHEMA["name"]` must not collide with existing tools (meta or generated). Suggest a renamed version on collision.
7. **No top-level side effects** — Other than imports and the two required definitions, no other top-level statements.

If any check fails, return a structured error: `{check: "...", reason: "...", line: ...}`.

---

## 9. Registry & Hot-Loading

### 9.1 Registry

- In-memory: a dict `{name: {schema, handler, file_path, created_at}}`.
- On disk: `tools_manifest.json` at project root.

Manifest schema:
```json
{
  "version": 1,
  "tools": [
    {
      "name": "get_weather",
      "description": "...",
      "file_path": "generated_tools/get_weather.py",
      "created_at": "2026-05-21T10:30:00Z"
    }
  ]
}
```

### 9.2 Hot-loading

Use `importlib.util.spec_from_file_location` and `importlib.util.module_from_spec` to load the new tool file dynamically. Extract `TOOL_SCHEMA` and `handler` from the loaded module. Register them with the MCP server's tool list.

Reference pattern:
```python
import importlib.util
spec = importlib.util.spec_from_file_location(tool_name, file_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
schema = module.TOOL_SCHEMA
handler = module.handler
# register with MCP server
```

### 9.3 Startup loading

On server boot:
1. Read `tools_manifest.json`.
2. For each entry, load the file via importlib.
3. If a file is missing or fails to load, log a warning and skip (don't crash).
4. Register all valid tools with the MCP server.
5. Register the built-in meta-tools last.

---

## 10. Project Structure

```
genesis-mcp/
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── .gitignore
├── config.yaml
├── genesis/
│   ├── __init__.py
│   ├── server.py
│   ├── meta_tools.py
│   ├── generator.py
│   ├── validator.py
│   ├── registry.py
│   ├── loader.py
│   ├── config.py
│   └── templates/
│       └── tool_template.py
├── generated_tools/
│   └── .gitkeep
├── tools_manifest.json     # created at runtime
├── examples/
│   ├── README.md
│   ├── weather_demo.md
│   ├── notes_demo.md
│   └── currency_demo.md
└── tests/
    ├── __init__.py
    ├── test_validator.py
    ├── test_generator.py
    ├── test_registry.py
    └── fixtures/
        ├── valid_tool.py
        ├── bad_imports.py
        └── bad_syntax.py
```

---

## 11. Dependencies

`pyproject.toml` should declare:

- `mcp` — official MCP Python SDK
- `anthropic` — Anthropic API client
- `jsonschema` — schema validation
- `pyyaml` — config file
- `python-dotenv` — env var loading
- `requests` — for generated tools that need HTTP
- `pytest` (dev) — testing

Python 3.11+.

---

## 12. Configuration

### `.env.example`
```
ANTHROPIC_API_KEY=sk-ant-...
```

### `config.yaml`
```yaml
generator:
  model: claude-sonnet-4-5-20250929
  temperature: 0
  max_tokens: 2000
  max_retries: 1

validator:
  import_allowlist:
    - requests
    - json
    - datetime
    - pathlib
    - re
    - math
    - typing
    - urllib.parse

paths:
  generated_tools_dir: ./generated_tools
  manifest_file: ./tools_manifest.json

server:
  name: genesis-mcp
  version: 0.1.0
```

---

## 13. The Three Demo Tools (acceptance test cases)

After scaffolding, prove the system works by creating these three tools via `create_tool`:

### Demo 1: `get_weather`
**Description to pass to `create_tool`:**
> "Create a tool called get_weather that takes a city name and returns the current temperature in Celsius and weather conditions. Use the Open-Meteo API at api.open-meteo.com (free, no key needed). First geocode the city using their geocoding endpoint, then fetch the current weather for those coordinates."

**Expected:** A working tool that, when called with `{"city": "Lagos"}`, returns weather data.

### Demo 2: `save_note`
**Description to pass to `create_tool`:**
> "Create a tool called save_note that takes a title and content, and saves it as a markdown file in the ~/genesis_notes folder. Prepend today's date in YYYY-MM-DD format to the filename. Create the folder if it doesn't exist. Return the full path of the saved file."

**Expected:** A working tool that writes a file and returns its path.

### Demo 3: `convert_currency`
**Description to pass to `create_tool`:**
> "Create a tool called convert_currency that converts an amount between NGN, USD, EUR, and GBP using live rates from open.er-api.com (free, no key). It should take amount (number), from_currency, and to_currency. Return the converted amount, the exchange rate used, and a timestamp."

**Expected:** A working tool that returns a converted amount.

These three cover the three main tool archetypes: external API, filesystem, data transformation.

---

## 14. Build Plan (suggested order for Claude Code)

**Phase 1 — Skeleton**
1. Init project with `pyproject.toml`, README skeleton, `.gitignore`, `LICENSE` (MIT).
2. Create folder structure.
3. Set up `config.py` to load `config.yaml` and `.env`.

**Phase 2 — Core subsystems**
4. Implement `validator.py` with all checks. Write tests using fixtures.
5. Implement `registry.py` (in-memory + manifest persistence). Test.
6. Implement `loader.py` (importlib-based dynamic loading). Test.

**Phase 3 — Generator**
7. Implement `generator.py` calling Anthropic API with the system prompt. Test with a mock.

**Phase 4 — Meta-tools**
8. Implement all 5 meta-tools in `meta_tools.py`.

**Phase 5 — Server**
9. Implement `server.py` using the MCP SDK, wire up everything, expose via stdio.

**Phase 6 — Demos & docs**
10. Run the three demo tool creations manually. Save the resulting files into `examples/`.
11. Write the full `README.md` with install/run instructions and demos.

**Phase 7 — Handover for audit**
12. Produce `CLAUDE_CODE_HANDOVER.md` documenting what was built, deviations from this spec, known issues, and what Codex/Cursor should audit (security, edge cases, error handling, MCP SDK compliance, prompt robustness).

---

## 15. Acceptance Criteria

The build is "done" for v1 when:

- [ ] `python -m genesis.server` starts the MCP server without errors.
- [ ] Server connects successfully to Claude Desktop (via stdio config).
- [ ] `list_tools` returns the 5 built-in meta-tools.
- [ ] `create_tool` with the weather description produces a working `get_weather` tool.
- [ ] `create_tool` with the notes description produces a working `save_note` tool.
- [ ] `create_tool` with the currency description produces a working `convert_currency` tool.
- [ ] All three generated tools survive a server restart (loaded from manifest).
- [ ] `delete_tool` removes a tool from registry and disk.
- [ ] `describe_tool` returns the source code of any registered tool.
- [ ] Validator rejects code with forbidden imports (test with `subprocess`).
- [ ] Validator rejects code with invalid syntax.
- [ ] Validator rejects code missing `TOOL_SCHEMA` or `handler`.
- [ ] README contains a clear quick-start: install, set API key, configure Claude Desktop, create first tool.
- [ ] All tests pass: `pytest tests/`.

---

## 16. Known Risks & Open Questions

| Risk | Mitigation |
|---|---|
| LLM generates valid-looking but logically broken tools | Encourage users to test tools immediately after creation; v2 adds dry-run testing. |
| Users share tools that contain credentials | Document clearly: tool files may contain hardcoded API keys; users should not share blindly. |
| MCP SDK API changes | Pin SDK version in `pyproject.toml`; document upgrade path. |
| Anthropic API costs for users | Document expected cost per tool generation (~$0.01-0.05); offer config to use cheaper models. |
| Import allowlist too restrictive | Make it user-configurable in `config.yaml`. |
| Tool name collisions | Validator catches; suggest auto-suffix (e.g. `get_weather_2`). |

### Open questions for Claude Code to resolve during build:
1. Does the official `mcp` Python SDK support dynamic tool registration after server start? If not, the server may need a "reload" pattern — confirm and document.
2. Best pattern for stdio MCP server lifecycle (signal handling, graceful shutdown).
3. Whether to expose generated tool errors back through MCP as tool errors, or wrap as data in `status: error` responses.

---

## 17. For the Next Handover (Claude Code → Codex/Cursor)

After Claude Code finishes scaffolding, it should produce `CLAUDE_CODE_HANDOVER.md` containing:

1. What was built (file-by-file summary).
2. Deviations from this spec and why.
3. Test coverage report.
4. Known bugs or skipped edge cases.
5. **Audit checklist for Codex/Cursor**:
   - Security review of validator (can it be bypassed?)
   - MCP SDK compliance (does the server correctly implement the protocol?)
   - Generator prompt robustness (try adversarial descriptions)
   - Error handling completeness
   - Hot-loading edge cases (file deleted while loaded, name collisions, etc.)
   - README clarity (can a non-developer actually run this?)
6. Suggested polish before pushing to prod (GitHub public release).

---

## 18. Positioning Notes

- **Name:** Genesis MCP
- **Tagline:** *An MCP server with one tool — the tool that creates other tools.*
- **License:** MIT (maximum adoption).
- **Distribution:** GitHub, eventually PyPI (`pip install genesis-mcp`).
- **Demo asset:** A 60-second screen recording of creating the three demo tools via Claude Desktop.

---

**End of handover doc.**

Claude Code: Read this fully, ask clarifying questions if any sections are ambiguous, then propose your build plan before writing code.
