import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "dashboard.sqlite"


def database_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", str(DEFAULT_DB)))


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript((ROOT / "backend" / "schema.sql").read_text(encoding="utf-8"))


@contextmanager
def connect(path: Path):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()
