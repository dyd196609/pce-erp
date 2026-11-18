export const COMPLETED_MODULE_FREEZE_CONTRACT_VERSION = 'SUPPLIER-PROCUREMENT-COMPLETED-MODULE-V1'
export const COMPLETED_MODULE_LIFECYCLE = 'ACCEPTANCE_PENDING'

const moduleContract = (businessObject, route, canonicalName, api, authority, identity, readPermission, executePermission, component, menuPath, workflow, entryContract = null) => Object.freeze({
  businessObject, route, canonicalName, api, formalDataAuthority: authority,
  primaryBusinessIdentity: identity, readPermission, executePermission,
  pageComponent: component, menuPath, workflow, entryContract,
  uiDataContract: 'DB_IDENTITY == API_IDENTITY == UI_IDENTITY',
})

export const COMPLETED_MODULE_CONTRACTS = Object.freeze([
  moduleContract('Supplier', '/master-data/suppliers', '供应商', '/api/procurement/suppliers/', 'procurement.Supplier', 'supplierCode', 'supplier_view', 'supplier_create', 'EnterpriseMasterDataPage.vue', '企业基础资料 → 供应商 → 供应商', 'PRESERVE_AND_EXTEND'),
  moduleContract('Material', '/master-data/materials', '采购物料', '/api/masterdata/materials/', 'masterdata.Material', 'materialCode', 'material_view', 'material_create', 'EnterpriseMasterDataPage.vue', '企业基础资料 → 物料 → 采购物料', 'PRESERVE_AND_EXTEND'),
  moduleContract('PurchaseRequest', '/scm/purchase-request', '采购申请', '/api/procurement/scm-page-facts/purchase-request/', 'procurement.PurchaseRequest', 'requestNo', 'procurement.purchase_request.read', 'procurement.purchase_request.create', 'ScmPurchaseRequestPage.vue', '采购与质量 → 采购管理 → 采购申请', 'REQUEST_TO_ORDER', Object.freeze({ processCenterEntry: '/scm/purchase-request', newTabResolver: 'buildProcessNodeTabUrl', runtimeOriginResolver: 'window.location.origin' })),
  moduleContract('PurchaseOrder', '/scm/purchase-order', '采购订单', '/api/procurement/purchase_orders/', 'procurement.PurchaseOrder', 'poNo', 'purchase_order_view', 'procurement.purchase_order.release', 'ScmPage.vue', '业务流程中心 → 采购 → 采购订单', 'REQUEST_TO_ORDER'),
  moduleContract('PurchaseReceipt', '/wms/purchase-receives', '采购收货预备', '/api/procurement/formal-purchase-receipt-facts/', 'procurement.PurchaseReceipt', 'receiptNo', 'procurement.receipt.read', 'procurement.receipt.receive', 'PurchaseReceivePage.vue', '采购与质量 → 收货与检验 → 采购收货预备', 'ORDER_TO_RECEIPT'),
  moduleContract('PurchaseInspection', '/qms/incoming-inspections', '来料检验', '/api/procurement/formal-quality-facts/', 'procurement.PurchaseInspection', 'inspectionNo', 'quality.purchase_inspection.read', 'quality.purchase.inspect', 'QmsPage.vue', '采购与质量 → 收货与检验 → 来料检验', 'RECEIPT_TO_INSPECTION'),
  moduleContract('WarehouseInbound', '/wms/warehouse-tasks', '仓库入库', '/api/procurement/purchase-order-fulfillment/', 'procurement.WarehouseInbound', 'inboundNo', 'warehouse.inventory.read', 'warehouse.purchase.putaway', 'WmsPage.vue', '仓储库存 → 入库作业 → 仓库入库', 'INSPECTION_TO_INBOUND'),
  moduleContract('InventoryBalance', '/wms/inventory-balances', '库存余额', '/api/procurement/formal-inventory-facts/', 'procurement.InventoryBalance', 'warehouse+material+location+lot', 'warehouse.inventory.read', 'warehouse.purchase.putaway', 'FormalExecutionPage.vue', '仓储库存 → 库存查询 → 库存余额', 'READ_ONLY_FACT'),
  moduleContract('InventoryTransaction', '/wms/inventory-transactions', '库存流水', '/api/procurement/formal-inventory-facts/', 'procurement.InventoryTransaction', 'transactionNo', 'warehouse.inventory_transaction.read', 'warehouse.purchase.putaway', 'FormalExecutionPage.vue', '仓储库存 → 库存查询 → 库存流水', 'READ_ONLY_FACT'),
  moduleContract('PayableCheck', '/finance/payable-checks', '采购应付核对', '/api/procurement/formal-payable-check-facts/', 'reconciliation.PayableCheckAuthorityRecord', 'payableCheckNo', 'finance.payable_check.read', 'finance.payable_check.execute', 'PayableCheckPage.vue', '采购财务 → 应付与对账 → 采购应付核对', 'INBOUND_TO_PAYABLE_CHECK'),
  moduleContract('SupplierSettlement', '/scm/supplier-settlements', '供应商结算', '/api/procurement/formal-payable-check-facts/', 'reconciliation.SupplierSettlementAuthorityRecord', 'settlementNo', 'finance.payable_check.read', 'supplier.settlement.generate', 'SupplierSettlementPage.vue', '采购财务 → 应付与对账 → 供应商结算', 'PAYABLE_TO_SETTLEMENT'),
  moduleContract('PurchaseReconciliation', '/scm/purchase-reconciliations', '采购对账', '/api/scm/purchase-reconciliations/', 'reconciliation.PurchaseReconciliation', 'reconciliationNo', 'purchase.reconciliation.read', 'purchase.reconciliation.complete', 'PurchaseReconciliationPage.vue', '采购财务 → 应付与对账 → 采购对账', 'SETTLEMENT_TO_RECONCILIATION'),
])

export const ALLOWED_EXTENSION_POINTS = Object.freeze([
  'ADD_SUPPLIER', 'ADD_MATERIAL', 'ADD_PROCUREMENT_BUSINESS_FACT',
  'ADD_MASTER_DATA_FIELD', 'EXTEND_BUSINESS_CONFIGURATION',
])
