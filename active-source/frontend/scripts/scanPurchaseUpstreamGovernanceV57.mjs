import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.57'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'purchase-upstream-governance-v57',
)
const modules = [
  {
    module: 'payable_confirm',
    canonicalName: '应付确认准备',
    migrationStatus: 'partially_migrated',
    backend: [
      'backend/payable_confirmation_prepare/models.py',
      'backend/payable_confirmation_prepare/services.py',
      'backend/payable_confirmation_prepare/views.py',
    ],
    frontend: [
      'frontend/src/meta/pages/AccountPayableConfirmPage.vue',
    ],
  },
  {
    module: 'purchase_invoice_prepare',
    canonicalName: '采购发票准备',
    migrationStatus: 'partially_migrated',
    backend: [
      'backend/purchase_invoice_prepare/models.py',
      'backend/purchase_invoice_prepare/services.py',
      'backend/purchase_invoice_prepare/v44_services.py',
      'backend/purchase_invoice_prepare/views.py',
    ],
    frontend: [
      'frontend/src/meta/pages/InvoicePreparePage.vue',
      'frontend/src/meta/finance/invoicePrepareStore.js',
    ],
  },
  {
    module: 'purchase_accounts_payable_draft',
    canonicalName: '采购应付账款草稿',
    migrationStatus: 'partially_migrated',
    backend: [
      'backend/purchase_accounts_payable_draft/models.py',
      'backend/purchase_accounts_payable_draft/services.py',
      'backend/purchase_accounts_payable_draft/views.py',
    ],
    frontend: [
      'frontend/src/meta/pages/AccountPayableDraftPage.vue',
      'frontend/src/meta/finance/accountPayableDraftStore.js',
    ],
  },
  {
    module: 'purchase_reconciliation',
    canonicalName: '采购对账',
    migrationStatus: 'legacy',
    backend: [
      'backend/reconciliation/models.py',
      'backend/reconciliation/checking.py',
      'backend/reconciliation/views.py',
    ],
    frontend: [
      'frontend/src/meta/pages/PurchaseReconciliationPage.vue',
    ],
  },
]

const read = relative => fs.readFileSync(path.join(workspace, relative), 'utf8')
const lineEvidence = (relative, pattern, classification) => read(relative)
  .split(/\r?\n/)
  .flatMap((line, index) => pattern.test(line)
    ? [{
        file: relative,
        line: index + 1,
        excerpt: line.trim(),
        classification,
      }]
    : [])
