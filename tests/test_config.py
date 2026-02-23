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


def test_ensure_wattio_dir_creates_results_and_sim_work(tmp_path: Path) -> None:
    """Ensure results/ and sim_work/ are also created."""
    wattio_dir = ensure_wattio_dir(tmp_path)
    assert (wattio_dir / "results").is_dir()
    assert (wattio_dir / "sim_work").is_dir()


# ── _deep_merge tests ──────────────────────────────────────────────

from wattio.config import _deep_merge, _load_toml


def test_deep_merge_nested_override() -> None:
    base = {"llm": {"provider": "openai", "model": "gpt-4o"}}
    override = {"llm": {"model": "gpt-4-turbo"}}
    merged = _deep_merge(base, override)
    assert merged["llm"]["provider"] == "openai"
    assert merged["llm"]["model"] == "gpt-4-turbo"


def test_deep_merge_non_overlapping_keys() -> None:
    base = {"a": 1, "b": {"x": 10}}
    override = {"c": 3, "b": {"y": 20}}
    merged = _deep_merge(base, override)
    assert merged["a"] == 1
    assert merged["c"] == 3
    assert merged["b"]["x"] == 10
    assert merged["b"]["y"] == 20


def test_load_toml_nonexistent(tmp_path: Path) -> None:
    result = _load_toml(tmp_path / "nonexistent.toml")
    assert result == {}


def test_load_toml_valid(tmp_path: Path) -> None:
    toml_file = tmp_path / "test.toml"
    toml_file.write_text('[section]\nkey = "value"\n')
    result = _load_toml(toml_file)
    assert result["section"]["key"] == "value"
