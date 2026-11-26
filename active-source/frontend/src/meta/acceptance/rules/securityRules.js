import { outcome } from './pageRules.js'

const make = (id, name, field) => Object.freeze({
  id,
  name,
  family: 'SECURITY',
  evaluate: evidence => outcome(
    Number.isFinite(evidence.security?.[field]) ? evidence.security[field] === 0 : null,
    `${field}=${evidence.security?.[field]}`,
    `${field}必须为0`,
  ),
})

export const securityRules = Object.freeze([
  make('SECURITY-001', '业务推进写入为零', 'businessProgressWriteCount'),
  make('SECURITY-002', '银行发送写入为零', 'bankSendExecutionWriteCount'),
  make('SECURITY-003', '付款执行为零', 'paymentExecutionCount'),
  make('SECURITY-004', '资金扣减为零', 'fundDeductionCount'),
  make('SECURITY-005', '银行流水为零', 'bankTransactionCount'),
])
