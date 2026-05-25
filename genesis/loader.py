from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class LoadError(Exception):
    pass


def load_tool_file(file_path: Path) -> tuple[dict, Callable[[dict], dict]]:
    """
    Dynamically load a tool file and return (TOOL_SCHEMA, handler).
    Raises LoadError on any failure.
    """
    if not file_path.exists():
        raise LoadError(f"Tool file not found: {file_path}")

    module_name = f"genesis_tool_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise LoadError(f"Cannot create module spec for: {file_path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise LoadError(f"Error executing tool module '{file_path.name}': {e}") from e

    if not hasattr(module, "TOOL_SCHEMA"):
        raise LoadError(f"Tool file '{file_path.name}' missing TOOL_SCHEMA.")
    if not hasattr(module, "handler"):
        raise LoadError(f"Tool file '{file_path.name}' missing handler function.")

    schema = module.TOOL_SCHEMA
    handler = module.handler

    if not callable(handler):
        raise LoadError(f"'handler' in '{file_path.name}' is not callable.")

    return schema, handler
