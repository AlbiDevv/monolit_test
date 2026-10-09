import csv
import io

import pytest


@pytest.mark.parametrize("query", ["mode=invalid", "snapshot_date=2026-07-99", "department=missing",
                                 "snapshot_date=2026-07-09", "start=2026-07-09"])
def test_invalid_selections(client, query):
    assert client.get(f"/api/dashboard?{query}").status_code == 422


def test_duplicate_filter_is_not_double_count(client):
    response = client.get("/api/dashboard?department=completion&department=completion")
    assert response.status_code == 200
    assert response.json()["totals"]["total"] == 1120009050


def test_health_metadata_export(client):
    assert client.get("/api/health").json()["actual_snapshots"] == 1
    meta = client.get("/api/meta").json()
    assert len(meta["departments"]) == 2
    assert meta["snapshots"] == [{"date": "2026-07-08", "mode": "actual", "sources": 2,
                                  "departments": ["completion", "distribution"]}]
    response = client.get("/api/export?department=completion")
    assert response.status_code == 200
    assert "receivables-actual-2026-07-08.csv" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[1][3] == "11200090,50"
    assert rows[-1][2] == "ИТОГО"
    assert rows[-1][7] == "1182059,21"


def test_missing_document_and_injection(client):
    assert client.get("/api/documents?counterparty_id=999999&snapshot_date=2026-07-08").status_code == 404
    assert client.get("/api/documents?counterparty_id=-1&snapshot_date=2026-07-08").status_code == 422
    assert client.get("/api/documents?counterparty_id=9223372036854775808&snapshot_date=2026-07-08").status_code == 422
    assert client.get("/api/dashboard?department=completion%27%20OR%201%3D1").status_code == 422
