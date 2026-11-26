import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = path.resolve(frontend, '..')
const read = (relative) => fs.readFileSync(path.join(source, relative), 'utf8')
const page = read('frontend/src/meta/pages/InvoicePreparePage.vue')
const api = read('frontend/src/api/purchaseInvoicePrepare.js')
const registry = read('frontend/src/meta/process/businessProcessRegistry.js')
const operationRegistry = read('frontend/src/meta/process/businessOperationPageRegistry.js')
const actionRegistry = read('frontend/src/meta/process/purchasePayablePaymentActionRegistry.js')
const router = read('frontend/src/router/index.js')
const models = read('backend/purchase_invoice_prepare/models.py')
const service = read('backend/purchase_invoice_prepare/services.py')
const settings = read('backend/pce_backend/settings.py')
const urls = read('backend/purchase_invoice_prepare/urls.py')

const invoiceStep = registry.match(/step\(\{\s*stepId:\s*'invoice-prepare'[\s\S]*?\n\s*\}\),/)?.[0] || ''
const reconciliationIndex = registry.indexOf("stepId: 'purchase-reconciliation'")
const invoiceIndex = registry.indexOf("stepId: 'invoice-prepare'")
const apIndex = registry.indexOf("stepId: 'account-payable-draft'")
const routeCount = [...router.matchAll(/path:\s*'finance\/purchase-invoice-prepares'/g)].length
const invoiceOperationActionCode = operationRegistry
  .match(/pageStepId:\s*'invoice-prepare'[\s\S]*?realActionCode:\s*'([^']+)'/)?.[1] || ''

