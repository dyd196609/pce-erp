import { cloneBusinessActionTransactionValue } from './businessActionTransactionIntegrity.js'

const capabilityNames = [
  'supportsAtomicTransaction', 'supportsUniqueIdempotencyKey', 'supportsUniqueSourceKey', 'supportsUniqueDocumentNumber',
  'supportsDurableSourceLock', 'supportsCommitOutcomeRecovery', 'supportsAtomicAuditWrite', 'supportsServerSideAuthorization',
]

export const disabledProductionCapabilities = Object.freeze(Object.fromEntries(capabilityNames.map((name) => [name, false])))
export const canaryIsolatedCapabilities = Object.freeze(Object.fromEntries(capabilityNames.map((name) => [name, true])))

export function createEmptyCanaryPersistenceState() {
  return { formalObjects: [], idempotencyRecords: [], numberReservations: [], sourceTargetRelations: [], sourceBackReferences: [], auditRecords: [], commitRecords: [], rollbackRecords: [], recoveryRecords: [], locks: [] }
}

export function createCanaryIsolatedPersistenceAdapter(state = createEmptyCanaryPersistenceState()) {
  return Object.freeze({
    adapterType: 'canary_isolated', capabilities: canaryIsolatedCapabilities, state,
    beginTransaction: () => cloneBusinessActionTransactionValue(state),
    readSourceSnapshot: (source) => cloneBusinessActionTransactionValue(source),
    readExistingTargets: (sourceKey) => state.formalObjects.filter((item) => item.sourceKey === sourceKey),
    acquireSourceLock: (lockKey, owner) => {
      if (state.locks.some((item) => item.lockKey === lockKey && item.status === 'acquired')) return { acquired: false, status: 'conflict' }
      state.locks.push({ lockKey, owner, status: 'acquired' })
      return { acquired: true, status: 'acquired', lockKey, owner }
    },
    readIdempotencyRecord: (key) => state.idempotencyRecords.find((item) => item.idempotencyKey === key) || null,
    createIdempotencyRecord: (working, record) => { working.idempotencyRecords.push(cloneBusinessActionTransactionValue(record)); return record },
    reserveDocumentNumber: (working, reservation) => {
      if (working.numberReservations.some((item) => item.number === reservation.number && item.idempotencyKey !== reservation.idempotencyKey)) return { reserved: false, errorCode: 'CANARY_NUMBER_COLLISION' }
      working.numberReservations.push(cloneBusinessActionTransactionValue(reservation)); return { reserved: true, reservation }
    },
    writeFormalObject: (working, object) => { working.formalObjects.push(cloneBusinessActionTransactionValue(object)); return object },
    writeSourceTargetRelation: (working, relation) => { working.sourceTargetRelations.push(cloneBusinessActionTransactionValue(relation)); return relation },
    writeSourceRelationBackReference: (working, relation) => { working.sourceBackReferences.push(cloneBusinessActionTransactionValue(relation)); return relation },
    writeAuditRecord: (working, record) => { working.auditRecords.push(cloneBusinessActionTransactionValue(record)); return record },
    validateStagedState: (working) => ({ valid: working.formalObjects.length > 0 && working.sourceTargetRelations.length > 0 && working.sourceBackReferences.length > 0 && working.auditRecords.length > 0 }),
    commit: (working) => { for (const key of Object.keys(state)) state[key] = cloneBusinessActionTransactionValue(working[key]); return { committed: true, copyOnWrite: true } },
    rollback: (record) => { state.rollbackRecords.push(cloneBusinessActionTransactionValue(record)); return { rolledBack: true } },
    recoverCommitOutcome: ({ idempotencyKey }) => {
      const record = state.idempotencyRecords.find((item) => item.idempotencyKey === idempotencyKey)
      const object = state.formalObjects.find((item) => item.idempotencyKey === idempotencyKey)
      if (record?.status === 'committed' && object) return { classification: 'committed', object }
      if (!record && !object) return { classification: 'not_committed_safe_to_retry' }
      return { classification: 'partial_commit_requires_intervention', object: object || null }
    },
    releaseSourceLock: (lockKey) => {
      const lock = state.locks.find((item) => item.lockKey === lockKey && item.status === 'acquired')
      if (lock) lock.status = 'released'
      return { released: true, lockKey }
    },
  })
}

const disabled = () => ({ success: false, errorCode: 'BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED', productionBusinessWriteCount: 0 })
export function createDisabledProductionPersistenceAdapter() {
  return Object.freeze({
    adapterType: 'production_disabled', capabilities: disabledProductionCapabilities,
    beginTransaction: disabled, readSourceSnapshot: disabled, readExistingTargets: disabled, acquireSourceLock: disabled,
    readIdempotencyRecord: disabled, createIdempotencyRecord: disabled, reserveDocumentNumber: disabled,
    writeFormalObject: disabled, writeSourceTargetRelation: disabled, writeSourceRelationBackReference: disabled,
    writeAuditRecord: disabled, validateStagedState: disabled, commit: disabled, rollback: disabled,
    recoverCommitOutcome: disabled, releaseSourceLock: disabled,
  })
}
