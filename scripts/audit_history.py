"""Independent SQL/HTTP checks of every snapshot, filter and previous-date delta."""
import argparse
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
JOINS = "FROM document_balances b JOIN documents doc ON doc.id=b.document_id " \
        "JOIN contracts ct ON ct.id=doc.contract_id JOIN counterparties c ON c.id=ct.counterparty_id"


def audit(db_path, base_url):
    checks = 0
    requests = 0

    def check(condition, message):
        nonlocal checks
        if not condition:
            raise RuntimeError(message)
        checks += 1

    def get(**params):
        nonlocal requests
        requests += 1
        with urlopen(base_url + "/api/dashboard?" + urlencode(params), timeout=10) as response:
            return json.load(response)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        snapshots = conn.execute("SELECT * FROM snapshots ORDER BY mode,snapshot_date").fetchall()
        for snapshot in snapshots:
            departments = [r[0] for r in conn.execute("SELECT department_id FROM imports WHERE snapshot_id=? "
                                                     "ORDER BY department_id", (snapshot["id"],))]
            for department in [None, *departments]:
                params = {"mode": snapshot["mode"], "snapshot_date": snapshot["snapshot_date"]}
                if department:
                    params["department"] = department
                result = get(**params)
                chosen = [department] if department else departments
                marks = ",".join("?" for _ in chosen)
                records = [dict(r) for r in conn.execute(
                    "SELECT b.*,c.id AS counterparty_id,c.name AS counterparty " + JOINS +
                    f" WHERE b.snapshot_id=? AND c.department_id IN ({marks})",
                    (snapshot["id"], *chosen),
                )]
                day = date.fromisoformat(snapshot["snapshot_date"])
                values = {
                    "total": sum(r["total"] for r in records),
                    "overdue": sum(r["overdue"] for r in records),
                    "expected": sum(r["total"] for r in records if r["days_until"] is not None
                                    and 1 <= r["days_until"] <= 5),
                    "forecast": sum(r["total"] for r in records if r["due_date"] and
                                    day + timedelta(days=1) <= date.fromisoformat(r["due_date"])
                                    <= day + timedelta(days=7)),
                }
                for key, value in values.items():
                    check(result["totals"][key] == value, f"{params}: incorrect {key}")
                    check(sum(d[key] for d in result["departments"]) == value, f"{params}: department sum")
                    check(result["history"][-1][key] == value, f"{params}: history endpoint")
                    check(result["metrics"][key]["value"] == value, f"{params}: KPI endpoint")
                check(result["totals"]["documents"] == len(records), f"{params}: document count")
                ratio = values["overdue"] / values["total"] * 100 if values["total"] else 0
                check(abs(result["totals"]["overdue_pct"] - ratio) <= .000001, f"{params}: percentage")
                expected_status = "critical" if values["total"] and values["overdue"]*100 >= values["total"]*20 \
                    else "attention" if values["total"] and values["overdue"]*100 >= values["total"]*10 \
                    else "normal"
                check(result["totals"]["status"] == expected_status, f"{params}: threshold classification")
                check(all(q["reconciled"] for q in result["quality"]), f"{params}: failed import control")
                if snapshot["mode"] == "demo":
                    check(all(r["created_date"] <= snapshot["snapshot_date"] for r in records),
                          f"{params}: a future document")
                previous = result["previous_date"]
                if previous:
                    old_params = dict(params, snapshot_date=previous)
                    old = get(**old_params)
                    for key, value in values.items():
                        metric = result["metrics"][key]
                        check(metric["previous"] == old["totals"][key], f"{params}: prior {key}")
                        check(metric["delta"] == value - old["totals"][key], f"{params}: delta {key}")
                        percent_change = round((value-old["totals"][key])/old["totals"][key]*100,6) \
                            if old["totals"][key] else None
                        check(metric["delta_pct"] == percent_change, f"{params}: relative delta {key}")
                else:
                    check(all(m["delta"] is None and m["previous"] is None
                              for m in result["metrics"].values()), f"{params}: fabricated previous date")
                for span in [7, 14]:
                    start = (day - timedelta(days=span - 1)).isoformat()
                    ranged = get(**params, start=start)
                    check(ranged["totals"] == result["totals"], f"{params}: period changed current figures")
                    check(ranged["metrics"] == result["metrics"], f"{params}: period changed deltas")
                    check(all(start <= p["date"] <= snapshot["snapshot_date"] for p in ranged["history"]),
                          f"{params}: invalid history period")
    return {"result": "PASS", "snapshots": len(snapshots), "http_requests": requests,
            "checks_passed": checks, "scope": "All snapshots, actual/demo, all/each department, 7/14-day ranges and deltas"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "dashboard.sqlite")
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    result = audit(args.db, args.url)
    (ROOT / "output").mkdir(parents=True, exist_ok=True)
    (ROOT / "output" / "history-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
