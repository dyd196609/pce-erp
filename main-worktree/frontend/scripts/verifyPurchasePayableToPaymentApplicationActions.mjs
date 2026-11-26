import { executeSeededAction, installMemoryLocalStorage, loadActionModules, seedForAction } from './purchasePayablePaymentActionTestHarness.mjs'

installMemoryLocalStorage()
const modules = await loadActionModules()
const actions = modules.registry.listPurchasePayablePaymentActions()

const results = []
for (const action of actions) {
  const outcome = await executeSeededAction(modules, action.actionCode)
  results.push({
    actionCode: action.actionCode,
    actionName: action.actionName,
    success: outcome.success === true,
    executionStatus: outcome.executionStatus,
    targetNo: outcome.targetNo,
    sourceWritebackStatus: outcome.sourceWritebackStatus,
    flowLinkStatus: outcome.flowLinkStatus,
    transactionCommitted: outcome.transactionCommitted,
    error: outcome.error || '',
  })
}

const failed = results.filter((item) => !item.success || !item.targetNo)
seedForAction(modules, 'CREATE_PAYMENT_APPLICATION')
const firstPaymentApplication = await modules.executor.executeBusinessFlowAction('CREATE_PAYMENT_APPLICATION')
const countAfterFirst = modules.paymentApplication.listPaymentApplications().length
const secondPaymentApplication = await modules.executor.executeBusinessFlowAction('CREATE_PAYMENT_APPLICATION')
const countAfterSecond = modules.paymentApplication.listPaymentApplications().length

seedForAction(modules, 'CREATE_SUPPLIER_SETTLEMENT')
const rollbackOutcome = await modules.executor.executeBusinessFlowAction('CREATE_SUPPLIER_SETTLEMENT', {
  forceFailureAt: 'after_target_created',
})
const rollbackTargetCount = modules.supplierSettlement.listSupplierSettlements().length

const duplicateProtection = {
  firstTargetNo: firstPaymentApplication.targetNo,
  secondExecutionStatus: secondPaymentApplication.executionStatus,
  secondTargetNo: secondPaymentApplication.targetNo,
  countAfterFirst,
  countAfterSecond,
  passed: countAfterFirst === countAfterSecond
    && secondPaymentApplication.executionStatus === 'already_completed_reused'
    && firstPaymentApplication.targetNo === secondPaymentApplication.targetNo,
}

const rollbackCheck = {
  executionStatus: rollbackOutcome.executionStatus,
  rollbackStatus: rollbackOutcome.rollbackStatus,
  cleanupRequired: rollbackOutcome.cleanupRequired,
  targetCountAfterRollback: rollbackTargetCount,
  passed: rollbackOutcome.success === false
    && rollbackOutcome.rollbackStatus === 'rolled_back'
    && rollbackOutcome.cleanupRequired === false
    && rollbackTargetCount === 0,
}

if (!duplicateProtection.passed || !rollbackCheck.passed) failed.push({ actionCode: 'duplicate_or_rollback', success: false })
console.log(JSON.stringify({
  page: 'verifyPurchasePayableToPaymentApplicationActions',
  version: 'V1.14.2.3',
  actionCount: actions.length,
  successCount: results.length - failed.length,
  failedCount: failed.length,
  results,
  duplicateProtection,
  rollbackCheck,
  protectionFlags: {
    submitOrApprove: false,
    executePayment: false,
    generateVoucher: false,
    generateFormalVoucher: false,
    writeOff: false,
    writeLedger: false,
    posting: false,
    bankFlow: false,
  },
  checkedAt: new Date().toISOString(),
}, null, 2))

if (failed.length) process.exit(1)
