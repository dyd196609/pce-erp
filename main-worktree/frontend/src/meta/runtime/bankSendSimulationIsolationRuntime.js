export const BANK_SEND_SIMULATION_ISOLATION_VERSION = 'V1.14.2.8.4.7.65'

export const AUDIT_FILTER_SCHEMA = Object.freeze([
  { field: 'auditNo', key: 'auditNo', label: '审计编号', type: 'searchable_select' },
  { field: 'simulationNo', key: 'simulationNo', label: '模拟编号', type: 'searchable_select' },
  {
    field: 'auditType', key: 'auditType', label: '审计类型', type: 'select',
    options: [
      { value: 'simulation_created', label: '已创建' },
      { value: 'simulation_validated', label: '已校验' },
      { value: 'simulation_started', label: '模拟开始' },
      { value: 'simulation_completed', label: '模拟完成' },
      { value: 'simulation_failed', label: '模拟失败' },
      { value: 'simulation_recovered', label: '已恢复' },
    ],
  },
  { field: 'operator', key: 'operator', label: '操作人', type: 'searchable_select' },
])

export const ISOLATION_FILTER_SCHEMA = Object.freeze([
  { field: 'gateNo', key: 'gateNo', label: '门禁编号', type: 'searchable_select' },
  {
    field: 'status', key: 'status', label: '隔离状态', type: 'select',
    options: [
      { value: 'created', label: '已创建' },
      { value: 'checked', label: '已检查' },
      { value: 'isolated', label: '隔离有效' },
    ],
  },
  { field: 'tenantId', key: 'tenantId', label: '租户', type: 'searchable_select' },
  { field: 'batchId', key: 'batchId', label: '批次', type: 'searchable_select' },
])

function assertServerFacts(payload, factKey, factType) {
  const envelope = payload?.success === true ? payload.data : payload
  const data = envelope?.data
  const facts = data?.[factKey]
  if (!facts || facts.factType !== factType || facts.factSource !== 'server') {
    throw new Error(`${factType} missing`)
  }
  if (facts.factLoadStatus !== 'success') {
    throw new Error(`${factType} read failed`)
  }
  const rows = Array.isArray(data.results) ? data.results : []
  if (rows.length !== facts.recordCount) throw new Error(`${factType} count mismatch`)
  const acceptanceFacts = data.acceptanceFacts
  if (
    acceptanceFacts?.factSource !== 'server'
    || acceptanceFacts?.recordCount !== facts.recordCount
    || acceptanceFacts?.pageAcceptanceContractVersion !== 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0'
  ) {
    throw new Error(`${factType} acceptance mismatch`)
  }
  return {
    facts,
    rows,
    acceptanceFacts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
  }
}

export function createSimulationAuditPageFacts(payload) {
  const loaded = assertServerFacts(
    payload, 'auditFacts', 'BankSendSimulationAuditFacts',
  )
  if (loaded.rows.some(row => (
    !row.operator || !row.reason || !row.auditReference || !row.auditTypeLabel
  ))) {
    throw new Error('simulation audit completeness violated')
  }
  return loaded
}

export function createIsolationGatePageFacts(payload) {
  const loaded = assertServerFacts(
    payload, 'isolationFacts', 'BankSendProductionIsolationGateFacts',
  )
  if (loaded.rows.some(row => (
    row.status !== 'isolated'
    || row.simulationEnvironment !== true
    || row.productionConnectionEnabled !== false
    || row.productionSecretAvailable !== false
    || row.productionSendAllowed !== false
    || row.paymentExecutionAllowed !== false
    || row.stateMachineConsistent !== true
  ))) {
    throw new Error('production isolation boundary violated')
  }
  return loaded
}
