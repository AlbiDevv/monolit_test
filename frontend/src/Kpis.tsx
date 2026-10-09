import { ArrowDownIcon, ArrowUpIcon } from '@radix-ui/react-icons';
import type { DashboardData, MetricKey } from './types';
import { money, numericDate, pct } from './format';
import { metricTone } from './metric-tone';

const cards = [
  { key: 'total' as MetricKey, title: 'Общая ДЗ' },
  { key: 'overdue' as MetricKey, title: 'Просроченная ДЗ' },
  { key: 'expected' as MetricKey, title: 'В подходе · 1–5 дней' },
  { key: 'forecast' as MetricKey, title: 'Прогноз · следующие 7 дней' },
];

export function Kpis({ data }: { data: DashboardData }) {
  return <div className="kpi-grid">
    {cards.map(({ key, title }) => {
      const metric = data.metrics[key];
      const tone = metricTone(key,metric.delta);
      return <article className={`metric-card metric-${key}`} key={key} data-testid={`kpi-${key}`}>
        <p className="metric-label">{title}</p>
        <div className="metric-value" title={money(metric.value)}>{money(metric.value)}</div>
        <div className="metric-description">{key === 'total' ? 'Весь непогашенный долг' : key === 'overdue' ? `${pct(data.totals.overdue_pct)} от общей задолженности` : key === 'expected' ? 'Плановое погашение через 1–5 дней' : `${numericDate(data.forecast_from)} — ${numericDate(data.forecast_to)}`}</div>
        <div className={`metric-delta delta-${tone}`}>
          {metric.delta === null ? <span className="delta-dash" title="Нет предыдущего среза">—</span> : <>
            {metric.delta < 0 ? <ArrowDownIcon /> : metric.delta > 0 ? <ArrowUpIcon /> : <span>—</span>}
            <span title={`Изменение: ${money(metric.delta)}; предыдущий срез: ${numericDate(data.previous_date)}`}>
              {metric.delta > 0 ? '+' : ''}{money(metric.delta)}{metric.delta_pct !== null ? ` (${metric.delta_pct > 0 ? '+' : ''}${pct(metric.delta_pct)})` : ''}
            </span>
          </>}
        </div>
      </article>;
    })}
  </div>;
}
