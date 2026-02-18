"""Tests for configuration loading."""

from pathlib import Path

from wattio.config import ensure_wattio_dir, load_config


def test_load_default_config() -> None:
    """Loading config without any files returns defaults."""
    config = load_config()
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4o"
    assert config.diary.enabled is True


def test_load_project_config(tmp_path: Path) -> None:
    """Project config overrides defaults."""
    wattio_dir = tmp_path / "wattio"
    wattio_dir.mkdir()
    config_file = wattio_dir / "config.toml"
    config_file.write_text(
        '[llm]\nprovider = "anthropic"\nmodel = "claude-sonnet-4-5-20250929"\n'
    )
    config = load_config(tmp_path)
    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-sonnet-4-5-20250929"
    # Diary should still be default
    assert config.diary.enabled is True


def test_ensure_wattio_dir(tmp_path: Path) -> None:
    """Ensure wattio directory structure is created."""
    wattio_dir = ensure_wattio_dir(tmp_path)
    assert (wattio_dir / "diary").is_dir()
    assert (wattio_dir / "knowledge" / "curated").is_dir()
