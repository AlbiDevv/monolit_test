import assert from 'node:assert/strict';
import test from 'node:test';
import { selectionQuery } from '../src/api.ts';

test('response identity changes with mode, date, department and range',()=>{
  const base=selectionQuery('actual','2026-07-08',[],'all');
  for(const changed of [selectionQuery('demo','2026-07-08',[],'all'),
    selectionQuery('actual','2026-07-07',[],'all'),selectionQuery('actual','2026-07-08',['completion'],'all'),
    selectionQuery('actual','2026-07-08',[],'7')]) assert.notEqual(changed,base);
  assert.equal(new URLSearchParams(selectionQuery('demo','2026-07-08',[],'7')).get('start'),'2026-07-02');
  assert.equal(selectionQuery('actual','',[],'all'),'');
});
