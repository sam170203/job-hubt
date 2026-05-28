"""Pytest fixtures shared across tests."""
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_dir(monkeypatch):
    """Point JOB_HUNT_DATA_DIR at a fresh tempdir and clear cached path."""
    from job_hunt import settings

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("JOB_HUNT_DATA_DIR", tmp)
        settings.get_data_dir.cache_clear()
        yield Path(tmp)
        settings.get_data_dir.cache_clear()
