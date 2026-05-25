# Genesis MCP — Security Fixes (v0.1)

**Date:** 2026-05-25
**Branch:** `security/critical-fixes`
**Scope:** Path B — fix only CRITICAL findings (F-01, F-02, F-03) plus honest
security documentation (F-18). All HIGH/MEDIUM/LOW findings deferred to v0.2.
**Tests:** 34/34 passing (29 pre-existing + 5 new regression tests).

This document records exactly what was fixed against the
[`SECURITY_AUDIT_REPORT.md`](SECURITY_AUDIT_REPORT.md), what regression tests
protect each fix, and what was deliberately deferred.

---

## Critical fixes applied

### F-01 — Arbitrary command execution via `__builtins__` (validator-bypass / CRITICAL)

**Original audit PoC:** A `handler` that obtains `__import__` via
`__builtins__["__import__"]` (subscript) or `getattr(__builtins__, "__import__")`
(attribute), then loads `subprocess` and runs an arbitrary command — all
without importing `subprocess` at module level.

**Root cause:** `genesis/validator.py::_check_forbidden_calls` inspected only
`ast.Call.func` nodes whose `id` matched `eval`/`exec`/`compile`/`__import__`.
References to `__builtins__` and reflection builtins like `getattr` were not
checked at all.

**Fix:** Added `_check_forbidden_names` to `genesis/validator.py`. It walks the
full AST and rejects three bypass primitives:

| AST shape | Rejected because |
|---|---|
| `Name(id='__builtins__')` | Direct or indirect reference to the builtins mapping is the F-01/F-02 primary vector. Caught for `__builtins__["x"]` (Subscript wraps an inner Name), `__builtins__.x` (Attribute root is a Name), and bare `b = __builtins__`. |
| `Attribute(attr ∈ DUNDER_ATTRS)` | Attribute access to any of `__import__`, `__builtins__`, `__globals__`, `__loader__`, `__getattribute__` on any object — blocks `obj.__import__("subprocess")` even when `obj` is benign. |
| `Call(func=Name(id ∈ {getattr, globals, locals, vars}))` | Reflection primitives used to defeat name-based checks. No legitimate generated tool needs them. |

Inserted as **check 4** in the fail-fast order in `validate()`, between
"forbidden calls" and "required structure". Validator order in `CLAUDE.md`
updated to 8 checks.

**Regression test:** `tests/test_validator.py::test_f01_builtins_subscript_import_blocked`

The test feeds the **exact PoC code** from the audit report (the `sys_info`
tool body) into `validate()` and asserts that at least one returned error has
`check == "forbidden_name"`.

**Re-running the audit's F-01 PoC against the patched validator produces:**

```
[forbidden_name] line 4: Call to reflection builtin 'getattr' is not allowed.
[forbidden_name] line 4: Reference to '__builtins__' is not allowed (bypass primitive).
[forbidden_name] line 4: Reference to '__builtins__' is not allowed (bypass primitive).
[forbidden_name] line 4: Reference to '__builtins__' is not allowed (bypass primitive).
```

Defense-in-depth: every primitive in the PoC is flagged independently. Removing
any one of `__builtins__`, `getattr`, or the subscript access still trips at
least one other check.

---

### F-02 — `eval`/`exec` via `__builtins__` (validator-bypass / CRITICAL)

**Original audit PoC:** A `calc` tool whose `handler` obtains `eval` via
`__builtins__["eval"]` or `getattr(__builtins__, "eval")` and calls it on
attacker-controlled input.

**Root cause:** Same as F-01 — direct `eval(...)` was blocked, but indirect
access through `__builtins__` was not inspected.

**Fix:** Same single patch as F-01 (`_check_forbidden_names`). The `__builtins__`
reference is rejected before `eval` is ever resolved, so this PoC fails at the
same point F-01 does.

**Regression test:** `tests/test_validator.py::test_f02_builtins_subscript_eval_blocked`

Uses the exact `calc` PoC from the audit report.

**Re-running the audit's F-02 PoC against the patched validator produces:**

```
[forbidden_name] line 4: Call to reflection builtin 'getattr' is not allowed.
[forbidden_name] line 4: Reference to '__builtins__' is not allowed (bypass primitive).
[forbidden_name] line 4: Reference to '__builtins__' is not allowed (bypass primitive).
[forbidden_name] line 4: Reference to '__builtins__' is not allowed (bypass primitive).
```

---

### F-03 — `register_tool` accepts arbitrary code from any MCP client (process-model / CRITICAL)

