from collections import Counter
from copy import deepcopy
from datetime import date

import pytest

import backend.metrics as metrics_module
from backend.db import connect, initialize
from backend.demo import seed_demo
from backend.importer import import_report
from backend.metrics import dashboard, percentage, status
from backend.parser import ImportValidationError, allocation_keys, minor_units, parse_date

EXPECTED = {
    "completion": (1120009050, 254524237, 110011221, 118205921, 258),
    "distribution": (7564646133, 669391009, 448139695, 1041699718, 688),
}


@pytest.mark.parametrize("department", EXPECTED)
def test_real_department_controls(db_path, department):
    with connect(db_path) as conn:
        result = dashboard(conn, "actual", date(2026, 7, 8), [department])
    values = result["totals"]
    assert tuple(values[key] for key in ["total", "overdue", "expected", "forecast", "documents"]) \
        == EXPECTED[department]
    assert result["previous_date"] is None
    assert all(metric["delta"] is None for metric in result["metrics"].values())
    assert result["quality"][0]["reconciled"]


def test_combined_controls_and_filters(client):
    combined = client.get("/api/dashboard").json()
    assert combined["totals"]["total"] == 8684655183
    assert combined["totals"]["overdue"] == 923915246
    assert combined["totals"]["expected"] == 558150916
    assert combined["totals"]["forecast"] == 1159905639
    assert combined["totals"]["documents"] == 946
    assert combined["forecast_from"] == "2026-07-09"
    assert combined["forecast_to"] == "2026-07-15"
    assert combined["snapshot_date"] == "2026-07-08"
    assert combined["totals"]["overdue_pct"] == percentage(923915246, 8684655183)
    assert sum(row["total"] for row in combined["departments"]) == combined["totals"]["total"]
    assert combined["history"][0]["total"] == combined["totals"]["total"]
    assert all(not any(row["differences"].values()) for row in combined["quality"])


def test_variable_depth_and_all_subtotals(reports):
    assert {node.indent for node in reports["completion"].leaves} == {12}
    assert {node.indent for node in reports["distribution"].leaves} == {16, 18}
    for report in reports.values():
        for node in report.nodes:
            if node.children:
                for key in node.amounts:
                    assert sum(child.amounts[key] for child in node.children) == node.amounts[key]
            else:
                assert node.parent.role == "contract"
                assert node.parent.parent.role == "counterparty"


def test_repeated_payment_allocations_are_preserved(reports, db_path):
    report = reports["distribution"]
    counts = Counter(node.label for node in report.leaves)
    assert sum(count > 1 for count in counts.values()) == 6
    assert len(set(allocation_keys(report).values())) == 688
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 946
        payments = conn.execute("SELECT COUNT(*) FROM documents WHERE kind='Поступление безналичных ДС'")
        assert payments.fetchone()[0] == 184


def test_idempotent_import(reports, db_path):
    for report in reports.values():
        result = import_report(report, db_path)
        assert result["status"] == "unchanged"
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM document_balances").fetchone()[0] == 946
        assert conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 2


def test_failed_replacement_rolls_back(reports, db_path):
    broken = deepcopy(reports["completion"])
    broken.source_hash = "invalid-new-hash"
    broken.controls["total"] += 1
    with pytest.raises(ValueError, match="импорт отменён"):
        import_report(broken, db_path)
    with connect(db_path) as conn:
        original = dashboard(conn, "actual", None, [])
        assert original["totals"]["total"] == 8684655183
        assert original["totals"]["documents"] == 946
        assert all(item["reconciled"] for item in original["quality"])


