import { useEffect, useRef, useState } from 'react';
import { Cross2Icon, FileTextIcon } from '@radix-ui/react-icons';
import type { Counterparty, DocumentRow, Mode } from './types';
import { money, numericDate } from './format';
import { query, request } from './api';
import { documentTotals } from './document-totals';

export function DocumentDrawer({ client, mode, date, onClose }: { client: Counterparty; mode: Mode; date: string; onClose: () => void }) {
  const [rows, setRows] = useState<DocumentRow[] | null>(null);
  const [error, setError] = useState('');
  const loadedTotals = rows ? documentTotals(rows) : null;
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    node?.showModal();
    return () => { node?.close(); previousFocus?.focus(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setRows(null); setError('');
    request<{ documents: DocumentRow[] }>(`/api/documents?${query(mode, date)}&counterparty_id=${client.id}`, controller.signal)
      .then(result => setRows(result.documents)).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [client.id, mode, date]);
  return <dialog className="document-dialog" ref={dialog} aria-labelledby="document-title" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="drawer-inner"><div className="drawer-header"><div><p className="eyebrow">{client.department} · {numericDate(date)}{mode === 'demo' ? ' · Тестовые данные' : ''}</p><h2 id="document-title">{client.name}</h2></div><button className="icon-button close-button" onClick={onClose} aria-label="Закрыть документы"><Cross2Icon /></button></div>
      <div className="drawer-summary"><div><span>Общий долг</span><strong>{loadedTotals ? money(loadedTotals.total) : '—'}</strong></div><div><span>Просрочено</span><strong>{loadedTotals ? money(loadedTotals.overdue) : '—'}</strong></div><div><span>Максимальная просрочка</span><strong>{loadedTotals ? `${loadedTotals.days} дн.` : '—'}</strong></div></div>
      <p className="drawer-caption">Все документы контрагента в выбранном срезе. Платежи и корректировки сохранены отдельными строками.</p>
      {error ? <p role="alert" className="error-box">{error}</p> : rows === null ? <div className="skeleton h-48" aria-label="Загрузка документов" /> : <div className="table-scroll"><table className="documents-table"><thead><tr><th>Документ / договор</th><th>План оплаты</th><th>Долг</th><th>Просрочено</th><th>Дней</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.id}-${index}`}>
        <td><div className="document-name"><FileTextIcon /><span>{row.name}</span></div><small>{row.contract}</small><small>{row.manager ?? 'Менеджер не указан'} · строка источника {row.source_row}</small></td><td>{numericDate(row.due_date)}</td><td className="amount">{money(row.total)}</td><td className="amount">{money(row.overdue)}</td><td className="amount">{row.overdue > 0 ? row.overdue_days : '—'}</td>
      </tr>)}</tbody><tfoot><tr><td>ИТОГО · {rows.length} документов</td><td></td><td className="amount">{money(rows.reduce((sum, row) => sum + row.total, 0))}</td><td className="amount">{money(rows.reduce((sum, row) => sum + row.overdue, 0))}</td><td className="amount">{loadedTotals?.days ?? '—'}</td></tr></tfoot></table></div>}
    </div>
  </dialog>;
}
