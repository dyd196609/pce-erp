import {
  PURCHASE_PAYABLE_PAYMENT_PROCESS_ID,
  listBusinessProcessSteps,
  resolveBusinessProcessContext,
} from '../src/meta/process/businessProcessRegistry.js'
import { listBusinessActionsByStep } from '../src/meta/process/businessActionRegistry.js'

const expectedFlow = [
  'purchase-receive-preview',
  'incoming-inspection',
  'payable-prepare',
  'payable-check',
  'supplier-settlement',
  'purchase-reconciliation',
  'invoice-prepare',
  'account-payable-draft',
  'account-payable-confirm',
  'payment-application',
  'payment-instruction-prepare',
  'payment-order-prepare',
  'payment-order-draft',
  'payment-risk-review',
  'payment-execution-prepare',
  'payment-execution',
  'payment-voucher-draft',
  'payment-voucher-review',
  'payment-record-review',
  'formal-payment-voucher',
]

const expectedRoutes = {
  'purchase-receive-preview': '/wms/purchase-receive-preview',
  'incoming-inspection': '/qms/incoming-inspections',
  'payable-prepare': '/finance/payable-prepares',
  'payable-check': '/finance/payable-checks',
  'supplier-settlement': '/scm/supplier-settlements',
  'purchase-reconciliation': '/scm/purchase-reconciliations',
  'invoice-prepare': '/finance/purchase-invoice-prepares',
  'account-payable-draft': '/finance/ap-drafts',
  'account-payable-confirm': '/finance/account-payable-confirms',
  'payment-application': '/finance/payment-applications',
  'payment-instruction-prepare': '/finance/payment-order-prepares',
  'payment-order-prepare': '/finance/payment-prepares',
  'payment-order-draft': '/finance/payment-order-drafts',
  'payment-risk-review': '/finance/payment-risk-reviews',
  'payment-execution-prepare': '/finance/payment-execution-prepares',
  'payment-execution': '/finance/payment-executions',
  'payment-voucher-draft': '/finance/payment-voucher-drafts',
  'payment-voucher-review': '/finance/payment-voucher-reviews',
  'payment-record-review': '/finance/payment-record-reviews',
  'formal-payment-voucher': '/finance/formal-payment-vouchers',
}

const errors = []
function assert(condition, message) {
  if (!condition) errors.push(message)
}

const steps = listBusinessProcessSteps()
const stepById = new Map(steps.map((step) => [step.stepId, step]))

assert(steps.length === expectedFlow.length, `流程步骤数量应为 ${expectedFlow.length}，实际为 ${steps.length}`)

expectedFlow.forEach((stepId, index) => {
  const step = stepById.get(stepId)
  assert(Boolean(step), `缺少流程步骤：${stepId}`)
  if (!step) return

  assert(step.processId === PURCHASE_PAYABLE_PAYMENT_PROCESS_ID, `${stepId} 流程 ID 不正确`)
  assert(step.stepSequence === index + 1, `${stepId} 步骤序号不正确`)
  assert(step.routePath === expectedRoutes[stepId], `${stepId} 路由不正确：${step.routePath}`)

  const previousStepId = expectedFlow[index - 1] || null
  const nextStepId = expectedFlow[index + 1] || null
  if (previousStepId) assert(step.previousStepId === previousStepId, `${stepId} 上一步应为 ${previousStepId}`)
  if (nextStepId) assert(step.defaultNextStepId === nextStepId, `${stepId} 默认下一步应为 ${nextStepId}`)
  if (!nextStepId) assert(!step.defaultNextStepId && step.nextStepIds.length === 0, `${stepId} 应为流程终点`)

  const context = resolveBusinessProcessContext(step.routePath)
  assert(context?.step?.stepId === stepId, `${stepId} 无法通过路由解析上下文`)
  if (previousStepId) assert(context.previousStep?.stepId === previousStepId, `${stepId} 通过路由解析的上一步不正确`)
  if (nextStepId) assert(context.defaultNextStep?.stepId === nextStepId, `${stepId} 通过路由解析的下一步不正确`)

  const actions = listBusinessActionsByStep(stepId)
  assert(actions.some((action) => action.actionCode === `view_source_${stepId}`), `${stepId} 缺少查看来源动作`)
  if (previousStepId) assert(actions.some((action) => action.actionCode === `go_previous_${stepId}`), `${stepId} 缺少上一步动作`)
  if (nextStepId) assert(actions.some((action) => action.actionCode === `go_next_${stepId}`), `${stepId} 缺少下一步动作`)
})

if (errors.length) {
  console.error('采购到付款关键链路校验失败：')
  errors.forEach((error) => console.error(`- ${error}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'verifyPurchasePayablePaymentFlow',
  version: 'V1.14.2.8.2',
  processId: PURCHASE_PAYABLE_PAYMENT_PROCESS_ID,
  stepCount: steps.length,
  firstStep: expectedFlow[0],
  lastStep: expectedFlow[expectedFlow.length - 1],
  payablePrepare: {
    routePath: expectedRoutes['payable-prepare'],
    sourcePage: expectedRoutes['incoming-inspection'],
    nextPage: expectedRoutes['payable-check'],
  },
  completeFlow: expectedFlow.map((stepId) => ({
    stepId,
    routePath: expectedRoutes[stepId],
  })),
  protectionFlags: {
    writeBusinessData: false,
    modifyPurchaseOrder: false,
    modifyReceipt: false,
    modifyInspection: false,
    modifyInventory: false,
    modifyPayable: false,
    modifyPayment: false,
    writeLedger: false,
    writeOffPayment: false,
    generateBankFlow: false,
  },
  checkedAt: new Date().toISOString(),
}, null, 2))
