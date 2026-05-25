# Genesis MCP — Pre-Audit Report

**Date:** 2026-05-24
**Scope:** Pre-release polish pass before formal security audit (Codex/Cursor)
**Reviewer:** Claude (Cursor pre-audit pass)
**Status:** Working end-to-end in Claude Desktop. Not yet pushed to GitHub.

---

## Summary

Genesis MCP is functionally complete and tested end-to-end. The core architecture
(low-level `mcp.Server` with dynamic dispatch, AST-based validator, dynamic loader)
is sound. Before public release there are **one hard bug**, several documentation
inconsistencies, and a handful of polish items. None of the issues found block the
formal security audit — but fixing the items in §"Must fix before any push" below
will save the audit from flagging duplicates of obvious issues.

---

## What passed

### Repo health
- **29/29 tests pass** in 0.36s on Python 3.14.0 / Windows.
- Server starts cleanly via `python -m genesis.server`; registry loads expected
  meta + generated tools.
- No deprecation or import warnings.

### .gitignore & secrets
- `.env`, `tools_manifest.json`, `generated_tools/*.py`, and `__pycache__/` are
  all correctly ignored.
- `generated_tools/.gitkeep` is preserved via negation rule.
- No real API keys (`sk-ant-...`), tokens, or passwords found in the codebase —
  only documented placeholders in `.env.example` and `README.md`.
- No git repo exists yet, so no risk of already-committed secrets.

### Architecture
- File layout and responsibilities match the CLAUDE.md contract.
- Cross-platform rules (`pathlib.Path`, `encoding="utf-8"`) appear to be followed
  in core modules (not exhaustively re-checked in this pass).

---

## Must fix before any push

### 1. `anthropic` is not declared as a dependency (HARD BUG)
`genesis/generator.py` imports `anthropic`, but `pyproject.toml`'s `dependencies`
list omits it. A fresh `pip install -e .` in a clean venv will install Genesis
successfully but fail at runtime the first time `create_tool` is called. This
only works on the dev machine because `anthropic` is installed transitively from
something else.

**Fix:** add `anthropic ~= 0.103.0` (or current) to `[project] dependencies`.

### 2. Meta-tool count is wrong in docs
Live server logs report **6 meta-tools**. README (§Quick Start example output,
§Connect to Claude Desktop closing line, §Built-in Meta-Tools table) and
CLAUDE.md all say **5**. Either a 6th tool was added and never documented, or
the count is stale. Reconcile against `META_TOOL_SCHEMAS` in
`genesis/meta_tools.py`.

### 3. Test count is wrong in docs
Live run: **29 tests pass**. CLAUDE.md and handover docs say 28.

### 4. Linux Claude Desktop row is misleading
README §Connect to Claude Desktop lists a Linux config path, but Claude Desktop
is not officially distributed for Linux. Either remove the row or annotate as
"(unofficial / community builds)".

---

## Should fix before public release

### Versioning / packaging
- Tighten pins on fast-moving deps: `mcp ~= 1.27.1`, `anthropic ~= 0.103.0`.
- Cap all other deps at next major: `<5` (jsonschema), `<7` (pyyaml), `<2`
  (python-dotenv), `<3` (requests), `<10` (pytest), `<2` (pytest-asyncio).
- Add `[project.urls]` (homepage, issues, repo) and PyPI classifiers.
- Consider committing a lockfile (`uv lock` or `pip freeze`-derived) for
  reproducible installs — important because generated code must pass a fixed
  validator across users.
- `requires-python = ">=3.11"` is fine as a floor, but you have only tested on
  3.14 locally. Document tested versions or add CI matrix.

### README
- Add a 10s demo GIF under the tagline. Highest sell-through item missing.
- Expand the Security Notes section: explicitly state that generated code runs
  in-process, that the import allowlist is the *only* sandbox, that network
  egress is unrestricted via allowed imports like `requests`, and that users
  should review `generated_tools/*.py` before sharing.
- Add a Troubleshooting section: missing `ANTHROPIC_API_KEY`, tool not
  appearing in Claude Desktop, validator rejection, wrong Python version, venv
  path wrong in config.
- Fix Windows command: `cp .env.example .env` → `copy .env.example .env` (or
  PowerShell `Copy-Item`).
- Inline the contents of `.env.example` so users know what to expect.
- Clarify line 128: hot-loaded tools are available immediately, not only after
  restart (current wording understates the feature).
- Either trim the inline `config.yaml` snippet or commit to keeping it in sync
  with the real file — currently risks drift.
- The `~$0.01–0.05 per tool` cost estimate is unverified. Measure or soften.

### .gitignore / repo hygiene
- Add `.pytest_cache/` to `.gitignore`.
- Add a non-Windows example output to `examples/notes_demo.md` so macOS/Linux
  users aren't second-class.
- Verify `registry.py` can rebuild `tools_manifest.json` from
  `generated_tools/*.py` on first run after a fresh clone — otherwise the
  user-specific manifest paths become a portability problem.

### Process / hygiene
- Before `git init && git add .`: visually inspect the staged file list.
  Confirm `.env`, `tools_manifest.json`, generated `.py` files, and
  `PROJECT_LOG.md` are not staged.
- README §Install references `github.com/adeoluwaadesinadboy/genesis-mcp.git` —
  verify the remote exists / will exist before publishing the link.

---

## Recommended focus areas for the Codex/Cursor security audit

The audit should spend the bulk of its time here, in priority order:

### P0 — Generated-code execution model
This is the unique risk surface of Genesis. The validator is the only line of
defense between an LLM-authored Python file and `importlib`-driven execution in
the server process.

- **Validator bypass attempts.** Can a generated tool evade the import
  allowlist via `__import__`, `importlib.import_module`, attribute access on an
  allowed module (`os.path.__loader__`, `requests.utils.__builtins__`), or
  string-built module names? Forbidden-call list covers `eval`/`exec`/
  `os.system`/`subprocess.*` — but check `compile`, `__builtins__`,
  `pickle.loads`, `marshal.loads`, `ctypes`, `breakpoint()`, `getattr` chains.
- **AST top-level side-effects check** — only catches calls. Does it catch
  decorators with side effects, class-level statements, dict/list comprehensions
  that hit the network?
- **Schema injection.** A malicious or weird `TOOL_SCHEMA` — does it crash the
  server, register over a meta-tool, or trigger pathological behavior in
  `list_tools`?
- **Filename / `name` field validation.** Is the `name` field sanitized before
  becoming a filesystem path? Path traversal via `../../foo`?
- **Concurrent registration races.** If two `create_tool` calls land at once,
  can one observe the other's half-written file?

### P1 — Process model & secrets
- Generated code shares the process with the Anthropic API key in env. A
  generated tool could trivially `print(os.environ)` over MCP. Document or
  redact.
- Network egress is open via `requests` for any generated tool — no egress
  policy. Document.
- Filesystem writes from generated handlers are unrestricted. Document.

### P2 — Supply chain
- Pinning (see §Should fix). Today's loose pins mean a malicious or broken
  `mcp` minor release silently flows to users.
- No lockfile means installs are not reproducible.

### P3 — Prompt-injection on the generator
- The prompt assembled in `generator.py` includes the user's natural-language
  description verbatim. Can a crafted description make the model produce
  validator-evading code (e.g., by claiming the allowlist should be ignored)?
  Worth an adversarial-prompt eval before public release.

---

## Out of scope for this pass (deliberately)

- Performance benchmarking
- Cross-platform test execution (only Windows / Python 3.14 was run)
- End-to-end re-test in Claude Desktop (already confirmed working by the user)
- Code-style / lint pass
- License compatibility of transitive deps
