import { useMemo, useState } from 'react';
import { ArrowDownIcon, ArrowRightIcon, ArrowUpIcon } from '@radix-ui/react-icons';
import type { Counterparty } from './types';
import { money } from './format';
import { rankDebtors } from './ranking';

export function DebtorTable({ rows, order, search, onSelect }: {
  rows: Counterparty[]; order: 'overdue' | 'days'; search: string; onSelect: (row: Counterparty) => void;
}) {
  const [descending, setDescending] = useState(true);
  const [sort, setSort] = useState<'overdue' | 'days'>(order);
  const selected = useMemo(() => rankDebtors(rows, order, search, sort, descending), [rows, order, search, descending, sort]);
  function toggle(key: 'overdue' | 'days') {
    if (key === sort) setDescending(!descending); else { setSort(key); setDescending(true); }
  }
  const header = (key: 'overdue' | 'days', text: string) => <th className="text-right" aria-sort={sort === key ? descending ? 'descending' : 'ascending' : 'none'}>
    <button className="sort-button" onClick={() => toggle(key)}>{text}{sort === key ? descending ? <ArrowDownIcon /> : <ArrowUpIcon /> : null}</button>
  </th>;
  return <div className="table-scroll"><table className="debtors-table">
    <thead><tr><th className="rank">#</th><th>Контрагент / отдел</th>{order === 'overdue' ? <>{header('overdue', 'Сумма')}{header('days', 'Дней')}</> : <>{header('days', 'Дней')}{header('overdue', 'Сумма')}</>}<th className="sr-only">Документы</th></tr></thead>
    <tbody>{selected.length ? selected.map((row, index) => <tr key={row.id}>
      <td className="rank">{index + 1}</td><td><button className="debtor-name" onClick={() => onSelect(row)}>{row.name}</button><span className="debtor-department">{row.department}</span></td>
      {order === 'overdue' ? <><td className="amount">{money(row.overdue)}</td><td className="days-cell"><span className={row.days > 30 ? 'long-overdue' : ''}>{row.days}</span></td></> : <><td className="days-cell"><span className={row.days > 30 ? 'long-overdue' : ''}>{row.days}</span></td><td className="amount">{money(row.overdue)}</td></>}
      <td className="drill-cell"><button aria-label={`Документы: ${row.name}`} className="icon-button" onClick={() => onSelect(row)}><ArrowRightIcon /></button></td>
    </tr>) : <tr><td colSpan={5} className="empty-cell">{search ? 'По запросу ничего не найдено. Попробуйте другое название.' : 'Просроченной задолженности нет.'}</td></tr>}</tbody>
  </table></div>;
}
