from datetime import date, timedelta

JOINS = """
FROM document_balances b
JOIN documents doc ON doc.id=b.document_id
JOIN contracts contract ON contract.id=doc.contract_id
JOIN counterparties c ON c.id=contract.counterparty_id
JOIN departments d ON d.id=c.department_id
"""
METRIC_NAMES = ("total", "overdue", "expected", "forecast")


class SelectionError(ValueError):
    pass


def percentage(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 6) if denominator else 0.0


def status(overdue: int, total: int) -> str:
    if total > 0 and overdue * 100 >= total * 20:
        return "critical"
    if total > 0 and overdue * 100 >= total * 10:
        return "attention"
    return "normal"


def available_departments(conn, snapshot_id: int) -> list[str]:
    return [r[0] for r in conn.execute("SELECT department_id FROM imports WHERE snapshot_id=? "
                                      "ORDER BY department_id", (snapshot_id,))]


def resolve_selection(conn, mode: str, snapshot_date: date | None, departments: list[str]):
    chosen = list(dict.fromkeys(departments)) if departments else [r[0] for r in conn.execute(
        "SELECT id FROM departments ORDER BY id"
    )]
    if snapshot_date is None:
        candidates = conn.execute("SELECT * FROM snapshots WHERE mode=? ORDER BY snapshot_date DESC",
                                  (mode,)).fetchall()
        snapshot = next((candidate for candidate in candidates
                         if set(chosen).issubset(available_departments(conn, candidate["id"]))), None)
    else:
        snapshot = conn.execute("SELECT * FROM snapshots WHERE mode=? AND snapshot_date=?",
                                (mode, snapshot_date.isoformat())).fetchone()
    if not snapshot:
        raise SelectionError("Срез за выбранную дату не найден")
    available = available_departments(conn, snapshot["id"])
    if not chosen or any(department not in available for department in chosen):
        raise SelectionError("Срез неполный: для выбранных отделов нет всех данных на эту дату")
    return snapshot, chosen


