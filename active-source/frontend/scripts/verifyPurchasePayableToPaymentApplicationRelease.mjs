import { installMemoryLocalStorage, loadActionModules, seedForAction, resetActionStores } from './purchasePayablePaymentActionTestHarness.mjs'

installMemoryLocalStorage()
const modules = await loadActionModules()
const actions = modules.registry.listPurchasePayablePaymentActions()
const terminalNotice = modules.registry.terminalPaymentApplicationNotice

function targetNoField(action) {
  return action.targetNoField
}

function sourceNoField(action) {
  return action.sourceNoField
}

function targetCollection(action) {
  return {
    payablePrepare: ['payablePrepare', 'payablePrepares', modules.payablePrepare.savePayablePrepareState],
    payableCheck: ['payableCheck', 'payableChecks', modules.payableCheck.savePayableCheckState],
    supplierSettlement: ['supplierSettlement', 'supplierSettlements', modules.supplierSettlement.saveSupplierSettlementState],
    invoicePrepare: ['invoicePrepare', 'invoicePrepares', modules.invoicePrepare.saveInvoicePrepareState],
    accountPayableDraft: ['accountPayableDraft', 'accountPayableDrafts', modules.apDraft.saveAccountPayableDraftState],
    accountPayableConfirm: ['accountPayableConfirm', 'accountPayableConfirms', modules.apConfirm.saveAccountPayableConfirmState],
    paymentApplication: ['paymentApplication', 'paymentApplications', modules.paymentApplication.savePaymentApplicationState],
  }[action.targetObjectType]
}

function sourceStatePatch(action, source, patch) {
  if (action.sourceObjectType === 'inventoryTransaction') {
    modules.wms.saveWmsState({
      inventoryBalances: [],
      inventoryTransactions: [{ ...source, ...patch }],
      warehouseTasks: [],
      stockWarnings: [],
    })
    return
  }
  if (action.sourceObjectType === 'payablePrepare') modules.payablePrepare.savePayablePrepareState({ payablePrepares: [{ ...source, ...patch }] })
  if (action.sourceObjectType === 'payableCheck') modules.payableCheck.savePayableCheckState({ payableChecks: [{ ...source, ...patch }] })
  if (action.sourceObjectType === 'supplierSettlement') modules.supplierSettlement.saveSupplierSettlementState({ supplierSettlements: [{ ...source, ...patch }] })
  if (action.sourceObjectType === 'invoicePrepare') modules.invoicePrepare.saveInvoicePrepareState({ invoicePrepares: [{ ...source, ...patch }] })
  if (action.sourceObjectType === 'accountPayableDraft') modules.apDraft.saveAccountPayableDraftState({ accountPayableDrafts: [{ ...source, ...patch }] })
  if (action.sourceObjectType === 'accountPayableConfirm') modules.apConfirm.saveAccountPayableConfirmState({ accountPayableConfirms: [{ ...source, ...patch }] })
}

function resolveSource(action) {
  const context = modules.executor.resolveBusinessActionContext(action.pageStepId)
  return context.source
}

