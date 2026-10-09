PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL, source_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY, snapshot_date TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('actual', 'demo')),
    UNIQUE(snapshot_date, mode)
);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    department_id TEXT NOT NULL REFERENCES departments(id), source_filename TEXT NOT NULL,
    source_hash TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_count INTEGER NOT NULL, node_count INTEGER NOT NULL,
    control_sales INTEGER NOT NULL, control_total INTEGER NOT NULL,
    control_overdue INTEGER NOT NULL, control_our_debt INTEGER NOT NULL,
    UNIQUE(snapshot_id, department_id)
);
CREATE TABLE IF NOT EXISTS hierarchy_nodes (
    id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES hierarchy_nodes(id) ON DELETE CASCADE,
    source_row INTEGER NOT NULL, indent INTEGER NOT NULL, label TEXT NOT NULL, role TEXT NOT NULL,
    sales INTEGER NOT NULL, total INTEGER NOT NULL, overdue INTEGER NOT NULL, our_debt INTEGER NOT NULL,
    UNIQUE(import_id, source_row)
);
CREATE TABLE IF NOT EXISTS counterparties (
    id INTEGER PRIMARY KEY, department_id TEXT NOT NULL REFERENCES departments(id),
    name TEXT NOT NULL, UNIQUE(department_id, name)
);
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY, counterparty_id INTEGER NOT NULL REFERENCES counterparties(id),
    name TEXT NOT NULL, UNIQUE(counterparty_id, name)
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY, contract_id INTEGER NOT NULL REFERENCES contracts(id),
    allocation_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL, kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_balances (
    id INTEGER PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    hierarchy_node_id INTEGER REFERENCES hierarchy_nodes(id) ON DELETE CASCADE,
    source_row INTEGER NOT NULL, created_date TEXT, due_date TEXT, days_until INTEGER,
    sales INTEGER NOT NULL, total INTEGER NOT NULL CHECK(total >= 0),
    overdue INTEGER NOT NULL CHECK(overdue >= 0 AND overdue <= total),
    overdue_days INTEGER NOT NULL DEFAULT 0 CHECK(overdue_days >= 0),
    our_debt INTEGER NOT NULL, manager TEXT, unit_path TEXT NOT NULL,
    UNIQUE(snapshot_id, document_id)
);
CREATE INDEX IF NOT EXISTS idx_balance_snapshot ON document_balances(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_balance_due ON document_balances(snapshot_id, due_date);
CREATE INDEX IF NOT EXISTS idx_counterparty_department ON counterparties(department_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_mode_date ON snapshots(mode, snapshot_date);
