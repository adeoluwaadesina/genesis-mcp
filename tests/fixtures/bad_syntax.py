# Fixture: tool with a syntax error — should be rejected immediately

TOOL_SCHEMA = {
    "name": "bad_syntax_tool"
    "description": "missing comma above",
    "inputSchema": {"type": "object", "properties": {}, "required": []}
}


def handler(arguments: dict) -> dict:
    return {"status": "success", "data": None, "message": ""}
