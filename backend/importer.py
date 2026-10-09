from pathlib import Path

from .db import connect, initialize
from .parser import ParsedReport, allocation_keys, document_kind, parse_report


def import_report(report: ParsedReport, db_path: Path) -> dict:
    initialize(db_path)
    with connect(db_path) as conn, conn:
        conn.execute("INSERT OR IGNORE INTO organizations(name) VALUES (?)", (report.organization,))
        organization_id = conn.execute("SELECT id FROM organizations WHERE name=?",
                                       (report.organization,)).fetchone()[0]
        department = conn.execute("SELECT organization_id FROM departments WHERE id=?",
                                  (report.department_id,)).fetchone()
        if department and department[0] != organization_id:
            raise ValueError("Отдел с этим ключом уже относится к другой организации")
        conn.execute("INSERT OR IGNORE INTO departments VALUES (?, ?, ?, ?)",
                     (report.department_id, organization_id, report.department_name,
                      report.department_source_name))
        conn.execute("INSERT OR IGNORE INTO snapshots(snapshot_date,mode) VALUES (?, 'actual')",
                     (report.snapshot_date.isoformat(),))
        snapshot_id = conn.execute("SELECT id FROM snapshots WHERE mode='actual' AND snapshot_date=?",
                                   (report.snapshot_date.isoformat(),)).fetchone()[0]
        existing = conn.execute("SELECT id,source_hash FROM imports WHERE snapshot_id=? AND department_id=?",
                                (snapshot_id, report.department_id)).fetchone()
        if existing and existing["source_hash"] == report.source_hash:
            return {"department": report.department_name, "date": report.snapshot_date.isoformat(),
                    "documents": len(report.leaves), "status": "unchanged", "controls": report.controls}
        if existing:
            conn.execute("DELETE FROM imports WHERE id=?", (existing["id"],))
        cursor = conn.execute(
            "INSERT INTO imports(snapshot_id,department_id,source_filename,source_hash,document_count,"
            "node_count,control_sales,control_total,control_overdue,control_our_debt) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (snapshot_id, report.department_id, report.filename, report.source_hash, len(report.leaves),
             len(report.nodes), report.controls["sales"], report.controls["total"],
             report.controls["overdue"], report.controls["our_debt"]),
        )
        import_id = cursor.lastrowid
        node_ids = {}
        for node in report.nodes:
            cursor = conn.execute(
                "INSERT INTO hierarchy_nodes(import_id,parent_id,source_row,indent,label,role,"
                "sales,total,overdue,our_debt) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (import_id, node_ids.get(node.parent.row) if node.parent else None, node.row,
                 node.indent, node.label, node.role, node.amounts["sales"], node.amounts["total"],
                 node.amounts["overdue"], node.amounts["our_debt"]),
            )
            node_ids[node.row] = cursor.lastrowid
        keys = allocation_keys(report)
        for node in report.leaves:
            client = node.parent.parent
            contract = node.parent
            conn.execute("INSERT OR IGNORE INTO counterparties(department_id,name) VALUES (?,?)",
                         (report.department_id, client.label))
            client_id = conn.execute("SELECT id FROM counterparties WHERE department_id=? AND name=?",
                                     (report.department_id, client.label)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO contracts(counterparty_id,name) VALUES (?,?)",
                         (client_id, contract.label))
            contract_id = conn.execute("SELECT id FROM contracts WHERE counterparty_id=? AND name=?",
                                       (client_id, contract.label)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO documents(contract_id,allocation_key,name,kind) VALUES (?,?,?,?)",
                         (contract_id, keys[node.row], node.label, document_kind(node.label)))
            document_id = conn.execute("SELECT id FROM documents WHERE allocation_key=?",
                                       (keys[node.row],)).fetchone()[0]
            ancestors = node.ancestors()
            manager = next((n.label for n in reversed(ancestors) if n.role == "manager"), None)
            conn.execute(
                "INSERT INTO document_balances(snapshot_id,import_id,document_id,hierarchy_node_id,"
                "source_row,created_date,due_date,days_until,sales,total,overdue,overdue_days,our_debt,"
                "manager,unit_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (snapshot_id, import_id, document_id, node_ids[node.row], node.row,
                 node.created.isoformat(), node.due.isoformat() if node.due else None, node.days_until,
                 node.amounts["sales"], node.amounts["total"], node.amounts["overdue"], node.overdue_days,
                 node.amounts["our_debt"], manager, " / ".join(n.label for n in ancestors[:-2])),
            )
        stored = conn.execute("SELECT SUM(sales), SUM(total), SUM(overdue), SUM(our_debt),COUNT(*) "
                              "FROM document_balances WHERE import_id=?", (import_id,)).fetchone()
        expected = (*[report.controls[key] for key in ["sales", "total", "overdue", "our_debt"]],
                    len(report.leaves))
        if tuple(stored) != expected:
            raise ValueError("Суммы записанных документов не совпали с контролем; импорт отменён")
    return {"department": report.department_name, "date": report.snapshot_date.isoformat(),
            "documents": len(report.leaves), "status": "imported", "controls": report.controls}


def import_file(path: Path, db_path: Path) -> dict:
    return import_report(parse_report(path), db_path)
