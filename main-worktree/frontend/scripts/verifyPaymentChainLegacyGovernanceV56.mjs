import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.56'
const frontendRoot = process.cwd()
const repositoryRoot = path.resolve(frontendRoot, '..')
const projectRoot = path.resolve(repositoryRoot, '..')
const backendRoot = path.join(repositoryRoot, 'backend')
const sourceRoot = path.join(frontendRoot, 'src')
const resultRoot = path.join(
  frontendRoot,
  'test-results',
  'payment-chain-legacy-governance-v56',
)

const read = file => fs.readFileSync(file, 'utf8')
const exists = file => fs.existsSync(file)
const relative = file => path
  .relative(repositoryRoot, file)
  .replaceAll('\\', '/')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}
const linesMatching = (file, expression, classification) => {
  if (!exists(file)) return []
  return read(file).split(/\r?\n/).flatMap((line, index) => {
    expression.lastIndex = 0
    return expression.test(line)
      ? [{
          file: relative(file),
          line: index + 1,
          excerpt: line.trim(),
          classification,
        }]
      : []
  })
}
const sourceFiles = directory => fs.readdirSync(
  directory,
  { withFileTypes: true },
).flatMap(entry => {
  const target = path.join(directory, entry.name)
  if (entry.isDirectory()) return sourceFiles(target)
  return /\.(js|vue)$/.test(entry.name) ? [target] : []
})

const modules = [
  {
    module: 'payable_prepare',
    registryModule: 'payable-prepare',
    canonicalName: '采购应付预备',
    riskLevel: 'level_3',
    migrationStatus: 'legacy_observability_gap',
    page: 'PayablePreparePage.vue',
    store: 'meta/finance/payablePrepareStore.js',
  },
  {
    module: 'payable_check',
    registryModule: 'payable-check',
    canonicalName: '采购应付核对',
    riskLevel: 'level_3',
    migrationStatus: 'legacy_observability_gap',
    page: 'PayableCheckPage.vue',
    store: 'meta/finance/payableCheckStore.js',
  },
  {
    module: 'supplier_settlement',
    registryModule: 'supplier-settlement',
    canonicalName: '供应商结算',
    riskLevel: 'level_3',
    migrationStatus: 'legacy_observability_gap',
    page: 'SupplierSettlementPage.vue',
    store: 'meta/scm/supplierSettlementStore.js',
  },
  {
    module: 'purchase_reconciliation',
    backendModule: 'reconciliation',
    registryModule: 'purchase-reconciliation',
    canonicalName: '采购对账',
    riskLevel: 'level_2',
    migrationStatus: 'legacy_observability_gap',
    page: 'PurchaseReconciliationPage.vue',
  },
  {
    module: 'purchase_invoice_prepare',
    backendModule: 'purchase_invoice_prepare',
    registryModule: 'purchase-invoice-prepare',
    canonicalName: '采购发票准备',
    riskLevel: 'level_2',
    migrationStatus: 'partially_migrated',
    page: 'InvoicePreparePage.vue',
    store: 'meta/finance/invoicePrepareStore.js',
  },
  {
    module: 'ap_draft',
    backendModule: 'purchase_accounts_payable_draft',
    registryModule: 'accounts-payable-draft',
    canonicalName: '采购应付账款草稿',
    riskLevel: 'level_2',
    migrationStatus: 'partially_migrated',
    page: 'AccountPayableDraftPage.vue',
    store: 'meta/finance/accountPayableDraftStore.js',
  },
  {
    module: 'payable_confirm',
    backendModule: 'payable_confirmation_prepare',
    registryModule: 'payable-confirmation-prepare',
    canonicalName: '应付确认准备',
    riskLevel: 'level_1',
    migrationStatus: 'partially_migrated',
    page: 'AccountPayableConfirmPage.vue',
  },
  {
    module: 'payment_request_prepare',
    backendModule: 'payment_request_prepare',
    registryModule: 'payment-request-prepare',
    canonicalName: '付款申请准备',
    riskLevel: 'level_1',
    migrationStatus: 'migrated',
    priority: true,
    model: 'PaymentRequestPrepare',
    page: 'PaymentApplicationPage.vue',
    api: 'paymentRequestPrepare.js',
  },
  {
    module: 'payment_request',
    backendModule: 'payment_request',
    registryModule: 'payment-request',
    canonicalName: '付款申请',
    riskLevel: 'level_1',
    migrationStatus: 'migrated',
    priority: true,
    model: 'PaymentRequest',
    page: 'PaymentRequestPage.vue',
    api: 'paymentRequest.js',
  },
  {
    module: 'payment_instruction_prepare',
    backendModule: 'payment_instruction_prepare',
    registryModule: 'payment-instruction-prepare',
    canonicalName: '付款指令准备',
    riskLevel: 'level_1',
    migrationStatus: 'migrated',
    priority: true,
    model: 'PaymentInstructionPrepare',
    page: 'PaymentInstructionPreparePage.vue',
    api: 'paymentInstructionPrepare.js',
  },
  {
    module: 'payment_order_prepare',
    backendModule: 'payment_order_prepare',
    registryModule: 'payment-order-prepare',
    canonicalName: '正式付款单预备',
    riskLevel: 'level_1',
    migrationStatus: 'migrated',
    priority: true,
    model: 'PaymentOrderPrepare',
    page: 'PaymentOrderPreparePage.vue',
    api: 'paymentOrderPrepare.js',
  },
  {
    module: 'payment_order_draft',
    backendModule: 'payment_order_draft',
    registryModule: 'payment-order-draft',
    canonicalName: '正式付款单草稿',
    riskLevel: 'level_1',
    migrationStatus: 'migrated',
    model: 'PaymentOrderDraft',
    page: 'PaymentOrderDraftPage.vue',
    api: 'paymentOrderDraft.js',
  },
  {
    module: 'payment_risk_review',
    backendModule: 'payment_risk_review',
    registryModule: 'payment-risk-review',
    canonicalName: '真实付款风险评审',
    riskLevel: 'level_3',
    migrationStatus: 'legacy_observability_gap',
    page: 'PaymentExecutionRiskReviewPage.vue',
    api: 'paymentRiskReview.js',
  },
  {
    module: 'formal_payment_order',
    backendModule: 'formal_payment_order',
    registryModule: 'formal-payment-order',
    canonicalName: '正式付款单',
    riskLevel: 'level_3',
    migrationStatus: 'partially_migrated',
    model: 'FormalPaymentOrder',
    page: 'FormalPaymentOrderPage.vue',
    api: 'formalPaymentOrder.js',
  },
]

