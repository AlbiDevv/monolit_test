import assert from 'node:assert/strict';
import test from 'node:test';
import { rankDebtors } from '../src/ranking.ts';

const clients = Array.from({ length: 30 }, (_, index) => ({ id: index + 1, name: `Контрагент ${index + 1}`,
  department_id: 'completion', department: 'Комплектация', total: 50000, overdue: (index + 1) * 100,
  days: 30 - index, documents: 1 }));

test('amount top-15 remains the same when the display order is ascending', () => {
  const descending = rankDebtors(clients, 'overdue', '', 'overdue', true);
  const ascending = rankDebtors(clients, 'overdue', '', 'overdue', false);
  assert.deepEqual(ascending.map(r => r.id), descending.map(r => r.id).reverse());
  assert.equal(ascending[0].id, 16);
});
test('sorting by days does not replace the selected top by amount', () => {
  assert.deepEqual(rankDebtors(clients, 'overdue', '', 'days', true).map(r => r.id),
    Array.from({ length: 15 }, (_, i) => i + 16));
});
test('days top-15 is independent from amount and search is case insensitive', () => {
  assert.deepEqual(rankDebtors(clients, 'days', '', 'days', true).map(r => r.id),
    Array.from({ length: 15 }, (_, i) => i + 1));
  assert.equal(rankDebtors(clients, 'overdue', 'КОНТРАГЕНТ 30', 'overdue', true)[0].id, 30);
  assert.equal(rankDebtors(clients, 'overdue', 'missing', 'overdue', true).length, 0);
});
