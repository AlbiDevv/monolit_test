import type { Mode } from './types';

export function query(mode: Mode, date: string, departments: string[] = [], start?: string) {
  const params = new URLSearchParams({ mode, snapshot_date: date });
  departments.forEach(id => params.append('department', id));
  if (start) params.set('start', start);
  return params.toString();
}

export function selectionQuery(mode: Mode, date: string, departments: string[], period: string): string {
  if (!date) return '';
  let start: string | undefined;
  if (period !== 'all') {
    const day = new Date(date + 'T12:00:00Z');
    day.setUTCDate(day.getUTCDate() - Number(period) + 1);
    start = day.toISOString().slice(0,10);
  }
  return query(mode,date,departments,start);
}

export async function request<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    let detail = 'Не удалось получить данные. Проверьте соединение и повторите попытку.';
    try {
      const error = await response.json();
      if (typeof error.detail === 'string') detail = error.detail;
    } catch { /* Keep the useful user-facing connection message for a non-JSON response. */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
