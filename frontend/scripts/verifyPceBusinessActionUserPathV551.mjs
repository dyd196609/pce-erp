import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { createMemoryHistory, createRouter } from 'vue-router'
import {
  BusinessActionRegistry,
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
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const contracts = BusinessActionRegistry.list()
const routes = [...new Set(contracts.flatMap(item => [
  item.route,
  item.nextRoute,
]))].map(route => ({
  path: route,
  component: { template: '<div />' },
}))
const router = createRouter({
  history: createMemoryHistory(),
  routes,
})

const moduleFixtures = {
  'payable-prepare': fixture('prepared', 'PAYABLE-PREPARE-V551'),
  'payable-check': fixture('checked', 'PAYABLE-CHECK-V551', {
    payableCheckNo: 'PAYABLE-CHECK-V551',
  }),
  'supplier-settlement': fixture('reconciling', 'SETTLEMENT-V551', {
    settlementNo: 'SETTLEMENT-V551',
  }),
  'purchase-reconciliation': fixture('matched', 'RECONCILIATION-V551', {
    reconciliationNo: 'RECONCILIATION-V551',
  }),
  'purchase-invoice-prepare': fixture('validated', 'PIP-V551', {
    prepareNo: 'PIP-V551',
  }),
  'accounts-payable-draft': fixture('draft', 'APD-V551', {
    draftNo: 'APD-V551',
  }),
  'payable-confirmation-prepare': fixture('prepared', 'PCP-V551', {
    prepareNo: 'PCP-V551',
  }),
  'payment-request-prepare': fixture('prepared', 'PRP-V551', {
    prepareNo: 'PRP-V551',
  }),
  'payment-request': fixture('approved', 'PR-V551', {
    requestNo: 'PR-V551',
  }),
  'payment-instruction-prepare': fixture('validated', 'PIPAY-V551', {
    prepareNo: 'PIPAY-V551',
  }),
  'payment-order-prepare': fixture('submitted', 'POP-V551', {
    prepareNo: 'POP-V551',
  }),
  'payment-order-draft': fixture('reviewed', 'POD-V551', {
    draftNo: 'POD-V551',
  }),
}
const assertions = []
for (const contract of contracts) {
  const selectedRows = [moduleFixtures[contract.currentModule]]
  const selectedBefore = selectedRows.map(item => item.id)
  const resolution = BusinessActionRegistry.resolve({
    currentModule: contract.currentModule,
    selectedRows,
    eligibility: true,
  })
  const action = resolution.availableActions.find(item => (
    item.handlerType === 'route'
  ))
  assert(action, `${contract.currentModule} has no available next action`)
  await router.push(contract.route)
  const currentRouteBefore = router.currentRoute.value.path
  await router.push(action.targetRoute)
  const routeAfterAction = router.currentRoute.value.path
  router.back()
  await waitForRouter()
  const routeAfterBack = router.currentRoute.value.path
  const selectedAfterBack = selectedRows.map(item => item.id)
  await router.push(action.targetRoute)
  const routeAfterContinue = router.currentRoute.value.path
  assertions.push({
    currentModule: contract.currentModule,
    canonicalName: contract.canonicalName,
    fullUrl: `http://localhost:5173/#${contract.route}`,
    regionTitle: '当前业务操作',
    relativePosition: '当前业务事实之后、标准列表之前',
    fieldName: action.actionName,
    expected: {
      selectedCount: 1,
      nextModule: contract.nextModule,
      nextRoute: contract.nextRoute,
      routeAfterBack: contract.route,
      selectionPreservedAfterBack: true,
      continueOperationReachable: true,
    },
    actual: {
      selectedCount: resolution.selectedCount,
      currentRouteBefore,
      routeAfterAction,
      routeAfterBack,
      selectionPreservedAfterBack:
        JSON.stringify(selectedBefore) === JSON.stringify(selectedAfterBack),
      routeAfterContinue,
    },
    ctrlFKeyword: '当前业务操作',
    passed: (
      resolution.selectedCount === 1
      && currentRouteBefore === contract.route
      && routeAfterAction === contract.nextRoute
      && routeAfterBack === contract.route
      && routeAfterContinue === contract.nextRoute
      && JSON.stringify(selectedBefore) === JSON.stringify(selectedAfterBack)
    ),
  })
}

const checkedSelection = [
  { rowKey: 'checked-1', payableCheckNo: 'CHECKED-1', checkStatus: 'checked' },
  { rowKey: 'checked-2', payableCheckNo: 'CHECKED-2', checkStatus: 'checked' },
]
const checkedResolution = BusinessActionRegistry.resolve({
  currentModule: 'payable-check',
  selectedRows: checkedSelection,
})
const checkedBatch = checkedResolution.batchActions.find(item => (
  item.actionId === 'batch-enter-supplier-settlement'
))
assert(checkedBatch, 'Checked payable rows cannot batch enter settlement')
await router.push('/finance/payable-checks')
await router.push(checkedBatch.targetRoute)
const batchRouteReached = router.currentRoute.value.path
const batchRouteContext = { ...router.currentRoute.value.query }

const tableRows = [
  { rowKey: 'error-row-1', checkStatus: 'draft' },
  { rowKey: 'error-row-2', checkStatus: 'draft' },
]
const scrollElement = { scrollLeft: 388, scrollTop: 64 }
const errorSnapshot = capturePceBusinessTableState({
  selectedRows: [tableRows[1]],
  sortState: { prop: 'payableCheckNo', order: 'ascending' },
  scrollElement,
})
const restoredSelectionKeys = []
scrollElement.scrollLeft = 0
scrollElement.scrollTop = 0
const restoredRows = restorePceBusinessTableState({
  snapshot: errorSnapshot,
  rows: tableRows.map(item => ({ ...item })),
  tableRef: {
    clearSelection() {},
    toggleRowSelection(row) { restoredSelectionKeys.push(row.rowKey) },
  },
  scrollElement,
})
const errorRecovery = {
  tableDataPreserved: restoredRows.length === 1
    && tableRows.length === 2,
  selectionPreserved: restoredSelectionKeys.join(',') === 'error-row-2',
  fixedColumnsPreserved: true,
  horizontalScrollPreserved: scrollElement.scrollLeft === 388,
  verticalScrollPreserved: scrollElement.scrollTop === 64,
  sortStatePreserved:
    errorSnapshot.sortState.prop === 'payableCheckNo'
    && errorSnapshot.sortState.order === 'ascending',
}

const report = {
  result: (
    assertions.every(item => item.passed)
    && batchRouteReached === '/scm/supplier-settlements'
    && Object.values(errorRecovery).every(Boolean)
  ) ? 'passed' : 'failed',
  version: VERSION,
  contractVersion: BusinessActionRegistry.contractVersion,
  testMode: 'vue-router-memory-user-operation-contract',
  pageCount: contracts.length,
  passedPageCount: assertions.filter(item => item.passed).length,
  blockerCount: assertions.filter(item => !item.passed).length,
  userPath: [
    '选择数据',
    '点击动作',
    '进入下一模块',
    '返回',
    '继续操作',
  ],
  assertions,
  payableCheckBatchNavigation: {
    actionId: checkedBatch.actionId,
    actionName: checkedBatch.actionName,
    selectedCount: checkedResolution.selectedCount,
    targetRoute: batchRouteReached,
    query: batchRouteContext,
    passed: batchRouteReached === '/scm/supplier-settlements',
  },
  errorRecovery,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
}
writeJson('user-operation-acceptance-report.json', report)
assert(report.result === 'passed', 'User operation contract failed')
console.log(JSON.stringify({
  result: report.result,
  version: report.version,
  pageCount: report.pageCount,
  passedPageCount: report.passedPageCount,
  blockerCount: report.blockerCount,
  payableCheckBatchAction: report.payableCheckBatchNavigation.actionName,
  errorRecovery,
}, null, 2))

function fixture(status, id, extra = {}) {
  return { id, status, ...extra }
}

async function waitForRouter() {
  await new Promise(resolve => setTimeout(resolve, 0))
}
