import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.importer import import_report
from backend.parser import parse_report

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def reports():
    paths = sorted((ROOT / "data" / "input").glob("*.xlsx"))
    if len(paths) != 2:
        pytest.skip("Source integration tests require the two supplied XLSX files in data/input")
    return {report.department_id: report for report in (parse_report(path) for path in paths)}


@pytest.fixture(scope="session")
def baseline_db(tmp_path_factory, reports):
    path = tmp_path_factory.mktemp("baseline") / "test.sqlite"
    for report in reports.values():
        import_report(report, path)
    return path


@pytest.fixture
def db_path(tmp_path, baseline_db):
    path = tmp_path / "test.sqlite"
    shutil.copy2(baseline_db, path)
    return path


@pytest.fixture
def client(db_path):
    with TestClient(create_app(db_path)) as api:
        yield api
