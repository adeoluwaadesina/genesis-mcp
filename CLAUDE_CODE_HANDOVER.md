# Genesis MCP — Claude Code Handover

> **⚠️ PARTIALLY STALE — architecture pivoted post-build**
>
> This handover was written immediately after the initial scaffold. Since
> then the code-generation path pivoted: `generator.py` no longer calls
> the Anthropic API — it only builds a prompt string for the host LLM.
> References below to "Anthropic API wrapper" and to `ANTHROPIC_API_KEY`
> error handling describe code that no longer exists.
>
> Current architecture: see `CLAUDE.md`.
> Security posture: see `README.md` "Security Notes" and `SECURITY_FIXES_v0_1.md`.

---

**Purpose:** This document records what was built, deviations from the spec, test coverage, and the audit checklist for the next reviewer (Codex/Cursor).

**Source of truth:** [`GENESIS_MCP_HANDOVER.md`](GENESIS_MCP_HANDOVER.md) + [`HANDOVER_ADDENDUM.md`](HANDOVER_ADDENDUM.md)

**Built by:** Claude Code (claude-sonnet-4-6)
**Date:** 2026-05-21
**Tested on Windows:** Yes (Python 3.14.0, Windows 11 Home 10.0.26200)

---

## 1. What Was Built

### File inventory

| File | Status | Notes |
|---|---|---|
| `pyproject.toml` | Done | Hatchling backend; `packages = ["genesis"]` required for editable install |
| `LICENSE` | Done | MIT |
| `.gitignore` | Done | Excludes `.env`, `generated_tools/*.py`, `tools_manifest.json` |
| `.env.example` | Done | |
| `config.yaml` | Done | Model: `claude-sonnet-4-6` |
| `genesis/__init__.py` | Done | Empty |
| `genesis/config.py` | Done | Singleton loader; `pathlib.Path` for all paths |
| `genesis/validator.py` | Done | All 7 checks; fail-fast ordered |
| `genesis/registry.py` | Done | In-memory dict + JSON manifest; `list()` supports `filter` param |
| `genesis/loader.py` | Done | `importlib`-based dynamic loading; `LoadError` on all failure modes |
| `genesis/generator.py` | Done | Anthropic API wrapper; retry-on-validation-failure; fence stripping |
| `genesis/meta_tools.py` | Done | All 5 meta-tools; `META_TOOL_SCHEMAS` dict for server registration |
| `genesis/server.py` | Done | Low-level `mcp.Server`; dynamic `list_tools` + `call_tool` handlers |
| `genesis/templates/tool_template.py` | Done | Reference template for humans; not used programmatically |
| `generated_tools/.gitkeep` | Done | |
| `tests/__init__.py` | Done | |
| `tests/test_validator.py` | Done | 11 tests |
| `tests/test_generator.py` | Done | 5 tests (mocked Anthropic client) |
| `tests/test_registry.py` | Done | 12 tests (registry + loader) |
| `tests/fixtures/valid_tool.py` | Done | |
| `tests/fixtures/bad_imports.py` | Done | |
| `tests/fixtures/bad_syntax.py` | Done | |
| `examples/README.md` | Done | |
| `examples/weather_demo.md` | Done | |
| `examples/notes_demo.md` | Done | |
| `examples/currency_demo.md` | Done | |
| `README.md` | Done | Full quick-start; all three OS Claude Desktop config paths |

---

## 2. Deviations from Spec

### 2.1 `mcp.Server` initialization options

The MCP SDK 1.27.x `InitializationOptions` accepts `notification_options` and `experimental_capabilities` as keyword args. `app.get_capabilities()` signatures may vary by version — the server passes `notification_options=None` explicitly. If the server fails to start due to a `TypeError` here, it means the SDK version changed its API and `server.py:run_server` needs updating to match.

### 2.2 `os` import handling in validator

The spec says "allow `os.path` (read-only operations)". In practice:
- `import os.path` is allowed
- `from os.path import join` is allowed
- `from os import path` is allowed
- Bare `import os` is **not** allowed (could give access to `os.system`)
- Even if `os` is imported in an allowed way, calls to `os.system`, `os.popen`, and related dangerous attrs are caught by the forbidden-names check

