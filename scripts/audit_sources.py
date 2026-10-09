"""Independent financial oracle: stdlib OOXML reader, SQLite and live HTTP API.

Does not import openpyxl, the application parser, or application metric functions.
Document rows are identified by their creation-date cells, independently of the
parser's leaf detection. Amounts are computed directly from original XML values.
"""
import argparse
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FIELDS = {"sales": "I", "total": "J", "overdue": "L", "our_debt": "N"}


def cents(value):
    return int((Decimal(str(value or "0")) * 100).quantize(Decimal("1")))


def read_source(path):
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(n.itertext()) for n in shared_xml.findall("s:si", NS)]
        styles = ET.fromstring(archive.read("xl/styles.xml"))
        indents = []
        for style in styles.find("s:cellXfs", NS):
            alignment = style.find("s:alignment", NS)
            indents.append(int(alignment.attrib.get("indent", 0)) if alignment is not None else 0)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        values, depths = {}, {}
        for cell in sheet.findall(".//s:sheetData/s:row/s:c", NS):
            address = cell.attrib["r"]
            raw = cell.find("s:v", NS)
            value = raw.text if raw is not None else None
            if cell.attrib.get("t") == "s" and value is not None:
                value = shared[int(value)]
            elif cell.attrib.get("t") == "inlineStr":
                value = "".join(cell.find("s:is", NS).itertext())
            values[address] = value
            depths[address] = indents[int(cell.attrib.get("s", 0))]
    stamp = re.search(r"Дата отчета:\s*(\d{2}\.\d{2}\.\d{4})", values["C4"])[1]
    day = datetime.strptime(stamp, "%d.%m.%Y").date()
    last_row = max(int(address[1:]) for address, value in values.items()
                   if re.fullmatch(r"A\d+", address) and value and value.strip().casefold() == "итого")
    department = "completion" if "комплектац" in values["A19"].casefold() else "distribution"
    controls = {key: cents(values.get(f"{column}{last_row}")) for key, column in FIELDS.items()}
    calculated = dict.fromkeys([*FIELDS, "expected", "forecast"], 0)
    documents = []
    clients = defaultdict(lambda: {"total": 0, "overdue": 0, "days": 0, "documents": 0})
    stack = []
    for row in range(17, last_row):
        label = values.get(f"A{row}")
        if not label:
            continue
        indent = depths[f"A{row}"]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        created = values.get(f"E{row}") or ""
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", created):
            amounts = {key: cents(values.get(f"{column}{row}")) for key, column in FIELDS.items()}
            for key in FIELDS:
                calculated[key] += amounts[key]
            days_until = values.get(f"H{row}")
            if days_until is not None and 1 <= int(days_until) <= 5:
                calculated["expected"] += amounts["total"]
            due = values.get(f"G{row}")
            if due:
                due_day = datetime.strptime(due, "%d.%m.%Y").date()
                if day + timedelta(days=1) <= due_day <= day + timedelta(days=7):
                    calculated["forecast"] += amounts["total"]
            client_name = stack[-2][1].strip()
            client = clients[client_name]
            client["total"] += amounts["total"]
            client["overdue"] += amounts["overdue"]
            client["documents"] += 1
            if amounts["overdue"] > 0:
                client["days"] = max(client["days"], int(values.get(f"M{row}") or 0))
            documents.append({"row": row, "label": label, **amounts})
        stack.append((indent, label))
    return {"department": department, "date": day.isoformat(), "filename": path.name,
            "controls": controls, "calculated": calculated, "documents": documents,
            "clients": dict(clients)}


