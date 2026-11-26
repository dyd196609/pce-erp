import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(process.cwd(), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const models = read('backend/procurement/models.py')
const service = read('backend/procurement/scm_runtime_services.py')
const facts = read('backend/procurement/scm_page_facts.py')
const migration = read('backend/procurement/migrations/0020_standard_purchase_price_link_v46_batch2.py')
const request = read('frontend/src/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderGateCreationRequestV11428427219.js')
const schema = read('frontend/src/meta/schema/purchase/purchaseOrder.js')
const viewModel = read('frontend/src/meta/viewModels/purchaseOrderViewModelV1142842724.js')
const tests = read('backend/procurement/tests_v11428427246_batch2.py')
const gatePage = read('frontend/src/meta/pages/ScmPurchaseOrderGatePage.vue')
const gateProvider = read('frontend/src/meta/providers/supplierRecommendationGateProviderV11428425.js')
const actions = read('backend/procurement/scm_runtime_actions.py')
const masterViews = read('backend/masterdata/views.py')
const caseLibrary = read('docs/acceptance/standard-purchase-price-link-failure-case-library-v11428427246-batch2.md')
const remediation = read('docs/governance/V1.14.2.8.4.27.2.46-Batch2-人工验收失败整改与复测报告.md')

const checks = [
  ['01 Canonical domain', /class PurchaseOrder\(models\.Model\)/.test(models)
    && /db_table = "purchase_order"/.test(models)],
  ['02 STANDARD mode', /\("STANDARD",/.test(models) && /purchase_mode="STANDARD"/.test(service)],
  ['03 Header supplier snapshots', ['supplier_code_snapshot', 'supplier_name_snapshot',
    'supplier_contact_snapshot', 'supplier_phone_snapshot', 'supplier_address_snapshot',
    'delivery_address_snapshot'].every(value => models.includes(value))],
  ['04 Formal material reference', /material = models\.ForeignKey\(/.test(models)
    && /material\.is_active or not material\.is_purchased/.test(service)],
  ['05 Purchase request item reference', /source_purchase_request_item = models\.ForeignKey\(/.test(models)
    && /"source_purchase_request_item": source_item/.test(service)],
  ['06 PriceApprovalResult reference', /price_approval_result = models\.ForeignKey\(/.test(models)
    && /"price_approval_result": price_result/.test(service)],
  ['07 SupplierMaterialPrice reference', /supplier_material_price = models\.ForeignKey\(/.test(models)
    && /"supplier_material_price": effective_price/.test(service)],
  ['08 Effective price validity guard', /price\.status != "ACTIVE"/.test(service)
    && /price\.effective_date > order_date/.test(service)
    && /price\.expiry_date and price\.expiry_date < order_date/.test(service)],
  ['09 Exact price identity', /_identity_values/.test(service)
    && /_result_identities/.test(service) && /len\(candidates\) != 1/.test(service)],
  ['10 Same transaction rollback', /@transaction\.atomic/.test(service)
    && /test_invalid_effective_period_rolls_back_whole_order/.test(tests)],
  ['11 Immutable execution snapshots', ['unit_price_snapshot', 'tax_rate_snapshot',
    'currency_snapshot', 'material_code_snapshot', 'material_name_snapshot'].every(value => models.includes(value))
    && /test_snapshot_is_protected_when_effective_price_changes_and_is_restored/.test(tests)],
  ['12 Detail and print projection', ['supplierMaterialPriceNo', 'priceApprovalResultNo',
    'priceEffectiveDate', 'taxRate', 'currency'].every(value => facts.includes(value)
      && schema.includes(value) && viewModel.includes(value))],
  ['13 Gate carries identities only', /priceApprovalResultId/.test(request)
    && /quoteComparisonIds/.test(request) && !/SupplierMaterialFactResolver/.test(service)],
  ['14 Historical compatibility', /default="LEGACY"/.test(models)
    && /default="LEGACY_UNTRACED"/.test(models)
    && /AddField/.test(migration) && !/RunPython/.test(migration)],
  ['15 STANDARD-CREATION-CONTEXT-REQUIRED-001', /previewOnly/.test(actions)
    && /standard-purchase-server-context/.test(gatePage)
    && /serverContextReady/.test(gatePage)
    && /test_preview_returns_complete_server_context_without_write/.test(tests)],
  ['16 STANDARD-NO-IMPLICIT-DEFAULT-OBJECT-001', /EXPLICIT_DECISION_BATCH_REQUIRED/.test(gateProvider)
    && !/decisionBatchStore\.activeBatchId\(\)/.test(gateProvider)
    && /route\.query\.batchId/.test(gatePage)],
  ['17 STANDARD-APPROVED-PRICE-IDENTITY-001', /PRICE_APPROVAL_RESULT_IDENTITY_REQUIRED/.test(service)
    && /return \{str\(result\.pk\), result\.result_no\}/.test(service)
    && !/candidates = \[row for row in candidates if _result_inquiry_no/.test(service)],
  ['18 STANDARD-PRICE-VALUE-CONSISTENCY-001', /STANDARD_PRICE_VALUE_CONSISTENCY_FAILED/.test(service)
    && /supplied_price_no != effective_price\.price_no/.test(service)
    && /test_visible_context_value_mismatch_rolls_back_whole_order/.test(tests)],
  ['19 STANDARD-BROWSER-SAME-OBJECT-001', /PO202608140001/.test(remediation)
    && /SMP-PAP-REAL-SQ-202608040011-L1/.test(remediation)
    && /SMP-PAP-QC-PI-202608040009-MT005/.test(remediation)
    && /OVERLAPPING_EFFECTIVE_PRICE/.test(masterViews)],
  ['20 STANDARD-HUMAN-OBJECT-TRACE-001', /STANDARD-HUMAN-OBJECT-TRACE-001/.test(caseLibrary)
    && /132\.0100/.test(remediation) && /WAITING_RETEST/.test(remediation)],
]

let failed = 0
for (const [name, passed] of checks) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`)
  if (!passed) failed += 1
}
console.log(`STANDARD_PURCHASE_PRICE_LINK_CHECKS=${checks.length}`)
console.log(`STANDARD_PURCHASE_PRICE_LINK_RESULT=${failed ? 'FAIL' : 'PASS'}`)
if (failed) process.exit(1)
