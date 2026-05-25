from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.models import InitializationOptions

from genesis.config import get_config
from genesis.loader import load_tool_file, LoadError
from genesis.meta_tools import META_TOOL_SCHEMAS, _META_HANDLER_MAP
from genesis.registry import ToolEntry, get_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def _boot_registry() -> None:
    """Load persisted tools from manifest into registry on startup."""
    config = get_config()
    registry = get_registry()

    # Register meta-tools
    for meta_name, schema in META_TOOL_SCHEMAS.items():
        handler_fn = _META_HANDLER_MAP[meta_name]
        entry = ToolEntry(
            name=meta_name,
            description=schema["description"],
            schema=schema,
            handler=handler_fn,
            file_path=Path(__file__),
            created_at=None,
            tool_type="meta",
        )
        registry.register(entry)

    # Load persisted generated tools
    manifest_entries = registry.load_manifest()
    loaded = 0
    for item in manifest_entries:
        name = item.get("name", "")
        file_path_str = item.get("file_path", "")
        if not name or not file_path_str:
            logger.warning("Skipping malformed manifest entry: %s", item)
            continue

        file_path = Path(file_path_str)
        try:
            schema, handler = load_tool_file(file_path)
        except LoadError as e:
            logger.warning("Skipping tool '%s': %s", name, e)
            continue

        entry = ToolEntry(
            name=name,
            description=schema.get("description", ""),
            schema=schema,
            handler=handler,
            file_path=file_path,
            created_at=item.get("created_at"),
            tool_type="generated",
        )
        registry.register(entry)
        loaded += 1
        logger.info("Loaded tool '%s' from disk.", name)

    logger.info(
        "Registry ready: %d meta-tool(s), %d generated tool(s).",
        len(META_TOOL_SCHEMAS),
        loaded,
    )


def _result_to_content(result: dict) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def run_server() -> None:
    config = get_config()
    _boot_registry()

    app = Server(config.server.name)
    registry = get_registry()

    @app.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=entry.name,
                description=entry.schema.get("description", ""),
                inputSchema=entry.schema.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for entry in registry._tools.values()
        ]

    @app.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        entry = registry.get(name)
        if entry is None:
            return _result_to_content({
                "status": "error",
                "data": None,
                "message": f"Unknown tool '{name}'. Use list_tools to see available tools.",
            })

        try:
            result = entry.handler(arguments or {})
        except Exception as e:
            logger.exception("Error executing tool '%s'", name)
            result = {
                "status": "error",
                "data": None,
                "message": f"Tool '{name}' raised an unexpected error: {e}",
            }

        return _result_to_content(result)

    logger.info(
        "Starting Genesis MCP server '%s' v%s via stdio.",
        config.server.name,
        config.server.version,
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=config.server.name,
                server_version=config.server.version,
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
