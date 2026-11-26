import { buildPurchaseReconciliationFinalReviewCanaries, buildPurchaseReconciliationFinalReviewScenarioArtifacts } from './purchaseReconciliationFinalReviewCanaryFixtures.js'
import {
  CONTROLLED_GENERATION_WRITE_STEPS, createCanaryIsolatedPersistenceAdapter,
  createDisabledProductionPersistenceAdapter, executePurchaseReconciliationControlledGeneration,
  recoverPurchaseReconciliationControlledGeneration,
} from '../../src/meta/scm/purchaseReconciliationControlledGeneration.js'

const clone = (value) => JSON.parse(JSON.stringify(value))

function sourceFromScenario(scenario) {
  const candidate = scenario.candidate
  return {
    sourcePayableCheckNo: candidate.sourcePayableCheckNo, sourcePayablePrepareNo: candidate.sourcePayablePrepareNo,
    purchaseOrderNo: candidate.purchaseOrderNo, priceApprovalNo: candidate.priceApprovalNo,
    supplierId: candidate.supplierId, supplierName: candidate.supplierName, legalEntityId: candidate.legalEntityId,
    ledgerBookId: candidate.ledgerBookId, accountingPeriod: scenario.simulationScenario.candidateInput.sourceSettlement.accountingPeriod || '',
    currency: candidate.currency, exchangeRate: candidate.exchangeRate, quantity: candidate.quantity,
    unit: candidate.unit, settlementAmount: candidate.amount,
  }
}

export function trustedControlledGenerationContext(batchId) {
  return {
    canaryBatchId: batchId,
    runnerContextRecord: { controlledByRunner: true, canaryBatchId: batchId, adapterType: 'canary_isolated', environmentFlag: 'PCE_CONTROLLED_CANARY_EXECUTION', storageStateId: `storage-${batchId}` },
  }
}

export function buildPurchaseReconciliationControlledGenerationCanaries(batchId) {
  const finalScenarios = buildPurchaseReconciliationFinalReviewCanaries(batchId)
  const artifacts = finalScenarios.map((scenario) => ({ scenario, ...buildPurchaseReconciliationFinalReviewScenarioArtifacts(scenario) }))
  const approvedArtifact = artifacts.find((item) => item.scenario.scenarioCode === 'CANARY_A')
  const approved = approvedArtifact.review
  const baseSource = sourceFromScenario(approvedArtifact.scenario)
  const blockedReview = clone(approved); blockedReview.reviewState = 'review_blocked'; blockedReview.reviewDecision = 'blocked'
  const staleReview = clone(approved); staleReview.freshnessResult.status = 'stale'; staleReview.reviewHash = `${approved.reviewHash}-STALE`
  const changedReview = clone(approved); changedReview.reviewHash = `${approved.reviewHash}-CHANGED`; changedReview.simulationResultId = `${approved.simulationResultId}-CHANGED`
  const make = (letter, purpose, overrides = {}) => ({
    scenarioCode: `CANARY_${letter}`, purpose, canaryBatchId: batchId, review: approved, source: baseSource,
    executionContext: trustedControlledGenerationContext(batchId), canaryRuntimeSwitchEnabled: true, explicitUserAction: true,
    expectedProductionBusinessWriteCount: 0, ...overrides,
  })
  return [
    make('A', '双门禁通过并受控生成成功'),
    make('B', '业务门禁阻断', { review: blockedReview }),
    make('C', '事务能力门禁阻断', { forceTransactionGateFailure: true }),
    make('D', '最终评审已过期', { review: staleReview }),
    make('E', '锁内来源快照变化', { currentSourceSnapshotHash: 'CANARY-MUTATED-SOURCE' }),
    make('F', '锁内存在一个目标', { currentTargetEvidence: [{ targetNo: 'SIM-PRC-EXISTING-F' }] }),
    make('G', '锁内存在多个目标', { currentTargetEvidence: [{ targetNo: 'SIM-PRC-EXISTING-G1' }, { targetNo: 'SIM-PRC-EXISTING-G2' }] }),
    make('H', '相同幂等键顺序重试', { testKind: 'sequential_retry' }),
    make('I', '相同幂等键并发双击', { testKind: 'concurrent_same_idempotency' }),
    make('J', '同来源不同幂等键并发', { testKind: 'same_source_different_idempotency', secondReview: changedReview }),
    make('K', '隔离编号碰撞', { numberCollision: true }),
    make('L', '对象写入失败', { failureAtStep: 'PRC_CONTROLLED_WRITE_FORMAL_OBJECT' }),
    make('M', '来源目标关系写入失败', { failureAtStep: 'PRC_CONTROLLED_WRITE_SOURCE_TARGET_RELATION' }),
    make('N', '来源反向关系写入失败', { failureAtStep: 'PRC_CONTROLLED_WRITE_SOURCE_BACK_REFERENCE' }),
    make('O', '审计写入失败', { failureAtStep: 'PRC_CONTROLLED_WRITE_AUDIT' }),
    make('P', '提交可确认失败', { failureAtStep: 'PRC_CONTROLLED_COMMIT_COPY_ON_WRITE' }),
    make('Q', '响应丢失但实际已提交', { commitAcknowledgementLoss: 'committed', testKind: 'recover_committed' }),
    make('R', '响应丢失且实际未提交', { commitAcknowledgementLoss: 'not_committed', testKind: 'recover_not_committed' }),
    make('S', '部分提交残留', { partialCommit: true, testKind: 'partial_commit' }),
    make('T', '回滚补偿失败', { failureAtStep: 'PRC_CONTROLLED_WRITE_SOURCE_TARGET_RELATION', rollbackFailure: true }),
    make('U', '执行结果完整性被篡改', { testKind: 'integrity_tamper' }),
    make('V', '页面刷新重入', { testKind: 'refresh_reentry' }),
    make('W', '跨进程恢复已提交结果', { testKind: 'cross_process_committed' }),
    make('X', '普通浏览器复制金丝雀URL', { executionContext: { canaryBatchId: batchId } }),
    make('Y', '越权调用生产适配器', { adapterType: 'production_disabled' }),
    make('Z', '下游零对象边界'),
  ]
}

export function executeControlledGenerationScenario(scenario) {
  const adapter = scenario.adapterType === 'production_disabled' ? createDisabledProductionPersistenceAdapter() : createCanaryIsolatedPersistenceAdapter()
  if (adapter.state && scenario.currentTargetEvidence?.length) {
    adapter.state.formalObjects.push(...scenario.currentTargetEvidence.map((target, index) => ({
      id: `PRC-EXISTING-${scenario.scenarioCode}-${index + 1}`,
      reconciliationNo: target.reconciliationNo || target.targetNo,
      sourceKey: scenario.review.sourceKey,
      idempotencyKey: target.idempotencyKey || `EXISTING-${scenario.scenarioCode}-${index + 1}`,
      status: 'draft',
    })))
  }
  const input = { ...clone(scenario), adapter }
  const first = executePurchaseReconciliationControlledGeneration(input)
  let retry = null
  let recovery = null
  if (['sequential_retry', 'concurrent_same_idempotency', 'refresh_reentry'].includes(scenario.testKind)) retry = executePurchaseReconciliationControlledGeneration(input)
  if (scenario.testKind === 'same_source_different_idempotency') retry = executePurchaseReconciliationControlledGeneration({ ...input, review: scenario.secondReview })
  if (scenario.testKind?.startsWith('recover_') || scenario.testKind === 'cross_process_committed') recovery = recoverPurchaseReconciliationControlledGeneration({ adapter, result: first })
  if (scenario.testKind === 'integrity_tamper') recovery = recoverPurchaseReconciliationControlledGeneration({ adapter, result: { ...first, outcome: 'tampered' } })
  return { first, retry, recovery, state: clone(adapter.state || {}), failureStepDefinitions: CONTROLLED_GENERATION_WRITE_STEPS }
}
