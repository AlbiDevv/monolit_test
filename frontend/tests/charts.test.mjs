import assert from 'node:assert/strict';
import test from 'node:test';
import { overallOptions, departmentOptions, comparisonOptions, historyCaption } from '../src/chart-options.ts';

function dataset(mode, count) {
  const history = Array.from({ length: count }, (_, i) => ({ date: `2026-07-${String(i + 1).padStart(2,'0')}`,
    total: 30000 + i * 100, overdue: 6000 + i * 50, overdue_pct: 20,
    departments: [{ id:'completion', name:'Комплектация', total:10000+i*100, overdue:2000+i*50 },
      { id:'distribution', name:'Дистрибьюция', total:20000, overdue:4000 }] }));
  return { mode, snapshot_date: history.at(-1).date, history,
    departments: [{ id:'completion', name:'Комплектация', total:10000, overdue:2000, expected:1000 },
      { id:'distribution', name:'Дистрибьюция', total:20000, overdue:4000, expected:2000 }] };
}
for (const count of [1, 2, 14]) {
  test(`demo with ${count} dates always uses three lines and a right percentage axis`, () => {
    const data=dataset('demo',count), option=overallOptions(data);
    assert.deepEqual(option.series.map(s=>s.type), ['line','line','line']);
    assert.equal(option.series[2].lineStyle.type,'dashed');
    assert.equal(option.series[2].yAxisIndex,1);
    for(const [i,key] of ['total','overdue','overdue_pct'].entries()) assert.deepEqual(option.series[i].data,data.history.map(p=>p[key]));
    for(const metric of ['total','overdue']) {
      const dep=departmentOptions(data,metric);
      assert.deepEqual(dep.series.map(s=>s.type),['line','line']);
      assert.deepEqual(dep.series[0].data,data.history.map(p=>p.departments[0][metric]));
    }
  });
}
test('actual with multiple dates uses the time-series lines from the assignment',()=>{
  assert.deepEqual(overallOptions(dataset('actual',2)).series.map(s=>s.type),['line','line','line']);
});
test('one actual snapshot remains readable while one demo point stays a line',()=>{
  const data=dataset('actual',1);
  assert.deepEqual(overallOptions(data).series.map(s=>s.type),['line','line','line']);
  assert.match(historyCaption(data),/реальный срез/);
  assert.equal(overallOptions(dataset('demo',1)).series[0].showSymbol,true);
  assert.match(historyCaption(dataset('demo',1)),/тестовый срез/);
});
test('department comparison stays grouped bars in both modes',()=>{
  for(const mode of ['actual','demo']) {
    const option=comparisonOptions(dataset(mode,14));
    assert.deepEqual(option.series.map(s=>s.type),['bar','bar','bar']);
    assert.deepEqual(option.series.map(s=>s.data),[[10000,20000],[2000,4000],[1000,2000]]);
  }
});
