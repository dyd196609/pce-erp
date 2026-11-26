import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import {
  BusinessActionRegistry,
  PCE_BUSINESS_ACTION_REGISTRY_VERSION,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'

const VERSION = 'V1.14.2.8.4.7.55.1.1'
const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-real-data-v5511',
)
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
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

const paymentRequestPage = read(
  'src/meta/pages/PaymentRequestPage.vue',
)
const paymentRequestPreparePage = read(
  'src/meta/pages/PaymentApplicationPage.vue',
)
const actionBar = read(
  'src/meta/components/PceBusinessActionBar.vue',
)
const registrySource = read(
  'src/meta/runtime/pceBusinessActionRegistry.js',
)
const paymentRequestPrepareView = read(
  '../backend/payment_request_prepare/views.py',
)
const paymentRequestPrepareTests = read(
  '../backend/payment_request_prepare/tests/test_v47.py',
)
const paymentRequestTests = read(
  '../backend/payment_request/tests/test_v5511.py',
)
const acceptanceStandard = read(
  '../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md',
)

const firstRow = {
  id: 1,
  requestNo: 'PRQ20260700000001',
  status: 'approved',
}
const secondRow = {
  id: 2,
  requestNo: 'PRQ20260700000002',
  status: 'approved',
}
const single = BusinessActionRegistry.resolve({
  currentModule: 'payment-request',
  selectedRows: [firstRow],
  eligibility: true,
})
const batch = BusinessActionRegistry.resolve({
  currentModule: 'payment-request',
  selectedRows: [firstRow, secondRow],
  eligibility: true,
})
const noSelection = BusinessActionRegistry.resolve({
  currentModule: 'payment-request',
  selectedRows: [],
  eligibility: true,
})
const protectedActionIds = [
  'create-bank-send-task',
  'execute-payment',
  'create-payment-voucher',
  'write-general-ledger',
]

const singleAction = single.availableActions.find(
  action => action.actionId === 'enter-payment-instruction-prepare',
)
const batchAction = batch.batchActions.find(
  action => action.actionId === 'batch-enter-payment-instruction-prepare',
)
const singleBatchUnavailable = single.unavailableActions.find(
  action => action.actionId === 'batch-enter-payment-instruction-prepare',
)

