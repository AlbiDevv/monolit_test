const number = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const money = (minor: number) => number.format(minor / 100);
export const pct = (value: number) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value) + '%';
export const shortDate = (iso: string) => new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(new Date(iso + 'T12:00:00'));
export const fullDate = (iso: string) => new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(iso + 'T12:00:00'));
export const numericDate = (iso: string | null) => iso ? iso.split('-').reverse().join('.') : '—';
export const million = (minor: number) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(minor / 100000000);