def department_metrics(conn, snapshot, departments: list[str]) -> list[dict]:
    day = date.fromisoformat(snapshot["snapshot_date"])
    placeholders = ",".join("?" for _ in departments)
    rows = conn.execute(
        "SELECT d.id,d.name,COALESCE(SUM(b.total),0) AS total,COALESCE(SUM(b.overdue),0) AS overdue,"
        "COALESCE(SUM(CASE WHEN b.days_until BETWEEN 1 AND 5 THEN b.total ELSE 0 END),0) AS expected,"
        "COALESCE(SUM(CASE WHEN b.due_date BETWEEN ? AND ? THEN b.total ELSE 0 END),0) AS forecast,"
        "COUNT(*) AS documents " + JOINS + f" WHERE b.snapshot_id=? AND d.id IN ({placeholders}) "
        "GROUP BY d.id,d.name ORDER BY d.id",
        ((day + timedelta(days=1)).isoformat(), (day + timedelta(days=7)).isoformat(),
         snapshot["id"], *departments),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["overdue_pct"] = percentage(item["overdue"], item["total"])
        item["status"] = status(item["overdue"], item["total"])
        result.append(item)
    return result


def totals(rows: list[dict]) -> dict:
    result = {key: sum(row[key] for row in rows) for key in METRIC_NAMES}
    result["documents"] = sum(row["documents"] for row in rows)
    result["overdue_pct"] = percentage(result["overdue"], result["total"])
    result["status"] = status(result["overdue"], result["total"])
    return result


def complete_snapshots(conn, mode: str, departments: list[str], end: str, start: str | None = None):
    snapshots = conn.execute("SELECT * FROM snapshots WHERE mode=? AND snapshot_date<=? "
                             "AND (? IS NULL OR snapshot_date>=?) ORDER BY snapshot_date",
                             (mode, end, start, start)).fetchall()
    selected = set(departments)
    return [snapshot for snapshot in snapshots
            if selected.issubset(available_departments(conn, snapshot["id"]))]


def quality(conn, snapshot_id: int, departments: list[str]) -> list[dict]:
    placeholders = ",".join("?" for _ in departments)
    result = []
    for row in conn.execute(
        "SELECT i.*,d.name AS department_name,COALESCE(SUM(b.sales),0) AS stored_sales,"
        "COALESCE(SUM(b.total),0) AS stored_total,COALESCE(SUM(b.overdue),0) AS stored_overdue,"
        "COALESCE(SUM(b.our_debt),0) AS stored_our_debt,COUNT(b.id) AS stored_documents "
        "FROM imports i JOIN departments d ON d.id=i.department_id "
        "LEFT JOIN document_balances b ON b.import_id=i.id "
        f"WHERE i.snapshot_id=? AND i.department_id IN ({placeholders}) GROUP BY i.id ORDER BY d.id",
        (snapshot_id, *departments),
    ):
        differences = {key: row[f"stored_{key}"] - row[f"control_{key}"]
                       for key in ["sales", "total", "overdue", "our_debt"]}
        count_ok = row["stored_documents"] == row["document_count"]
        result.append({"department": row["department_name"], "filename": row["source_filename"],
                       "source_hash": row["source_hash"], "imported_at": row["imported_at"],
                       "documents": row["stored_documents"], "nodes": row["node_count"],
                       "control_total": row["control_total"], "control_overdue": row["control_overdue"],
                       "differences": differences, "reconciled": not any(differences.values()) and count_ok})
    return result


def dashboard(conn, mode: str, snapshot_date: date | None, departments: list[str],
              start: date | None = None) -> dict:
    # A concurrent import must not mix old KPI with new control totals or details.
    if not conn.in_transaction:
        conn.execute("BEGIN")
    snapshot, selected = resolve_selection(conn, mode, snapshot_date, departments)
    if start and start.isoformat() > snapshot["snapshot_date"]:
        raise SelectionError("Начало периода не может быть позже даты среза")
    rows = department_metrics(conn, snapshot, selected)
    current = totals(rows)
    all_history = complete_snapshots(conn, mode, selected, snapshot["snapshot_date"])
    earlier = [item for item in all_history if item["snapshot_date"] < snapshot["snapshot_date"]]
    previous = totals(department_metrics(conn, earlier[-1], selected)) if earlier else None
    metrics = {}
    for key in METRIC_NAMES:
        old = previous[key] if previous else None
        change = current[key] - old if old is not None else None
        metrics[key] = {"value": current[key], "previous": old, "delta": change,
                        "delta_pct": round(change / old * 100, 6) if old and change is not None else None}
    placeholders = ",".join("?" for _ in selected)
    clients = [dict(row) for row in conn.execute(
        "SELECT c.id,c.name,d.id AS department_id,d.name AS department,"
        "SUM(b.total) AS total,SUM(b.overdue) AS overdue,"
        "MAX(CASE WHEN b.overdue>0 THEN b.overdue_days ELSE 0 END) AS days,"
        "COUNT(*) AS documents " + JOINS + f" WHERE b.snapshot_id=? AND d.id IN ({placeholders}) "
        "GROUP BY c.id,c.name,d.id,d.name HAVING SUM(b.overdue)>0 "
        "ORDER BY overdue DESC,c.name,c.id", (snapshot["id"], *selected),
    )]
    history = []
    for item in all_history:
        if start and item["snapshot_date"] < start.isoformat():
            continue
        item_rows = department_metrics(conn, item, selected)
        history.append({"date": item["snapshot_date"], **totals(item_rows), "departments": item_rows})
    day = date.fromisoformat(snapshot["snapshot_date"])
    return {
        "mode": mode, "snapshot_date": snapshot["snapshot_date"],
        "previous_date": earlier[-1]["snapshot_date"] if earlier else None,
        "currency_label": "валюта управленческого учёта", "minor_unit_scale": 100,
        "forecast_from": (day + timedelta(days=1)).isoformat(),
        "forecast_to": (day + timedelta(days=7)).isoformat(),
        "metrics": metrics, "totals": current, "departments": rows,
        "counterparties": clients,
        "top_amount": clients[:15],
        "top_days": sorted(clients, key=lambda x: (-x["days"], -x["overdue"], x["name"], x["id"]))[:15],
        "history": history, "quality": quality(conn, snapshot["id"], selected),
        "status_thresholds": {"attention": 10, "critical": 20},
    }


def document_detail(conn, mode: str, snapshot_date: date, counterparty_id: int) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT doc.id,doc.name,doc.kind,contract.name AS contract,b.created_date,b.due_date,"
        "b.days_until,b.sales,b.total,b.overdue,b.overdue_days,b.our_debt,b.manager,b.source_row,"
        "i.source_filename " + JOINS + " JOIN snapshots s ON s.id=b.snapshot_id "
        "JOIN imports i ON i.id=b.import_id WHERE s.mode=? AND s.snapshot_date=? AND c.id=? "
        "ORDER BY b.overdue DESC,b.due_date,doc.id", (mode, snapshot_date.isoformat(), counterparty_id),
    )]
