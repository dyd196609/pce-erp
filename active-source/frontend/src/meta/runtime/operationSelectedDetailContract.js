// A lightweight server directory is navigation metadata, never eligibility.
// Only the explicitly selected full row may supply proofs or available actions.
export function assertOperationSelectedDetailDirectory(facts, expectedOperationId) {
  if (facts.responseMode === undefined || facts.responseMode === 'legacy-full') return
  if (facts.responseMode !== 'selected-detail' || !Array.isArray(facts.operationOptions)
    || facts.directoryResultCount !== facts.operationOptions.length || facts.detailResultCount !== facts.operations.length
    || facts.operations.length > 1) throw new Error('工序轻目录与本次完整事实读取范围不一致。')
  const positive = value => Number.isSafeInteger(value) && value > 0
  const text = value => typeof value === 'string' && !!value.trim()
  const keys = ['id', 'operationId', 'workOrderId', 'workOrderNo', 'sequence', 'operationName', 'statusLabel', 'directoryOnly',
    'qualificationIncluded', 'actionsIncluded', 'proofsIncluded']
  if (!facts.operationOptions.every(row => keys.every(key => Object.hasOwn(row, key))
    && Object.keys(row).every(key => keys.includes(key)) && positive(row.operationId) && row.id === row.operationId
    && row.workOrderId === facts.workOrderId && positive(row.sequence) && row.directoryOnly === true
    && ['qualificationIncluded', 'actionsIncluded', 'proofsIncluded'].every(key => row[key] === false)
    && ['workOrderNo', 'operationName', 'statusLabel'].every(key => text(row[key])))
    || new Set(facts.operationOptions.map(row => row.operationId)).size !== facts.operationOptions.length)
    throw new Error('工序轻目录身份不完整，不能据目录形成正式准入或操作。')
  if (expectedOperationId ? facts.operations.length !== 1 || facts.operations[0]?.operationId !== expectedOperationId
      || !facts.operationOptions.some(row => row.operationId === expectedOperationId)
    : facts.operations.length !== 0 || facts.selectedOperation !== null)
    throw new Error('本次完整工序事实未对应明确选择的定位。')
}
export function latestOwnFormalLocation(facts, expected, { group = false } = {}) {
  const value=facts.viewLocationSuggestion
  if(!value)return null
  const positive=value=>Number.isSafeInteger(value)&&value>0
  const actions=['production.order.select_operation_resource','production.order.receive_operation','production.order.resource_handoff']
  if(!expected.allowLatestFormalLocation||!positive(expected.userId)||value.kind!=='LATEST_OWN_FORMAL_ACTION'
    ||value.actorId!==expected.userId||value.companyId!==expected.companyId||!positive(value.productionPlanId)
    ||value.workOrderId!==(group?facts.workOrder?.id:facts.workOrderId)||!positive(value.operationId)
    ||!actions.includes(value.actionCode)||typeof value.auditReference!=='string'||!value.auditReference.trim()
    ||typeof value.statusLabel!=='string'||!value.statusLabel.trim()
    ||group&&value.productionPlanId!==facts.productionPlanId)
    throw new Error('最近本人正式办理对象的定位建议未对应本次账号、公司、计划及工单；已停止恢复。')
  if(!group){const row=facts.selectedOperation,proof=value.actionCode===actions[0]?(row?.resourceSelectionProof||row?.resourceSelection)
    :value.actionCode===actions[1]?(row?.preciseReceiptProof||row?.preciseReceipt):row?.resourceHandoff||row?.currentResourceFacts?.resourceHandoff
    if(row?.operationId!==value.operationId||!proof||proof.actorId!==value.actorId||proof.auditReference!==value.auditReference)
      throw new Error('最近本人办理定位缺少本工序对应的正式证明；未换用其他对象。')}
  return value
}
