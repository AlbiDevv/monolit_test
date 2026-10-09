import { CheckCircledIcon, FileTextIcon } from '@radix-ui/react-icons';
import type { DashboardData } from './types';
import { money } from './format';

export function QualityPanel({ data }: { data: DashboardData }) {
  return <details className="panel quality-panel" id="quality"><summary className="quality-summary"><span><CheckCircledIcon />Сверка с исходными файлами</span><span className={data.quality.every(q => q.reconciled) ? 'verified-badge' : 'verified-badge verification-failed'}>{data.quality.every(q => q.reconciled) ? 'Расхождение: 0,00' : 'Есть расхождения'}</span></summary><div className="quality-content">
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">{data.quality.map(source => <div className="source-item" key={source.department}>
      <FileTextIcon className="source-icon" /><div className="min-w-0 flex-1"><h3>{source.department}</h3><p className="source-filename" title={source.filename}>{source.filename}</p><div className="source-stats"><span>{source.documents} документов</span><span>Общая ДЗ {money(source.control_total)}</span></div><p className={source.reconciled ? 'control-ok' : 'control-error'}>{source.reconciled ? 'Расхождение с источником: 0,00' : 'Контроль сумм не пройден'}</p></div>
    </div>)}</div>
    <details className="methodology"><summary>Как рассчитаны показатели</summary><div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
      <p><strong>Общая и просроченная ДЗ.</strong> Сумма остатков по отдельным документам. Промежуточные итоги и «Наш долг» не добавляются к дебиторской задолженности.</p>
      <p><strong>Ближайшие поступления.</strong> Остаток долга с числом дней до оплаты от 1 до 5. Прогноз — остатки с плановой датой от следующего дня до седьмого дня включительно.</p>
      <p><strong>Топы и статусы.</strong> Просрочка суммируется по контрагенту и отделу; дни — максимальная просрочка среди его просроченных документов. Норма &lt; 10%, внимание 10–20%, критично ≥ 20%.</p>
      <p><strong>История и дельты.</strong> Сравнение с предыдущим доступным полным срезом в том же режиме. Для единственного реального среза дельта отсутствует. Демонстрационная история — отдельный сценарий.</p>
    </div></details>
  </div></details>;
}
