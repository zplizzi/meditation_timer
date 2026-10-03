import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

# Set by OpenHost because openhost.toml declares `sqlite = ["main"]`. `just run` sets it for local development.
DB_PATH_ENV = "OPENHOST_SQLITE_MAIN"

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def db_path() -> Path:
    raw = os.environ.get(DB_PATH_ENV)
    if not raw:
        raise RuntimeError(f'{DB_PATH_ENV} is not set — openhost.toml must declare sqlite = ["main"]')
    return Path(raw)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection. Cheap enough for a single-user app, and sidesteps cross-thread sharing."""
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.executescript(_SCHEMA_PATH.read_text())
    logger.info("initialized database at {}", path)
