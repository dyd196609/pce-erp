import { outcome } from './pageRules.js'

const make = (id, name, evaluate) => Object.freeze({ id, name, family: 'STATUS', evaluate })

export const statusRules = Object.freeze([
  make('STATUS-001', '技术状态不直接展示', e => outcome(
    Array.isArray(e.status?.technicalStatuses)
      ? e.status.technicalStatuses.every(status => !e.status.visibleText?.includes(status))
      : null,
    `forbidden=${JSON.stringify(e.status?.technicalStatuses || [])}`,
    '页面可见区域暴露技术状态',
  )),
  make('STATUS-002', '中文业务状态存在', e => outcome(
    Boolean(e.status?.expectedLabel) && e.status?.visibleText?.includes(e.status.expectedLabel),
    `expectedLabel=${e.status?.expectedLabel}; visibleLabels=${JSON.stringify(e.status?.visibleText || '')}`,
    '页面未显示期望中文业务状态',
  )),
  make('STATUS-003', '状态来源为服务端', e => outcome(
    e.status?.source === 'server',
    `source=${e.status?.source || ''}`,
    '状态来源不是server',
  )),
])
