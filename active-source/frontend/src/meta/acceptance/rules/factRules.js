import { outcome } from './pageRules.js'

const make = (id, name, evaluate) => Object.freeze({ id, name, family: 'FACT', evaluate })
const same = values => values.every(value => value === values[0])

export const factRules = Object.freeze([
  make('FACT-001', 'API与页面数量一致', e => outcome(
    Number.isFinite(e.facts?.apiCount) && Number.isFinite(e.facts?.pageCount)
      ? e.facts.apiCount === e.facts.pageCount
      : null,
    `api=${e.facts?.apiCount}; page=${e.facts?.pageCount}`,
    'API与页面数量不一致',
  )),
  make('FACT-002', 'Diagnostic与StrictFacts数量一致', e => outcome(
    Number.isFinite(e.facts?.diagnosticCount) && Number.isFinite(e.facts?.strictCount)
      ? e.facts.diagnosticCount === e.facts.strictCount
      : null,
    `diagnostic=${e.facts?.diagnosticCount}; strict=${e.facts?.strictCount}`,
    'Diagnostic与StrictFacts数量不一致',
  )),
  make('FACT-003', '四端状态一致', e => outcome(
    Array.isArray(e.facts?.statusValues) && e.facts.statusValues.length >= 2
      ? same(e.facts.statusValues)
      : null,
    `statusValues=${JSON.stringify(e.facts?.statusValues || [])}`,
    '状态事实不一致',
  )),
  make('FACT-004', '事实来源为服务端', e => outcome(
    e.facts?.source === 'server',
    `source=${e.facts?.source || ''}`,
    '事实来源不是server',
  )),
  make('FACT-005', '读取失败不伪装为零', e => outcome(
    e.facts?.readFailureTested === true
      ? e.facts.readFailureStatus === 'read_failed' && e.facts.readFailureCount !== 0
      : null,
    `tested=${e.facts?.readFailureTested === true}; status=${e.facts?.readFailureStatus || ''}`,
    e.facts?.readFailureTested === true
      ? '读取失败契约不符合read_failed且非零语义'
      : '当前只读环境未提供无副作用故障注入',
  )),
])
