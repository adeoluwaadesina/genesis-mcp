# Genesis MCP — Handover Addendum

> **⚠️ HISTORICAL DOCUMENT — DOES NOT REFLECT SHIPPED ARCHITECTURE**
>
> Captures design decisions made before the build. The code-generation
> architecture pivoted during implementation: Genesis does not make
> server-side Anthropic API calls; the host LLM generates code. The "API
> cost per generation" notes below describe a path that was not built.
> See [`../../CLAUDE.md`](../../CLAUDE.md) and [`../security/SECURITY_FIXES_v0_1.md`](../security/SECURITY_FIXES_v0_1.md) for current architecture.

---

**Purpose:** This file captures decisions made after the initial handover doc (`GENESIS_MCP_HANDOVER.md`) in response to clarifying questions raised during the build planning phase. Treat these as authoritative — they override or refine the original spec.

**Read this together with `GENESIS_MCP_HANDOVER.md`.**

**Date:** 2026-05-21
**Phase:** Pre-scaffold, post-planning Q&A
**Status:** Approved, ready to build

---

## Decision 1 — MCP SDK: Use low-level `mcp.Server`, not `FastMCP`

**Resolves:** Open Question 1 in the original handover (Section 16).

**Decision:** Use the low-level `mcp.Server` class. Implement `list_tools` and `call_tool` as dynamic handlers that read from the registry at call time.

**Rationale:**
- `FastMCP` is a decorator-based ergonomic API optimized for static tool sets defined at import time. It registers tools at decoration time and does not support clean dynamic registration after server start.
- Hot-loading via `FastMCP` would require either rebuilding the server instance or reaching into internals — both fragile.
- The low-level `Server` class with dynamic handlers is the correct architectural choice for a self-extending server. The registry becomes the single source of truth; the server queries it on every `list_tools` and `call_tool` request.

**Implementation note for Claude Code:**
- The `list_tools` handler returns the current registry snapshot.
- The `call_tool` handler looks up the tool by name in the registry and invokes its `handler(arguments)` function.
- No server restart is ever needed when `create_tool`, `update_tool`, or `delete_tool` modifies the registry.

---

## Decision 2 — Default generator model: `claude-sonnet-4-6`

**Resolves:** Stale model ID in `config.yaml` example (handover Section 12).

**Decision:** Default model in `config.yaml` is `claude-sonnet-4-6`.

**Rationale:**
- `claude-sonnet-4-5-20250929` in the original spec was stale.
- `claude-sonnet-4-6` is the current Sonnet release and the most capable model for following the strict template prompt.

**Additional config guidance:**
- The model ID lives in `config.yaml` as the single source of truth.
- README should document that users can swap to `claude-haiku-4-5-20251001` for cheaper generation. Haiku 4.5 is the current Haiku and is more than capable for this template-following task — likely good enough for ~90% of tool generations at a fraction of the cost.
- Anthropic API costs per generation are roughly: Sonnet 4.6 ~$0.01–0.05 per tool; Haiku 4.5 significantly less. Document this in the README so users can make an informed choice.

---

## Decision 3 — `list_tools` returns everything by default, with a `filter` parameter

**Resolves:** Scope ambiguity in `list_tools` spec (handover Section 6.2).

**Decision:** `list_tools` returns both generated tools and built-in meta-tools by default. Discoverability is the killer feature; new users need to see what's available immediately.

**Updated input schema:**
```json
{
  "type": "object",
  "properties": {
    "filter": {
      "type": "string",
      "enum": ["all", "generated", "meta"],
      "default": "all",
      "description": "Which tools to return."
    }
  }
}
```

**Updated return:** Each tool object in the response array gets a `type` field set to `"meta"` or `"generated"` so the AI client (and user) can visually distinguish them without losing discoverability.

Example return entry:
```json
{
  "name": "get_weather",
  "description": "Fetches current weather for a city.",
  "type": "generated",
  "created_at": "2026-05-21T10:30:00Z",
  "file_path": "generated_tools/get_weather.py"
}
```

For meta-tools, `file_path` should point to `genesis/meta_tools.py` and `created_at` can be omitted or set to the server build date.

---

## Decision 4 — `describe_tool` works on both meta-tools and generated tools

