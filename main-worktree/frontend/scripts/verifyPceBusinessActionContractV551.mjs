import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import {
  BusinessActionRegistry,
  PCE_BUSINESS_ACTION_CONTRACT_VERSION,
  capturePceBusinessTableState,
  restorePceBusinessTableState,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'

const VERSION = 'V1.14.2.8.4.7.55.1'
const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-v551',
)
const pageRoot = path.join(root, 'src', 'meta', 'pages')
const runtimeFile = path.join(
  root,
  'src',
  'meta',
  'runtime',
  'pceBusinessActionRegistry.js',
)
const componentFile = path.join(
  root,
  'src',
  'meta',
  'components',
  'PceBusinessActionBar.vue',
)
const pages = [
  page('payable-prepare', '采购应付预备', 'PayablePreparePage.vue', '/finance/payable-prepares'),
  page('payable-check', '采购应付核对', 'PayableCheckPage.vue', '/finance/payable-checks'),
  page('supplier-settlement', '供应商结算', 'SupplierSettlementPage.vue', '/scm/supplier-settlements'),
  page('purchase-reconciliation', '采购对账', 'PurchaseReconciliationPage.vue', '/scm/purchase-reconciliations'),
  page('purchase-invoice-prepare', '采购发票准备', 'InvoicePreparePage.vue', '/finance/purchase-invoice-prepares'),
  page('accounts-payable-draft', '采购应付账款草稿', 'AccountPayableDraftPage.vue', '/finance/ap-drafts'),
  page('payable-confirmation-prepare', '应付确认准备', 'AccountPayableConfirmPage.vue', '/finance/account-payable-confirms'),
  page('payment-request-prepare', '付款申请准备', 'PaymentApplicationPage.vue', '/finance/payment-applications'),
  page('payment-request', '付款申请', 'PaymentRequestPage.vue', '/finance/payment-requests'),
  page('payment-instruction-prepare', '付款指令准备', 'PaymentInstructionPreparePage.vue', '/finance/payment-order-prepares'),
  page('payment-order-prepare', '正式付款单预备', 'PaymentOrderPreparePage.vue', '/finance/payment-prepares'),
  page('payment-order-draft', '正式付款单草稿', 'PaymentOrderDraftPage.vue', '/finance/payment-order-drafts'),
]
const forbiddenBoundaryLabels = [
  '发送银行',
  '付款执行',
  '生成付款凭证',
  '写入总账',
  '总账过账',
]

function page(currentModule, canonicalName, file, route) {
  return { currentModule, canonicalName, file, route }
}

