import { PCE_PAGE_CONTRACT_ENGINE_VERSION } from '../runtime/pcePageContractEngine.js'
import { BUSINESS_ACCEPTANCE_COPY_VERSION } from '../runtime/businessAcceptanceCopy.js'
import { PAYMENT_REQUEST_PREPARE_VERSION } from '../runtime/paymentRequestPrepareRuntime.js'
import { PAYMENT_REQUEST_VERSION } from '../runtime/paymentRequestRuntime.js'
import { PAYMENT_INSTRUCTION_PREPARE_VERSION } from '../runtime/paymentInstructionPrepareRuntime.js'
import { PAYMENT_ORDER_PREPARE_VERSION } from '../runtime/paymentOrderPrepareRuntime.js'
import { PAYMENT_ORDER_DRAFT_VERSION } from '../runtime/paymentOrderDraftRuntime.js'
import { PAYMENT_RISK_REVIEW_VERSION } from '../runtime/paymentRiskReviewRuntime.js'
import { FORMAL_PAYMENT_ORDER_VERSION } from '../runtime/formalPaymentOrderRuntime.js'
import { BANK_SEND_PREPARATION_VERSION } from '../runtime/bankSendPreparationRuntime.js'
import { BANK_SEND_TASK_VERSION } from '../runtime/bankSendTaskRuntime.js'
import { BANK_SEND_EXECUTION_GATE_VERSION } from '../runtime/bankSendExecutionGateRuntime.js'
import { BANK_SEND_REQUEST_VERSION } from '../runtime/bankSendRequestRuntime.js'
import { BANK_SEND_SIMULATION_VERSION } from '../runtime/bankSendSimulationRuntime.js'
import { BANK_SEND_SIMULATION_ISOLATION_VERSION } from '../runtime/bankSendSimulationIsolationRuntime.js'
import { BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION } from '../runtime/bankSendChainFinalApprovalRuntime.js'
import { BANK_SEND_PRODUCTION_RELEASE_VERSION } from '../runtime/bankSendProductionReleaseRuntime.js'
import { BANK_SEND_EXECUTION_FRAMEWORK_VERSION } from '../runtime/bankSendExecutionFrameworkRuntime.js'
import { listBusinessProcessSteps } from './businessProcessRegistry.js'

export const FINANCE_PROCESS_STRUCTURE_VERSION = 'V1.14.2.8.4.7.52'
export const FINANCE_STRICT_ACCEPTANCE_MIGRATION_VERSION = 'V1.14.2.8.4.7.52'

export const DEFAULT_PAGE_OBSERVABILITY_ACTIONS = Object.freeze({
  refresh: true,
  copyDiagnostics: true,
  returnToProcessCenter: true,
  location: 'page_action_bar',
  sourceRequirement: 'current_server_state',
  readOnly: true,
})

const commonStructureSequence = Object.freeze([
  'framework_title',
  'operation_summary',
  'process_navigation',
  'business_content',
  'formal_list',
])