const governanceFiles = [
  path.join(projectRoot, 'AGENTS.md'),
  path.join(
    repositoryRoot,
    'docs',
    'standards',
    'PCE-STATE-MACHINE-CONTRACT-V1.1.md',
  ),
  path.join(
    repositoryRoot,
    'docs',
    'standards',
    'PCE-BUSINESS-ACTION-CONTRACT-V1.0.md',
  ),
  path.join(
    repositoryRoot,
    'docs',
    'standards',
    'PCE-WEB-ACCEPTANCE-V1.1.md',
  ),
  path.join(
    repositoryRoot,
    'docs',
    'standards',
    'PCE-PAYMENT-CHAIN-LEGACY-GOVERNANCE-V1.0.md',
  ),
]
const governanceStandardsSynchronized = (
  read(governanceFiles[0]).includes('BusinessStateTransition')
  && read(governanceFiles[0]).includes('BusinessActionRegistry')
  && read(governanceFiles[0]).includes('currentStateSource=server')
  && read(governanceFiles[1]).includes('BusinessStateTransition')
  && read(governanceFiles[1]).includes('statusTransitionCount')
  && read(governanceFiles[2]).includes('BusinessActionRegistry')
  && read(governanceFiles[2]).includes('serverEligibilityCheck')
  && read(governanceFiles[3]).includes('currentStateSource=server')
  && read(governanceFiles[3]).includes('strictFacts')
  && [
    'BusinessStateTransition',
    'BusinessActionRegistry',
    'currentStateSource=server',
  ].every(term => read(governanceFiles[4]).includes(term))
)

const actionRegistryFile = path.join(
  sourceRoot,
  'meta',
  'runtime',
  'pceBusinessActionRegistry.js',
)
const actionRegistry = read(actionRegistryFile)
const stateTransitionServiceFile = path.join(
  backendRoot,
  'workflow_runtime',
  'state_transitions.py',
)
const stateFactServiceFile = path.join(
  backendRoot,
  'workflow_runtime',
  'facts.py',
)
const stateManagedModelFile = path.join(
  backendRoot,
  'workflow_runtime',
  'state_models.py',
)
const frontendStateFactFile = path.join(
  sourceRoot,
  'meta',
  'runtime',
  'pceStateMachineFactContract.js',
)