**Original audit observation:** `register_tool` accepts any Python string a
connected MCP client supplies. There is no LLM in the loop — the server-side
validator is the **only** gate.

**Fix applied in v0.1:** Two parts.

1. **Validator hardening for the bypass primitives that F-01/F-02 exploit.**
   Since the validator is the sole gate, every fix to F-01/F-02 directly
   reduces the F-03 attack surface. The `_check_forbidden_names` check applies
   to all code submitted via `register_tool` regardless of source.

2. **Explicit trust-model documentation** in `README.md` "Security Notes".
   Users are now told plainly that:
   - Genesis v0.1 has **no sandbox** — the validator is the entire trust boundary.
   - v0.1 is designed for **local, single-user use only**.
   - Do not expose Genesis to multiple users, untrusted clients, or networks.
   - Generated code can read files, make HTTPS requests, and DoS the process
     even after the validator passes — those are not blocked in v0.1.

**Not fixed in v0.1 (deferred to v0.2):**
- No client authentication or capability tokens on `register_tool`.
- No human-approval step before a tool is hot-loaded.
- No subprocess or container isolation for handler execution.

**Regression test:** No standalone F-03 test — its mitigation in v0.1 is
mechanically the same as F-01/F-02 (validator). The 5 new validator tests
listed in this document cover the bypass primitives that F-03 could otherwise
ship to the server unfiltered.

---

### F-18 — Documentation / architecture drift (process-model / LOW, but in scope)

**Original audit observation:** `CLAUDE.md`, `GENESIS_MCP_HANDOVER.md`, and
README claimed Genesis makes server-side Anthropic API calls
(`generator.generate_tool()`). The shipped code does not — `generator.py`
only builds a prompt string, and the host LLM generates code and posts it
back via `register_tool`.

**Additional findings during this fix pass:**

- `genesis/` contains **zero** `import anthropic` statements. The
  `anthropic` dependency was added to `pyproject.toml` earlier on the
  premise (from stale docs) that the server calls it. It was unused.
- `genesis/` contains **zero** references to `ANTHROPIC_API_KEY`.
  The `.env.example` file, the `env:` block in the Claude Desktop config,
  and the "Set your API key" README step were all pointing users at a
  credential the server doesn't consume.
- `config.yaml` contained no `generator:` section, but the README displayed
  one with `model` / `temperature` / `max_tokens` / `max_retries` keys.
- The "API cost per tool generation" table in the README described
  Genesis-side costs that don't exist (the host LLM is billed by its own
  provider).

**Fixes applied:**

| File | Change |
|---|---|
| `pyproject.toml` | Removed `anthropic` from `dependencies`. Unused. |
| `.env.example` | **Deleted.** Genesis v0.1 reads no environment variables. |
| `README.md` | Removed "Anthropic API key" prerequisite. Removed "Set your API key" step. Replaced `env: { ANTHROPIC_API_KEY: ... }` in both Claude Desktop config snippets. Replaced the stale `config.yaml` snippet with the actual file contents. Replaced the "API cost per tool" table with a note that Genesis makes no API calls and host LLM billing is independent. Updated two stale references in the new Security Notes (`ANTHROPIC_API_KEY` no longer relevant). |
| `CLAUDE.md` | Rewrote the "Data flow for `create_tool`" section to describe the real two-step host-LLM flow (`create_tool` returns prompt → host generates → `register_tool` validates and loads). Updated the file table to reflect 6 meta-tools (not 5), the new `_check_forbidden_names` step, and the fact that `generator.py` makes no API calls. Updated validator check order to 8 steps. Added a "Security posture (v0.1)" pointer. |
| `GENESIS_MCP_HANDOVER.md` | Added a "HISTORICAL DOCUMENT" banner at the top pointing readers to `CLAUDE.md` and `SECURITY_FIXES_v0_1.md`. Body preserved for historical rationale. |
| `HANDOVER_ADDENDUM.md` | Same banner treatment as the main handover. |
| `CLAUDE_CODE_HANDOVER.md` | "PARTIALLY STALE" banner — flags the `generator.py` description and the `ANTHROPIC_API_KEY` checklist items as describing code that no longer exists. |

**Vestigial code flagged but not modified (v0.2):**

- `genesis/config.py` still calls `load_dotenv(_ENV_PATH)`. Since no subsystem
  reads any env var, this is a silent no-op (the file no longer exists either).
  Removing the call is a code change outside this fix pass's scope.
- The `python-dotenv` dependency in `pyproject.toml` is therefore the only
  consumer of one no-op call. It can be removed in v0.2 alongside the
  `load_dotenv` call.

