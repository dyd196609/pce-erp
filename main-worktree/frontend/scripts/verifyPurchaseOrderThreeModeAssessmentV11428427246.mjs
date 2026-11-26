import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(process.cwd(), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(root, relative))

const procurementModels = read('backend/procurement/models.py')
const legacyModels = read('backend/purchase/models.py')
const service = read('backend/procurement/scm_runtime_services.py')
const pageFacts = read('backend/procurement/scm_page_facts.py')
const resolver = read('backend/procurement/supplier_material_fact_resolver.py')
const routes = read('frontend/src/router/index.js')
const schema = read('frontend/src/meta/schema/scm/scmStandardPageContract.js')
const provider = read('frontend/src/meta/providers/purchaseOrderListDataProviderV1142842729.js')
const action = read('frontend/src/meta/actions/scm/createPurchaseOrderActionV114284271.js')
const store = read('frontend/src/meta/scm/scmStore.js')
const bpm = read('frontend/src/domain/workflow/bpmRuntime.js')
const inquiryGuard = read('frontend/src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryTransitionGuard.js')
const governance = read('docs/governance/PCE采购三模式治理规范.md')

const checks = {
  'PURCHASE-ORDER-CURRENT-CREATION-CHAIN-001':
    routes.includes("path: 'scm/purchase-order/create'")
    && schema.includes("businessObject: 'PurchaseOrder'")
    && provider.includes('/api/procurement/scm-page-facts/purchase-order/')
    && service.includes('class PurchaseOrderCreationService')
    && procurementModels.includes('class PurchaseOrder(models.Model)'),
  'PURCHASE-ORDER-PRICE-SOURCE-SCAN-001':
    resolver.includes('SupplierQuoteItem.unitPrice')
    && action.includes('confirmedPrice ?? line.unitPrice')
    && store.includes('patch.planPrice ?? patch.price ?? patch.unitPrice')
    && pageFacts.includes('priceSource'),
  'PURCHASE-ORDER-MASTER-DATA-BINDING-001':
    procurementModels.includes('supplier = models.ForeignKey')
    && procurementModels.includes('"masterdata.Material"')
    && service.includes('is_active=True')
    && service.includes('MATERIAL_MASTER_NOT_MAINTAINED'),
  'PURCHASE-ORDER-SNAPSHOT-SCAN-001':
    !procurementModels.includes('supplier_code_snapshot')
    && !procurementModels.includes('unit_price_snapshot')
    && pageFacts.includes('supplierInformationSource'),
  'PURCHASE-SUPPLIER-MATERIAL-PRICE-LINK-001':
    !procurementModels.includes('supplier_material_price = models.ForeignKey')
    && !service.includes('SupplierMaterialPrice.objects'),
  'PURCHASE-WORKFLOW-FLEXIBILITY-SCAN-001':
    bpm.includes("case 'gateway'") && bpm.includes('evaluateGateway')
    && inquiryGuard.includes('skip_transition_forbidden'),
  'PURCHASE-EXISTING-INTELLIGENCE-REUSE-001':
    exists('frontend/src/platform/registry/metaRegistry.js')
    && exists('frontend/src/meta/workflow/businessWorkflowEngine.js')
    && exists('frontend/src/meta/runtime/permissionEngine.js')
    && exists('frontend/src/meta/ai/workflowEvolutionEngine.js'),
  'PURCHASE-DUPLICATE-FRAMEWORK-001':
    procurementModels.includes('class PurchaseOrder(models.Model)')
    && legacyModels.includes('class PurchaseOrder(models.Model)')
    && governance.includes('LEGACY（历史兼容）'),
  'PURCHASE-BUSINESS-WRITE-ZERO-001':
    !governance.includes('本批次创建订单') && governance.includes('零写入诊断'),
  'PURCHASE-MODE-SINGLE-ORDER-001': governance.includes('PURCHASE-MODE-SINGLE-ORDER-001'),
  'PURCHASE-ORDER-MASTER-DATA-BOUNDARY-001': governance.includes('PURCHASE-ORDER-MASTER-DATA-BOUNDARY-001'),
  'PURCHASE-PRICE-CLOSED-LOOP-001': governance.includes('PURCHASE-PRICE-CLOSED-LOOP-001'),
  'PURCHASE-DIRECT-PRICE-CONFIRM-001': governance.includes('PURCHASE-DIRECT-PRICE-CONFIRM-001'),
  'PURCHASE-AGREED-PRICE-VALIDITY-001': governance.includes('PURCHASE-AGREED-PRICE-VALIDITY-001'),
  'PURCHASE-ORDER-SNAPSHOT-001': governance.includes('PURCHASE-ORDER-SNAPSHOT-001'),
  'PURCHASE-PROCESS-BYPASS-TRACE-001': governance.includes('PURCHASE-PROCESS-BYPASS-TRACE-001'),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([code]) => code)
const report = {
  version: 'V1.14.2.8.4.27.2.46', batch: 'Assessment / Design',
  checks, failed,
  findings: {
    currentPurchaseOrderModel: 'procurement.PurchaseOrder',
    legacyPurchaseOrderModel: 'purchase.PurchaseOrder',
    supplierMaterialPriceLink: 'MISSING',
    masterDataBinding: 'PARTIAL', purchaseOrderSnapshot: 'FAIL',
    workflowFlexibility: 'PARTIAL', businessWriteCount: 0,
  },
}
console.log(JSON.stringify(report, null, 2))
if (failed.length) process.exitCode = 1
