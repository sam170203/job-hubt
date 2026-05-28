from job_hunt.settings import get_data_dir, get_db_path


def test_default_data_dir_is_project_data(monkeypatch):
    monkeypatch.delenv("JOB_HUNT_DATA_DIR", raising=False)
    get_data_dir.cache_clear()
    assert get_data_dir().name == "data"


def test_env_override_data_dir(tmp_data_dir):
    assert get_data_dir() == tmp_data_dir


def test_db_path_lives_in_data_dir(tmp_data_dir):
    assert get_db_path() == tmp_data_dir / "jobs.db"