function seedHistoryScenario(action, overrides = {}) {
  seedForAction(modules, action.actionCode)
  const source = resolveSource(action)
  const sourceNo = source?.[sourceNoField(action)] || source?.transactionNo || 'SOURCETEST001'
  const targetNo = Object.prototype.hasOwnProperty.call(overrides, 'targetNo') ? overrides.targetNo : `${action.targetNoField.toUpperCase()}TEST001`
  const target = {
    id: `target-${action.actionCode}`,
    [targetNoField(action)]: targetNo,
    sourceObjectType: overrides.targetSourceLinkCompleted === false ? '' : action.sourceObjectType,
    sourceObjectId: overrides.targetSourceLinkCompleted === false ? '' : source.id,
    sourceObjectNo: overrides.targetSourceLinkCompleted === false ? '' : sourceNo,
    sourceLinkStatus: overrides.targetSourceLinkCompleted === false ? '' : 'linked',
  }
  const collection = targetCollection(action)
  collection[2]({ [collection[1]]: [target] })
  sourceStatePatch(action, source, {
    flowWritebackStatus: overrides.sourceWritebackCompleted === false ? '' : 'written_back',
    downstreamObjectNo: targetNo,
    downstreamObjectId: target.id,
    downstreamObjectType: action.targetObjectType,
  })
  modules.flowLink.saveBusinessFlowLinkState({
    links: overrides.flowLinkCompleted === false ? [] : [{
      id: `link-${action.actionCode}`,
      actionCode: action.actionCode,
      sourceObjectType: action.sourceObjectType,
      sourceObjectId: source.id,
      sourceObjectNo: sourceNo,
      targetObjectType: action.targetObjectType,
      targetObjectId: target.id,
      targetObjectNo: targetNo,
      linkStatus: overrides.flowLinkStatus || 'linked',
    }],
  })
  modules.flowAudit.saveBusinessFlowActionAuditState({
    audits: overrides.transactionCommitted === false ? [] : [{
      id: `audit-${action.actionCode}`,
      actionCode: action.actionCode,
      sourceObjectNo: sourceNo,
      targetObjectNo: targetNo,
      executionStatus: 'completed',
      cleanupRequired: Boolean(overrides.cleanupRequired),
    }],
  })
  return modules.transition.evaluateBusinessFlowNextStep(action.pageStepId)
}

const results = []
for (const action of actions) {
  seedForAction(modules, action.actionCode)
  const outcome = await modules.executor.executeBusinessFlowAction(action.actionCode)
  const release = modules.transition.evaluateBusinessFlowNextStep(action.pageStepId)
  results.push({
    scenario: 'normal_execution',
    actionCode: action.actionCode,
    pageStepId: action.pageStepId,
    targetNo: outcome.targetNo,
    released: release.released,
    reason: release.reason,
    conditionCount: release.conditions.length,
    expectedReleased: false,
  })
}

const reusableActions = actions.filter((action) => action.actionCode !== 'CREATE_PAYMENT_APPLICATION')
for (const action of reusableActions) {
  const release = seedHistoryScenario(action)
  results.push({
    scenario: 'history_reuse_valid',
    actionCode: action.actionCode,
    released: release.released,
    reason: release.reason,
    conditionCount: release.conditions.length,
    expectedReleased: true,
  })
}

const firstAction = actions[0]
const malformedScenarios = [
  ['target_no_boolean', { targetNo: false }],
  ['target_no_empty', { targetNo: '' }],
  ['source_writeback_missing', { sourceWritebackCompleted: false }],
  ['target_source_link_missing', { targetSourceLinkCompleted: false }],
  ['flow_link_missing', { flowLinkCompleted: false }],
  ['transaction_not_committed', { transactionCommitted: false, sourceWritebackCompleted: false }],
  ['cleanup_required', { cleanupRequired: true }],
]

for (const [scenario, overrides] of malformedScenarios) {
  const release = seedHistoryScenario(firstAction, overrides)
  results.push({
    scenario,
    actionCode: firstAction.actionCode,
    released: release.released,
    reason: release.reason,
    conditionCount: release.conditions.length,
    expectedReleased: false,
  })
}

const paymentApplication = actions.find((action) => action.actionCode === 'CREATE_PAYMENT_APPLICATION')
const paymentRelease = seedHistoryScenario(paymentApplication)
results.push({
  scenario: 'payment_application_terminal_lock',
  actionCode: paymentApplication.actionCode,
  released: paymentRelease.released,
  reason: paymentRelease.reason,
  conditionCount: paymentRelease.conditions.length,
  expectedReleased: false,
  reasonExact: paymentRelease.reason === terminalNotice,
})

const failed = results.filter((item) => item.released !== item.expectedReleased || (item.scenario === 'payment_application_terminal_lock' && !item.reasonExact))

console.log(JSON.stringify({
  page: 'verifyPurchasePayableToPaymentApplicationRelease',
  version: 'V1.14.2.7',
  checkedCount: results.length,
  failedCount: failed.length,
  results,
  checkedAt: new Date().toISOString(),
}, null, 2))

if (failed.length) process.exit(1)

