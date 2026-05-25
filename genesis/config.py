from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
_ENV_PATH = Path(__file__).parent.parent / ".env"


@dataclass
class ValidatorConfig:
    import_allowlist: list[str]


@dataclass
class PathsConfig:
    generated_tools_dir: Path
    manifest_file: Path


@dataclass
class ServerConfig:
    name: str
    version: str


@dataclass
class Config:
    validator: ValidatorConfig
    paths: PathsConfig
    server: ServerConfig


_instance: Config | None = None


def get_config() -> Config:
    global _instance
    if _instance is None:
        _instance = _load()
    return _instance


def _load() -> Config:
    load_dotenv(_ENV_PATH)

    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    project_root = Path(__file__).parent.parent

    val = raw["validator"]
    paths = raw["paths"]
    srv = raw["server"]

    return Config(
        validator=ValidatorConfig(
            import_allowlist=val["import_allowlist"],
        ),
        paths=PathsConfig(
            generated_tools_dir=(project_root / paths["generated_tools_dir"]).resolve(),
            manifest_file=(project_root / paths["manifest_file"]).resolve(),
        ),
        server=ServerConfig(
            name=srv["name"],
            version=srv["version"],
        ),
    )
