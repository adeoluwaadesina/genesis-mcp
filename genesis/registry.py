from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from genesis.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ToolEntry:
    name: str
    description: str
    schema: dict
    handler: Callable[[dict], dict]
    file_path: Optional[Path]
    created_at: Optional[str]
    tool_type: str  # "meta" or "generated"

    def to_manifest_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "file_path": str(self.file_path) if self.file_path else None,
            "created_at": self.created_at,
        }

    def to_list_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.tool_type,
            "created_at": self.created_at,
            "file_path": str(self.file_path) if self.file_path else None,
        }


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(self, entry: ToolEntry) -> None:
        self._tools[entry.name] = entry

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[ToolEntry]:
        return self._tools.get(name)

    def names(self) -> set[str]:
        return set(self._tools.keys())

    def list(self, filter: str = "all") -> list[dict]:
        entries = self._tools.values()
        if filter == "generated":
            entries = (e for e in entries if e.tool_type == "generated")
        elif filter == "meta":
            entries = (e for e in entries if e.tool_type == "meta")
        return [e.to_list_dict() for e in entries]

    def save_manifest(self) -> None:
        config = get_config()
        manifest_path = config.paths.manifest_file
        generated = [
            e.to_manifest_dict()
            for e in self._tools.values()
            if e.tool_type == "generated"
        ]
        manifest = {"version": 1, "tools": generated}
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def load_manifest(self) -> list[dict]:
        config = get_config()
        manifest_path = config.paths.manifest_file
        if not manifest_path.exists():
            return []
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tools", [])


_registry: Optional[Registry] = None


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry
