import { buildPurchaseReconciliationFinalReviewCanaries, buildPurchaseReconciliationFinalReviewScenarioArtifacts } from './purchaseReconciliationFinalReviewCanaryFixtures.js'
import { executePurchaseReconciliationIsolatedTransaction } from '../../src/meta/scm/purchaseReconciliationFormalGenerationTransaction.js'

const clone = (value) => JSON.parse(JSON.stringify(value))

export function buildPurchaseReconciliationTransactionCanaries(batchId) {
  const finalScenarios = buildPurchaseReconciliationFinalReviewCanaries(batchId)
  const reviewByCode = Object.fromEntries(finalScenarios.map((scenario) => [scenario.scenarioCode, buildPurchaseReconciliationFinalReviewScenarioArtifacts(scenario).review]))
  const approved = reviewByCode.CANARY_A
  const changed = reviewByCode.CANARY_K
  const make = (scenarioCode, purpose, overrides = {}) => ({
    origin: 'canary', canaryBatchId: batchId, scenarioCode, purpose, review: approved,
    context: { legalEntityId: 'LE-PCE', ledgerBookId: 'LEDGER-PCE', accountingPeriod: '2026-07' },
    expectedFormalExecutionAllowed: false, expectedFormalBusinessWriteCount: 0,
    expectedTransactionState: 'committed', expectedRollbackResult: 'not_required', ...overrides,
  })
  return [
    make('CANARY_A', '有效事务完整隔离提交'),
    make('CANARY_B', '最终评审 blocked', { review: reviewByCode.CANARY_B, expectedTransactionState: 'transaction_blocked' }),
    make('CANARY_C', '最终评审 stale', { review: reviewByCode.CANARY_E, expectedTransactionState: 'transaction_blocked' }),
    make('CANARY_D', '最终评审 failed', { review: reviewByCode.CANARY_O, expectedTransactionState: 'transaction_blocked' }),
    make('CANARY_E', '最终评审后来源变化', { currentSourceSnapshotHash: 'SOURCE-MUTATED-AFTER-REVIEW', expectedTransactionState: 'transaction_blocked' }),
    make('CANARY_F', '最终评审后出现一个已有目标', { currentTargetEvidence: [{ targetNo: 'SIM-EXISTING-PRC-F' }], expectedTransactionState: 'transaction_blocked' }),
    make('CANARY_G', '最终评审后出现多个目标', { currentTargetEvidence: [{ targetNo: 'SIM-EXISTING-PRC-G1' }, { targetNo: 'SIM-EXISTING-PRC-G2' }], expectedTransactionState: 'transaction_blocked' }),
    make('CANARY_H', '来源锁冲突', { lockConflict: true, expectedTransactionState: 'transaction_failed' }),
    make('CANARY_I', '相同幂等键顺序重试', { testKind: 'sequential_idempotency_retry' }),
    make('CANARY_J', '相同幂等键并发双提交', { testKind: 'concurrent_same_idempotency' }),
    make('CANARY_K', '同一来源不同幂等键并发', { review: changed, testKind: 'concurrent_same_source_different_idempotency', lockConflict: true, expectedTransactionState: 'transaction_failed' }),
    make('CANARY_L', '隔离编号预留冲突', { numberCollision: true, expectedTransactionState: 'transaction_failed' }),
    make('CANARY_M', '隔离编号服务受控失败', { failureAtStep: 'PRC_TX_RESERVE_DOCUMENT_NUMBER', expectedTransactionState: 'transaction_failed' }),
    make('CANARY_N', '正式对象暂存失败', { failureAtStep: 'PRC_TX_STAGE_FORMAL_OBJECT', expectedTransactionState: 'rolled_back', expectedRollbackResult: 'rolled_back' }),
    make('CANARY_O', '来源目标关系暂存失败', { failureAtStep: 'PRC_TX_STAGE_SOURCE_TARGET_RELATION', expectedTransactionState: 'rolled_back', expectedRollbackResult: 'rolled_back' }),
    make('CANARY_P', '供应商结算回写暂存失败', { failureAtStep: 'PRC_TX_STAGE_SUPPLIER_SETTLEMENT_WRITEBACK', expectedTransactionState: 'rolled_back', expectedRollbackResult: 'rolled_back' }),
    make('CANARY_Q', '审计记录暂存失败', { failureAtStep: 'PRC_TX_STAGE_AUDIT_RECORD', expectedTransactionState: 'rolled_back', expectedRollbackResult: 'rolled_back' }),
    make('CANARY_R', '提交可确认失败', { failureAtStep: 'PRC_TX_COMMIT', expectedTransactionState: 'rolled_back', expectedRollbackResult: 'rolled_back' }),
    make('CANARY_S', '提交响应丢失', { commitAcknowledgementLoss: true, expectedTransactionState: 'commit_unknown', expectedRollbackResult: 'not_allowed' }),
    make('CANARY_T', '回滚步骤受控失败', { failureAtStep: 'PRC_TX_STAGE_SOURCE_TARGET_RELATION', rollbackFailureAt: 'PRC_TX_COMPENSATE_FORMAL_OBJECT_STAGE', expectedTransactionState: 'rollback_failed', expectedRollbackResult: 'rollback_failed' }),
    make('CANARY_U', '已预留隔离编号的失败事务', { failureAtStep: 'PRC_TX_STAGE_FORMAL_OBJECT', expectedTransactionState: 'rolled_back', expectedRollbackResult: 'rolled_back' }),
    make('CANARY_V', '事务计划稳定性', { testKind: 'plan_stability' }),
    make('CANARY_W', '有效输入变化', { review: changed, testKind: 'valid_input_change' }),
    make('CANARY_X', '越权调用正式执行器', { testKind: 'unauthorized_formal_executor' }),
    make('CANARY_Y', '已提交隔离事务跨进程恢复', { testKind: 'committed_recovery' }),
    make('CANARY_Z', 'commit_unknown 跨进程恢复', { commitAcknowledgementLoss: true, testKind: 'commit_unknown_recovery', expectedTransactionState: 'commit_unknown', expectedRollbackResult: 'not_allowed' }),
  ]
}

export function buildPurchaseReconciliationTransactionScenarioArtifacts(scenario) {
  const transactionResult = executePurchaseReconciliationIsolatedTransaction(clone(scenario))
  return { transactionResult }
}