def run_audit(db_path, base_url, paths):
    checks = []

    def check(condition, label):
        if not condition:
            raise RuntimeError("FAIL: " + label)
        checks.append(label)

    def api(endpoint, **params):
        with urlopen(base_url.rstrip("/") + endpoint + "?" + urlencode(params), timeout=10) as response:
            return json.load(response)

    sources = [read_source(path) for path in paths]
    check(len(sources) == 2, "01: два независимых исходных файла")
    check(len({s["date"] for s in sources}) == 1, "01: дата среза совпадает в двух исходниках")
    results = {}
    for source in sources:
        dep = source["department"]
        for key in FIELDS:
            check(source["calculated"][key] == source["controls"][key], f"02: {dep}, {key}: XML-документы = итог Excel")
        result = api("/api/dashboard", mode="actual", snapshot_date=source["date"], department=dep)
        check(result["snapshot_date"] == source["date"], f"01: {dep}, дата API = дата Excel")
        check(result["totals"]["documents"] == len(source["documents"]), f"03: {dep}, число документов")
        for key in ["total", "overdue", "expected", "forecast"]:
            check(result["totals"][key] == source["calculated"][key], f"04: {dep}, KPI {key} = независимый XML-расчёт")
            check(result["departments"][0][key] == source["calculated"][key], f"05: {dep}, детализация {key}")
        ratio = float(Decimal(source["calculated"]["overdue"]) / source["calculated"]["total"] * 100)
        check(abs(result["totals"]["overdue_pct"] - ratio) < .000001, f"05: {dep}, процент просрочки")
        expected_clients = {name: values for name, values in source["clients"].items() if values["overdue"] > 0}
        actual_clients = {r["name"]: {key: r[key] for key in ["total", "overdue", "days", "documents"]}
                          for r in result["counterparties"]}
        check(actual_clients == expected_clients, f"06: {dep}, суммы и максимальные дни всех должников")
        for key, expected_order in [
            ("top_amount", sorted(expected_clients, key=lambda n: (-expected_clients[n]["overdue"], n))[:15]),
            ("top_days", sorted(expected_clients,
                                key=lambda n: (-expected_clients[n]["days"], -expected_clients[n]["overdue"], n))[:15]),
        ]:
            check([r["name"] for r in result[key]] == expected_order, f"07: {dep}, состав и порядок {key}")
        for client in result["counterparties"]:
            rows = api("/api/documents", mode="actual", snapshot_date=source["date"],
                       counterparty_id=client["id"])["documents"]
            check(sum(r["total"] for r in rows) == client["total"]
                  and sum(r["overdue"] for r in rows) == client["overdue"]
                  and len(rows) == client["documents"], f"08: {dep}, документы контрагента {client['name']}")
        results[dep] = result
    combined = api("/api/dashboard", mode="actual", snapshot_date=sources[0]["date"])
    for key in ["total", "overdue", "expected", "forecast", "documents"]:
        check(combined["totals"][key] == sum(r["totals"][key] for r in results.values()),
              f"09: общий итог {key} = сумма отделов")
    check(combined["history"][-1]["total"] == combined["totals"]["total"]
          and combined["history"][-1]["overdue"] == combined["totals"]["overdue"],
          "09: точки графиков совпадают с KPI")
    with sqlite3.connect(db_path) as conn:
        check(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "10: SQLite integrity_check")
        check(not conn.execute("PRAGMA foreign_key_check").fetchall(), "10: все внешние ключи целы")
        stored = conn.execute("SELECT SUM(b.sales),SUM(b.total),SUM(b.overdue),SUM(b.our_debt),COUNT(*) "
                              "FROM document_balances b JOIN snapshots s ON s.id=b.snapshot_id "
                              "WHERE s.mode='actual' AND s.snapshot_date=?", (sources[0]["date"],)).fetchone()
        expected = tuple(sum(s["calculated"][key] for s in sources) for key in FIELDS) \
            + (sum(len(s["documents"]) for s in sources),)
        check(stored == expected, "10: непосредственный SQL-контроль = независимый XML-контроль")
    return {"result": "PASS", "check_groups": 10, "checks_passed": len(checks),
            "date": sources[0]["date"], "totals_minor_units": combined["totals"], "checks": checks}


def main():
    args_parser = argparse.ArgumentParser(description="Независимая сверка Excel, БД и работающего API")
    args_parser.add_argument("--db", type=Path, default=ROOT / "data" / "dashboard.sqlite")
    args_parser.add_argument("--url", default="http://127.0.0.1:8010")
    args = args_parser.parse_args()
    result = run_audit(args.db, args.url, sorted((ROOT / "data" / "input").glob("*.xlsx")))
    output = ROOT / "output" / "financial-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
