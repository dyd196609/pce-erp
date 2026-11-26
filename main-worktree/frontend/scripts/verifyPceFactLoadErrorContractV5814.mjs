import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.58.1.4'
const CONTRACT_VERSION = 'PCE-FACT-LOAD-CONTRACT-V1.0'
const root = process.cwd()
const backendRoot = path.resolve(root, '..', 'backend')
const resultRoot = path.join(
  root,
  'test-results',
  'bank-send-preparation-v58-1-4',
)
const read = file => fs.readFileSync(path.resolve(root, file), 'utf8')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}
const walk = (directory) => fs.readdirSync(directory, {
  withFileTypes: true,
}).flatMap(entry => (
  entry.isDirectory()
    ? walk(path.join(directory, entry.name))
    : [path.join(directory, entry.name)]
))

const targetModules = [
  {
    code: 'payment_request',
    apiFile: 'src/api/paymentRequest.js',
    pageFile: 'src/meta/pages/PaymentRequestPage.vue',
    backendView: '../backend/payment_request/views.py',
    backendUrls: '../backend/payment_request/urls.py',
    apiUrl: '/api/finance/payment-requests/',
  },
  {
    code: 'payment_instruction_prepare',
    apiFile: 'src/api/paymentInstructionPrepare.js',
    pageFile: 'src/meta/pages/PaymentInstructionPreparePage.vue',
    backendView: '../backend/payment_instruction_prepare/views.py',
    backendUrls: '../backend/payment_instruction_prepare/urls.py',
    apiUrl: '/api/finance/payment-instruction-prepares/',
  },
  {
    code: 'payment_order_prepare',
    apiFile: 'src/api/paymentOrderPrepare.js',
    pageFile: 'src/meta/pages/PaymentOrderPreparePage.vue',
    backendView: '../backend/payment_order_prepare/views.py',
    backendUrls: '../backend/payment_order_prepare/urls.py',
    apiUrl: '/api/finance/payment-order-prepares/',
  },
  {
    code: 'payment_order_draft',
    apiFile: 'src/api/paymentOrderDraft.js',
    pageFile: 'src/meta/pages/PaymentOrderDraftPage.vue',
    runtimeFile: 'src/meta/runtime/paymentOrderDraftRuntime.js',
    backendView: '../backend/payment_order_draft/views.py',
    backendUrls: '../backend/payment_order_draft/urls.py',
    apiUrl: '/api/finance/payment-order-drafts/',
  },
  {
    code: 'formal_payment_order',
    apiFile: 'src/api/formalPaymentOrder.js',
    pageFile: 'src/meta/pages/FormalPaymentOrderPage.vue',
    runtimeFile: 'src/meta/runtime/formalPaymentOrderRuntime.js',
    backendView: '../backend/formal_payment_order/views.py',
    backendUrls: '../backend/formal_payment_order/urls.py',
    apiUrl: '/api/finance/formal-payment-orders/',
  },
  {
    code: 'bank_send_preparation',
    apiFile: 'src/api/bankSendPreparation.js',
    pageFile: 'src/meta/pages/BankSendPreparationPage.vue',
    runtimeFile: 'src/meta/runtime/bankSendPreparationRuntime.js',
    backendView: '../backend/bank_send_preparation/views.py',
    backendUrls: '../backend/bank_send_preparation/urls.py',
    apiUrl: '/api/finance/bank-send-prepares/',
  },
]

