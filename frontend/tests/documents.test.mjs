import assert from 'node:assert/strict';
import test from 'node:test';
import { documentTotals } from '../src/document-totals.ts';

test('document totals use the loaded records and only positive overdue days',()=>{
  assert.deepEqual(documentTotals([{total:12345,overdue:2000,overdue_days:7},
    {total:6789,overdue:0,overdue_days:90},{total:111,overdue:111,overdue_days:14}]),
  {total:19245,overdue:2111,days:14});
  assert.deepEqual(documentTotals([]),{total:0,overdue:0,days:0});
});
