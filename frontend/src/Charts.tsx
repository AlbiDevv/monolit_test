import { useEffect, useMemo, useRef } from 'react';
import { init, use } from 'echarts/core';
import { BarChart, LineChart } from 'echarts/charts';
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import type { DashboardData } from './types';
import { overallOptions, comparisonOptions, departmentOptions } from './chart-options';

use([LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent, AriaComponent, SVGRenderer]);
export function Chart({ option, label }: { option: EChartsOption; label: string }) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const chart = init(element.current, undefined, { renderer: 'svg' });
    chart.setOption({ ...option, aria: { enabled: true, description: label + ' Денежные значения — в валюте управленческого учёта. Точные суммы приведены в таблицах.' }, animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element.current);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [option, label]);
  return <div className="chart" ref={element} role="img" aria-label={label} />;
}

export function OverallChart({ data }: { data: DashboardData }) {
  const option = useMemo(() => overallOptions(data), [data]);
  return <Chart option={option} label="Общая и просроченная задолженность. Доля просрочки на правой оси в процентах." />;
}
export function ComparisonChart({ data }: { data: DashboardData }) {
  const option = useMemo(() => comparisonOptions(data), [data]);
  return <Chart option={option} label="Сравнение общей, просроченной и ожидаемой задолженности по отделам." />;
}
export function DepartmentChart({ data, metric }: { data: DashboardData; metric: 'total' | 'overdue' }) {
  const option = useMemo(() => departmentOptions(data, metric), [data, metric]);
  return <Chart option={option} label={`Динамика ${metric === 'total' ? 'общей' : 'просроченной'} задолженности по отделам.`} />;
}
