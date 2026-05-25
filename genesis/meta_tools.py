from __future__ import annotations

import ast
import inspect
import logging
from datetime import datetime, timezone
from pathlib import Path

from genesis.generator import build_generation_prompt
from genesis.loader import load_tool_file, LoadError
from genesis.registry import ToolEntry, get_registry

logger = logging.getLogger(__name__)

_META_TOOL_NAMES = {
    "create_tool", "register_tool", "list_tools",
    "delete_tool", "update_tool", "describe_tool",
}


# ── Schema definitions ────────────────────────────────────────────────────────

META_TOOL_SCHEMAS = {
    "create_tool": {
        "name": "create_tool",
        "description": "Describe a new MCP tool and receive a code generation prompt. Then call register_tool with the generated code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of the tool to create.",
                },
                "name_hint": {
                    "type": "string",
                    "description": "Optional suggested name (snake_case). Inferred from description if omitted.",
                },
            },
            "required": ["description"],
        },
    },
    "register_tool": {
        "name": "register_tool",
        "description": "Validate and register a generated tool file. Call this after create_tool or update_tool with the Python code you generated.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The complete Python source code of the tool file.",
                },
            },
            "required": ["code"],
        },
    },
    "list_tools": {
        "name": "list_tools",
        "description": "List all registered tools (built-in meta-tools and user-generated tools).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "enum": ["all", "generated", "meta"],
                    "description": "Which tools to return. Defaults to 'all'.",
                },
            },
        },
    },
    "delete_tool": {
        "name": "delete_tool",
        "description": "Remove a user-generated tool from the server and disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the generated tool to delete."},
            },
            "required": ["name"],
        },
    },
    "update_tool": {
        "name": "update_tool",
        "description": "Describe changes to an existing tool and receive a code generation prompt. Then call register_tool with the new code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the tool to update."},
                "new_description": {"type": "string", "description": "New natural language description."},
            },
            "required": ["name", "new_description"],
        },
    },
    "describe_tool": {
        "name": "describe_tool",
        "description": "Return the full schema and source code of any registered tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the tool to describe."},
            },
            "required": ["name"],
        },
    },
}


# ── Handlers ──────────────────────────────────────────────────────────────────

def create_tool(arguments: dict) -> dict:
    """Return a code generation prompt for Claude. Claude then calls register_tool with the result."""
    description = arguments.get("description", "").strip()
    if not description:
        return {"status": "error", "data": None, "message": "Missing required argument: description"}

    name_hint = arguments.get("name_hint", "").strip() or None
    registry = get_registry()
    existing_names = registry.names()

    prompt = build_generation_prompt(description, name_hint, existing_names)

    return {
        "status": "awaiting_code_generation",
        "data": {
            "generation_prompt": prompt,
            "next_action": "register_tool",
            "instructions": (
                "Generate the complete Python tool file following every rule in the prompt above. "
                "Output ONLY raw Python code — no markdown fences, no commentary. "
                "Then call register_tool with that code as the 'code' argument."
            ),
        },
        "message": (
            "Tool description received. "
            "Generate the Python code following the prompt in data.generation_prompt, "
            "then call register_tool(code=<your generated code>)."
        ),
    }


def register_tool(arguments: dict) -> dict:
    """Validate, write, and hot-load generated tool code into the live server."""
    from genesis.config import get_config
    from genesis.validator import validate

    code = arguments.get("code", "").strip()
    if not code:
        return {"status": "error", "data": None, "message": "Missing required argument: code"}

    # Strip accidental markdown fences
    import re
    code = re.sub(r"^```(?:python)?\n?", "", code)
    code = re.sub(r"\n?```$", "", code.strip()).strip()

    registry = get_registry()
    config = get_config()

    # Determine if this is an update (name already exists as generated tool)
    # Extract name from code to check before full validation
    tool_name = _extract_name_from_code(code)
    is_update = tool_name is not None and registry.get(tool_name) is not None and registry.get(tool_name).tool_type == "generated"

    # For updates, exclude the current name from uniqueness check
    existing_names = registry.names()
    if is_update and tool_name:
        existing_names = existing_names - {tool_name}

    errors = validate(code, existing_names)
    if errors:
        error_lines = "\n".join(
            f"  [{e.check}] {e.reason}" + (f" (line {e.line})" if e.line else "")
            for e in errors
        )
        return {
            "status": "error",
            "data": {"validation_errors": [e.to_dict() for e in errors]},
            "message": f"Code failed validation. Fix these issues and call register_tool again:\n{error_lines}",
        }

    # Re-extract name from validated code (guaranteed to have TOOL_SCHEMA now)
    tool_name = _extract_name_from_code(code)
    if not tool_name:
        return {"status": "error", "data": None, "message": "Could not extract tool name from TOOL_SCHEMA."}

    tool_dir = config.paths.generated_tools_dir
    tool_dir.mkdir(parents=True, exist_ok=True)
    file_path = tool_dir / f"{tool_name}.py"

    # Preserve original created_at if updating
    original_created_at = None
    if is_update:
        existing = registry.get(tool_name)
        if existing:
            original_created_at = existing.created_at

    file_path.write_text(code, encoding="utf-8")

    try:
        schema, handler = load_tool_file(file_path)
    except LoadError as e:
        file_path.unlink(missing_ok=True)
        return {"status": "error", "data": None, "message": f"Tool file failed to load after writing: {e}"}

    created_at = original_created_at or datetime.now(timezone.utc).isoformat()
    entry = ToolEntry(
        name=tool_name,
        description=schema.get("description", ""),
        schema=schema,
        handler=handler,
        file_path=file_path,
        created_at=created_at,
        tool_type="generated",
    )
    registry.register(entry)
    registry.save_manifest()

    action = "updated" if is_update else "created"
    return {
        "status": "success",
        "data": {
            "tool_name": tool_name,
            "file_path": str(file_path),
            "schema": schema,
            "ready": True,
            "action": action,
        },
        "message": f"Tool '{tool_name}' {action} and registered. You can now use it.",
    }


