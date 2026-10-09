import type { EChartsOption } from 'echarts';
import type { DashboardData } from './types.ts';
import { million, money, pct, shortDate } from './format.ts';

const primary = '#783018', secondary = '#bb765c', slate = '#8b8177';

type TooltipItem = { name: string; seriesName: string; value: number; color: string };
const amountLabel = (raw: unknown) => money(Number((raw as { value: number }).value));
const percentLabel = (raw: unknown) => pct(Number((raw as { value: number }).value));
const escape = (s: string) => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
function tooltip(raw: unknown) {
  const items = (Array.isArray(raw) ? raw : [raw]) as TooltipItem[];
  return `<strong>${escape(items[0]?.name ?? '')}</strong>` + items.map(p =>
    `<div style="margin-top:7px;display:flex;gap:24px;justify-content:space-between"><span>${escape(p.seriesName)}</span><b>${p.seriesName.includes('%') ? pct(Number(p.value)) : money(Number(p.value))}</b></div>`).join('');
}

function base(): EChartsOption {
  return {
    animationDuration: 300, textStyle: { fontFamily: 'Geist, Segoe UI, sans-serif', color: '#786b63', fontSize: 12 },
    aria: { enabled: true }, color: [primary, secondary, slate],
    tooltip: { trigger: 'axis', confine: true, backgroundColor: '#fff', borderColor: '#e6ded7', padding: 14, textStyle: { color: '#281414', fontSize: 13 }, formatter: tooltip },
    legend: { type: 'scroll', left: 0, top: 0, icon: 'rect', itemWidth: 12, itemHeight: 4, itemGap: 18, textStyle: { color: '#786b63', fontSize: 12 } },
    grid: { left: 42, right: 24, top: 48, bottom: 29, containLabel: false },
    xAxis: { type: 'category', boundaryGap: false, axisTick: { show: false }, axisLine: { lineStyle: { color: '#e6ded7' } }, axisLabel: { margin: 12 } },
    yAxis: { type: 'value', min: 0, name: 'млн', nameTextStyle: { color: '#64584f' }, splitNumber: 4, splitLine: { lineStyle: { color: '#ede6df', type: 'dashed' } }, axisLabel: { formatter: (v: number) => million(v) } },
  };
}

export function singleActual(data: DashboardData): boolean {
  return data.mode === 'actual' && data.history.length === 1;
}
export function historyCaption(data: DashboardData): string {
  if (singleActual(data)) return `Один реальный срез — ${shortDate(data.snapshot_date)}, поэтому показаны точки. Линии появятся после загрузки срезов за другие дни.`;
  if (data.history.length === 1) return 'В выбранном периоде один тестовый срез. Для линии выберите более позднюю дату.';
  return `С ${shortDate(data.history[0].date)} по ${shortDate(data.snapshot_date)} · ${data.history.length} срезов`;
}
export function overallOptions(data: DashboardData): EChartsOption {

    const single = data.history.length === 1;

    return {
      ...base(), grid: { left: 43, right: 45, top: 48, bottom: 30 },
      xAxis: { ...(base().xAxis as object), boundaryGap: false, data: data.history.map(p => shortDate(p.date)) },
      yAxis: [base().yAxis as object, { type: 'value', min: 0, max: Math.max(30, ...data.history.map(p => p.overdue_pct + 5)), name: '%', splitLine: { show: false }, axisLabel: { formatter: (v: number) => Math.round(v) + '%' } }],
      series: [
        { type: 'line', name: 'Общая ДЗ', data: data.history.map(p => p.total), label: { show: single, position: 'top', formatter: amountLabel, color: primary, fontSize: 12 }, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: single ? 10 : 5, showSymbol: single, smooth: false },
        { type: 'line', name: 'Просроченная', data: data.history.map(p => p.overdue), label: { show: single, position: 'top', formatter: amountLabel, color: secondary, fontSize: 12 }, lineStyle: { width: 2 }, symbol: 'circle', symbolSize: single ? 10 : 5, showSymbol: single },
        { type: 'line', name: 'Доля просрочки, %', yAxisIndex: 1, data: data.history.map(p => p.overdue_pct), label: { show: single, position: 'right', offset: [55, 0], formatter: percentLabel, color: slate, fontSize: 12 }, lineStyle: { width: 2, type: 'dashed' }, symbol: single ? 'diamond' : 'circle', symbolSize: single ? 9 : 4, showSymbol: single },
      ],
    };
}

export function comparisonOptions(data: DashboardData): EChartsOption {
  return {
    ...base(), xAxis: { ...(base().xAxis as object), boundaryGap: true, data: data.departments.map(d => d.name) },
    color: [primary, secondary, '#fca91b'],
    series: [
      { type: 'bar', name: 'Общая ДЗ', barMaxWidth: 28, data: data.departments.map(d => d.total) },
      { type: 'bar', name: 'Просроченная', barMaxWidth: 28, data: data.departments.map(d => d.overdue) },
      { type: 'bar', name: 'В подходе', barMaxWidth: 28, data: data.departments.map(d => d.expected) },
    ],
  };
}

export function departmentOptions(data: DashboardData, metric: 'total' | 'overdue'): EChartsOption {

  return {
    ...base(), color: data.departments.map(d => d.id === 'completion' ? '#d18d21' : primary),
    xAxis: { ...(base().xAxis as object), boundaryGap: false, data: data.history.map(p => shortDate(p.date)) },
    series: data.departments.map(d => ({
      type: 'line', name: d.name,
      label: { show: data.history.length === 1, position: 'top', formatter: amountLabel, fontSize: 12 }, lineStyle: { width: 2.5 }, symbol: 'circle', symbolSize: 9,
      showSymbol: data.history.length < 3,
      data: data.history.map(p => p.departments.find(item => item.id === d.id)?.[metric] ?? null),
    })),
  };
}
