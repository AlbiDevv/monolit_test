import hashlib
import math
from datetime import date, timedelta
from pathlib import Path

from .db import connect, initialize


def seed_demo(db_path: Path, days: int = 14) -> dict:
    """Deterministic illustrative history. Never updates or compares against actual mode."""
    if not 2 <= days <= 60:
        raise ValueError("Длина демонстрационной истории должна быть от 2 до 60 дней")
    initialize(db_path)
    with connect(db_path) as conn, conn:
        base = conn.execute("SELECT s.* FROM snapshots s JOIN imports i ON i.snapshot_id=s.id "
                            "WHERE s.mode='actual' GROUP BY s.id "
                            "HAVING COUNT(DISTINCT i.department_id)=(SELECT COUNT(*) FROM departments) "
                            "ORDER BY s.snapshot_date DESC LIMIT 1").fetchone()
        if not base:
            raise ValueError("Сначала импортируйте реальные файлы")
        base_day = date.fromisoformat(base["snapshot_date"])
        base_imports = conn.execute("SELECT * FROM imports WHERE snapshot_id=? ORDER BY department_id",
                                   (base["id"],)).fetchall()
        conn.execute("DELETE FROM imports WHERE snapshot_id IN (SELECT id FROM snapshots WHERE mode='demo')")
        conn.execute("DELETE FROM snapshots WHERE mode='demo'")
        for offset in range(days - 1, -1, -1):
            day = base_day - timedelta(days=offset)
            cursor = conn.execute("INSERT INTO snapshots(snapshot_date,mode) VALUES (?, 'demo')",
                                  (day.isoformat(),))
            snapshot_id = cursor.lastrowid
            for source in base_imports:
                originals = conn.execute(
                    "SELECT b.*,doc.allocation_key FROM document_balances b "
                    "JOIN documents doc ON doc.id=b.document_id WHERE b.import_id=? ORDER BY b.id",
                    (source["id"],),
                ).fetchall()
                rows = []
                controls = dict.fromkeys(["sales", "total", "overdue", "our_debt"], 0)
                for original in originals:
                    if original["created_date"] > day.isoformat():
                        continue
                    fingerprint = int(hashlib.sha256(original["allocation_key"].encode()).hexdigest()[:8], 16)
                    # Only illustrative scenarios, not reconstructed historical receivables.
                    scale = 1 + offset * 0.011 + math.sin(offset * .7 + fingerprint % 9) * .035
                    amounts = {key: round(original[key] * scale) for key in controls}
                    due = date.fromisoformat(original["due_date"]) if original["due_date"] else None
                    if offset == 0:
                        amounts = {key: original[key] for key in controls}
                        overdue_days = original["overdue_days"]
                    else:
                        ratio = original["overdue"] / original["total"] if original["total"] else 0
                        amounts["overdue"] = round(amounts["total"] * (ratio or .65)) \
                            if due and due < day else 0
                        overdue_days = max(0, (day - due).days) if amounts["overdue"] else 0
                    amounts["overdue"] = min(amounts["total"], amounts["overdue"])
                    for key in controls:
                        controls[key] += amounts[key]
                    created = original["created_date"]
                    rows.append((original, created, due, amounts, overdue_days))
                cursor = conn.execute(
                    "INSERT INTO imports(snapshot_id,department_id,source_filename,source_hash,document_count,"
                    "node_count,control_sales,control_total,control_overdue,control_our_debt) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (snapshot_id, source["department_id"], "Демонстрационный сценарий " + day.isoformat(),
                     f"demo-v2:{source['source_hash']}:{day.isoformat()}", len(rows), 0,
                     controls["sales"], controls["total"], controls["overdue"], controls["our_debt"]),
                )
                import_id = cursor.lastrowid
                for original, created, due, amounts, overdue_days in rows:
                    conn.execute(
                        "INSERT INTO document_balances(snapshot_id,import_id,document_id,source_row,"
                        "created_date,due_date,days_until,sales,total,overdue,overdue_days,our_debt,manager,unit_path) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (snapshot_id, import_id, original["document_id"], original["source_row"], created,
                         due.isoformat() if due else None, (due - day).days if due and due >= day else None,
                         amounts["sales"], amounts["total"], amounts["overdue"], overdue_days,
                         amounts["our_debt"], original["manager"], original["unit_path"]),
                    )
    return {"mode": "demo", "snapshots": days, "from": (base_day - timedelta(days=days - 1)).isoformat(),
            "to": base_day.isoformat(), "status": "seeded"}
