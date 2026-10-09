import type { DocumentRow } from './types.ts';

export function documentTotals(rows: DocumentRow[]) {
  return {
    total: rows.reduce((sum,row)=>sum+row.total,0),
    overdue: rows.reduce((sum,row)=>sum+row.overdue,0),
    days: Math.max(0,...rows.filter(row=>row.overdue>0).map(row=>row.overdue_days)),
  };
}
