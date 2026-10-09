import assert from 'node:assert/strict';
import test from 'node:test';
import { metricTone } from '../src/metric-tone.ts';

test('only overdue direction carries a judgement; total debt and plans stay neutral',()=>{
  for(const key of ['total','expected','forecast']) {
    for(const delta of [-100,0,100,null]) assert.equal(metricTone(key,delta),'neutral');
  }
  assert.equal(metricTone('overdue',100),'risk');
  assert.equal(metricTone('overdue',-100),'improved');
  assert.equal(metricTone('overdue',0),'neutral');
});
