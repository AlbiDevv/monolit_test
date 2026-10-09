import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { CalendarIcon, DownloadIcon, FileTextIcon, InfoCircledIcon, ReloadIcon, MagnifyingGlassIcon, MixerHorizontalIcon } from '@radix-ui/react-icons';
import { query, request, selectionQuery } from './api';
import { DebtorTable } from './DebtorTable';
import { DocumentDrawer } from './DocumentDrawer';
import { fullDate, money, numericDate, pct } from './format';
import { Kpis } from './Kpis';
import { historyCaption } from './chart-options';
import { QualityPanel } from './QualityPanel';
import type { Counterparty, DashboardData, Metadata, Mode, Status, Totals } from './types';

const OverallChart = lazy(() => import('./Charts').then(m => ({ default: m.OverallChart })));
const ComparisonChart = lazy(() => import('./Charts').then(m => ({ default: m.ComparisonChart })));
const DepartmentChart = lazy(() => import('./Charts').then(m => ({ default: m.DepartmentChart })));
function Plot({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="skeleton h-[250px]" aria-label="Загрузка графика" />}>{children}</Suspense>;
}

const statuses: Record<Status, string> = { normal: 'Норма', attention: 'Внимание', critical: 'Критично' };
function Badge({ status }: { status: Status }) { return <span className={`status-badge status-${status}`}><i />{statuses[status]}</span>; }
function SummaryCells({ row }: { row: Totals }) {
  return <><td className="amount">{money(row.total)}</td><td className="amount overdue-amount">{money(row.overdue)}</td><td className="amount">{pct(row.overdue_pct)}</td><td className="amount">{money(row.expected)}</td><td className="amount">{money(row.forecast)}</td><td><Badge status={row.status} /></td></>;
}
function Loading() {
  return <div className="loading-layout" aria-busy="true" aria-label="Загрузка показателей"><div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{[1, 2, 3, 4].map(i => <div className="skeleton h-44" key={i} />)}</div><div className="skeleton mt-5 h-80" /><div className="skeleton mt-5 h-56" /></div>;
}

