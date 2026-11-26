import { installMemoryLocalStorage, loadActionModules, seedForAction } from './purchasePayablePaymentActionTestHarness.mjs'

installMemoryLocalStorage()
const modules = await loadActionModules()

seedForAction(modules, 'CREATE_PAYMENT_APPLICATION')
const outcome = await modules.executor.executeBusinessFlowAction('CREATE_PAYMENT_APPLICATION')
const paymentApplications = modules.paymentApplication.listPaymentApplications()
const release = modules.transition.evaluateBusinessFlowNextStep('payment-application')
const target = paymentApplications.find((item) => item.paymentApplicationNo === outcome.targetNo)
const evidenceStatus = release.evidence?.targetEvidenceStatus || ''
const acceptableBlockReason = release.reason.includes('后续版本接入')
  || release.reason.includes('证据不完整')
  || release.reason.includes('存在冲突')
  || release.reason.includes('读取失败')

const checks = [
  { code: 'payment_application_created', passed: Boolean(outcome.success && target?.paymentApplicationNo) },
  { code: 'next_step_blocked', passed: release.released === false },
  { code: 'block_reason_precise', passed: acceptableBlockReason },
  { code: 'target_evidence_status_available', passed: ['complete', 'incomplete', 'conflict', 'read_failed', 'not_found'].includes(evidenceStatus) },
  { code: 'not_submitted', passed: target?.paymentApplicationStatus === 'draft' },
  { code: 'not_approved', passed: target?.paymentApprovalStatus === 'not_submitted' },
  { code: 'not_paid', passed: target?.paymentExecutionStatus === 'not_started' },
  { code: 'voucher_not_generated', passed: target?.paymentVoucherStatus === 'not_generated' },
  { code: 'writeoff_not_written', passed: target?.writeOffStatus === 'not_written_off' },
  { code: 'ledger_not_written', passed: target?.ledgerStatus === 'not_written_ledger' },
  { code: 'posting_not_posted', passed: target?.postingStatus === 'not_posted' },
]

const failed = checks.filter((item) => !item.passed)
console.log(JSON.stringify({
  page: 'verifyPurchasePayableToPaymentApplicationClosure',
  version: 'V1.14.2.7',
  outcome,
  release,
  chineseSummary: {
    付款申请是否创建: outcome.targetCreated === true || Boolean(target?.paymentApplicationNo) ? '是' : '否',
    来源应付确认状态是否回写: outcome.sourceWritebackStatus === 'written_back' ? '是' : '否',
    双向关联是否完成: outcome.flowLinkStatus === 'linked' ? '是' : '否',
    事务是否提交: outcome.transactionCommitted === true ? '是' : '否',
    是否执行回滚: outcome.rollbackStatus === 'rolled_back' ? '是' : '否',
    是否需要人工清理: outcome.cleanupRequired === true ? '是' : '否',
    采购应付至付款申请闭环是否完成: Boolean(outcome.success && target?.paymentApplicationNo) ? '是' : '否',
    目标证据状态: evidenceStatus,
    付款指令准备是否放行: release.released === true ? '是' : '否',
    付款指令准备未放行原因: release.reason,
  },
  checks,
  failedCount: failed.length,
  protectionFlags: {
    autoSubmit: false,
    autoApprove: false,
    executePayment: false,
    generatePaymentVoucher: false,
    generateFormalPaymentVoucher: false,
    writeOff: false,
    writeLedger: false,
    posting: false,
    bankFlow: false,
  },
  overall: failed.length ? 'failed' : 'passed',
}, null, 2))

if (failed.length) process.exit(1)

