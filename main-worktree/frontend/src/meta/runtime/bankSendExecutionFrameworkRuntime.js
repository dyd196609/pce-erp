export const BANK_SEND_EXECUTION_FRAMEWORK_VERSION = 'V1.14.2.8.4.7.68'

export const FRAMEWORK_FILTER_SCHEMA = Object.freeze([
  { field: 'frameworkNo', key: 'frameworkNo', label: '框架编号', type: 'searchable_select' },
  { field: 'sourceReviewNo', key: 'sourceReviewNo', label: '来源生产评审', type: 'searchable_select' },
  { field: 'environment', key: 'environment', label: '执行环境', type: 'select', options: [
    { value: 'simulation', label: '隔离模拟' },
    { value: 'sandbox', label: '银行沙箱' },
  ] },
  { field: 'status', key: 'status', label: '框架状态', type: 'select', options: [
    { value: 'draft', label: '框架草稿' },
    { value: 'designed', label: '框架设计完成' },
    { value: 'security_reviewed', label: '生产安全评审通过' },
  ] },
])

export const ADAPTER_FILTER_SCHEMA = Object.freeze([
  { field: 'interfaceName', key: 'interfaceName', label: '接口名称', type: 'searchable_select' },
  { field: 'environment', key: 'environment', label: '环境', type: 'select', options: [
    { value: 'simulation', label: '模拟允许' },
    { value: 'sandbox', label: '银行沙箱' },
  ] },
  { field: 'status', key: 'status', label: '状态', type: 'select', options: [
    { value: 'simulation_only', label: '仅模拟' },
  ] },
])

function assertFacts(payload, factKey, factType) {
  const envelope = payload?.success === true ? payload.data : payload
  const data = envelope?.data
  const facts = data?.[factKey]
  if (!facts || facts.factType !== factType || facts.factSource !== 'server') {
    throw new Error(`${factType} missing`)
  }
  if (facts.factLoadStatus !== 'success') throw new Error(`${factType} read failed`)
  const rows = Array.isArray(data.results) ? data.results : []
  const counts = [
    rows.length,
    facts.recordCount,
    data.diagnosticFacts?.recordCount,
    data.strictFacts?.recordCount,
    data.acceptanceFacts?.recordCount,
  ]
  if (new Set(counts).size !== 1) throw new Error(`${factType} five-surface mismatch`)
  if (
    data.acceptanceFacts?.factSource !== 'server'
    || data.acceptanceFacts?.acceptanceStatus !== 'PASS'
    || data.acceptanceFacts?.unknownReason !== ''
  ) throw new Error(`${factType} acceptance failed`)
  return {
    rows,
    facts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
    acceptanceFacts: data.acceptanceFacts,
  }
}

export function createFrameworkPageFacts(payload) {
  const loaded = assertFacts(
    payload, 'frameworkFacts', 'BankSendExecutionFrameworkFacts',
  )
  if (loaded.rows.some(row => (
    row.environment === 'production'
    || row.interfaceMode !== 'simulated'
    || row.executionMode !== 'design_only'
    || row.productionConnectionEnabled
    || row.productionSecretAvailable
    || row.sendPermissionEnabled
    || row.paymentPermissionEnabled
    || row.realSendCapabilityOpen
    || row.frameworkExistsMeansSendEnabled
    || ['enabled', 'sent'].includes(row.status)
    || row.stateMachineConsistent !== true
  ))) throw new Error('execution framework boundary violated')
  return loaded
}

export function createAdapterPageFacts(payload) {
  const loaded = assertFacts(
    payload, 'adapterFacts', 'BankConnectorAdapterReviewFacts',
  )
  if (loaded.rows.some(row => (
    row.productionMode !== '关闭'
    || row.networkCallPerformed
    || row.realBankMessageSent
    || row.signature?.certificateMode !== 'simulation_only'
    || row.failure?.retryAllowed !== false
    || row.receipt?.simulated !== true
  ))) throw new Error('connector adapter boundary violated')
  return loaded
}
