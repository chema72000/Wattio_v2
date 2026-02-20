"""Configuration loading: defaults → user config → project config."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from wattio.models import WattioConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file, return empty dict if it doesn't exist."""
    if not path.is_file():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(project_dir: Path | None = None) -> WattioConfig:
    """Load configuration from all layers.

    Order (later overrides earlier):
      1. Hardcoded defaults (in WattioConfig)
      2. User config: ~/.config/wattio/config.toml
      3. Project config: <project_dir>/wattio/config.toml
    """
    # Load .env files
    if project_dir:
        load_dotenv(project_dir / ".env")
    load_dotenv()  # also load from ~/.env or cwd

    user_config_path = Path.home() / ".config" / "wattio" / "config.toml"
    user_data = _load_toml(user_config_path)

    project_data: dict[str, Any] = {}
    if project_dir:
        project_config_path = project_dir / "wattio" / "config.toml"
        project_data = _load_toml(project_config_path)

    merged = _deep_merge(user_data, project_data)
    return WattioConfig(**merged)


def ensure_wattio_dir(project_dir: Path) -> Path:
    """Create wattio/ directory structure if it doesn't exist."""
    wattio_dir = project_dir / "wattio"
    (wattio_dir / "diary").mkdir(parents=True, exist_ok=True)
    (wattio_dir / "knowledge" / "curated").mkdir(parents=True, exist_ok=True)
    (wattio_dir / "results").mkdir(parents=True, exist_ok=True)
    (wattio_dir / "sim_work").mkdir(parents=True, exist_ok=True)
    return wattio_dir
