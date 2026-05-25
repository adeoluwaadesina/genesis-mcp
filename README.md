# Genesis MCP

**An MCP server with one tool — the tool that creates other tools.**

Genesis is a self-extending [Model Context Protocol](https://modelcontextprotocol.io/) server. It ships with 6 built-in meta-tools — most importantly `create_tool` and `register_tool` — that let you generate, register, and use new MCP tools at runtime by describing them in plain language. No code. No server restart.

---

## Quick Start

### 1. Prerequisites

- Python 3.11 or newer
- An [Anthropic API key](https://console.anthropic.com/)
- Claude Desktop (or any MCP-compatible client)

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

### 3. Set your API key

```bash
cp .env.example .env
```

Edit `.env` and replace the placeholder:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Test the server starts

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
      "cwd": "/path/to/genesis-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-your-key-here"
      }
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
      "cwd": "C:\\path\\to\\genesis-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-your-key-here"
      }
    }
  }
}
```

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

Edit `config.yaml` to customize:

```yaml
generator:
  model: claude-sonnet-4-6      # change to claude-haiku-4-5-20251001 for cheaper generation
  temperature: 0
  max_tokens: 2000
  max_retries: 1

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
```

### API cost per tool generation

| Model | Approx. cost |
|---|---|
| `claude-sonnet-4-6` (default) | ~$0.01–0.05 per tool |
| `claude-haiku-4-5-20251001` | Significantly less; suitable for ~90% of tools |

To use Haiku, change `model` in `config.yaml`. Haiku is capable of following the strict tool template and is the recommended choice for cost-sensitive usage.

---

## Security Notes

Genesis v1 uses an import allowlist (not full sandboxing). Generated tool files execute in the same process as the server. This is safe for personal local use — do not run Genesis on shared or networked systems without additional isolation.

Generated tools may contain hardcoded API keys if you describe a tool that uses authenticated APIs. **Do not share tool files without reviewing them first.**

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

## License

MIT — see [LICENSE](LICENSE).
