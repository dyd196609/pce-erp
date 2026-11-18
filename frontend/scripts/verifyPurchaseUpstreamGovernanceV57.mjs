import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

import {
  BusinessActionRegistry,
  PCE_BUSINESS_ACTION_REGISTRY_VERSION,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'

const VERSION = 'V1.14.2.8.4.7.57'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'purchase-upstream-governance-v57',
)
const read = relative => fs.readFileSync(
  path.join(workspace, relative),
  'utf8',
)
const writeJson = (name, value) => fs.writeFileSync(
  path.join(resultRoot, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)

const registry = BusinessActionRegistry.list()
const registryByModule = new Map(
  registry.map(contract => [contract.currentModule, contract]),
)
const modules = [
  {
    module: 'payable_confirm',
    canonicalName: '应付确认准备',
    riskLevel: 'Level 1',
    moduleCode: 'payable-confirmation-prepare',
    model: 'backend/payable_confirmation_prepare/models.py',
    services: ['backend/payable_confirmation_prepare/services.py'],
    view: 'backend/payable_confirmation_prepare/views.py',
    page: 'frontend/src/meta/pages/AccountPayableConfirmPage.vue',
    transitionRequired: false,
    requiredActions: ['enter-payment-request-prepare'],
  },
  {
    module: 'purchase_invoice_prepare',
    canonicalName: '采购发票准备',
    riskLevel: 'Level 2',
    moduleCode: 'purchase-invoice-prepare',
    model: 'backend/purchase_invoice_prepare/models.py',
    services: [
      'backend/purchase_invoice_prepare/services.py',
      'backend/purchase_invoice_prepare/v44_services.py',
    ],
    view: 'backend/purchase_invoice_prepare/views.py',
    page: 'frontend/src/meta/pages/InvoicePreparePage.vue',
    transitionRequired: true,
    requiredActions: [
      'save-purchase-invoice-data',
      'validate-purchase-invoice-data',
      'enter-accounts-payable-draft',
    ],
  },
  {
    module: 'purchase_accounts_payable_draft',
    canonicalName: '采购应付账款草稿',
    riskLevel: 'Level 2',
    moduleCode: 'accounts-payable-draft',
    model: 'backend/purchase_accounts_payable_draft/models.py',
    services: ['backend/purchase_accounts_payable_draft/services.py'],
    view: 'backend/purchase_accounts_payable_draft/views.py',
    page: 'frontend/src/meta/pages/AccountPayableDraftPage.vue',
    transitionRequired: false,
    requiredActions: [
      'generate-purchase-accounts-payable-draft',
      'enter-payable-confirmation-prepare',
    ],
  },
  {
    module: 'purchase_reconciliation',
    canonicalName: '采购对账',
    riskLevel: 'Level 2',
    moduleCode: 'purchase-reconciliation',
    model: 'backend/reconciliation/models.py',
    services: [
      'backend/reconciliation/services.py',
      'backend/reconciliation/checking.py',
    ],
    view: 'backend/reconciliation/views.py',
    page: 'frontend/src/meta/pages/PurchaseReconciliationPage.vue',
    transitionRequired: true,
    requiredActions: [
      'generate-purchase-invoice-prepare',
      'complete-purchase-reconciliation',
      'enter-purchase-invoice-prepare',
    ],
  },
]

const moduleReports = modules.map(item => {
  const model = read(item.model)
  const service = item.services.map(read).join('\n')
  const view = read(item.view)
  const page = read(item.page)
  const contract = registryByModule.get(item.moduleCode)
  const actions = contract?.actions || []
  const actionById = new Map(actions.map(action => [action.actionId, action]))
  const requiredActionReports = item.requiredActions.map(actionId => {
    const action = actionById.get(actionId)
    return {
      actionId,
      registered: Boolean(action),
      declarationsComplete: Boolean(
        action?.actionCode
        && action?.displayName
        && action?.allowedRoles?.length
        && action?.allowedStatus?.length
        && action?.singleOrBatch
        && action?.serverEligibilityCheck === true
      ),
    }
  })
  const directBusinessStatusWrite = (
    /\b(?:obj|prepare|source|reconciliation|draft)\.status\s*=(?!=)/.test(service)
    || /\.update\s*\([^)]*\bstatus\s*=/.test(service)
    || /bulk_update\s*\([^)]*["']status["']/.test(service)
  )
  const checks = {
    managedModel: model.includes('BusinessStateManagedModel'),
    initializationService:
      service.includes('create_business_object_with_initial_state'),
    transitionService:
      !item.transitionRequired || service.includes('transition_business_object'),
    noDirectBusinessStatusWrite: !directBusinessStatusWrite,
    persistedTransitionFacts:
      service.includes('business_state_transition_facts_from_allowed_transitions'),
    apiStrictFacts:
      view.includes('business_state_collection_facts')
      && view.includes('"strictFacts"'),
    pageServerFacts:
      page.includes('strictFacts')
      && page.includes("currentStateSource: 'server'"),
    diagnosticUsesServerFacts:
      /copyDiagnostics|copyDiagnostic/.test(page)
      && /strictFacts:\s*\{\s*\.\.\.strictFacts\s*\}/s.test(page),
    pageUsesRegistry: page.includes('PceBusinessActionBar'),
    requiredActionsRegistered:
      requiredActionReports.every(action => (
        action.registered && action.declarationsComplete
      )),
    noClientTransitionDefault:
      !/statusTransitionCount[^;\n]*Number\s*\([^)]*\|\|\s*0/.test(page),
  }
  const blockers = Object.entries(checks)
    .filter(([, passed]) => !passed)
    .map(([name]) => name)
  return {
    module: item.module,
    canonicalName: item.canonicalName,
    riskLevel: item.riskLevel,
    migrationStatus: blockers.length ? 'partially_migrated' : 'migrated',
    checks,
    requiredActions: requiredActionReports,
    blockers,
  }
})

const guards = {
  registryVersionCurrent: [
    VERSION,
    'V1.14.2.8.4.7.58',
    'V1.14.2.8.4.7.59',
    'V1.14.2.8.4.8.3.1',
    'V1.14.2.8.4.8.3.1.1',
  ].includes(PCE_BUSINESS_ACTION_REGISTRY_VERSION),
  fourPriorityModulesCovered: moduleReports.length === 4,
  allPriorityModulesMigrated:
    moduleReports.every(item => item.migrationStatus === 'migrated'),
  noStatusDirectWrite:
    moduleReports.every(item => item.checks.noDirectBusinessStatusWrite),
  actionRegistryConsistent:
    moduleReports.every(item => item.checks.requiredActionsRegistered),
  fourSurfaceStaticContract:
    moduleReports.every(item => (
      item.checks.persistedTransitionFacts
      && item.checks.apiStrictFacts
      && item.checks.pageServerFacts
      && item.checks.diagnosticUsesServerFacts
    )),
}
const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const result = failedGuards.length ? 'failed' : 'passed'

fs.mkdirSync(resultRoot, { recursive: true })
writeJson('governance-verification-report.json', {
  result,
  version: VERSION,
  reportPhase: 'post_governance_static_verification',
  moduleCount: moduleReports.length,
  migratedModuleCount:
    moduleReports.filter(item => item.migrationStatus === 'migrated').length,
  partiallyMigratedModuleCount:
    moduleReports.filter(
      item => item.migrationStatus === 'partially_migrated',
    ).length,
  stateMachineConsistent: guards.noStatusDirectWrite,
  actionRegistryConsistent: guards.actionRegistryConsistent,
  fourSurfaceStaticContract: guards.fourSurfaceStaticContract,
  productionUserDataWritten: false,
  migrationExecuted: false,
  guards,
  failedGuards,
  moduleReports,
})

console.log(JSON.stringify({
  result,
  version: VERSION,
  moduleCount: moduleReports.length,
  migratedModuleCount:
    moduleReports.filter(item => item.migrationStatus === 'migrated').length,
  failedGuards,
}, null, 2))
if (failedGuards.length) {
  throw new Error(`V57 governance guards failed: ${failedGuards.join(', ')}`)
}
