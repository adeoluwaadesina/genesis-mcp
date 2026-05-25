# Fixture: tool with forbidden imports — should be rejected by validator

import subprocess
import os

TOOL_SCHEMA = {
    "name": "bad_imports_tool",
    "description": "A tool with forbidden imports.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


def handler(arguments: dict) -> dict:
    """Handler that uses forbidden modules."""
    result = subprocess.check_output(["echo", "hello"])
    return {"status": "success", "data": result.decode(), "message": ""}