const entries = [
  ['payable-prepare', 'FIN_PAYABLE_PREPARE', '采购应付预备', '/finance/payable-prepares', 'FinancePayablePrepares', 'PayablePreparePage.vue', 'V1.14.2.8.4.7.32', 'payable-prepare-main'],
  ['payable-check', 'FIN_PAYABLE_CHECK', '采购应付核对', '/finance/payable-checks', 'FinancePayableChecks', 'PayableCheckPage.vue', 'V1.14.2.8.4.7', 'payable-check-main'],
  ['supplier-settlement', 'SCM_SUPPLIER_SETTLEMENT', '供应商结算', '/scm/supplier-settlements', 'ScmSupplierSettlements', 'SupplierSettlementPage.vue', 'V1.14.2.8.4.7', 'supplier-settlement-main'],
  ['purchase-reconciliation', 'SCM_PURCHASE_RECONCILIATION', '采购对账', '/scm/purchase-reconciliations', 'ScmPurchaseReconciliations', 'PurchaseReconciliationPage.vue', 'V1.14.2.8.4.7.42', 'purchase-reconciliation-main'],
  ['invoice-prepare', 'FIN_INVOICE_PREPARE', '采购发票准备', '/finance/purchase-invoice-prepares', 'FinancePurchaseInvoicePrepares', 'InvoicePreparePage.vue', 'V1.14.2.8.4.7.43.1', 'invoice-prepare-main'],
  ['account-payable-draft', 'FIN_AP_DRAFT', '采购应付账款草稿', '/finance/ap-drafts', 'FinanceAccountPayableDrafts', 'AccountPayableDraftPage.vue', 'V1.14.2.8.4.7.45.3', 'account-payable-draft-main'],
  ['account-payable-confirm', 'FIN_AP_CONFIRM', '应付确认准备', '/finance/account-payable-confirms', 'FinanceAccountPayableConfirms', 'AccountPayableConfirmPage.vue', 'V1.14.2.8.4.7.46', 'account-payable-confirm-main'],
  ['payment-application', 'FIN_PAYMENT_APPLICATION', '付款申请准备', '/finance/payment-applications', 'FinancePaymentApplications', 'PaymentApplicationPage.vue', PAYMENT_REQUEST_PREPARE_VERSION, 'payment-application-main'],
  ['payment-request', 'FIN_PAYMENT_REQUEST', '付款申请', '/finance/payment-requests', 'FinancePaymentRequests', 'PaymentRequestPage.vue', PAYMENT_REQUEST_VERSION, 'payment-request-main'],
  ['payment-instruction-prepare', 'FIN_PAYMENT_INSTRUCTION_PREPARE', '付款指令准备', '/finance/payment-order-prepares', 'FinancePaymentOrderPrepares', 'PaymentInstructionPreparePage.vue', PAYMENT_INSTRUCTION_PREPARE_VERSION, 'payment-instruction-prepare-main'],
  ['payment-order-prepare', 'FIN_PAYMENT_ORDER_PREPARE', '正式付款单预备', '/finance/payment-prepares', 'FinancePaymentPrepares', 'PaymentOrderPreparePage.vue', PAYMENT_ORDER_PREPARE_VERSION, 'payment-order-prepare-main'],
  ['payment-order-draft', 'FIN_PAYMENT_ORDER_DRAFT', '正式付款单草稿', '/finance/payment-order-drafts', 'FinancePaymentOrderDrafts', 'PaymentOrderDraftPage.vue', PAYMENT_ORDER_DRAFT_VERSION, 'payment-order-draft-main'],
  ['payment-risk-review', 'FIN_PAYMENT_RISK_REVIEW', '真实付款风险评审', '/finance/payment-risk-reviews', 'FinancePaymentRiskReviews', 'PaymentExecutionRiskReviewPage.vue', PAYMENT_RISK_REVIEW_VERSION, 'payment-risk-reviews-main'],
  ['formal-payment-order', 'FIN_FORMAL_PAYMENT_ORDER', '正式付款单', '/finance/formal-payment-orders', 'FinanceFormalPaymentOrders', 'FormalPaymentOrderPage.vue', FORMAL_PAYMENT_ORDER_VERSION, 'formal-payment-orders-main'],
  ['bank-send-preparation', 'FIN_BANK_SEND_PREPARATION', '银行发送准备', '/finance/bank-send-prepares', 'FinanceBankSendPrepares', 'BankSendPreparationPage.vue', BANK_SEND_PREPARATION_VERSION, 'bank-send-preparations-main'],
  ['bank-send-task', 'FIN_BANK_SEND_TASK', '银行发送任务', '/finance/bank-send-tasks', 'FinanceBankSendTasks', 'BankSendTaskPage.vue', BANK_SEND_TASK_VERSION, 'bank-send-tasks-main'],
  ['bank-send-execution-gate', 'FIN_BANK_SEND_EXECUTION_GATE', '银行发送执行授权', '/finance/bank-send-execution-gates', 'FinanceBankSendExecutionGates', 'BankSendExecutionGatePage.vue', BANK_SEND_EXECUTION_GATE_VERSION, 'bank-send-execution-gates-main'],
  ['bank-send-request', 'FIN_BANK_SEND_REQUEST', '银行发送请求准备', '/finance/bank-send-requests', 'FinanceBankSendRequests', 'BankSendRequestPage.vue', BANK_SEND_REQUEST_VERSION, 'bank-send-requests-main'],
  ['bank-send-simulation', 'FIN_BANK_SEND_SIMULATION', '银行发送执行模拟', '/finance/bank-send-simulations', 'FinanceBankSendSimulations', 'BankSendSimulationPage.vue', BANK_SEND_SIMULATION_VERSION, 'bank-send-simulations-main'],
  ['bank-send-simulation-audit', 'FIN_BANK_SEND_SIMULATION_AUDIT', '银行发送模拟审计', '/finance/bank-send-simulation-audits', 'FinanceBankSendSimulationAudits', 'BankSendSimulationAuditPage.vue', BANK_SEND_SIMULATION_ISOLATION_VERSION, 'bank-send-simulation-audits-main'],
  ['bank-send-isolation-gate', 'FIN_BANK_SEND_ISOLATION_GATE', '银行发送生产隔离门禁', '/finance/bank-send-isolation-gates', 'FinanceBankSendIsolationGates', 'BankSendIsolationGatePage.vue', BANK_SEND_SIMULATION_ISOLATION_VERSION, 'bank-send-isolation-gates-main'],
  ['bank-send-chain-trace', 'FIN_BANK_SEND_CHAIN_TRACE', '银行发送全链路追踪', '/finance/bank-send-chain-traces', 'FinanceBankSendChainTraces', 'BankSendChainTracePage.vue', BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION, 'bank-send-chain-traces-main'],
  ['bank-send-final-approval', 'FIN_BANK_SEND_FINAL_APPROVAL', '银行发送最终审批', '/finance/bank-send-final-approvals', 'FinanceBankSendFinalApprovals', 'BankSendFinalApprovalPage.vue', BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION, 'bank-send-final-approvals-main'],
  ['bank-send-dual-isolation-check', 'FIN_BANK_SEND_DUAL_ISOLATION_CHECK', '银行发送双重隔离检查', '/finance/bank-send-dual-isolation-checks', 'FinanceBankSendDualIsolationChecks', 'BankSendDualIsolationCheckPage.vue', BANK_SEND_PRODUCTION_RELEASE_VERSION, 'bank-send-dual-isolation-checks-main'],
  ['bank-send-production-release-review', 'FIN_BANK_SEND_PRODUCTION_RELEASE_REVIEW', '真实银行发送前生产隔离评审', '/finance/bank-send-production-release-reviews', 'FinanceBankSendProductionReleaseReviews', 'BankSendProductionReleaseReviewPage.vue', BANK_SEND_PRODUCTION_RELEASE_VERSION, 'bank-send-production-release-reviews-main'],
  ['bank-send-execution-framework-review', 'FIN_BANK_SEND_EXECUTION_FRAMEWORK_REVIEW', '银行发送执行框架评审', '/finance/bank-send-execution-framework-reviews', 'FinanceBankSendExecutionFrameworkReviews', 'BankSendExecutionFrameworkReviewPage.vue', BANK_SEND_EXECUTION_FRAMEWORK_VERSION, 'bank-send-execution-framework-reviews-main'],
  ['bank-connector-adapter-review', 'FIN_BANK_CONNECTOR_ADAPTER_REVIEW', '银行接口适配评审', '/finance/bank-connector-adapter-reviews', 'FinanceBankConnectorAdapterReviews', 'BankConnectorAdapterReviewPage.vue', BANK_SEND_EXECUTION_FRAMEWORK_VERSION, 'bank-connector-adapter-reviews-main'],
]

