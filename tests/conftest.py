"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with wattio structure."""
    wattio_dir = tmp_path / "wattio"
    (wattio_dir / "diary").mkdir(parents=True)
    (wattio_dir / "knowledge" / "curated").mkdir(parents=True)

    # Create a dummy .asc file
    ltspice_dir = tmp_path / "01 - LTspice" / "flyback"
    ltspice_dir.mkdir(parents=True)
    asc_file = ltspice_dir / "test.asc"
    asc_file.write_text("Version 4\nSHEET 1 880 680\nSYMBOL ind2 300 200 R0\n")

    return tmp_path