const guards = {
  business_action_registry_version_current:
    [
      VERSION,
      'V1.14.2.8.4.7.55.2',
      'V1.14.2.8.4.7.56',
      'V1.14.2.8.4.7.57',
      'V1.14.2.8.4.7.58',
      'V1.14.2.8.4.7.59',
      'V1.14.2.8.4.8.3.1',
      'V1.14.2.8.4.8.3.1.1',
    ].includes(PCE_BUSINESS_ACTION_REGISTRY_VERSION),
  payment_request_prepare_real_rows_are_diagnosable:
    paymentRequestPreparePage.includes('formalRows: rows.value')
      && paymentRequestPreparePage.includes(
        'formalObjectCount: rows.value.length',
      ),
  payment_request_real_rows_are_diagnosable:
    paymentRequestPage.includes('formalRows: rows.value')
      && (
        paymentRequestPage.includes('formalObjectCount: rows.value.length')
        || paymentRequestPage.includes(
          'formalObjectCount: factLoadResultCount(factLoadFacts.value, rows.value.length)',
        )
      ),
  strict_facts_include_server_eligibility:
    paymentRequestPreparePage.includes(
      'eligibility: current.value.eligibility',
    )
      && paymentRequestPage.includes('eligibility: row.eligibility'),
  historical_prepare_rows_use_server_read_model:
    paymentRequestPrepareView.includes('successful_lineage_by_object_no')
      && paymentRequestPrepareView.includes('historical_lineage_facts')
      && paymentRequestPrepareTests.includes(
        'historical_formal_objects_remain_visible_after_chain_advances',
      ),
  single_action_exists_for_one_approved_row:
    Boolean(singleAction)
      && singleAction.enabled === true
      && singleAction.targetRoute?.path
        === '/finance/payment-order-prepares',
  no_selection_disables_single_action:
    !noSelection.availableActions.some(
      action => action.actionId === 'enter-payment-instruction-prepare',
    ),
  one_row_does_not_enable_batch_action:
    !single.batchActions.some(
      action => action.actionId
        === 'batch-enter-payment-instruction-prepare',
    )
      && singleBatchUnavailable?.disabledReason
        === '批量业务动作至少需要选择两条记录。',
  two_rows_enable_batch_action:
    Boolean(batchAction)
      && batchAction.enabled === true
      && batchAction.selectedRows.length === 2
      && batchAction.targetRoute?.path
        === '/finance/payment-order-prepares',
  navigation_revalidates_eligibility_on_server:
    actionBar.includes('beforeNavigate')
      && actionBar.includes('await props.beforeNavigate(action)')
      && paymentRequestPage.includes(
        ':before-navigate='
          + '"revalidatePaymentInstructionPrepareEligibility"',
      )
      && paymentRequestPage.includes(
        'paymentRequestApi.eligibility(row.id)',
      )
      && paymentRequestPage.includes('item.serverDerived === true')
      && paymentRequestPage.includes(
        "'ready_for_payment_instruction_prepare'",
      ),
  navigation_revalidation_is_observable:
    paymentRequestPage.includes(
      'payment-request-action-server-revalidation',
    )
      && paymentRequestPage.includes('businessActionRevalidation:')
      && paymentRequestPage.includes('businessWriteRequestCount: 0'),
  action_error_is_closable:
    paymentRequestPage.includes('showClose: true')
      && paymentRequestPage.includes(
        "'付款指令准备资格服务端复核失败。'",
      ),
  navigation_does_not_call_generation_api:
    !paymentRequestPage
      .match(
        /revalidatePaymentInstructionPrepareEligibility[\s\S]*?function clearSelection/,
      )?.[0]
      .includes('paymentRequestApi.generate'),
  real_data_backend_tests_exist:
    paymentRequestTests.includes(
      'server_list_returns_eight_approved_formal_objects',
    )
      && paymentRequestTests.includes(
        'single_and_batch_sources_are_server_eligible',
      )
      && paymentRequestTests.includes(
        'navigation_acceptance_creates_no_instruction_prepare',
      ),
  acceptance_standard_has_four_proofs:
    acceptanceStandard.includes(
      '数据存在、动作存在、动作可执行、结果可验证',
    ),
  forbidden_write_boundaries_remain_absent:
    BusinessActionRegistry.list().every(contract => (
      protectedActionIds.every(
        actionId => (
          contract.currentModule === 'bank-send-task'
          && actionId === 'create-bank-send-task'
            ? !contract.forbiddenActions.includes(actionId)
              && contract.actions.some(action => action.actionId === actionId)
            : contract.forbiddenActions.includes(actionId)
        ),
      )
        && !contract.actions.some(
          action => (
            protectedActionIds.includes(action.actionId)
            && !(
              contract.currentModule === 'bank-send-task'
              && action.actionId === 'create-bank-send-task'
            )
          ),
        )
    ))
      && registrySource.includes('forbiddenExecutionActions'),
}

const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const report = {
  result: failedGuards.length === 0 ? 'passed' : 'failed',
  version: VERSION,
  canonicalName: 'PCE业务动作真实数据验收补全',
  contractVersion: BusinessActionRegistry.contractVersion,
  registryVersion: PCE_BUSINESS_ACTION_REGISTRY_VERSION,
  guardCount: Object.keys(guards).length,
  passedGuardCount: Object.values(guards).filter(Boolean).length,
  failedGuardCount: failedGuards.length,
  failedGuards,
  guards,
  singleAction: singleAction
    ? {
        actionId: singleAction.actionId,
        actionName: singleAction.actionName,
        selectedCount: single.selectedCount,
        targetRoute: singleAction.targetRoute,
      }
    : null,
  batchAction: batchAction
    ? {
        actionId: batchAction.actionId,
        actionName: batchAction.actionName,
        selectedCount: batch.selectedCount,
        targetRoute: batchAction.targetRoute,
      }
    : null,
  businessWriteRequestCount: 0,
  paymentInstructionPrepareCreated: false,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
}

writeJson('static-guard-report.json', report)
assert(
  report.result === 'passed',
  `V55.1.1 static guards failed: ${failedGuards.join(', ')}`,
)
console.log(JSON.stringify(report, null, 2))