export const financeProcessPageRegistry = Object.freeze(entries.map(([
  pageStepId,
  moduleCode,
  canonicalName,
  routePath,
  routeName,
  pageComponent,
  runtimeBusinessVersion,
  mainTableId,
]) => Object.freeze({
  pageStepId,
  moduleCode,
  canonicalName,
  routePath,
  fullUrl: `http://localhost:5173/#${routePath}`,
  routeName,
  pageComponent: `src/meta/pages/${pageComponent}`,
  outerShellComponent: 'ProfitCockpit.vue',
  frameworkShellComponent: 'PceListPageShell.vue',
  operationShellComponent: 'BusinessOperationPageShell.vue',
  listComponent: 'StandardListToolbar.vue',
  runtimeBusinessVersion,
  mainTableId,
  pageFrameworkVersion: PCE_PAGE_CONTRACT_ENGINE_VERSION,
  operationFrameworkVersion: BUSINESS_ACCEPTANCE_COPY_VERSION,
  structureSequence: commonStructureSequence,
  observabilityActions: DEFAULT_PAGE_OBSERVABILITY_ACTIONS,
  enforcementMode: 'strict',
  acceptanceLevel: 5,
  acceptanceMigrationVersion: FINANCE_STRICT_ACCEPTANCE_MIGRATION_VERSION,
})))

export function findFinanceProcessPage(pageStepIdOrRoutePath = '') {
  const value = String(pageStepIdOrRoutePath)
  return financeProcessPageRegistry.find(item => (
    item.pageStepId === value || item.routePath === value
  )) || null
}

const STRICT_FLOW_START = 'payable-prepare'
const STRICT_FLOW_END = 'bank-send-task'

export function listFinanceStrictProcessSteps() {
  const steps = listBusinessProcessSteps()
  const start = steps.findIndex(step => step.stepId === STRICT_FLOW_START)
  const end = steps.findIndex(step => step.stepId === STRICT_FLOW_END)
  return steps.slice(start, end + 1).map(step => ({
    pageStepId: step.stepId,
    canonicalName: step.pageTitle || step.stepName,
    routePath: step.routePath,
  }))
}