def test_changed_valid_import_replaces_snapshot(reports, db_path):
    replacement = deepcopy(reports["completion"])
    replacement.source_hash = "new-valid-hash"
    result = import_report(replacement, db_path)
    assert result["status"] == "imported"
    with connect(db_path) as conn:
        assert dashboard(conn, "actual", None, ["completion"])["totals"]["total"] == 1120009050
        assert conn.execute("SELECT COUNT(*) FROM document_balances").fetchone()[0] == 946
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_top_days_and_document_drilldown(client):
    result = client.get("/api/dashboard").json()
    assert len(result["top_amount"]) <= 15
    assert result["top_amount"] == sorted(result["counterparties"], key=lambda r: -r["overdue"])[:15]
    assert [r["days"] for r in result["top_days"]] == sorted([r["days"] for r in result["counterparties"]],
                                                            reverse=True)[:15]
    assert result["top_days"][0]["days"] == 75
    for row in result["counterparties"]:
        documents = client.get("/api/documents", params={"counterparty_id": row["id"],
                                                        "snapshot_date": "2026-07-08"}).json()["documents"]
        assert sum(item["total"] for item in documents) == row["total"]
        assert sum(item["overdue"] for item in documents) == row["overdue"]
        assert max(item["overdue_days"] for item in documents if item["overdue"] > 0) == row["days"]


def test_demo_isolation_and_idempotence(db_path):
    with connect(db_path) as conn:
        before = dashboard(conn, "actual", None, [])
    seed_demo(db_path)
    with connect(db_path) as conn:
        actual = dashboard(conn, "actual", None, [])
        demo = dashboard(conn, "demo", None, [])
    assert actual == before
    assert len(demo["history"]) == 14
    assert demo["previous_date"] == "2026-07-07"
    assert demo["metrics"]["total"]["delta"] == demo["totals"]["total"] - demo["history"][-2]["total"]
    assert demo["totals"] == actual["totals"]
    assert all(item["reconciled"] for item in demo["quality"])
    seed_demo(db_path)
    with connect(db_path) as conn:
        repeated = dashboard(conn, "demo", None, [])
        assert repeated["metrics"] == demo["metrics"]
        assert repeated["history"] == demo["history"]
        assert conn.execute("SELECT COUNT(*) FROM snapshots WHERE mode='demo'").fetchone()[0] == 14


def test_incomplete_previous_snapshot_is_not_zero_delta(db_path):
    with connect(db_path) as conn, conn:
        conn.execute("INSERT INTO snapshots(snapshot_date,mode) VALUES ('2026-07-07','actual')")
        snapshot_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO imports(snapshot_id,department_id,source_filename,source_hash,document_count,"
                     "node_count,control_sales,control_total,control_overdue,control_our_debt) "
                     "VALUES (?,'completion','partial','partial',0,0,0,0,0,0)", (snapshot_id,))
        combined = dashboard(conn, "actual", date(2026, 7, 8), [])
        assert combined["previous_date"] is None
        assert len(combined["history"]) == 1


def test_latest_all_departments_requires_a_complete_snapshot(db_path):
    with connect(db_path) as conn, conn:
        conn.execute("INSERT INTO snapshots(snapshot_date,mode) VALUES ('2026-07-09','actual')")
        snapshot_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO imports(snapshot_id,department_id,source_filename,source_hash,document_count,"
                     "node_count,control_sales,control_total,control_overdue,control_our_debt) "
                     "VALUES (?,'completion','partial','partial',0,0,0,0,0,0)", (snapshot_id,))
    with connect(db_path) as conn:
        assert dashboard(conn, "actual", None, [])["snapshot_date"] == "2026-07-08"
    seed_demo(db_path)
    with connect(db_path) as conn:
        assert dashboard(conn, "demo", None, [])["snapshot_date"] == "2026-07-08"


def test_response_does_not_mix_versions_during_a_concurrent_import(reports, db_path, monkeypatch):
    replacement = deepcopy(reports["completion"])
    replacement.source_hash = "concurrent-replacement"
    leaf = next(node for node in replacement.leaves if node.amounts["total"] > 0)
    leaf.amounts["total"] += 1
    for node in leaf.ancestors():
        node.amounts["total"] += 1
    replacement.controls["total"] += 1
    original_metrics = metrics_module.department_metrics
    imported = False

    def concurrent_write(conn, snapshot, departments):
        nonlocal imported
        rows = original_metrics(conn, snapshot, departments)
        if not imported:
            imported = True
            import_report(replacement, db_path)
        return rows

    monkeypatch.setattr(metrics_module, "department_metrics", concurrent_write)
    with connect(db_path) as conn:
        result = dashboard(conn, "actual", None, [])
    assert result["totals"]["total"] == 8684655183
    assert all(item["reconciled"] for item in result["quality"])
    assert result["history"][-1]["total"] == result["totals"]["total"]
    with connect(db_path) as conn:
        assert dashboard(conn, "actual", None, [])["totals"]["total"] == 8684655184


