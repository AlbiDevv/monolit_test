import type { MetricKey } from './types.ts';

export function metricTone(key: MetricKey, delta: number | null): 'neutral' | 'improved' | 'risk' {
  if (key !== 'overdue' || delta === null || delta === 0) return 'neutral';
  return delta < 0 ? 'improved' : 'risk';
}