export function App() {
  const [meta, setMeta] = useState<Metadata | null>(null);
  const [loadedData, setLoadedData] = useState<{selection:string;payload:DashboardData} | null>(null);
  const [mode, setMode] = useState<Mode>('actual');
  const [date, setDate] = useState('');
  const [department, setDepartment] = useState('all');
  const [period, setPeriod] = useState('all');
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<Counterparty | null>(null);
  const [nav, setNav] = useState('overview');
  const dates = useMemo(() => meta?.snapshots.filter(s => s.mode === mode && (department === 'all'
    ? s.departments.length === meta.departments.length : s.departments.includes(department))) ?? [], [meta, mode, department]);
  const departments = useMemo(() => department === 'all' ? [] : [department], [department]);
  const selection = useMemo(() => selectionQuery(mode,date,departments,period),[mode,date,departments,period]);
  const data = loadedData?.selection === selection ? loadedData.payload : null;

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    request<Metadata>('/api/meta', controller.signal).then(result => {
      setMeta(result);
      setDate(old => old || result.snapshots.find(s => s.mode === 'actual' && s.departments.length === result.departments.length)?.date || '');
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    if (dates.length && !dates.some(s => s.date === date)) setDate(dates[0].date);
  }, [dates, date]);

  useEffect(() => {
    if (!date || !meta || !dates.some(s => s.date === date)) return;
    const controller = new AbortController();
    setLoadedData(null); setError(''); setSelected(null);
    request<DashboardData>(`/api/dashboard?${selection}`, controller.signal)
      .then(payload=>{ if (!controller.signal.aborted) setLoadedData({selection,payload}); }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [meta, mode, date, dates, departments, period, revision, selection]);

  function changeMode(next: Mode) {
    const available = meta?.snapshots.filter(s => s.mode === next) ?? [];
    setMode(next);
    if (!available.some(s => s.date === date)) setDate(available[0]?.date ?? '');
  }
  const noSources = meta !== null && (meta.snapshots.length === 0 || dates.length === 0);
  const noHistory = data !== null && data.history.length < 2;
  const navItems = [
    { id: 'overview', label: 'Сводка' },
    { id: 'dynamics', label: 'Динамика' },
    { id: 'counterparties', label: 'Должники' },
    { id: 'quality', label: 'Сверка' },
  ];
  return <div className="app-shell">
    <a className="skip-link" href="#overview">Перейти к показателям</a>
    <div className="workspace">
      <header className="topbar"><a className="brand" href="#overview" aria-label="Монолит — начало отчёта"><img src="/brand-logo.svg" alt="Монолит" width="100" height="55" /></a><nav className="top-nav" aria-label="Разделы дашборда">{navItems.map(({ id, label }) => <a className={nav === id ? 'nav-item active' : 'nav-item'} href={`#${id}`} key={id} onClick={() => setNav(id)}>{label}</a>)}</nav><span className="topbar-source">{mode === 'actual' ? 'Отчёт по данным 1С' : 'Тестовая история'}</span></header>
      <main className="main-content" id="overview">
        <div className="page-heading"><div><h1>Дебиторская задолженность</h1><p className="report-subtitle">ТД «Монолит Р» · управленческий отчёт</p></div><a className={`export-button ${!data ? 'disabled-link' : ''}`} href={data ? `/api/export?${query(mode, date, departments)}` : undefined} aria-disabled={!data}><DownloadIcon />Экспорт CSV</a></div>
        <section className="filters" aria-label="Фильтры отчёта">
          <div className="filter-left"><span className="filter-label"><MixerHorizontalIcon />Отдел</span><div className="department-tabs"><button className={department === 'all' ? 'selected' : ''} onClick={() => setDepartment('all')}>Все отделы</button>{meta?.departments.map(d => <button key={d.id} className={department === d.id ? 'selected' : ''} onClick={() => setDepartment(d.id)}>{d.name}</button>)}</div></div>
          <div className="filter-right"><label className="date-field"><CalendarIcon /><span>Срез</span><select value={date} onChange={e => setDate(e.target.value)} aria-label="Дата среза">{dates.length ? dates.map(s => <option value={s.date} key={s.date}>{numericDate(s.date)}</option>) : <option value="">Нет срезов</option>}</select></label><label className="period-field"><span>Период графиков</span><select aria-label="Период графиков" value={period} onChange={e => setPeriod(e.target.value)}><option value="all">Все срезы</option><option value="7">Последние 7 дней</option><option value="14">Последние 14 дней</option><option value="30">Последние 30 дней</option></select></label><div className="mode-tabs" role="group" aria-label="Режим данных"><button aria-pressed={mode === 'actual'} className={mode === 'actual' ? 'selected' : ''} onClick={() => changeMode('actual')}>Факт</button><button aria-pressed={mode === 'demo'} className={mode === 'demo' ? 'selected' : ''} onClick={() => changeMode('demo')}>Тестовая история</button></div></div>
        </section>
        {mode === 'demo' && <div className="demo-notice" role="status"><InfoCircledIcon /><p><strong>Тестовая история.</strong> Искусственные данные: {meta?.snapshots.filter(s => s.mode === 'demo').length ?? 0} тестовых срезов для проверки графиков и дельт. Реальные показатели находятся в режиме «Факт».</p></div>}
        {error ? <div className="error-box" role="alert"><h2>Не удалось загрузить отчёт</h2><p>{error}</p><button className="secondary-button" onClick={() => setRevision(r => r + 1)}><ReloadIcon />Повторить</button></div> : noSources ? <div className="empty-state"><FileTextIcon /><h2>{mode === 'demo' ? 'Тестовая история пока не подготовлена' : 'Пока нет загруженных отчётов'}</h2><p>{mode === 'demo' ? 'Переключитесь на «Факт», чтобы увидеть реальные данные.' : 'После загрузки выгрузок здесь появятся показатели, отделы и документы.'}</p>{mode === 'demo' && <button className="secondary-button" onClick={() => changeMode('actual')}>Открыть реальные данные</button>}</div> : !data ? <Loading /> : <>
          <div className="snapshot-line"><span>Данные на {fullDate(data.snapshot_date)}</span><span>{data.totals.documents} документов<span className="dot-separator">·</span>{data.quality.length} {data.quality.length === 1 ? 'источник' : 'источника'}<span className="dot-separator">·</span>Валюта управленческого учёта</span></div>
          <Kpis data={data} /><p className="comparison-reference">{data.previous_date ? `Изменение к ${numericDate(data.previous_date)}: сумма и процент.` : "Предыдущий срез отсутствует — сравнение недоступно."}</p>
          <section className="panel department-panel"><div className="panel-heading"><div><h2>Детализация по отделам</h2></div><span className="small-label">Порог внимания — 10% просрочки</span></div><div className="table-scroll"><table className="department-table"><thead><tr><th>Отдел</th><th>Общая ДЗ</th><th>Просроченная</th><th>% просрочки</th><th>В подходе <small>1–5 дней</small></th><th>Прогноз <small>следующие 7 дней</small></th><th>Статус</th></tr></thead><tbody>{data.departments.map(row => <tr key={row.id}><td><button className="department-name" onClick={() => setDepartment(row.id)}><span className={`department-dot ${row.id}`} />{row.name}</button></td><SummaryCells row={row} /></tr>)}</tbody><tfoot><tr><td>ИТОГО</td><SummaryCells row={data.totals} /></tr></tfoot></table></div></section>
          <div className="grid gap-4 xl:grid-cols-12 mt-5">
            <section className="panel xl:col-span-8"><div className="panel-heading"><div><h2>Общая и просроченная ДЗ</h2></div><span className="small-label">По дням · сумма и доля просрочки</span></div><Plot><OverallChart data={data} /></Plot><p className="chart-caption">{historyCaption(data)}</p></section>
            <section className="panel xl:col-span-4"><div className="panel-heading"><div><h2>Сравнение отделов</h2></div><span className="small-label">На {numericDate(data.snapshot_date)}</span></div><Plot><ComparisonChart data={data} /></Plot><p className="chart-caption">В подходе: документы со сроком оплаты через 1–5 дней.</p></section>
          </div>
          <section id="dynamics" className="mt-8 scroll-section"><div className="section-heading"><div><h2>Динамика по отделам</h2></div></div>{noHistory && <p className="history-notice"><InfoCircledIcon />{historyCaption(data)}</p>}<div className="grid gap-4 lg:grid-cols-2"><div className="panel"><div className="panel-heading"><h3>Общая задолженность</h3><span className="small-label">По отделам</span></div><Plot><DepartmentChart data={data} metric="total" /></Plot></div><div className="panel"><div className="panel-heading"><h3>Просроченная задолженность</h3><span className="small-label">По отделам</span></div><Plot><DepartmentChart data={data} metric="overdue" /></Plot></div></div></section>
          <section id="counterparties" className="mt-8 scroll-section"><div className="section-heading"><div><h2>Просроченная задолженность по контрагентам</h2></div><label className="search-field"><MagnifyingGlassIcon /><input aria-label="Поиск контрагента в топах" placeholder="Найти контрагента" value={search} onChange={e => setSearch(e.target.value)} /></label></div><div className="grid gap-4 xl:grid-cols-2"><section className="panel debtor-panel"><div className="panel-heading"><h3>Топ-15 по сумме просрочки</h3><span className="small-label">Нажмите на клиента для детализации</span></div><DebtorTable rows={data.counterparties} order="overdue" search={search} onSelect={setSelected} /></section><section className="panel debtor-panel"><div className="panel-heading"><h3>Топ-15 по дням просрочки</h3><span className="small-label">Максимальный срок по документам</span></div><DebtorTable rows={data.counterparties} order="days" search={search} onSelect={setSelected} /></section></div></section>
          <div className="mt-8 scroll-section"><QualityPanel data={data} /></div>

        </>}
      </main>
    </div>
    {selected && data && <DocumentDrawer client={selected} mode={data.mode} date={data.snapshot_date} onClose={() => setSelected(null)} />}
  </div>;
}