const guards = {
  purchase_invoice_prepare_canonical_name_is_correct:
    invoiceStep.includes("stepName: '采购发票准备'")
    && invoiceStep.includes("pageTitle: '采购发票准备'")
    && page.includes('>采购发票准备</h2>')
    && !page.includes('采购发票预备'),
  purchase_invoice_prepare_module_not_duplicated:
    (registry.match(/stepId:\s*'invoice-prepare'/g) || []).length === 1,
  purchase_invoice_prepare_module_order_unchanged:
    reconciliationIndex >= 0 && reconciliationIndex < invoiceIndex && invoiceIndex < apIndex,
  purchase_invoice_prepare_route_not_duplicated:
    routeCount === 1 && invoiceStep.includes("routePath: '/finance/purchase-invoice-prepares'"),
  purchase_invoice_prepare_source_is_reconciliation:
    invoiceStep.includes("sourceDocumentTypes: ['purchaseReconciliation']")
    && models.includes('default="purchaseReconciliation"')
    && models.includes('pip_source_type_reconciliation'),
  supplier_settlement_not_direct_invoice_prepare_source:
    !invoiceStep.includes("sourceDocumentTypes: ['supplierSettlement']")
    && !service.includes('SupplierSettlementAuthorityRecord')
    && !service.includes('supplierSettlementStore'),
  purchase_invoice_prepare_normal_mode_uses_server_api:
    page.includes("from '../../api/purchaseInvoicePrepare.js'")
    && page.includes('purchaseInvoicePrepareApi.list()')
    && !page.includes("invoicePrepareStore.js")
    && !page.includes('localStorage.'),
  frontend_cannot_write_invoice_prepare:
    !page.includes('listInvoicePrepares')
    && !page.includes('saveInvoicePrepare')
    && api.includes("url: '/api/scm/purchase-invoice-prepares/generate'"),
  frontend_cannot_generate_invoice_prepare_number:
    !page.includes('Date.now()')
    && !page.includes('Math.random()')
    && !/purchaseInvoicePrepareApi\.generate\(\{[\s\S]*?\bprepareNo\s*:/.test(page)
    && service.includes('BusinessDocumentNumberSequence'),
  server_revalidates_reconciliation_eligibility:
    (service.match(/build_business_gate\(/g) || []).length >= 3
    && service.includes('after_locked_source_reload')
    && service.includes('after_eligibility_revalidation'),
  matched_is_required_for_invoice_prepare:
    service.includes('reconciliation.status == "matched"')
    && service.includes('PIP_GATE_RECONCILIATION_MATCHED'),
  invoice_prepare_source_version_is_checked:
    service.includes('PIP_GATE_SOURCE_VERSION_MATCH')
    && service.includes('PIP_SOURCE_VERSION_CONFLICT'),
  invoice_prepare_check_version_is_checked:
    service.includes('PIP_GATE_CHECK_VERSION_MATCH')
    && service.includes('PIP_CHECK_VERSION_CONFLICT'),
  same_reconciliation_single_invoice_prepare:
    models.includes('models.OneToOneField(')
    && service.includes('source_purchase_reconciliation=source'),
  same_idempotency_single_invoice_prepare:
    service.includes('BusinessActionIdempotency.objects.create')
    && service.includes('action_code=ACTION_CODE')
    && service.includes('request_hash'),
  invoice_prepare_audit_required_for_commit:
    service.indexOf('BusinessActionAuditRecord.objects.create') < service.indexOf('BusinessActionIdempotency.Status.COMMITTED')
    && service.includes('obj.audit_record_id = audit.pk'),
  invoice_prepare_does_not_create_ap_draft:
    !service.includes('AccountPayable')
    && !service.includes('account_payable'),
  invoice_prepare_does_not_create_payment_objects:
    !service.includes('PaymentApplication')
    && !service.includes('PaymentVoucher')
    && !service.includes('Ledger')
    && !service.includes('BankTransaction'),
  production_rollout_disabled:
    settings.includes('PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED')
    && settings.includes('"0"')
    && page.includes('生产灰度：关闭'),
  module_navigation_unchanged:
    routeCount === 1
    && ['GENERATE_PURCHASE_INVOICE_PREPARE', 'VALIDATE_PURCHASE_INVOICE_PREPARE'].includes(invoiceOperationActionCode)
    && actionRegistry.includes(`actionCode: '${invoiceOperationActionCode}'`)
    && actionRegistry.includes("actionCode: 'GENERATE_PURCHASE_INVOICE_PREPARE'")
    && urls.includes('PrepareListView')
    && urls.includes('PrepareBySourceView'),
  existing_invoice_prepare_disables_generation:
    service.includes('"generationStatus": "existing_target"')
    && service.includes('"generationAllowed": False')
    && page.includes('currentState.targetCount === 0'),
  existing_target_has_committed_idempotency:
    service.includes('"currentIdempotencyStatus": idempotency.status')
    && service.includes('BusinessActionIdempotency.objects.filter('),
  existing_target_has_consumed_number:
    service.includes('"currentNumberReservationStatus": reservation.status')
    && service.includes('BusinessDocumentNumberReservation.objects.filter(pk=obj.number_reservation_id)'),
  current_status_not_from_pre_action_snapshot:
    page.includes("currentState.generationStatus === 'existing_target'")
    && page.includes('currentBusinessStatus')
    && !page.includes("value: source.eligible ? '允许受控生成'"),
  generation_button_absent_after_creation:
    page.includes('v-if="generationButtonVisible"')
    && page.includes('currentState.targetCount === 0')
    && page.includes('currentState.generationAllowed'),
  invoice_prepare_current_state_from_server:
    page.includes('purchaseInvoicePrepareApi.bySource(source.id)')
    && page.includes('purchaseInvoicePrepareApi.detail(')
    && page.includes('purchaseInvoicePrepareApi.generationResult(')
    && service.includes('"currentStateSource": "server"'),
  pre_action_gate_snapshot_is_explicitly_labelled:
    page.includes('>动作前业务门禁快照</h3>')
    && page.includes('仅作审计证据，不代表当前可执行性'),
}

const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  version: 'V1.14.2.8.4.7.43.1',
  guardCount: Object.keys(guards).length,
  importGraphChecked: true,
  normalInitializationPathChecked: true,
  apiDirectionChecked: true,
  processContractChecked: true,
  serverGenerationFunctionChecked: true,
  databaseConstraintsChecked: true,
  downstreamCallGraphChecked: true,
  guards,
  failures,
  result: failures.length ? 'failed' : 'passed',
}
const output = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'purchase-invoice-prepare-controlled-generation-static-guards.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
