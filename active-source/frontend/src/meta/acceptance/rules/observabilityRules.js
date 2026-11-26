import { outcome } from './pageRules.js'

const make = (id, name, evaluate) => Object.freeze({
  id,
  name,
  family: 'OBSERVABILITY',
  evaluate,
})

export const observabilityRules = Object.freeze([
  make('OBS-001', '事实来源字段存在且为server', evidence => outcome(
    evidence.acceptanceFacts?.factSource === 'server',
    `factSource=${evidence.acceptanceFacts?.factSource || ''}`,
    'acceptanceFacts.factSource必须为server',
  )),
  make('OBS-002', '服务端记录数量存在', evidence => {
    const value = evidence.acceptanceFacts?.recordCount
    return outcome(
      Number.isInteger(value) ? true : null,
      `recordCount=${value}; reason=${evidence.acceptanceFacts?.recordCountUnavailableReason || ''}`,
      evidence.acceptanceFacts?.recordCountUnavailableReason || 'recordCount缺失',
    )
  }),
  make('OBS-003', '危险动作数量为零', evidence => outcome(
    Number.isInteger(evidence.acceptanceFacts?.dangerActionCount)
      ? evidence.acceptanceFacts.dangerActionCount === 0
      : null,
    `dangerActionCount=${evidence.acceptanceFacts?.dangerActionCount}`,
    'dangerActionCount必须为0',
  )),
  make('OBS-004', '业务推进写入为零', evidence => outcome(
    Number.isInteger(evidence.acceptanceFacts?.businessProgressWriteCount)
      ? evidence.acceptanceFacts.businessProgressWriteCount === 0
      : null,
    `businessProgressWriteCount=${evidence.acceptanceFacts?.businessProgressWriteCount}`,
    'businessProgressWriteCount必须为0',
  )),
  make('OBS-005', '下游对象数量存在', evidence => outcome(
    Number.isInteger(evidence.acceptanceFacts?.downstreamObjectCount)
      ? evidence.acceptanceFacts.downstreamObjectCount >= 0
      : null,
    `downstreamObjectCount=${evidence.acceptanceFacts?.downstreamObjectCount}`,
    'downstreamObjectCount缺失',
  )),
])