const commonStateGuards = {
  transitionServiceRequiresTransaction:
    read(stateTransitionServiceFile).includes('connection.in_atomic_block'),
  transitionPersistsAuditFields: [
    'source_state',
    'target_state',
    'operator',
    'reason',
    'audit_reference',
    'version',
  ].every(field => read(stateTransitionServiceFile).includes(field)),
  directSaveBlocked:
    read(stateManagedModelFile).includes(
      'status must use BusinessStateTransition',
    ),
  querysetUpdateBlocked:
    read(stateManagedModelFile).includes('if "status" in kwargs:'),
  bulkUpdateBlocked:
    read(stateManagedModelFile).includes('if "status" in fields:'),
  serverCountDerivedFromHistory:
    read(stateFactServiceFile).includes(
      '"statusTransitionCount": len(persisted_history)',
    ),
  clientCountMustMatchHistory:
    read(frontendStateFactFile).includes(
      'facts.statusTransitionCount\n    !== facts.statusTransitionHistory.length',
    ),
}

const explicitDirectWritePatterns = {
  purchase_invoice_prepare: /\bprepare\.status\s*=(?!=)/,
  payment_risk_review: /\bcurrent\.status\s*=(?!=)/,
  reconciliation:
    /PurchaseReconciliation\.objects.*\.update\(|\.status\s*=(?!=)/,
  payable_confirmation_prepare:
    /PayableConfirmationPrepare\.objects\.create\(/,
  purchase_accounts_payable_draft:
    /PurchaseAccountsPayableDraft\.objects\.create\(/,
}

const stateRows = modules.map(module => {
  const moduleRoot = module.backendModule
    ? path.join(backendRoot, module.backendModule)
    : null
  const modelFile = moduleRoot
    ? path.join(moduleRoot, 'models.py')
    : null
  const serviceFiles = moduleRoot && exists(moduleRoot)
    ? fs.readdirSync(moduleRoot)
      .filter(name => /^(services|v\d+_services|checking)\.py$/.test(name))
      .map(name => path.join(moduleRoot, name))
    : []
  const serviceText = serviceFiles.map(read).join('\n')
  const modelText = modelFile && exists(modelFile) ? read(modelFile) : ''
  const pageFile = path.join(
    sourceRoot,
    'meta',
    'pages',
    module.page,
  )
  const pageText = read(pageFile)
  const storeFile = module.store
    ? path.join(sourceRoot, module.store)
    : null
  const storeText = storeFile && exists(storeFile) ? read(storeFile) : ''
  const customFormalGuard = module.module === 'formal_payment_order'
    && modelText.includes(
      'Formal payment order status must use BusinessStateTransition',
    )
  const managedModel = module.model
    ? (
        modelText.includes(
          `class ${module.model}(BusinessStateManagedModel):`,
        )
        || customFormalGuard
      )
    : false
  const usesTransitionService =
    serviceText.includes('create_business_object_with_initial_state(')
    && serviceText.includes('transition_business_object(')
  const usesPersistedFacts =
    serviceText.includes('business_state_transition_facts(')
    || (
      module.module === 'formal_payment_order'
      && exists(path.join(moduleRoot, 'facts.py'))
      && read(path.join(moduleRoot, 'facts.py')).includes(
        'BusinessStateTransition.objects.filter',
      )
    )
  const pageUsesServerFacts =
    pageText.includes('stateMachineFactsFromServer(')
    || pageText.includes('assertStatusTransitionCountMatchesHistory(')
  const pageHasStrictFacts =
    pageText.includes('strictFacts')
    || pageText.includes('strictServerFacts')
  const pageUsesLocalStorage = pageText.includes('localStorage')
  const storePersistsBusinessState =
    storeText.includes('localStorage.setItem')
  const directWriteExpression = explicitDirectWritePatterns[
    module.backendModule
  ]
  const directWriteEvidence = directWriteExpression
    ? serviceFiles.flatMap(file => linesMatching(
        file,
        directWriteExpression,
        'legacy-direct-business-state-write',
      ))
    : []
  const stateMachineIntegrated =
    managedModel
    && usesTransitionService
    && usesPersistedFacts
    && pageUsesServerFacts
    && pageHasStrictFacts
    && directWriteEvidence.length === 0
  return {
    module: module.module,
    canonicalName: module.canonicalName,
    riskLevel: module.riskLevel,
    migrationStatus: module.migrationStatus,
    priority: module.priority === true,
    stateMachineIntegrated,
    managedBusinessStateModel: managedModel,
    usesBusinessStateTransition: usesTransitionService,
    usesPersistedTransitionFacts: usesPersistedFacts,
    statusTransitionCountFromServer: usesPersistedFacts,
    statusTransitionCountMustEqualHistory:
      commonStateGuards.serverCountDerivedFromHistory
      && commonStateGuards.clientCountMustMatchHistory,
    directBusinessStatusWriteCount: directWriteEvidence.length,
    directBusinessStatusWriteEvidence: directWriteEvidence,
    pageUsesServerTransitionFacts: pageUsesServerFacts,
    pageHasStrictFacts,
    pageUsesLocalStorage,
    storePersistsBusinessState,
    evidence: [
      ...(modelFile && exists(modelFile) ? [relative(modelFile)] : []),
      ...serviceFiles.map(relative),
      relative(pageFile),
      ...(storeFile && exists(storeFile) ? [relative(storeFile)] : []),
    ],
  }
})

const hardcodedActionExpression =
  /<el-button[^>]*>[^<]*(进入|完成|生成|提交审批|审批|冻结|发送|批量)[^<]*<\/el-button>/
const actionRows = modules.map(module => {
  const pageFile = path.join(
    sourceRoot,
    'meta',
    'pages',
    module.page,
  )
  const pageText = read(pageFile)
  const hardcodedEvidence = linesMatching(
    pageFile,
    hardcodedActionExpression,
    'page-hardcoded-business-action',
  ).filter(row => !row.excerpt.includes('disabled data-acceptance-id='))
  const registered = actionRegistry.includes(
    `currentModule: '${module.registryModule}'`,
  )
  const pageUsesRegistryBar =
    pageText.includes('<PceBusinessActionBar')
    && pageText.includes(
      `current-module="${module.registryModule}"`,
    )
  return {
    module: module.module,
    canonicalName: module.canonicalName,
    riskLevel: module.riskLevel,
    migrationStatus: module.migrationStatus,
    registered,
    pageUsesBusinessActionRegistry: pageUsesRegistryBar,
    hardcodedBusinessActionCount: hardcodedEvidence.length,
    hardcodedBusinessActionEvidence: hardcodedEvidence,
    actionContractComplete: registered
      && pageUsesRegistryBar
      && hardcodedEvidence.length === 0,
    requiredDeclaration: {
      actionCode: registered,
      displayName: registered,
      allowedRoles: registered,
      allowedStatus: registered,
      singleOrBatch: registered,
      serverEligibilityCheck: registered,
    },
    evidence: [relative(actionRegistryFile), relative(pageFile)],
  }
})

const factRows = modules.map(module => {
  const pageFile = path.join(
    sourceRoot,
    'meta',
    'pages',
    module.page,
  )
  const pageText = read(pageFile)
  const apiFile = module.api
    ? path.join(sourceRoot, 'api', module.api)
    : null
  const stateRow = stateRows.find(row => row.module === module.module)
  const apiSurface = Boolean(apiFile && exists(apiFile))
  const pageSurface = pageText.includes('currentStateSource')
    && pageText.includes('server')
  const diagnosticSurface =
    /copyDiagnostic|copyDiagnostics|diagnostic/i.test(pageText)
  const strictFactsSurface =
    pageText.includes('strictFacts')
    || pageText.includes('strictServerFacts')
  const commonServerFactSource = Boolean(
    stateRow?.usesPersistedTransitionFacts
    && stateRow?.pageUsesServerTransitionFacts,
  )
  const fourSurfaceConsistentStatic =
    apiSurface
    && pageSurface
    && diagnosticSurface
    && strictFactsSurface
    && commonServerFactSource
  const gaps = [
    ...(!apiSurface ? ['api_surface_not_explicit'] : []),
    ...(!pageSurface ? ['page_currentStateSource_server_missing'] : []),
    ...(!diagnosticSurface ? ['copy_diagnostic_missing'] : []),
    ...(!strictFactsSurface ? ['strictFacts_missing'] : []),
    ...(!commonServerFactSource
      ? ['shared_persisted_state_fact_source_missing']
      : []),
  ]
  return {
    module: module.module,
    canonicalName: module.canonicalName,
    riskLevel: module.riskLevel,
    migrationStatus: module.migrationStatus,
    currentStateSource: commonServerFactSource ? 'server' : 'mixed_or_legacy',
    apiSurface,
    pageSurface,
    diagnosticSurface,
    strictFactsSurface,
    fourSurfaceConsistentStatic,
    gaps,
    evidence: [
      relative(pageFile),
      ...(apiFile && exists(apiFile) ? [relative(apiFile)] : []),
    ],
  }
})

const priorityStateFailures = stateRows.filter(
  row => row.priority && !row.stateMachineIntegrated,
)
const priorityActionFailures = actionRows.filter(row => (
  modules.find(item => item.module === row.module)?.priority
  && !row.actionContractComplete
))
const priorityFactFailures = factRows.filter(row => (
  modules.find(item => item.module === row.module)?.priority
  && !row.fourSurfaceConsistentStatic
))
const transitionCountClientFallbacks = sourceFiles(sourceRoot).flatMap(
  file => linesMatching(
    file,
    /statusTransitionCount[^\r\n]*(?:Number\([^)]*\|\|\s*0\)|\|\|\s*0|\.length)/,
    'client-default-or-recalculated-transition-count',
  ),
)
commonStateGuards.noClientTransitionCountDefault =
  transitionCountClientFallbacks.length === 0

const migrationSummary = {
  migrated: modules.filter(row => (
    row.migrationStatus === 'migrated'
  )).length,
  partiallyMigrated: modules.filter(row => (
    row.migrationStatus === 'partially_migrated'
  )).length,
  legacyObservabilityGap: modules.filter(row => (
    row.migrationStatus === 'legacy_observability_gap'
  )).length,
}

const common = {
  version: VERSION,
  scanScope: [
    'backend',
    'frontend/src',
  ],
  moduleCount: modules.length,
  priorityModules: modules
    .filter(row => row.priority)
    .map(row => row.module),
  migrationSummary,
  allSystemModulesMigrated: false,
  productionUserDataWritten: false,
}

const stateMachineCoverageReport = {
  ...common,
  result:
    priorityStateFailures.length || !governanceStandardsSynchronized
      ? 'failed'
      : 'passed',
  reportType: 'state-machine-coverage',
  commonStateGuards,
  transitionCountClientFallbackCount:
    transitionCountClientFallbacks.length,
  transitionCountClientFallbacks,
  governanceStandardsSynchronized,
  governanceFiles: governanceFiles.map(relative),
  priorityFailureCount: priorityStateFailures.length,
  priorityFailures: priorityStateFailures.map(row => row.module),
  moduleReports: stateRows,
  assertion:
    '未迁移模块如实保留在 backlog，未标记为符合统一状态机契约。',
}
const businessActionCoverageReport = {
  ...common,
  result: priorityActionFailures.length ? 'failed' : 'passed',
  reportType: 'business-action-coverage',
  registryVersion:
    actionRegistry.match(
      /PCE_BUSINESS_ACTION_REGISTRY_VERSION = '([^']+)'/,
    )?.[1] || '',
  registeredModuleCount: actionRows.filter(row => row.registered).length,
  missingRegistryModules: actionRows
    .filter(row => !row.registered)
    .map(row => row.module),
  priorityFailureCount: priorityActionFailures.length,
  priorityFailures: priorityActionFailures.map(row => row.module),
  moduleReports: actionRows,
}
const factConsistencyGapReport = {
  ...common,
  result: priorityFactFailures.length ? 'failed' : 'passed',
  reportType: 'fact-consistency-gap',
  requiredSurfaces: ['API', 'page', 'copyDiagnostic', 'strictFacts'],
  requiredCurrentStateSource: 'server',
  priorityFailureCount: priorityFactFailures.length,
  priorityFailures: priorityFactFailures.map(row => row.module),
  moduleReports: factRows,
  gapModuleCount: factRows.filter(
    row => row.gaps.length > 0,
  ).length,
}

writeJson('stateMachineCoverageReport.json', stateMachineCoverageReport)
writeJson(
  'businessActionCoverageReport.json',
  businessActionCoverageReport,
)
writeJson('factConsistencyGapReport.json', factConsistencyGapReport)

const failed = [
  stateMachineCoverageReport,
  businessActionCoverageReport,
  factConsistencyGapReport,
].filter(report => report.result !== 'passed')
console.log(JSON.stringify({
  result: failed.length ? 'failed' : 'passed',
  version: VERSION,
  moduleCount: modules.length,
  priorityModuleCount: modules.filter(row => row.priority).length,
  migratedModuleCount: migrationSummary.migrated,
  partiallyMigratedModuleCount: migrationSummary.partiallyMigrated,
  legacyObservabilityGapModuleCount:
    migrationSummary.legacyObservabilityGap,
  missingRegistryModules:
    businessActionCoverageReport.missingRegistryModules,
  factGapModuleCount: factConsistencyGapReport.gapModuleCount,
  allSystemModulesMigrated: false,
}, null, 2))
if (failed.length) process.exitCode = 1