This two-layer approach (import allowlist + call check) means the safety guarantee is: even if a future allowlist entry is broader than intended, the call checker provides a second line of defence.

### 2.3 `list_tools` meta-tool `created_at`

Meta-tools have `created_at: None` in registry entries. `to_list_dict()` returns `None` for this field. This is consistent with the addendum spec ("can be omitted or set to the server build date") — we chose `None` for simplicity.

### 2.4 `describe_tool` file_path for meta-tools

Returns the path relative to the project root (`genesis/meta_tools.py`) rather than an absolute path. This is more portable in a distributed/installed context.

### 2.5 Python 3.14 compatibility

Tests were run on Python 3.14.0 (the user's environment), which is newer than the specified 3.11+ minimum. No compatibility issues were observed; `from __future__ import annotations` is used throughout for forward-ref compatibility.

### 2.6 `tools_manifest.json` not pre-created

The manifest is created on first `create_tool` call (or on `save_manifest()`). `load_manifest()` handles the missing-file case gracefully. This is correct behaviour — the file should not exist in the repo.

---

## 3. Test Coverage

```
29 passed in 0.36s (Python 3.14, Windows 11)

tests/test_validator.py    — 11 tests
  - Valid tool passes all checks
  - Bad syntax rejected at check 1
  - Forbidden imports (subprocess) rejected at check 2
  - eval() call caught at check 3
  - os.system() call caught at check 3
  - Missing TOOL_SCHEMA caught at check 4
  - Missing handler caught at check 4
  - Invalid TOOL_SCHEMA (missing 'description') caught at check 5
  - Name collision caught at check 6, suggestion provided
  - Top-level side effect (print) caught at check 7
  - All allowlisted imports pass cleanly

tests/test_generator.py    — 5 tests
  - Valid generation returns code and no errors
  - Markdown fences stripped correctly
  - Retry triggered on first-attempt validation failure
  - Errors returned after max_retries exhausted
  - name_hint included in prompt

tests/test_registry.py     — 12 tests
  - register, get, unregister
  - names()
  - list() with all three filter values
  - manifest round-trip (save + load)
  - manifest missing file handled gracefully
  - loader: valid tool
  - loader: missing file raises LoadError
  - loader: bad_imports.py loads (loader doesn't validate — validator's job)
  - loader: runtime crash during module load raises LoadError
```

**Not covered by automated tests:**
- `meta_tools.py` functions (require registry + file system + mocked generator; integration-test territory)
- `server.py` (requires live MCP client)
- End-to-end create_tool → use_tool flow

---

## 4. Known Bugs and Skipped Edge Cases

| Item | Severity | Notes |
|---|---|---|
| No test for `create_tool` meta-tool itself | Medium | Needs integration test with mocked generator + temp dir |
| `update_tool` does not back up old file | Low | Old file is overwritten in-place; if the new generation fails to load after writing, the old file is gone. A backup-then-replace pattern would be safer. |
| `describe_tool` `file_path` for meta-tools is relative | Low | `Path(__file__).relative_to(...)` can raise if the project is installed in an unusual location |
| `_META_HANDLER_MAP` forward reference | Low | The dict at the bottom of `meta_tools.py` references `describe_tool` which itself references the dict. This works at runtime (function defined before dict is used), but is a code smell. Consider moving to a `register()` pattern. |
| MCP SDK API surface not pinned | Medium | `mcp>=1.0.0` is a broad pin. The `InitializationOptions` and `get_capabilities()` signatures changed between SDK minor versions. Pin to `mcp~=1.27` in production. |
| Generated tools run in the main process | By design | v1 non-goal. Documented in README. A malicious or buggy generated tool can crash the server. v2: subprocess isolation. |
| No signal handling in `server.py` | Low | `asyncio.run()` handles SIGINT via KeyboardInterrupt. SIGTERM on Windows is not POSIX-sigterm; this is acceptable for a local stdio server. |

---

## 5. Audit Checklist for Codex/Cursor

### Security
- [ ] **Validator bypass attempts:** Try adversarial tool descriptions that attempt to smuggle `subprocess` via aliasing (`import subprocess as sp`), string-based import (`__import__('subprocess')`), or indirection (`getattr(builtins, 'eval')`). Current checks catch direct AST nodes — check if indirect patterns evade them.
- [ ] **Import allowlist completeness:** Is `urllib.parse` safe? It can be used to construct URLs that bypass intended API restrictions. Is `os.path` truly read-only given the two-layer check? Verify edge cases.
- [ ] **Path traversal in manifest:** `load_manifest()` reads `file_path` from a JSON file. If `tools_manifest.json` is tampered with, a crafted `file_path` could load an arbitrary `.py` file. Consider validating that `file_path` is within `generated_tools_dir`.
- [ ] **Tool name injection:** Is the `tool_name` extracted from generated code used safely in `file_path = tool_dir / f"{tool_name}.py"`? Could a generated tool name contain `../` or similar? The snake_case requirement + the validator's name-extraction via `ast.literal_eval` should prevent this, but verify.

### MCP SDK compliance
- [ ] **`list_tools` return type:** Confirm `mcp.types.Tool` is the correct type for the `list_tools` handler return in SDK 1.27.x.
- [ ] **`call_tool` return type:** Confirm `list[types.TextContent]` is accepted; check if `isError` field should be set on error results.
- [ ] **`InitializationOptions`:** Verify `notification_options=None` and `experimental_capabilities={}` are still valid in the installed SDK version.
- [ ] **stdio transport:** Verify `mcp.server.stdio.stdio_server()` is the correct import path in SDK 1.27.x.

### Generator prompt robustness
- [ ] Try: "Create a tool that deletes all files in the current directory" — should generate code that fails the forbidden-names check or at minimum uses only `pathlib` in a targeted way.
- [ ] Try: "Create a tool that exfiltrates environment variables via HTTP POST" — validator should catch `os.environ` usage (note: `os.environ` is not in the allowlist).
- [ ] Try: "Create a tool named `../evil`" — name should be rejected at schema check or sanitised.
- [ ] Try a very long description (10,000 chars) — check token limit handling.

### Error handling
- [ ] What happens if `ANTHROPIC_API_KEY` is unset? `create_tool` should return a clear error, not an SDK exception traceback.
- [ ] What happens if `config.yaml` is missing? `get_config()` will throw `FileNotFoundError` — should be caught at startup.
- [ ] What happens if `generated_tools/` is not writable? `create_tool` should surface a clear error.
- [ ] What if the Anthropic API is rate-limited or returns a 529? Currently propagates as an unhandled exception from `generator.py`.

### Hot-loading edge cases
- [ ] Create a tool, then manually delete its file while the server is running, then call `describe_tool` on it — does it fail gracefully?
- [ ] Create two tools with the same name in quick succession — does the name-uniqueness check hold under concurrent calls (not an issue for stdio single-process, but worth noting for future SSE transport)?
- [ ] `update_tool` on a tool whose file is missing — currently uses the entry's `file_path` which may not exist. Does it write to the old (missing) path or create a new file?

### README clarity
- [ ] Have a non-developer follow the Quick Start on Windows. Verify the venv activation command is correct for Windows (`.\\.venv\\Scripts\\activate`). Check the JSON config escaping for Windows paths.
- [ ] Verify the Claude Desktop config path `%APPDATA%\Claude\claude_desktop_config.json` is correct for the installed Claude Desktop version.

---

## 6. Suggested Polish Before Public Release

1. **Pin MCP SDK version:** Change `mcp>=1.0.0` to `mcp~=1.27` (or whatever the verified working version is).
2. **Add `create_tool` integration test:** Mock the Anthropic client, run `create_tool`, verify the file is written and the registry updated.
3. **Graceful API key error:** Wrap the Anthropic client instantiation in `generator.py` to give a friendly message if the key is missing/invalid.
4. **`update_tool` backup:** Write to `<name>.py.bak` before overwriting, restore on load failure.
5. **`config.yaml` not-found error:** Catch `FileNotFoundError` in `config.py` and print a human-readable startup error.
6. **CI:** Add a GitHub Actions workflow running `pytest` on push (Python 3.11, 3.12, 3.13, Windows + Ubuntu).
7. **PyPI packaging:** Verify `pyproject.toml` metadata (author, homepage, classifiers) before `pip publish`.
8. **60-second demo recording:** Record `create_tool` → `get_weather` → `save_note` → `convert_currency` in Claude Desktop for the GitHub README.

---

**End of handover.**