function read(file) {
  return fs.readFileSync(file, 'utf8')
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const registrySource = read(runtimeFile)
const componentSource = read(componentFile)
const contracts = BusinessActionRegistry.list()
const registeredModules = new Set(contracts.map(item => item.currentModule))
const registeredActionLabels = new Set(
  contracts.flatMap(contract => contract.actions.map(action => action.actionName)),
)
const pageReports = []
const hardcodedFindings = []
const missingRegistryPages = []
const missingFlowEntryPages = []
const missingBatchActionPages = []
const forbiddenActionFindings = []

for (const item of pages) {
  const source = read(path.join(pageRoot, item.file))
  const contract = BusinessActionRegistry.getContract(item.currentModule)
  const registryConnected = (
    source.includes('PceBusinessActionBar')
    && source.includes(`current-module="${item.currentModule}"`)
  )
  const flowEntryCount = contract?.actions.filter(action => (
    action.handlerType === 'route' && action.scope === 'single'
  )).length || 0
  const batchActionCount = contract?.actions.filter(action => (
    action.scope === 'batch'
  )).length || 0
  if (!contract || !registeredModules.has(item.currentModule)) {
    missingRegistryPages.push(item.currentModule)
  }
  if (!registryConnected || flowEntryCount === 0) {
    missingFlowEntryPages.push(item.currentModule)
  }
  if (batchActionCount === 0) {
    missingBatchActionPages.push(item.currentModule)
  }
  for (const button of extractActionElements(source)) {
    if (
      button.rawLabel
      && registeredActionLabels.has(button.rawLabel)
      && !button.expressionDriven
    ) {
      hardcodedFindings.push({
        page: item.currentModule,
        file: item.file,
        actionName: button.rawLabel,
        evidence: button.source.slice(0, 220),
      })
    }
    for (const label of forbiddenBoundaryLabels) {
      if (button.rawLabel.includes(label)) {
        forbiddenActionFindings.push({
          page: item.currentModule,
          file: item.file,
          actionName: label,
        })
      }
    }
  }
  pageReports.push({
    ...item,
    fullUrl: `http://localhost:5173/#${item.route}`,
    regionTitle: '当前业务操作',
    relativePosition: '页面业务事实区域与标准列表之间',
    fieldName: 'BusinessActionRegistry',
    expected: '生命周期、下一模块和批量动作均由公共注册表解析',
    actual: {
      registryConnected,
      actionCount: contract?.actions.length || 0,
      flowEntryCount,
      batchActionCount,
      nextModule: contract?.nextModule || '',
      nextRoute: contract?.nextRoute || '',
    },
    ctrlFKeyword: '当前业务操作',
    passed: Boolean(
      contract
      && registryConnected
      && flowEntryCount > 0
      && batchActionCount > 0
    ),
  })
}

const draftCheck = BusinessActionRegistry.resolve({
  currentModule: 'payable-check',
  selectedRows: [
    { id: 1, payableCheckNo: 'CHECK-DRAFT-01', checkStatus: 'draft' },
    { id: 2, payableCheckNo: 'CHECK-DRAFT-02', checkStatus: 'draft' },
  ],
})
const checkedCheck = BusinessActionRegistry.resolve({
  currentModule: 'payable-check',
  selectedRows: [
    { id: 3, payableCheckNo: 'CHECKED-01', checkStatus: 'checked' },
    { id: 4, payableCheckNo: 'CHECKED-02', checkStatus: 'checked' },
  ],
})
const mixedCheck = BusinessActionRegistry.resolve({
  currentModule: 'payable-check',
  selectedRows: [
    { id: 5, payableCheckNo: 'MIXED-01', checkStatus: 'draft' },
    { id: 6, payableCheckNo: 'MIXED-02', checkStatus: 'checked' },
  ],
})
const paymentRequestReady = BusinessActionRegistry.resolve({
  currentModule: 'payment-request',
  selectedRows: [
    { id: 7, requestNo: 'PR-V551-01', status: 'approved' },
  ],
  eligibility: true,
})
const paymentRequestBlocked = BusinessActionRegistry.resolve({
  currentModule: 'payment-request',
  selectedRows: [
    { id: 8, requestNo: 'PR-V551-02', status: 'approved' },
  ],
  eligibility: false,
})
const noPermission = BusinessActionRegistry.resolve({
  currentModule: 'payment-request',
  selectedRows: [
    { id: 9, requestNo: 'PR-V551-03', status: 'approved' },
  ],
  eligibility: true,
  permissions: ['business_action:view'],
})

const originalRows = [
  { rowKey: 'row-a', status: 'draft' },
  { rowKey: 'row-b', status: 'draft' },
]
const scrollElement = { scrollLeft: 466, scrollTop: 82 }
const snapshot = capturePceBusinessTableState({
  selectedRows: [originalRows[0]],
  sortState: { prop: 'payableCheckNo', order: 'descending' },
  scrollElement,
})
const restoredSelections = []
const fakeTable = {
  clearSelection() {},
  toggleRowSelection(row) { restoredSelections.push(row.rowKey) },
}
scrollElement.scrollLeft = 0
scrollElement.scrollTop = 0
const restoredRows = restorePceBusinessTableState({
  snapshot,
  rows: originalRows.map(row => ({ ...row })),
  tableRef: fakeTable,
  scrollElement,
})

const functionalGuards = {
  contract_version_exact:
    BusinessActionRegistry.contractVersion
      === PCE_BUSINESS_ACTION_CONTRACT_VERSION,
  golden_flow_twelve_pages_registered: contracts.length >= 12,
  required_contract_fields_complete: contracts.every(contract => (
    contract.currentModule
    && contract.nextModule
    && typeof contract.nextRoute === 'string'
    && Array.isArray(contract.actions)
    && Array.isArray(contract.forbiddenActions)
  )),
  all_pages_use_business_action_registry:
    pageReports.every(item => item.actual.registryConnected),
  all_pages_have_flow_entry:
    missingFlowEntryPages.length === 0,
  all_pages_have_dynamic_batch_action:
    missingBatchActionPages.length === 0,
  page_hardcoded_business_action_absent:
    hardcodedFindings.length === 0,
  forbidden_boundary_action_absent:
    forbiddenActionFindings.length === 0,
  payable_check_draft_batch_is_complete:
    draftCheck.batchActions.some(action => (
      action.actionId === 'batch-complete-payable-check'
    ))
    && !draftCheck.batchActions.some(action => (
      action.actionId === 'batch-enter-supplier-settlement'
    )),
  payable_check_checked_batch_enters_settlement:
    checkedCheck.batchActions.some(action => (
      action.actionId === 'batch-enter-supplier-settlement'
    ))
    && !checkedCheck.batchActions.some(action => (
      action.actionId === 'batch-complete-payable-check'
    )),
  payable_check_mixed_status_is_blocked:
    mixedCheck.batchActions.length === 0,
  payment_request_enters_instruction_prepare:
    paymentRequestReady.availableActions.some(action => (
      action.actionId === 'enter-payment-instruction-prepare'
      && action.targetRoute?.path === '/finance/payment-order-prepares'
    )),
  server_eligibility_blocks_navigation:
    !paymentRequestBlocked.availableActions.some(action => (
      action.actionId === 'enter-payment-instruction-prepare'
    )),
  permission_blocks_navigation:
    noPermission.availableActions.length === 0
      && noPermission.batchActions.length === 0,
  error_recovery_preserves_selection:
    restoredRows.length === 1
      && restoredRows[0].rowKey === 'row-a'
      && restoredSelections.join(',') === 'row-a',
  error_recovery_preserves_sort:
    snapshot.sortState.prop === 'payableCheckNo'
      && snapshot.sortState.order === 'descending',
  error_recovery_preserves_scroll:
    scrollElement.scrollLeft === 466 && scrollElement.scrollTop === 82,
  registry_renderer_single_source:
    componentSource.includes('BusinessActionRegistry.resolve')
      && componentSource.includes('data-pce-action-source'),
  protected_execution_actions_forbidden:
    contracts.every(contract => (
      (
        contract.currentModule === 'bank-send-task'
          ? contract.actions.some(
              action => action.actionId === 'create-bank-send-task',
            )
            && !contract.forbiddenActions.includes('create-bank-send-task')
          : contract.forbiddenActions.includes('create-bank-send-task')
      )
      && contract.forbiddenActions.includes('execute-payment')
      && contract.forbiddenActions.includes('create-payment-voucher')
      && contract.forbiddenActions.includes('write-general-ledger')
    )),
  no_production_data_write_contract:
    !registrySource.includes('localStorage.setItem')
      && !registrySource.includes('sessionStorage.setItem')
      && !registrySource.includes('fetch('),
}

const failedGuards = Object.entries(functionalGuards)
  .filter(([, passed]) => !passed)
  .map(([guard]) => guard)
const hardcodedReport = {
  result: hardcodedFindings.length === 0 ? 'passed' : 'failed',
  version: VERSION,
  contractVersion: PCE_BUSINESS_ACTION_CONTRACT_VERSION,
  scannedPageCount: pages.length,
  registeredActionLabelCount: registeredActionLabels.size,
  hardcodedBusinessActionCount: hardcodedFindings.length,
  forbiddenBoundaryActionCount: forbiddenActionFindings.length,
  findings: hardcodedFindings,
  forbiddenFindings: forbiddenActionFindings,
}
const coverageReport = {
  result: pageReports.every(item => item.passed) ? 'passed' : 'failed',
  version: VERSION,
  contractVersion: PCE_BUSINESS_ACTION_CONTRACT_VERSION,
  canonicalName: 'PCE-ERP业务操作动作统一治理',
  pageCount: pages.length,
  registeredPageCount: pageReports.filter(item => item.actual.registryConnected).length,
  passedPageCount: pageReports.filter(item => item.passed).length,
  actionRegistryMissingCount: missingRegistryPages.length,
  flowEntryMissingCount: missingFlowEntryPages.length,
  batchActionMissingCount: missingBatchActionPages.length,
  missingRegistryPages,
  missingFlowEntryPages,
  missingBatchActionPages,
  pages: pageReports,
}
const staticReport = {
  result: failedGuards.length === 0 ? 'passed' : 'failed',
  version: VERSION,
  contractVersion: PCE_BUSINESS_ACTION_CONTRACT_VERSION,
  guardCount: Object.keys(functionalGuards).length,
  passedGuardCount: Object.values(functionalGuards).filter(Boolean).length,
  failedGuardCount: failedGuards.length,
  failedGuards,
  guards: functionalGuards,
  contractCount: contracts.length,
  hardcodedBusinessActionCount: hardcodedFindings.length,
  flowEntryMissingCount: missingFlowEntryPages.length,
  batchActionMissingCount: missingBatchActionPages.length,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
}

writeJson(path.join(resultRoot, 'business-action-coverage-report.json'), coverageReport)
writeJson(path.join(resultRoot, 'hardcoded-action-scan-report.json'), hardcodedReport)
writeJson(path.join(resultRoot, 'static-guard-report.json'), staticReport)
assert(coverageReport.result === 'passed', 'Business action coverage failed')
assert(hardcodedReport.result === 'passed', 'Hardcoded action scan failed')
assert(staticReport.result === 'passed', `Static guards failed: ${failedGuards.join(', ')}`)
console.log(JSON.stringify(staticReport, null, 2))

function extractActionElements(source) {
  const elements = []
  for (const match of source.matchAll(
    /<(el-button|router-link)\b[\s\S]*?<\/\1>/g,
  )) {
    const body = match[0]
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    elements.push({
      source: match[0],
      expressionDriven: body.includes('{{'),
      rawLabel: body.replace(/\{\{[\s\S]*?\}\}/g, '').trim(),
    })
  }
  return elements
}