**Resolves:** Scope ambiguity in `describe_tool` spec (handover Section 6.5).

**Decision:** `describe_tool` supports both built-in meta-tools and user-generated tools.

**Rationale:** Showing the source of meta-tools is a teaching moment. Users curious about how Genesis works can read the meta-tool implementations and learn how to write proper MCP tools themselves. This aligns with the open-source ethos and lowers the barrier for contributors.

**Implementation:**
- For generated tools: read the source from `file_path`.
- For meta-tools: use `inspect.getsource()` on the meta-tool function to return its actual source code from `genesis/meta_tools.py`.
- Add an `editable: bool` field to the return so AI clients know whether `update_tool` and `delete_tool` will work on this tool. `false` for meta-tools, `true` for generated.

**Updated return:**
```json
{
  "name": "create_tool",
  "type": "meta",
  "description": "...",
  "schema": { ... },
  "source_code": "def create_tool(arguments: dict) -> dict:\n    ...",
  "file_path": "genesis/meta_tools.py",
  "editable": false,
  "created_at": null
}
```

---

## Decision 5 — Cross-platform from day one (Windows is first-class)

**Resolves:** Platform target ambiguity raised during planning.

**Decision:** Genesis MCP must work on Windows, macOS, and Linux from v1. No platform is second-class.

**Rationale:**
- The maintainer's primary dev environment is Windows. The project must run there or it can't be dogfooded.
- Claude Desktop ships a Windows build; the Windows + Claude Desktop population is large and growing, especially outside Mac-heavy SF tech circles. Locking them out is a strategic mistake for an open-source project aiming at adoption.

**Concrete build rules:**

| Rule | Why |
|---|---|
| Use `pathlib.Path` everywhere. Never raw string paths or `os.path.join` with backslashes. | Path handling differs between OSes; `pathlib` abstracts this. |
| `~` expansion via `Path.home()`, never shell expansion or `os.path.expanduser` with assumptions. | Consistent home directory resolution. |
| `save_note` demo writes to `Path.home() / "genesis_notes"`. | Works identically on Windows (`C:\Users\<user>\genesis_notes`), macOS, and Linux. |
| Every `open()` call must specify `encoding="utf-8"` explicitly. | Windows defaults to cp1252, which silently corrupts non-ASCII content. This is a common, hard-to-debug bug. |
| Don't hardcode `\n` in files meant to be read back; let Python handle line endings. | Avoids CRLF/LF mismatch issues. |
| The `python -m genesis.server` invocation must work identically on all three platforms. Test on Windows specifically. | Entry point consistency. |
| Document Claude Desktop config file location for all three platforms in the README. | The config path differs per OS — users need OS-specific instructions. |

**Claude Desktop config file paths (for README documentation):**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json` (verify — Linux support may vary by Claude Desktop version)

**Testing requirement:** `CLAUDE_CODE_HANDOVER.md` must include a "tested on Windows: yes/no" entry so Codex/Cursor knows what to verify in the audit pass.

---

## Summary table

| # | Topic | Decision |
|---|---|---|
| 1 | MCP SDK choice | Low-level `mcp.Server` with dynamic handlers (not FastMCP) |
| 2 | Default LLM model | `claude-sonnet-4-6`; Haiku 4.5 documented as cheaper alternative |
| 3 | `list_tools` scope | Returns all by default; `filter` param: `all` / `generated` / `meta`; `type` field on each entry |
| 4 | `describe_tool` scope | Works on both meta and generated tools; includes `editable` flag and actual source via `inspect.getsource()` for meta-tools |
| 5 | Platform support | Cross-platform from v1: Windows, macOS, Linux. Windows is first-class. |

---

## Instructions to Claude Code

1. Re-read `GENESIS_MCP_HANDOVER.md` with these five decisions overlaid.
2. Propose your build plan (phased, per Section 14 of the original handover) before writing any code.
3. Apply these decisions consistently across all files you produce.
4. In `CLAUDE_CODE_HANDOVER.md` (the doc you produce at the end for Codex/Cursor), reference both `GENESIS_MCP_HANDOVER.md` and this addendum as the source of truth for the spec.

---

**End of addendum.**
