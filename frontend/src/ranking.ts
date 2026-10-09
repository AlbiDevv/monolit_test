import type { Counterparty } from './types';

export function rankDebtors(rows: Counterparty[], order: 'overdue' | 'days', search: string,
  sort: 'overdue' | 'days', descending: boolean): Counterparty[] {
  const top = rows.filter(row => row.name.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru')))
    .sort((a, b) => b[order] - a[order] || b.overdue - a.overdue || a.name.localeCompare(b.name, 'ru'))
    .slice(0, 15);
  return top.sort((a, b) => (descending ? -1 : 1) * (a[sort] - b[sort]) || b.overdue - a.overdue || a.name.localeCompare(b.name, 'ru'));
}