def list_tools(arguments: dict) -> dict:
    """List all registered tools filtered by type."""
    filter_val = arguments.get("filter", "all")
    if filter_val not in ("all", "generated", "meta"):
        filter_val = "all"

    registry = get_registry()
    tools = registry.list(filter=filter_val)

    return {
        "status": "success",
        "data": {"tools": tools, "count": len(tools)},
        "message": f"Found {len(tools)} tool(s).",
    }


def delete_tool(arguments: dict) -> dict:
    """Remove a generated tool from the registry and disk."""
    name = arguments.get("name", "").strip()
    if not name:
        return {"status": "error", "data": None, "message": "Missing required argument: name"}

    if name in _META_TOOL_NAMES:
        return {"status": "error", "data": None, "message": f"Cannot delete built-in meta-tool '{name}'."}

    registry = get_registry()
    entry = registry.get(name)

    if entry is None:
        return {"status": "error", "data": None, "message": f"Tool '{name}' not found."}

    if entry.tool_type == "meta":
        return {"status": "error", "data": None, "message": f"Cannot delete built-in meta-tool '{name}'."}

    registry.unregister(name)

    if entry.file_path and entry.file_path.exists():
        entry.file_path.unlink()

    registry.save_manifest()

    return {
        "status": "success",
        "data": {"deleted": name},
        "message": f"Tool '{name}' deleted successfully.",
    }


def update_tool(arguments: dict) -> dict:
    """Return a code generation prompt for updating an existing tool."""
    name = arguments.get("name", "").strip()
    new_description = arguments.get("new_description", "").strip()

    if not name:
        return {"status": "error", "data": None, "message": "Missing required argument: name"}
    if not new_description:
        return {"status": "error", "data": None, "message": "Missing required argument: new_description"}

    if name in _META_TOOL_NAMES:
        return {"status": "error", "data": None, "message": f"Cannot update built-in meta-tool '{name}'."}

    registry = get_registry()
    entry = registry.get(name)

    if entry is None:
        return {"status": "error", "data": None, "message": f"Tool '{name}' not found."}

    if entry.tool_type == "meta":
        return {"status": "error", "data": None, "message": f"Cannot update built-in meta-tool '{name}'."}

    # Exclude the existing name so Claude can reuse it
    existing_names = registry.names() - {name}
    prompt = build_generation_prompt(new_description, name_hint=name, existing_names=existing_names)

    return {
        "status": "awaiting_code_generation",
        "data": {
            "generation_prompt": prompt,
            "tool_name_required": name,
            "next_action": "register_tool",
            "instructions": (
                f"Generate the updated Python tool file. "
                f"The tool name MUST remain '{name}'. "
                "Output ONLY raw Python code — no markdown fences. "
                "Then call register_tool with that code."
            ),
        },
        "message": (
            f"Update requested for '{name}'. "
            "Generate new code following data.generation_prompt (keep the same tool name), "
            "then call register_tool(code=<your generated code>)."
        ),
    }


def describe_tool(arguments: dict) -> dict:
    """Return the schema and source code of any registered tool."""
    name = arguments.get("name", "").strip()
    if not name:
        return {"status": "error", "data": None, "message": "Missing required argument: name"}

    registry = get_registry()
    entry = registry.get(name)

    if entry is None:
        return {"status": "error", "data": None, "message": f"Tool '{name}' not found."}

    if entry.tool_type == "meta":
        meta_fn = _META_HANDLER_MAP.get(name)
        source = inspect.getsource(meta_fn) if meta_fn else "(source unavailable)"
        return {
            "status": "success",
            "data": {
                "name": name,
                "type": "meta",
                "description": entry.schema.get("description", ""),
                "schema": entry.schema,
                "source_code": source,
                "file_path": str(Path(__file__).relative_to(Path(__file__).parent.parent)),
                "editable": False,
                "created_at": None,
            },
            "message": f"Meta-tool '{name}' described. editable=false.",
        }

    source = "(source file missing)"
    if entry.file_path and entry.file_path.exists():
        source = entry.file_path.read_text(encoding="utf-8")

    return {
        "status": "success",
        "data": {
            "name": name,
            "type": "generated",
            "description": entry.schema.get("description", ""),
            "schema": entry.schema,
            "source_code": source,
            "file_path": str(entry.file_path),
            "editable": True,
            "created_at": entry.created_at,
        },
        "message": f"Tool '{name}' described.",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_name_from_code(code: str) -> str | None:
    """Extract TOOL_SCHEMA['name'] from code via AST without executing it."""
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "TOOL_SCHEMA":
                        val = ast.literal_eval(node.value)
                        return val.get("name")
    except Exception:
        pass
    return None


_META_HANDLER_MAP = {
    "create_tool": create_tool,
    "register_tool": register_tool,
    "list_tools": list_tools,
    "delete_tool": delete_tool,
    "update_tool": update_tool,
    "describe_tool": describe_tool,
}