def test_date_boundaries_and_outstanding_not_sales(tmp_path):
    path = tmp_path / "boundaries.sqlite"
    initialize(path)
    with connect(path) as conn, conn:
        conn.execute("INSERT INTO organizations VALUES (1,'Test')")
        conn.execute("INSERT INTO departments VALUES ('completion',1,'Комплектация','Отдел комплектации')")
        conn.execute("INSERT INTO snapshots VALUES (1,'2026-07-08','actual')")
        conn.execute("INSERT INTO imports(id,snapshot_id,department_id,source_filename,source_hash,"
                     "document_count,node_count,control_sales,control_total,control_overdue,control_our_debt) "
                     "VALUES (1,1,'completion','test','test',7,0,700000,2800,100,0)")
        conn.execute("INSERT INTO counterparties VALUES (1,'completion','Boundary client')")
        conn.execute("INSERT INTO contracts VALUES (1,1,'Boundary contract')")
        for index, (due, days) in enumerate([('2026-07-07', -1), ('2026-07-08', 0), ('2026-07-09', 1),
                                           ('2026-07-13', 5), ('2026-07-14', 6), ('2026-07-15', 7),
                                           ('2026-07-16', 8)], 1):
            conn.execute("INSERT INTO documents VALUES (?,1,?,'Document','Реализация')", (index, str(index)))
            conn.execute("INSERT INTO document_balances(snapshot_id,import_id,document_id,source_row,"
                         "created_date,due_date,days_until,sales,total,overdue,overdue_days,our_debt,unit_path) "
                         "VALUES (1,1,?,?, '2026-07-01',?,?,100000,?,?,?,0,'test')",
                         (index, index, due, days if days >= 0 else None, index * 100,
                          100 if days < 0 else 0, 1 if days < 0 else 0))
        result = dashboard(conn, "actual", None, [])
    assert result["totals"]["total"] == 2800
    assert result["totals"]["expected"] == 700
    assert result["totals"]["forecast"] == 1800
    assert result["totals"]["overdue"] == 100


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (123.45, 12345), ("1 234,56", 123456),
                                               ("0.005", 1), (None, 0)])
def test_money(value, expected):
    assert minor_units(value) == expected


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "garbage"])
def test_invalid_money(value):
    with pytest.raises(ImportValidationError):
        minor_units(value)


def test_dates_and_thresholds():
    assert parse_date("08.07.2026") == date(2026, 7, 8)
    assert parse_date(None) is None
    assert percentage(0, 0) == 0
    assert [status(value, 100000) for value in [0, 9999, 10000, 19999, 20000]] == \
        ["normal", "normal", "attention", "attention", "critical"]


def test_status_uses_exact_money_not_rounded_percentage():
    assert percentage(1999999999, 10000000000) == 20
    assert status(1999999999, 10000000000) == "attention"
    assert status(999999999, 10000000000) == "normal"
    assert status(2000000000, 10000000000) == "critical"
    assert status(0, 0) == "normal"


def test_demo_preserves_original_creation_dates(db_path):
    seed_demo(db_path)
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM document_balances b JOIN snapshots s ON s.id=b.snapshot_id "
                            "WHERE s.mode='demo' AND b.created_date>s.snapshot_date").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM document_balances demo "
                            "JOIN snapshots ds ON ds.id=demo.snapshot_id "
                            "JOIN document_balances actual ON actual.document_id=demo.document_id "
                            "JOIN snapshots act ON act.id=actual.snapshot_id "
                            "WHERE ds.mode='demo' AND act.mode='actual' "
                            "AND demo.created_date!=actual.created_date").fetchone()[0] == 0
