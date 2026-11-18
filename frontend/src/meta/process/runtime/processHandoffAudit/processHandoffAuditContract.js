const text = value => String(value ?? '').trim()

export function createProcessHandoffAuditContract(definition = {}) {
  if (!text(definition.auditCode)) throw new Error('PROCESS_HANDOFF_AUDIT_CODE_REQUIRED')
  if (!text(definition.sourceNode) || !text(definition.targetNode)) throw new Error('PROCESS_HANDOFF_AUDIT_NODES_REQUIRED')
  if (!definition.handoffContract?.handoffCode) throw new Error('PROCESS_HANDOFF_CONTRACT_REQUIRED')
  if (!Array.isArray(definition.requiredFields) || !definition.requiredFields.length) {
    throw new Error('PROCESS_HANDOFF_REQUIRED_FIELDS_REQUIRED')
  }
  return Object.freeze({ ...definition, requiredFields: Object.freeze([...definition.requiredFields]) })
}

