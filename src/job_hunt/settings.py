"""Project settings — paths, env loading. No business logic."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_data_dir() -> Path:
    override = os.getenv("JOB_HUNT_DATA_DIR")
    if override:
        return Path(override)
    return PROJECT_ROOT / "data"


def get_db_path() -> Path:
    return get_data_dir() / "jobs.db"
