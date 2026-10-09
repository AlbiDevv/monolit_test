export type Mode = 'actual' | 'demo';
export type Status = 'normal' | 'attention' | 'critical';
export type MetricKey = 'total' | 'overdue' | 'expected' | 'forecast';
export interface Metric { value: number; previous: number | null; delta: number | null; delta_pct: number | null }
export interface Totals {
  total: number; overdue: number; expected: number; forecast: number;
  overdue_pct: number; documents: number; status: Status;
}
export interface Department extends Totals { id: string; name: string }
export interface Counterparty {
  id: number; name: string; department_id: string; department: string;
  total: number; overdue: number; days: number; documents: number;
}
export interface HistoryPoint extends Totals { date: string; departments: Department[] }
export interface Quality {
  department: string; filename: string; source_hash: string; imported_at: string;
  documents: number; nodes: number; control_total: number; control_overdue: number;
  differences: Record<string, number>; reconciled: boolean;
}
export interface DashboardData {
  mode: Mode; snapshot_date: string; previous_date: string | null;
  currency_label: string; minor_unit_scale: number; forecast_from: string; forecast_to: string;
  metrics: Record<MetricKey, Metric>; totals: Totals; departments: Department[];
  counterparties: Counterparty[]; top_amount: Counterparty[]; top_days: Counterparty[];
  history: HistoryPoint[]; quality: Quality[];
}
export interface Metadata {
  organization: string | null; currency_label: string;
  departments: { id: string; name: string }[];
  snapshots: { date: string; mode: Mode; sources: number; departments: string[] }[];
}
export interface DocumentRow {
  id: number; name: string; kind: string; contract: string; created_date: string | null;
  due_date: string | null; days_until: number | null; sales: number; total: number;
  overdue: number; overdue_days: number; our_debt: number; manager: string | null;
  source_row: number; source_filename: string;
}
