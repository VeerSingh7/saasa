import pytest
from pathlib import Path
from app.db import database as db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Provide a fresh DB for each test by overriding DB_PATH to a temp file.

    This avoids interfering with any existing local DB and keeps tests isolated.
    """
    # Point DB_PATH to a temporary file for the duration of the test
    db_file = tmp_path / "inspection_data.db"
    # Monkeypatch the DB_PATH attribute in database module
    from app.db import database as database_module
    database_module.DB_PATH = db_file

    # Initialize schema (which will also run migrations)
    database_module.init_db()

    yield
