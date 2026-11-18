import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.resolve(frontend, '..')
const read = (...parts) => fs.readFileSync(path.join(...parts), 'utf8')
const page = read(frontend, 'src', 'meta', 'pages', 'PurchaseReconciliationPage.vue')
const invoicePage = read(frontend, 'src', 'meta', 'pages', 'InvoicePreparePage.vue')
const processRegistry = read(frontend, 'src', 'meta', 'process', 'businessProcessRegistry.js')
const operationRegistry = read(frontend, 'src', 'meta', 'process', 'businessOperationPageRegistry.js')
const navigation = read(frontend, 'src', 'meta', 'process', 'purchaseInvoicePrepareNavigation.js')
const actionRegistry = read(frontend, 'src', 'meta', 'process', 'purchasePayablePaymentActionRegistry.js')
const executor = read(frontend, 'src', 'meta', 'process', 'businessFlowActionExecutor.js')
const models = read(sourceRoot, 'backend', 'reconciliation', 'models.py')
const providers = read(sourceRoot, 'backend', 'reconciliation', 'providers.py')
const repositories = read(sourceRoot, 'backend', 'reconciliation', 'repositories.py')
const checking = read(sourceRoot, 'backend', 'reconciliation', 'checking.py')
const views = read(sourceRoot, 'backend', 'reconciliation', 'views.py')

const formalContracts = [page, invoicePage, processRegistry, operationRegistry, navigation, actionRegistry, executor].join('\n')
const rules = [
  ['purchase_reconciliation_normal_mode_uses_server_read_model',
    page.includes('listPurchaseReconciliations') && page.includes("source: 'server_purchase_reconciliation_api'")],
  ['supplier_settlement_store_not_formal_reconciliation_source',
    !page.includes('listSupplierSettlements') && !page.includes('supplierSettlementStore')],
  ['reconciliation_evidence_sources_are_independent',
    providers.includes('SupplierSettlementEvidenceProvider')
      && providers.includes('PayableCheckEvidenceProvider')
      && repositories.includes('SupplierSettlementAuthorityRepository')
      && repositories.includes('PayableCheckAuthorityRepository')
      && checking.includes('PRC_EVIDENCE_PROVIDER_COLLISION')
      && checking.includes('PRC_EVIDENCE_REPOSITORY_COLLISION')
      && !providers.includes('PurchaseReconciliationSourceSnapshot')],
  ['readiness_is_server_derived',
    checking.includes('def derive_next_step_readiness')
      && views.includes('build_invoice_prepare_eligibility')
      && page.includes('explicitUserAction: true')
      && !page.includes('nextStepReadiness: row.nextStepReadiness, expectedVersion')
      && !page.includes('readiness: row')],
  ['deprecated_purchase_reconciliation_readonly_contract_absent',
    !formalContracts.includes('purchaseReconciliationReadonly')
      && !formalContracts.includes('view_purchase_reconciliation_readonly')],
  ['purchase_invoice_prepare_source_is_reconciliation',
    processRegistry.includes("sourceDocumentTypes: ['purchaseReconciliation']")
      && actionRegistry.includes("sourceObjectType: 'purchaseReconciliation'")],
  ['matched_is_only_invoice_prepare_release_status',
    processRegistry.includes("completionStatusValues: ['matched']")
      && checking.includes('reconciliation.status == PurchaseReconciliation.Status.MATCHED')
      && navigation.includes("status !== 'matched'")],
  ['non_matched_states_cannot_enter_invoice_prepare',
    models.includes('DIFFERENCE_FOUND = "difference_found"')
      && models.includes('SOURCE_MISSING = "source_missing"')
      && processRegistry.includes("blockedStatusValues: ['draft', 'difference_found', 'source_missing']")
      && executor.includes('V42 禁止创建采购发票准备对象')],
]

const failures = rules.filter(([, passed]) => !passed).map(([ruleCode]) => ({
  ruleCode,
  expected: true,
  actual: false,
  failureReport: 'purchase-reconciliation-matched-ready-static-guards.json',
}))
const report = {
  version: 'V1.14.2.8.4.7.42',
  ruleCount: rules.length,
  passedCount: rules.length - failures.length,
  failedCount: failures.length,
  rules: rules.map(([ruleCode, passed]) => ({ ruleCode, passed })),
  failures,
  result: failures.length ? 'failed' : 'passed',
}
const output = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-matched-ready-static-guards.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
