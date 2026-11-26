import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { COMPLETED_MODULE_CONTRACTS, COMPLETED_MODULE_LIFECYCLE } from '../src/meta/governance/completedModuleFreezeContractV1.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const source = {
  qms: read('src/meta/pages/QmsPage.vue'), receipt: read('src/meta/pages/PurchaseReceivePage.vue'),
  payable: read('src/meta/pages/PayableCheckPage.vue'), settlement: read('src/meta/pages/SupplierSettlementPage.vue'),
  inventory: read('src/meta/pages/FormalExecutionPage.vue'), api: read('src/api/formalExecution.js'),
  menu: read('src/meta/enterprise-os/enterpriseOSModel.js'), router: read('src/router/index.js'),
  trace: read('src/meta/schema/scm/scmStandardPageContract.js'),
  purchaseRequest: read('src/meta/pages/ScmPurchaseRequestPage.vue'),
  processNavigation: read('src/meta/process/processNodeNavigation.js'),
  processRegistry: read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js'),
  backend: read('../backend/procurement/inventory_facts_api.py'),
  scmBackend: read('../backend/procurement/scm_page_facts.py'),
  migration: read('../backend/procurement/migrations/0028_completed_module_read_permissions.py'),
}

assert(COMPLETED_MODULE_LIFECYCLE === 'ACCEPTANCE_PENDING', 'Contract must remain acceptance pending before manual PASS')
assert(COMPLETED_MODULE_CONTRACTS.length === 12, 'Completed module contract must cover 12 candidates')
const gate = process.argv.find((arg) => arg.startsWith('--gate='))?.split('=')[1] || 'all'
const checks = {
  storage() {
    assert(source.qms.includes('formalExecutionApi.qualityFacts()'), 'QMS formal API binding missing')
    assert(!source.qms.includes('inspections.value = listIncomingInspections()'), 'QMS fell back to localStorage authority')
    assert(source.receipt.includes('formalExecutionApi.purchaseReceiptFacts()'), 'Receipt formal API binding missing')
    assert(source.receipt.includes("draftAuthority: 'DRAFT_ALLOWED'"), 'Browser drafts are not explicitly classified')
    assert(source.payable.includes('formalExecutionApi.payableCheckFacts()'), 'Payable Check formal API binding missing')
    assert(!source.payable.includes('payableChecks.value = listPayableChecks()'), 'Payable Check fell back to localStorage authority')
    assert(source.settlement.includes('formalExecutionApi.payableCheckFacts()'), 'Supplier Settlement formal API binding missing')
    assert(!source.settlement.includes('supplierSettlementStore.js'), 'Supplier Settlement fell back to localStorage authority')
    assert(!source.settlement.includes('localStorage.'), 'Supplier Settlement reads browser business storage')
  },
  data() {
    for (const token of ['formal-inventory-facts', 'formal-quality-facts', 'formal-purchase-receipt-facts', 'formal-payable-check-facts']) assert(source.api.includes(token), `API binding missing: ${token}`)
    for (const contract of COMPLETED_MODULE_CONTRACTS) assert(contract.primaryBusinessIdentity && contract.api && contract.pageComponent, `Incomplete contract: ${contract.businessObject}`)
    const purchaseRequest = COMPLETED_MODULE_CONTRACTS.find(contract => contract.businessObject === 'PurchaseRequest')
    assert(purchaseRequest?.api === '/api/procurement/scm-page-facts/purchase-request/', 'Purchase Request formal facts API missing')
    assert(purchaseRequest?.pageComponent === 'ScmPurchaseRequestPage.vue', 'Purchase Request formal page missing')
    assert(source.purchaseRequest.includes('PceEnterpriseListTable') && source.purchaseRequest.includes("pageCode:'purchase-request'"), 'Purchase Request visible formal table/API runtime binding missing')
    assert(source.scmBackend.includes('facts["itemCount"] = PurchaseRequestItem.objects.count()'), 'Purchase Request item count authority missing')
  },
  menu() {
    const required = [['采购申请','/scm/purchase-request'],['来料检验','/qms/incoming-inspections'],['采购收货预备','/wms/purchase-receives'],['采购应付预备','/finance/payable-prepares'],['供应商结算','/scm/supplier-settlements'],['采购对账','/scm/purchase-reconciliations'],['库存余额','/wms/inventory-balances'],['采购应付核对','/finance/payable-checks']]
    for (const [name, route] of required) {
      assert(source.menu.includes(`label: '${name}'`) && source.menu.includes(`path: '${route}'`), `Menu missing: ${name}`)
      assert(source.router.includes(route.slice(1)), `Route missing: ${route}`)
    }
    assert(source.menu.includes("requiredPermission: 'navigation.supplier_procurement.read'"), 'Menu permission projection missing')
    assert(source.router.includes("path: 'scm/purchase-requests'") && source.router.includes("redirect: '/scm/purchase-request'"), 'Legacy Purchase Request entry does not converge')
    assert(source.processRegistry.includes("['purchase-request', '采购申请', 'purchase-request', '/scm/purchase-request'"), 'Process-center Purchase Request entry missing')
    assert(source.processNavigation.includes("locationLike?.origin") && !source.processNavigation.includes('5183'), 'New-tab runtime origin resolver is not governed')
  },
  permission() {
    assert(source.backend.includes('_authorize(request, INVENTORY_READ_PERMISSION)'), 'Inventory read permission mapping missing')
    assert(!source.backend.includes('_authorize(request, "warehouse.purchase.putaway")'), 'Inventory read remains coupled to putaway')
    for (const code of ['warehouse.inventory.read','warehouse.inventory_transaction.read','procurement.receipt.read','quality.purchase_inspection.read','navigation.supplier_procurement.read','finance.payable_check.read']) assert(source.migration.includes(code), `Permission registration missing: ${code}`)
    assert(source.backend.includes('permission_classes = [permissions.IsAuthenticated]'), 'Authenticated boundary missing')
  },
  trace() {
    assert(source.trace.includes("businessObject: 'InventoryBalance'"), 'Inventory authority is not InventoryBalance')
    assert(source.trace.includes("sourceObjectType: 'WarehouseInbound', targetObjectType: null"), 'Stale reconciliation trace remains')
    assert(source.inventory.includes('暂无正式业务追踪关系'), 'Formal empty trace state missing')
    assert(source.trace.includes("traceAuthority: 'SCM Standard Page Facts API'"), 'Purchase Request trace authority missing')
    assert(!source.trace.includes("sourceObjectType: 'PDEManufacturingInput', targetObjectType: 'PurchaseInquiry'"), 'Static Purchase Request trace remains')
  },
}
const selected = gate === 'all' ? Object.entries(checks) : [[gate, checks[gate]]]
assert(selected.every(([, fn]) => typeof fn === 'function'), `Unknown gate: ${gate}`)
for (const [name, fn] of selected) { fn(); console.log(`COMPLETED MODULE ${name.toUpperCase()} GATE = PASS`) }