const writeJson = (name, value) => fs.writeFileSync(
  path.join(resultRoot, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)

fs.mkdirSync(resultRoot, { recursive: true })
const stateReports = modules.map(module => {
  const directWrites = module.backend.flatMap(file => lineEvidence(
    file,
    /(?:\.status\s*=\s*["'](?:prepared|matched|difference_found|source_missing|draft)["']|\.update\s*\([^)]*\bstatus\s*=|objects\.create\s*\()/,
    'direct-or-unmanaged-business-state-write',
  ))
  const localStorage = module.frontend.flatMap(file => lineEvidence(
    file,
    /localStorage\.(?:getItem|setItem)/,
    'client-business-state-storage',
  ))
  const backendText = module.backend.map(read).join('\n')
  return {
    module: module.module,
    canonicalName: module.canonicalName,
    migrationStatus: module.migrationStatus,
    businessStateManagedModel: backendText.includes('BusinessStateManagedModel'),
    businessStateInitializationService:
      backendText.includes('create_business_object_with_initial_state'),
    businessStateTransitionService:
      backendText.includes('transition_business_object'),
    persistedTransitionFacts:
      backendText.includes('business_state_transition_facts'),
    directWriteCount: directWrites.length,
    directWriteEvidence: directWrites,
    localStorageBusinessStateCount: localStorage.length,
    localStorageEvidence: localStorage,
  }
})
const registrySource = read(
  'frontend/src/meta/runtime/pceBusinessActionRegistry.js',
)
const actionReports = modules.map(module => {
  const pageText = module.frontend.map(read).join('\n')
  const hardcoded = module.frontend.flatMap(file => lineEvidence(
    file,
    /(?:完成应付核对|进入供应商结算|保存发票|生成AP草稿|查询生成结果|幂等重试|提交结果恢复)/,
    'module-private-or-hardcoded-business-action',
  ))
  const registryKeys = {
    payable_confirm: 'payable-confirm',
    purchase_invoice_prepare: 'purchase-invoice-prepare',
    purchase_accounts_payable_draft: 'account-payable-draft',
    purchase_reconciliation: 'purchase-reconciliation',
  }
  return {
    module: module.module,
    canonicalName: module.canonicalName,
    migrationStatus: module.migrationStatus,
    registryModuleCode: registryKeys[module.module],
    registered: registrySource.includes(registryKeys[module.module]),
    pageUsesBusinessActionRegistry: pageText.includes('PceBusinessActionBar'),
    hardcodedActionCount: hardcoded.length,
    hardcodedActionEvidence: hardcoded,
    requiredDeclarations: {
      actionCode: registrySource.includes('actionCode'),
      displayName: registrySource.includes('displayName'),
      allowedRoles: registrySource.includes('allowedRoles'),
      allowedStatus: registrySource.includes('allowedStatus'),
      singleOrBatch: registrySource.includes('singleOrBatch'),
      serverEligibilityCheck:
        registrySource.includes('serverEligibilityCheck'),
    },
  }
})
const factReports = modules.map(module => {
  const backendText = module.backend.map(read).join('\n')
  const pageText = module.frontend.map(read).join('\n')
  const surfaces = {
    api: backendText.includes('statusTransitionHistory'),
    page: pageText.includes('statusTransitionHistory'),
    diagnostic:
      /copyDiagnostics|copyDiagnostic/.test(pageText)
      && pageText.includes('statusTransitionHistory'),
    strictFacts: pageText.includes('strictFacts'),
  }
  return {
    module: module.module,
    canonicalName: module.canonicalName,
    migrationStatus: module.migrationStatus,
    currentStateSourceServer:
      backendText.includes('currentStateSource')
      && pageText.includes("currentStateSource: 'server'"),
    surfaces,
    fourSurfaceConsistent:
      Object.values(surfaces).every(Boolean)
      && backendText.includes('business_state_transition_facts'),
    gaps: [
      ...(!surfaces.api ? ['api_transition_facts_missing'] : []),
      ...(!surfaces.page ? ['page_transition_facts_missing'] : []),
      ...(!surfaces.diagnostic ? ['diagnostic_transition_facts_missing'] : []),
      ...(!surfaces.strictFacts ? ['strictFacts_missing'] : []),
      ...(!backendText.includes('business_state_transition_facts')
        ? ['shared_server_fact_builder_missing']
        : []),
    ],
  }
})

const base = {
  result: 'passed',
  version: VERSION,
  reportPhase: 'pre_governance_readonly_scan',
  scanScope: ['backend', 'frontend/src'],
  moduleCount: modules.length,
  productionUserDataWritten: false,
}
writeJson('purchase_upstream_state_machine_scan.json', {
  ...base,
  reportType: 'state_machine_scan',
  migrationSummary: {
    migrated: stateReports.filter(item => item.migrationStatus === 'migrated').length,
    partiallyMigrated:
      stateReports.filter(item => item.migrationStatus === 'partially_migrated').length,
    legacy: stateReports.filter(item => item.migrationStatus === 'legacy').length,
  },
  moduleReports: stateReports,
})
writeJson('purchase_upstream_action_scan.json', {
  ...base,
  reportType: 'business_action_scan',
  hardcodedActionCount:
    actionReports.reduce((total, item) => total + item.hardcodedActionCount, 0),
  moduleReports: actionReports,
})
writeJson('purchase_upstream_fact_consistency_scan.json', {
  ...base,
  reportType: 'four_surface_fact_scan',
  currentStateSourceRequired: 'server',
  consistentModuleCount:
    factReports.filter(item => item.fourSurfaceConsistent).length,
  gapModuleCount:
    factReports.filter(item => !item.fourSurfaceConsistent).length,
  moduleReports: factReports,
})

console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  moduleCount: modules.length,
  migrationSummary: {
    migrated: 0,
    partiallyMigrated: 3,
    legacy: 1,
  },
  hardcodedActionCount:
    actionReports.reduce((total, item) => total + item.hardcodedActionCount, 0),
  factGapModuleCount:
    factReports.filter(item => !item.fourSurfaceConsistent).length,
}, null, 2))
