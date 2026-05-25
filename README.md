# Genesis MCP

**An MCP server with one tool — the tool that creates other tools.**

Genesis is a self-extending [Model Context Protocol](https://modelcontextprotocol.io/) server. It ships with 6 built-in meta-tools — most importantly `create_tool` and `register_tool` — that let you generate, register, and use new MCP tools at runtime by describing them in plain language. No code. No server restart.

---

## Quick Start

### 1. Prerequisites

- Python 3.11 or newer
- Claude Desktop (or any MCP-compatible client)

Genesis MCP itself does not require an API key — code generation runs on the
**host LLM** (e.g. Claude Desktop, Cursor), which supplies its own credentials
independently. The Genesis server never calls the Anthropic API.

### 2. Install

```bash
git clone https://github.com/adeoluwaadesinadboy/genesis-mcp.git
cd genesis-mcp
pip install -e .
```

Or with a virtual environment (recommended):

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e .
```

### 3. Test the server starts

```bash
python -m genesis.server
```

You should see log output like:

```
[INFO] genesis.server: Registry ready: 6 meta-tool(s), 0 generated tool(s).
[INFO] genesis.server: Starting Genesis MCP server 'genesis-mcp' v0.1.0 via stdio.
```

Press `Ctrl+C` to stop.

---

## Connect to Claude Desktop

Find your Claude Desktop config file:

| OS | Path |
|---|---|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` *(unofficial / community builds — Claude Desktop is not officially distributed for Linux)* |

Add Genesis MCP to the `mcpServers` section:

**macOS / Linux:**
```json
{
  "mcpServers": {
    "genesis": {
      "command": "python",
      "args": ["-m", "genesis.server"],
      "cwd": "/path/to/genesis-mcp"
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "genesis": {
      "command": "python",
      "args": ["-m", "genesis.server"],
      "cwd": "C:\\path\\to\\genesis-mcp"
    }
  }
}
```

Genesis itself does not need any environment variables. Your host application
(Claude Desktop, Cursor, etc.) authenticates to its own LLM provider separately.

If you're using a virtual environment, replace `"python"` with the full path to the venv interpreter:
- Windows: `"C:\\path\\to\\genesis-mcp\\.venv\\Scripts\\python.exe"`
- macOS/Linux: `"/path/to/genesis-mcp/.venv/bin/python"`

Restart Claude Desktop. You should see 6 Genesis tools available in the tools panel.

---

## Your First Tool

In Claude Desktop, try:

> **"Use create_tool to make a tool that converts Celsius to Fahrenheit."**

Claude will call `create_tool`, Genesis will generate and register it, and you can immediately use it in the same conversation:

> **"Use the new tool to convert 100 degrees Celsius."**

The tool is saved to `generated_tools/` and loaded automatically on the next server restart.

---

## Built-in Meta-Tools

| Tool | What it does |
|---|---|
| `create_tool` | Describe a new tool in natural language and receive a code generation prompt |
| `register_tool` | Validate and register generated tool code (called after `create_tool` or `update_tool`) |
| `list_tools` | List all tools (filter: `all` / `generated` / `meta`) |
| `delete_tool` | Remove a generated tool from registry and disk |
| `update_tool` | Regenerate an existing tool with a new description |
| `describe_tool` | Return the schema and source code of any tool |

---

## Demo Tools

See [`examples/`](examples/) for walkthroughs of three ready-to-create tools:

- [`weather_demo.md`](examples/weather_demo.md) — Fetch live weather via Open-Meteo (no API key needed)
- [`notes_demo.md`](examples/notes_demo.md) — Save markdown notes to `~/genesis_notes/`
- [`currency_demo.md`](examples/currency_demo.md) — Currency conversion via open.er-api.com (no API key needed)

---

## Configuration

Edit `config.yaml` to customize the import allowlist, paths, and server identity:

```yaml
validator:
  import_allowlist:
    - requests
    - json
    - datetime
    - pathlib
    - os.path
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

### Code generation cost

Genesis MCP does not make any LLM API calls itself. Code generation runs on
your **host LLM** (Claude Desktop, Cursor, etc.) and is billed by whatever
provider that host uses. There is no separate Genesis-side cost.

---

## Security Notes

**Read this before running Genesis.**

### Trust model (v0.1)

Genesis v0.1 runs LLM-generated Python code in the same process as the MCP server.
The AST validator in `genesis/validator.py` is the only gate between the code your
host LLM produces and `importlib`-driven execution. There is no sandbox, no
subprocess isolation, and no container.

**v0.1 is designed for local, single-user use only.**

Do **not**:
- Expose Genesis to multiple users on a shared machine.
- Connect Genesis to untrusted MCP clients.
- Run Genesis on a server reachable from a network you don't fully control.
- Treat anything in `generated_tools/` as trusted code without reading it first.

### How code reaches the server

1. You call `create_tool` with a natural-language description.
2. Genesis returns a generation prompt to the host LLM (Claude Desktop, Cursor, etc).
3. The **host LLM** generates the Python code — Genesis does **not** call the
   Anthropic API itself for code generation.
4. The host then calls `register_tool(code=...)` with that code.
5. Genesis validates the string and, if it passes, writes it to disk and hot-loads
   it into the running server.

Anything that lands in step 4 — whether from the LLM, a misconfigured client, or
a malicious caller — runs in-process if it passes the validator. **The validator
is the entire trust boundary.**

### What the v0.1 validator does prevent

- Imports outside the allowlist (`requests`, `json`, `datetime`, `pathlib`,
  `os.path`, `re`, `math`, `typing`, `urllib.parse`).
- Direct calls to `eval`, `exec`, `compile`, `__import__`.
- Calls to `os.system`, `os.popen`, `os.exec*`, `os.spawn*`,
  `subprocess.{run,call,check_call,check_output,Popen}`.
- Reflection bypasses: any reference to `__builtins__`, attribute access to
  dunder names (`__import__`, `__globals__`, `__loader__`, `__getattribute__`,
  `__builtins__`), and calls to `getattr` / `globals` / `locals` / `vars`.
- Module-level side effects (anything other than imports, assignments,
  function/class definitions, and docstrings).
- Invalid or non-literal `TOOL_SCHEMA`, missing `handler`, duplicate names.

### What the v0.1 validator does **NOT** prevent

The validator catches known dangerous patterns. It is **not a sandbox.** The
following are all possible from validated code today:

- **Filesystem reads and writes anywhere the server process can reach** —
  `open()` is a builtin, and `pathlib.Path.read_text` / `write_text` / `unlink`
  are allowlisted. A generated tool can read `~/.ssh/id_rsa`, `.env`, browser
  profiles, etc., or overwrite arbitrary files.
- **Unrestricted outbound HTTPS via `requests`** — any tool can POST to any URL.
  This is sufficient to exfiltrate any file or secret the process can read.
- **In-process secret exposure** — anything in the Genesis process environment
  is reachable through the file-read and HTTPS-egress techniques above, even
  though `os.environ` itself is blocked. Genesis v0.1 has no environment
  variables of its own, but anything you launch it with is exposed.
- **Denial-of-service from inside `handler`** — infinite loops, large memory
  allocations, and recursive calls are not bounded.
- **MRO / `__subclasses__` reflection chains** — `(()).__class__.__mro__[1].__subclasses__()`
  is not blocked in v0.1. (Tested gadgets on Python 3.14 are benign; treat as
  defense-in-depth gap.)
- **Path traversal in tool names** — a `TOOL_SCHEMA["name"]` like `../../evil`
  will write a `.py` file outside `generated_tools/`. (Tracked as F-04, fixed
  in v0.2.)
- **Race conditions on concurrent registration**, **corrupt `tools_manifest.json`
  crashing startup**, **tampered manifest loading arbitrary `.py` files** — all
  tracked for v0.2.

### What to do before running Genesis

1. Treat `generated_tools/*.py` as code you wrote yourself — open and read each
   file before relying on it.
2. Do not share `generated_tools/` directories between machines or users without
   review.
3. If you're going to write to disk or call external APIs from a generated tool,
   describe exactly which path or domain the tool may touch — and verify the
   generated code matches.
4. Avoid launching Genesis with sensitive environment variables in scope —
   they're reachable from validated tool code even though `os.environ` is blocked.

### v0.2 scope

Hardened sandboxing (subprocess isolation, egress allowlist, filesystem
confinement, path-traversal hardening, manifest validation) is planned for v0.2.
Until then, treat every line in `generated_tools/` as code you are personally
responsible for. See [`docs/security/SECURITY_FIXES_v0_1.md`](docs/security/SECURITY_FIXES_v0_1.md) for the
explicit list of issues fixed in v0.1 versus deferred.

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```

Run a single test file:

```bash
pytest tests/test_validator.py -v
```

---

## Documentation

- [`docs/security/`](docs/security/) — security audit trail
  ([`SECURITY_AUDIT_REPORT.md`](docs/security/SECURITY_AUDIT_REPORT.md),
  [`PRE_AUDIT_REPORT.md`](docs/security/PRE_AUDIT_REPORT.md),
  [`SECURITY_FIXES_v0_1.md`](docs/security/SECURITY_FIXES_v0_1.md),
  [`SECURITY_REVERIFY_v0_1.md`](docs/security/SECURITY_REVERIFY_v0_1.md))
- [`docs/history/`](docs/history/) — original planning artifacts, marked as
  historical. Preserved for design-decision context; **does not reflect the
  shipped architecture.** See `CLAUDE.md` for the current source of truth.

---

## License

MIT — see [LICENSE](LICENSE).
