export const APPROVAL_RUNTIME_VERSION = 'V1.14.2.8.18.8.1'

const MODULE_OBJECTS = Object.freeze({
  purchaseRequest: 'PurchaseRequest',
  purchaseInquiry: 'PurchaseInquiry',
  priceApproval: 'PriceApproval',
  purchaseOrder: 'PurchaseOrder',
})

const GATE_DEFINITIONS = Object.freeze([
  Object.freeze({ gateCode: 'REVIEW', name: '审核', approverRole: '审核员' }),
  Object.freeze({ gateCode: 'RECHECK', name: '复核', approverRole: '复核员' }),
  Object.freeze({ gateCode: 'APPROVE', name: '审批', approverRole: '审批员' }),
])

const clone = value => JSON.parse(JSON.stringify(value))
const normalizedGateCount = value => Math.min(3, Math.max(1, Number(value) || 1))
const selectedGateDefinitions = count => count === 1
  ? [GATE_DEFINITIONS[2]]
  : count === 2 ? [GATE_DEFINITIONS[0], GATE_DEFINITIONS[2]] : GATE_DEFINITIONS

export function createApprovalContract(moduleName = 'purchaseRequest', gateCount = 1) {
  const normalizedCount = normalizedGateCount(gateCount)
  const businessObject = MODULE_OBJECTS[moduleName] || moduleName
  return Object.freeze({
    approvalContractCode: `APPROVAL_${String(businessObject).replace(/([a-z])([A-Z])/g, '$1_$2').toUpperCase()}_V1`,
    moduleName,
    businessObject,
    gateCount: normalizedCount,
    gates: Object.freeze(selectedGateDefinitions(normalizedCount).map((definition, index) => Object.freeze({
      ...definition,
      level: index + 1,
      permission: `${moduleName}.approve.level${index + 1}`,
      entryState: index === 0 ? 'submitted' : index === 1 ? 'reviewed' : 'rechecked',
      passState: index === normalizedCount - 1 ? 'approved' : index === 0 ? 'reviewed' : 'rechecked',
      rejectState: 'rejected',
    }))),
    states: Object.freeze(['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'rejected']),
    instance: Object.freeze({ instanceIdField: 'approvalInstanceId', businessObjectIdField: 'businessObjectId',
      currentGateField: 'currentGate', historyField: 'approvalHistory' }),
    resultWriteback: Object.freeze({ targetField: 'approvalStatus', successValue: 'approved',
      rejectValue: 'rejected', idempotencyKey: 'businessObjectId:approvalInstanceId:result' }),
  })
}

export function resolveApprovalStatusTransition(contract, currentStatus = 'draft') {
  const count = normalizedGateCount(contract?.gateCount)
  if (currentStatus === 'draft' || currentStatus === 'rejected') return 'submitted'
  if (currentStatus === 'submitted') return count === 1 ? 'approved' : 'reviewed'
  if (currentStatus === 'reviewed') return count === 2 ? 'approved' : 'rechecked'
  if (currentStatus === 'rechecked') return 'approved'
  return currentStatus
}

export function createApprovalInstance({ contract, businessObjectId, submittedBy = 'system', submittedAt } = {}) {
  if (!contract?.approvalContractCode || !businessObjectId) throw new Error('APPROVAL_INSTANCE_INPUT_REQUIRED')
  const stamp = submittedAt || new Date().toISOString()
  return Object.freeze({
    approvalInstanceId: `${contract.approvalContractCode}:${businessObjectId}`,
    approvalContractCode: contract.approvalContractCode,
    businessObjectId: String(businessObjectId),
    status: 'pending',
    approvalStatus: 'submitted',
    currentGate: 1,
    approvalHistory: Object.freeze([{ action: 'SUBMIT', actorId: submittedBy, at: stamp }]),
    approvalResult: null,
  })
}

export function executeApprovalAction(instance, contract, { action = 'APPROVE', actorId = 'approver', actorRole = '', at } = {}) {
  if (!instance?.approvalInstanceId || !contract?.approvalContractCode) throw new Error('APPROVAL_ACTION_INPUT_REQUIRED')
  if (instance.approvalResult) return Object.freeze({ instance, completed: true, idempotent: true })
  const stamp = at || new Date().toISOString()
  const currentGate = contract.gates[instance.currentGate - 1]
  if (!currentGate) throw new Error('APPROVAL_GATE_NOT_FOUND')
  if (action === 'REJECT') {
    const rejected = Object.freeze({ ...clone(instance), status: 'completed', approvalStatus: 'rejected',
      approvalHistory: Object.freeze([...instance.approvalHistory, { action, gateCode: currentGate.gateCode,
        actorId, actorRole, at: stamp }]),
      approvalResult: Object.freeze({ code: 'rejected', completedAt: stamp }) })
    return Object.freeze({ instance: rejected, completed: true, idempotent: false })
  }
  if (action !== 'APPROVE') throw new Error('APPROVAL_ACTION_NOT_SUPPORTED')
  const finalGate = instance.currentGate === contract.gateCount
  const approvalStatus = finalGate ? 'approved' : currentGate.passState
  const approved = Object.freeze({ ...clone(instance), status: finalGate ? 'completed' : 'in_progress',
    approvalStatus, currentGate: finalGate ? instance.currentGate : instance.currentGate + 1,
    approvalHistory: Object.freeze([...instance.approvalHistory, { action, gateCode: currentGate.gateCode,
      actorId, actorRole, at: stamp }]),
    approvalResult: finalGate ? Object.freeze({ code: 'approved', completedAt: stamp }) : null })
  return Object.freeze({ instance: approved, completed: finalGate, idempotent: false })
}

export function writeApprovalResultToBusinessObject(instance, businessObject = {}) {
  if (!instance?.approvalResult) throw new Error('APPROVAL_RESULT_REQUIRED')
  const key = `${instance.businessObjectId}:${instance.approvalInstanceId}:${instance.approvalResult.code}`
  const writtenKeys = [...(businessObject.approvalWritebackKeys || [])]
  if (writtenKeys.includes(key)) return Object.freeze({ object: Object.freeze({ ...businessObject }), written: false, idempotent: true, key })
  const targetState = instance.approvalResult.code
  return Object.freeze({ object: Object.freeze({ ...businessObject, approvalStatus: targetState, status: targetState,
    businessLifecycleState: targetState === 'approved' ? 'approved' : businessObject.businessLifecycleState,
    approvalInstanceId: instance.approvalInstanceId, approvalWritebackKeys: Object.freeze([...writtenKeys, key]) }),
  written: true, idempotent: false, key })
}

