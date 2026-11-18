import { executeSeededAction, installMemoryLocalStorage, loadActionModules, seedForAction } from './purchasePayablePaymentActionTestHarness.mjs'

installMemoryLocalStorage()
const modules = await loadActionModules()
const actions = modules.registry.listPurchasePayablePaymentActions()

function findSource(action) {
  const store = {
    inventoryTransaction: () => modules.wms.getWmsState().inventoryTransactions[0],
    payablePrepare: () => modules.payablePrepare.listPayablePrepares()[0],
    payableCheck: () => modules.payableCheck.listPayableChecks()[0],
    supplierSettlement: () => modules.supplierSettlement.listSupplierSettlements()[0],
    invoicePrepare: () => modules.invoicePrepare.listInvoicePrepares()[0],
    accountPayableDraft: () => modules.apDraft.listAccountPayableDrafts()[0],
    accountPayableConfirm: () => modules.apConfirm.listAccountPayableConfirms()[0],
  }
  return store[action.sourceObjectType]?.()
}

function findTarget(action, targetNo) {
  const store = {
    payablePrepare: () => modules.payablePrepare.listPayablePrepares(),
    payableCheck: () => modules.payableCheck.listPayableChecks(),
    supplierSettlement: () => modules.supplierSettlement.listSupplierSettlements(),
    invoicePrepare: () => modules.invoicePrepare.listInvoicePrepares(),
    accountPayableDraft: () => modules.apDraft.listAccountPayableDrafts(),
    accountPayableConfirm: () => modules.apConfirm.listAccountPayableConfirms(),
    paymentApplication: () => modules.paymentApplication.listPaymentApplications(),
  }
  return (store[action.targetObjectType]?.() || []).find((item) => (
    item[action.targetNoField] === targetNo
    || item.sourceObjectType === action.sourceObjectType
  ))
}

const results = []
for (const action of actions) {
  seedForAction(modules, action.actionCode)
  const sourceBefore = findSource(action)
  const outcome = await modules.executor.executeBusinessFlowAction(action.actionCode)
  const sourceAfter = findSource(action)
  const targetAfter = findTarget(action, outcome.targetNo)
  results.push({
    actionCode: action.actionCode,
    success: outcome.success === true,
    sourceNo: sourceBefore?.[action.sourceNoField] || '',
    targetNo: outcome.targetNo || '',
    sourceWritebackStatus: sourceAfter?.flowWritebackStatus || '',
    sourceDownstreamNo: sourceAfter?.downstreamObjectNo || '',
    targetSourceType: targetAfter?.sourceObjectType || '',
    targetSourceNo: targetAfter?.sourceObjectNo || '',
    flowLinkCount: modules.flowLink.listBusinessFlowLinks().length,
  })
}

const failed = results.filter((item) => (
  !item.success
  || item.sourceWritebackStatus !== 'written_back'
  || !item.sourceDownstreamNo
  || !item.targetSourceType
  || !item.targetSourceNo
))

console.log(JSON.stringify({
  page: 'verifyPurchasePayableToPaymentApplicationWriteback',
  version: 'V1.14.2.3',
  checkedCount: results.length,
  failedCount: failed.length,
  results,
  checkedAt: new Date().toISOString(),
}, null, 2))

if (failed.length) process.exit(1)