---

## What is **not** fixed in v0.1 (deferred to v0.2)

These were intentionally left unaddressed per Path B scope. Each is tracked
in the audit report.

| ID | Title | Severity | Why deferred |
|---|---|---|---|
| F-04 | Tool name path traversal writes outside `generated_tools/` | HIGH | Path-sanitization requires changes to `register_tool` and a path-confinement helper. Targeted for v0.2 alongside other process-model fixes. |
| F-05 | Duplicate `TOOL_SCHEMA`: validator uses first, runtime uses last | HIGH | Validator change — fold into v0.2 hardening pass with F-04/F-06. |
| F-06 | Duplicate `handler`: last definition wins at import | HIGH | Same as F-05. |
| F-07 | Unrestricted filesystem read/write via `open()` and `pathlib` | HIGH | Cannot be fixed by AST validator alone — requires subprocess sandbox or restricted-builtins shim. v0.2 sandbox work. |
| F-08 | Secret exfiltration via `requests` + filesystem | HIGH | Requires egress allowlist or subprocess with cleaned env. v0.2 sandbox work. |
| F-09 | Tampered `tools_manifest.json` can load arbitrary `.py` on startup | HIGH | Path-confinement check in `_boot_registry`. v0.2. |
| F-10 | Unrestricted HTTPS egress via `requests` | MEDIUM | Requires architectural change (request wrapper or network namespace). v0.2. |
| F-11 | Corrupt `tools_manifest.json` crashes server startup | MEDIUM | Small try/except fix; held for v0.2 to batch with manifest hardening. |
| F-12 | Race on concurrent `register_tool` | LOW | Per-name lock. v0.2. |
| F-13 | Loose dependency pin on `mcp` | MEDIUM | Pinning + lockfile pass is its own v0.2 stream. |
| F-14 | No lockfile | MEDIUM | Same as F-13. |
| F-15 | Prompt injection on generation prompt (host LLM) | MEDIUM | Partially mitigated by F-01/F-02 hardening (injected output that uses `__builtins__` now fails closed). Adversarial-eval CI deferred to v0.2. |
| F-16 | `breakpoint()` allowed in handler | LOW | One-line addition to `_FORBIDDEN_CALLS`. Held for v0.2 batch. |
| F-17 | MRO / dunder subclass chains allowed | LOW | Defense-in-depth gap; `__class__` / `__mro__` / `__subclasses__` / `__code__` not yet blocked. v0.2. |

---

## Verification

```
$ pytest tests/ -v
...
tests/test_validator.py::test_f01_builtins_subscript_import_blocked PASSED
tests/test_validator.py::test_f02_builtins_subscript_eval_blocked PASSED
tests/test_validator.py::test_builtins_bare_name_reference_blocked PASSED
tests/test_validator.py::test_getattr_call_blocked PASSED
tests/test_validator.py::test_attribute_dunder_blocked PASSED
...
============================= 34 passed in 0.30s ==============================
```

All 29 pre-existing tests still pass. The 5 new tests, run with the **exact
PoC code from the audit report**, confirm both F-01 and F-02 are now blocked.

---

## Files touched in this fix pass

| File | Change |
|---|---|
| `genesis/validator.py` | Added `_FORBIDDEN_NAMES`, `_FORBIDDEN_DUNDER_ATTRS`, `_FORBIDDEN_REFLECTION_CALLS`, and `_check_forbidden_names()`. Wired into `validate()` as check 4. Renumbered subsequent check comments. |
| `tests/test_validator.py` | Added 5 regression tests covering F-01/F-02 bypass primitives. |
| `pyproject.toml` | Removed `anthropic` dependency. |
| `.env.example` | Deleted. |
| `README.md` | Rewrote Security Notes, removed API-key prerequisite, removed `env:` block from Claude Desktop snippets, fixed `config.yaml` snippet, removed misleading cost table. |
| `CLAUDE.md` | Rewrote data flow, file responsibilities, validator order; added security pointer. |
| `GENESIS_MCP_HANDOVER.md` | "HISTORICAL DOCUMENT" banner. |
| `HANDOVER_ADDENDUM.md` | "HISTORICAL DOCUMENT" banner. |
| `CLAUDE_CODE_HANDOVER.md` | "PARTIALLY STALE" banner. |
| `PROJECT_LOG.md` | Dated entry summarising this fix pass. |
| `SECURITY_FIXES_v0_1.md` | This file. |

Nothing committed. All changes left unstaged on branch
`security/critical-fixes` for review.