const backendRootUrls = read('../backend/pce_backend/urls.py')
const registeredPrefixes = [...backendRootUrls.matchAll(
  /path\(\s*["'](api\/[^"']*)["']/g,
)].map(match => `/${match[1]}`)
const apiFiles = walk(path.join(root, 'src', 'api'))
  .filter(file => file.endsWith('.js'))
const routeRows = []
for (const file of apiFiles) {
  const source = fs.readFileSync(file, 'utf8')
  const routeRegex = /(?:url\s*:\s*|request\(\s*)(["'`])(\/api\/[\s\S]*?)\1/g
  for (const match of source.matchAll(routeRegex)) {
    const declared = match[2].split('${')[0].split('?')[0]
    const ownerPrefix = registeredPrefixes
      .filter(prefix => declared.startsWith(prefix))
      .sort((left, right) => right.length - left.length)[0] || ''
    routeRows.push({
      file: path.relative(root, file).replaceAll('\\', '/'),
      declaredRoute: match[2],
      normalizedStaticPrefix: declared,
      classification: ownerPrefix
        ? ownerPrefix === '/api/'
          ? 'generic_api_include_requires_runtime_validation'
          : 'matched_backend_include'
        : 'route_prefix_unmatched',
      backendOwnerPrefix: ownerPrefix,
    })
  }
}

const targetedRouteChecks = targetModules.map((module) => {
  const apiSource = read(module.apiFile)
  const childUrls = read(module.backendUrls)
  const rootRegistered = backendRootUrls.includes(
    `"${module.apiUrl.slice(1)}"`,
  )
  const frontendCanonical = apiSource.includes(
    `url: '${module.apiUrl}'`,
  )
  const backendListRegistered = /path\(\s*["']["']\s*,/.test(childUrls)
  return {
    moduleCode: module.code,
    expectedApiUrl: module.apiUrl,
    frontendCanonical,
    backendRootRegistered: rootRegistered,
    backendListRegistered,
    passed:
      frontendCanonical
      && rootRegistered
      && backendListRegistered,
  }
})
const prohibitedRouteOccurrences = apiFiles.flatMap((file) => {
  const source = fs.readFileSync(file, 'utf8')
  return source.includes('/api/finance/bank-send-preparations/')
    ? [path.relative(root, file).replaceAll('\\', '/')]
    : []
})
const unmatchedRoutes = routeRows.filter(
  row => row.classification === 'route_prefix_unmatched',
)
const apiRouteReport = {
  result:
    targetedRouteChecks.every(item => item.passed)
    && prohibitedRouteOccurrences.length === 0
      ? 'passed'
      : 'failed',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  scanRoot: 'frontend/src/api',
  scannedApiFileCount: apiFiles.length,
  literalApiRouteCount: routeRows.length,
  registeredBackendPrefixCount: registeredPrefixes.length,
  targetedRouteChecks,
  prohibitedRoute: '/api/finance/bank-send-preparations/',
  prohibitedRouteOccurrences,
  routePrefixUnmatchedCount: unmatchedRoutes.length,
  routePrefixUnmatched: unmatchedRoutes,
  validationScope:
    'all frontend API literals classified by backend root include; six payment-chain list routes additionally verified against child URLConf',
  routes: routeRows,
}
writeJson('api-route-contract-report.json', apiRouteReport)

const gapRows = targetModules.map((module) => {
  const apiSource = read(module.apiFile)
  const pageSource = read(module.pageFile)
  const runtimeSource = module.runtimeFile ? read(module.runtimeFile) : ''
  const backendView = read(module.backendView)
  const consumerSource = `${pageSource}\n${runtimeSource}`
  const gaps = []
  if (!apiSource.includes('factLoad: true')) {
    gaps.push('api_client_missing_fact_load_declaration')
  }
  if (
    !backendView.includes('successful_fact_load_facts')
    && !backendView.includes(
      'bank_send_preparation_facts["factLoadFacts"]',
    )
  ) {
    gaps.push('backend_list_missing_fact_load_facts')
  }
  if (!backendView.includes('"factLoadFacts": fact_load_facts')) {
    gaps.push('backend_response_missing_fact_load_facts')
  }
  if (!consumerSource.includes('factLoadFacts')) {
    gaps.push('diagnostic_missing_fact_load_facts')
  }
  if (!consumerSource.includes('pceFactLoadContract.js')) {
    gaps.push('page_or_runtime_missing_fact_load_contract')
  }
  if (
    !consumerSource.includes('factLoadFailureFromError')
    && !consumerSource.includes('readPceFactLoadEnvelope')
  ) {
    gaps.push('read_failure_not_explicitly_handled')
  }
  const silentEmptyPatterns = [
    /catch\s*\([^)]*\)\s*\{[^}]*return\s*\[\]/s,
    /catch\s*\([^)]*\)\s*\{[^}]*resultCount\s*:\s*0/s,
  ]
  if (silentEmptyPatterns.some(pattern => pattern.test(consumerSource))) {
    gaps.push('catch_silently_returns_empty_fact')
  }
  if (
    consumerSource.includes('FACT_LOAD_NOT_STARTED')
    || /ref\(\s*createReadFailedFactLoad\(/.test(consumerSource)
  ) {
    gaps.push('initial_state_impersonates_fact_load_result')
  }
  const numericFactDefaults = [
    ...consumerSource.matchAll(
      /Number\(\s*(?:data|facts|response|payload)[^)]*\|\|\s*0\s*\)/g,
    ),
  ].map(match => match[0])
  if (numericFactDefaults.length) {
    gaps.push('server_fact_number_defaulted_to_zero')
  }
  const catchBlocks = [
    ...consumerSource.matchAll(/catch\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}/g),
  ].map(match => match[1])
  const unauditedEmptyCatchCount = catchBlocks.filter(block => (
    /(?:rows(?:\.value)?|data)\s*=\s*\[\]/.test(block)
    && !block.includes('factLoadFailureFromError')
  )).length
  if (unauditedEmptyCatchCount) {
    gaps.push('catch_empty_array_without_error_fact')
  }
  return {
    moduleCode: module.code,
    apiUrl: module.apiUrl,
    classification: gaps.length ? 'fact-load-contract-gap' : 'migrated',
    catchEmptyArrayWithoutErrorFactCount: unauditedEmptyCatchCount,
    initialFactImpersonationCount:
      gaps.includes('initial_state_impersonates_fact_load_result') ? 1 : 0,
    numberDefaultToZeroCount: numericFactDefaults.length,
    gaps,
    passed: gaps.length === 0,
  }
})
const factLoadGapReport = {
  result: gapRows.every(item => item.passed) ? 'passed' : 'failed',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  scannedModuleCount: gapRows.length,
  migratedModuleCount: gapRows.filter(item => item.passed).length,
  gapModuleCount: gapRows.filter(item => !item.passed).length,
  modules: gapRows,
}
writeJson('fact-load-gap-report.json', factLoadGapReport)
writeJson('fact-load-error-contract-scan.json', {
  ...factLoadGapReport,
  scanRules: [
    'catch_after_error_must_emit_complete_read_failed_fact',
    'initial_state_cannot_impersonate_fact_load_result',
    'server_fact_cannot_use_Number(value || 0)',
  ],
  catchEmptyArrayWithoutErrorFactCount: gapRows.reduce(
    (sum, item) => sum + item.catchEmptyArrayWithoutErrorFactCount,
    0,
  ),
  initialFactImpersonationCount: gapRows.reduce(
    (sum, item) => sum + item.initialFactImpersonationCount,
    0,
  ),
  numberDefaultToZeroCount: gapRows.reduce(
    (sum, item) => sum + item.numberDefaultToZeroCount,
    0,
  ),
})

const backendContract = read('../backend/workflow_runtime/fact_loads.py')
const backendExceptionHandler = read(
  '../backend/workflow_runtime/exception_handler.py',
)
const backendSettings = read('../backend/pce_backend/settings.py')
const frontendContract = read('src/meta/runtime/pceFactLoadContract.js')
const requestClient = read('src/api/request.js')
const bankPage = read('src/meta/pages/BankSendPreparationPage.vue')
const bankRuntime = read(
  'src/meta/runtime/bankSendPreparationRuntime.js',
)
const strictPanel = read(
  'src/meta/components/PceStrictServerFactsPanel.vue',
)
const listPageShell = read(
  'src/meta/components/PceListPageShell.vue',
)
const requiredFields = [
  'factLoadStatus',
  'apiUrl',
  'httpStatus',
  'errorCode',
  'errorMessage',
  'loadedAt',
  'tenantId',
  'batchId',
]
const guards = {
  fact_load_contract_version_registered:
    backendContract.includes(CONTRACT_VERSION)
    && frontendContract.includes(CONTRACT_VERSION),
  fact_load_status_enum_complete:
    ['loaded', 'read_failed', 'empty_valid'].every(status => (
      backendContract.includes(`"${status}"`)
      && frontendContract.includes(`'${status}'`)
    )),
  fact_load_required_fields_complete: requiredFields.every(field => (
    backendContract.includes(`"${field}"`)
    && frontendContract.includes(`'${field}'`)
  )),
  get_failures_return_read_failed_contract:
    backendSettings.includes(
      '"EXCEPTION_HANDLER": "workflow_runtime.exception_handler.pce_exception_handler"',
    )
    && backendExceptionHandler.includes('failed_fact_load_facts')
    && backendExceptionHandler.includes('"result": "blocked"')
    && backendExceptionHandler.includes('pce_not_found_handler')
    && backendExceptionHandler.includes('pce_server_error_handler'),
  read_failed_fields_are_non_empty:
    backendContract.includes('FACT_LOAD_ERROR_REQUIRED_FIELDS')
    && backendContract.includes('read_failed contains empty fields')
    && frontendContract.includes(
      'PCE_FACT_LOAD_ERROR_REQUIRED_FIELDS',
    )
    && frontendContract.includes(
      'FACT_LOAD_CONTRACT_INCOMPLETE',
    ),
  server_request_context_preserved_on_failure:
    backendContract.includes('fact_load_context_from_request')
    && backendExceptionHandler.includes('request=request')
    && requestClient.includes('currentPceServerFactContext')
    && requestClient.includes('rememberPceServerFactContext'),
  client_http_failure_not_empty_valid:
    requestClient.includes("factLoadStatus: 'read_failed'")
      || (
        requestClient.includes('createReadFailedFactLoad')
        && requestClient.includes('success: false')
      ),
  read_failed_result_count_is_not_zero:
    frontendContract.includes("factLoadFacts.factLoadStatus === 'read_failed'")
    && frontendContract.includes('return null')
    && !frontendContract.includes('return Number(count || 0)'),
  read_failed_cannot_pass:
    frontendContract.includes(
      "factLoadFacts.factLoadStatus !== 'read_failed'",
    )
    && bankPage.includes('factLoadPassed(')
    && bankRuntime.includes('factLoadPassed('),
  canonical_bank_send_prepare_route:
    prohibitedRouteOccurrences.length === 0
    && targetedRouteChecks.find(
      item => item.moduleCode === 'bank_send_preparation',
    )?.passed === true,
  api_page_diagnostic_strict_facts_consistent:
    bankPage.includes('factLoadFacts: factLoadFacts.value')
    && bankRuntime.includes('factLoadFacts')
    && bankRuntime.includes('strictServerFacts')
    && bankRuntime.includes('bankSendPreparationFacts')
    && listPageShell.includes(
      "const resultCount = factLoadStatus === 'read_failed'",
    )
    && listPageShell.includes('@load-error="recordStrictServerFacts"'),
  server_supplies_tenant_and_batch:
    requiredFields.slice(-2).every(field => (
      backendContract.includes(`"${field}"`)
      && bankRuntime.includes(`factLoadFacts.${field}`)
    )),
  frontend_does_not_hardcode_batch:
    ![
      bankPage,
      bankRuntime,
      strictPanel,
      ...targetModules.map(module => read(module.pageFile)),
    ].some(source => source.includes('PURCHASE-FLOW-DEMO-V1')),
  route_contract_passed: apiRouteReport.result === 'passed',
  payment_chain_gap_scan_passed: factLoadGapReport.result === 'passed',
  initial_state_does_not_impersonate_fact:
    !targetModules.some((module) => {
      const source = `${read(module.pageFile)}\n${
        module.runtimeFile ? read(module.runtimeFile) : ''
      }`
      return source.includes('FACT_LOAD_NOT_STARTED')
        || /ref\(\s*createReadFailedFactLoad\(/.test(source)
    }),
  diagnostic_displays_complete_error_contract:
    listPageShell.includes("read_failed: '读取失败'")
    && requiredFields.every(field => listPageShell.includes(field)),
}
const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const guardReport = {
  result: failedGuards.length ? 'failed' : 'passed',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  canonicalName: '银行发送准备',
  blockerCount: failedGuards.length,
  failedGuards,
  guards,
  factLoadStatusOnSuccess: 'loaded',
  factLoadStatusOnEmpty: 'empty_valid',
  factLoadStatusOnReadFailure: 'read_failed',
  readFailedPassed: false,
  readFailedResultCount: null,
  productionUserDataWritten: false,
}
writeJson('static-guard-report.json', guardReport)
console.log(JSON.stringify(guardReport, null, 2))
if (failedGuards.length) {
  throw new Error(
    `V58.1.4 fact-load error guards failed: ${failedGuards.join(', ')}`,
  )
}
