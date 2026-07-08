import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getDepartmentOptions,
  getEmployeeOptions,
  getEnabledMaterials,
  getEnabledSuppliers,
  getEnabledWarehouses,
  getDefaultPrice,
  getLocationOptions,
  getMaterialOptions,
  getPrimarySupplierByMaterial,
  getSupplierOptions,
  getWarehouseOptions,
} from '../manufacturing/manufacturingReferenceService.js'
import {
  canAddLine,
  canApprove,
  canDeleteLine,
  canEditHeader,
  canEditLines,
  canSubmit,
  getReadonlyReason,
} from './scmDocumentRules.js'
import { generateScmMockState } from './scmMockDataGenerator.js'
import { getNextApprovalStatus } from '../workflow/approvalFlowConfigStore.js'

const STORAGE_KEY = 'scm-state-v1'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function createNo(prefix) {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `${prefix}${stamp}${Math.floor(Math.random() * 90 + 10)}`
}

function toNumber(value) {
  const next = Number(value)
  return Number.isFinite(next) ? next : 0
}

function firstId(collection) {
  return collection[0]?.id || ''
}

function byId(collection, id) {
  const direct = (collection || []).find((item) => String(item.id) === String(id))
  if (direct) return direct
  const numericIndex = Number(id)
  return Number.isInteger(numericIndex) ? collection[numericIndex] : null
}

function normalizeLines(items, parentKey, parentId) {
  return (items || [])
    .filter((item) => String(item[parentKey]) === String(parentId))
    .map((item, index) => ({ ...item, lineNo: index + 1 }))
}

function firstDateByPriority(source = {}, keys = []) {
  return keys.map((key) => source?.[key]).find(Boolean) || ''
}

function lineDemandDate(line = {}) {
  return firstDateByPriority(line, [
    'requiredDate',
    'demandDate',
    'needDate',
    'expectedDeliveryDate',
    'planDeliveryDate',
    'plannedArrivalDate',
    'lineExpectedDeliveryDate',
    'deliveryDate',
  ])
}

function headerDemandDate(header = {}) {
  return firstDateByPriority(header, ['requiredDate', 'demandDate', 'needDate', 'expectedDeliveryDate'])
}

function sourcePlanDate(line = {}, header = {}) {
  return lineDemandDate(line) || headerDemandDate(header)
}

function earliestDate(values = []) {
  return values.filter(Boolean).sort()[0] || ''
}

function demandDatePatch(planDate = '') {
  return {
    requiredDate: planDate || '',
    demandDate: planDate || '',
    expectedDeliveryDate: planDate || '',
    planDeliveryDate: planDate || '',
  }
}

function optionName(collection, id) {
  return byId(collection, id)?.name || ''
}

function displayName(type, id) {
  const collections = {
    employee: getEmployeeOptions(),
    department: getDepartmentOptions(),
    material: getMaterialOptions(),
    supplier: getSupplierOptions(),
    warehouse: getWarehouseOptions(),
    location: getLocationOptions(),
  }
  return optionName(collections[type] || [], id) || id || ''
}

function defaultPurchaseDepartment() {
  const departments = getDepartmentOptions()
  return departments.find((item) => `${item.name || ''}${item.raw?.name || ''}`.includes('采购'))?.id || firstId(departments)
}

function materialSnapshot(materialId) {
  const item = byId(getEnabledMaterials(), materialId) || {}
  const raw = item.raw || {}
  return {
    materialId: item.id || materialId || '',
    materialCode: item.code || raw.code || item.id || '',
    materialName: item.name || raw.name || '',
    specification: raw.specification || raw.model || raw.spec || '',
    unit: raw.unit || raw.unitName || raw.baseUnit || raw.purchaseUnit || '',
    materialType: raw.materialType || raw.type || '',
    safetyStock: toNumber(raw.safetyStock || 0),
    maxStock: toNumber(raw.maxStock || 0),
    defaultWarehouseId: raw.defaultWarehouseId || raw.defaultWarehouse || '',
    defaultLocationId: raw.defaultLocationId || raw.defaultLocation || '',
  }
}

function supplierPriceSnapshot(materialId, supplierId) {
  const price = getDefaultPrice(materialId, supplierId)
  if (!price) {
    return {
      priceFound: false,
      priceMessage: materialId && supplierId ? '未找到该供应商的物料价格，请先维护供应商物料价格。' : '',
    }
  }
  return {
    priceFound: true,
    quotedPrice: toNumber(price.price),
    approvedPrice: toNumber(price.price),
    price: toNumber(price.price),
    taxRate: toNumber(price.taxRate || 13),
    deliveryDays: toNumber(price.deliveryDays || 7),
    paymentTerms: price.paymentTerms || '月结30天',
    currency: price.currency || 'CNY',
    priceSourceId: price.id,
    priceMessage: '',
  }
}

function recommendedSupplierId(materialId) {
  return getPrimarySupplierByMaterial(materialId)?.supplierId || firstId(getEnabledSuppliers())
}

function writeLog(action, targetType, targetId, detail = '') {
  addOperationLog({
    module: 'SCM采购前端',
    action,
    targetType,
    targetId,
    detail,
  })
}

function writeFlowLog(action, payload = {}) {
  writeLog(action, payload.sourceModule || payload.targetModule || 'scm', payload.sourceOrderId || payload.targetOrderId || '', [
    `来源模块：${payload.sourceModule || '-'}`,
    `来源单据号：${payload.sourceOrderNo || '-'}`,
    `目标模块：${payload.targetModule || '-'}`,
    `目标单据号：${payload.targetOrderNo || '-'}`,
    `操作结果：${payload.result || '成功'}`,
  ].join('；'))
}

function defaultState() {
  return normalizeState(generateScmMockState()).state
}

function legacyDefaultState() {
  const materials = getEnabledMaterials()
  const suppliers = getEnabledSuppliers()
  const employees = getEmployeeOptions()
  const departments = getDepartmentOptions()
  const warehouses = getEnabledWarehouses()
  const locations = getLocationOptions(firstId(warehouses))
  const matA = materials[0]?.id || ''
  const matB = materials[1]?.id || matA
  const supplierA = suppliers[0]?.id || ''
  const supplierB = suppliers[1]?.id || supplierA
  const buyer = employees[0]?.id || ''
  const requester = employees[1]?.id || buyer
  const department = departments[0]?.id || ''
  const warehouse = warehouses[0]?.id || ''
  const location = locations[0]?.id || ''

  const request1 = 'pr-demo-1'
  const request2 = 'pr-demo-2'
  const inquiry1 = 'inq-demo-1'
  const inquiry2 = 'inq-demo-2'
  const approval1 = 'pa-demo-1'
  const approval2 = 'pa-demo-2'
  const po1 = 'po-demo-1'
  const po2 = 'po-demo-2'

  const purchaseRequestItems = [
    buildRequestItem({ id: 'pri-demo-1', requestId: request1, lineNo: 1, materialId: matA, quantity: 20, suggestedSupplierId: supplierA, purpose: '生产备料' }),
    buildRequestItem({ id: 'pri-demo-2', requestId: request1, lineNo: 2, materialId: matB, quantity: 12, suggestedSupplierId: supplierB, purpose: '设备维护' }),
    buildRequestItem({ id: 'pri-demo-3', requestId: request2, lineNo: 1, materialId: matA, quantity: 8, suggestedSupplierId: supplierA, purpose: '样品试制' }),
    buildRequestItem({ id: 'pri-demo-4', requestId: request2, lineNo: 2, materialId: matB, quantity: 16, suggestedSupplierId: supplierB, purpose: '安全库存' }),
  ]

  const purchaseInquiryItems = [
    buildInquiryItem({ id: 'inqi-demo-1', inquiryId: inquiry1, requestItemId: 'pri-demo-1', supplierId: supplierA, materialId: matA, quantity: 20, quotedPrice: 68, status: 'quoted' }),
    buildInquiryItem({ id: 'inqi-demo-2', inquiryId: inquiry1, requestItemId: 'pri-demo-2', supplierId: supplierB, materialId: matB, quantity: 12, quotedPrice: 126, status: 'quoted' }),
    buildInquiryItem({ id: 'inqi-demo-3', inquiryId: inquiry2, requestItemId: 'pri-demo-3', supplierId: supplierA, materialId: matA, quantity: 8, quotedPrice: 70, status: 'quoted' }),
    buildInquiryItem({ id: 'inqi-demo-4', inquiryId: inquiry2, requestItemId: 'pri-demo-4', supplierId: supplierB, materialId: matB, quantity: 16, quotedPrice: 122, status: 'quoted' }),
  ]

  const priceApprovalItems = [
    buildPriceApprovalItem({ id: 'pai-demo-1', approvalId: approval1, inquiryItemId: 'inqi-demo-1', supplierId: supplierA, materialId: matA, quantity: 20, quotedPrice: 68, approvedPrice: 66 }),
    buildPriceApprovalItem({ id: 'pai-demo-2', approvalId: approval1, inquiryItemId: 'inqi-demo-2', supplierId: supplierB, materialId: matB, quantity: 12, quotedPrice: 126, approvedPrice: 123 }),
    buildPriceApprovalItem({ id: 'pai-demo-3', approvalId: approval2, inquiryItemId: 'inqi-demo-3', supplierId: supplierA, materialId: matA, quantity: 8, quotedPrice: 70, approvedPrice: 69 }),
    buildPriceApprovalItem({ id: 'pai-demo-4', approvalId: approval2, inquiryItemId: 'inqi-demo-4', supplierId: supplierB, materialId: matB, quantity: 16, quotedPrice: 122, approvedPrice: 120 }),
  ]

  const purchaseOrderItems = [
    buildPurchaseOrderItem({ id: 'poi-demo-1', poId: po1, sourceItemId: 'pai-demo-1', materialId: matA, quantity: 20, price: 66, warehouseId: warehouse, locationId: location }),
    buildPurchaseOrderItem({ id: 'poi-demo-2', poId: po1, sourceItemId: 'pai-demo-3', materialId: matA, quantity: 8, price: 69, warehouseId: warehouse, locationId: location }),
    buildPurchaseOrderItem({ id: 'poi-demo-3', poId: po2, sourceItemId: 'pai-demo-2', materialId: matB, quantity: 12, price: 123, warehouseId: warehouse, locationId: location }),
    buildPurchaseOrderItem({ id: 'poi-demo-4', poId: po2, sourceItemId: 'pai-demo-4', materialId: matB, quantity: 16, price: 120, warehouseId: warehouse, locationId: location }),
  ]

  return normalizeState({
    purchaseRequests: [
      requestHeader({ id: request1, requestNo: 'PR-202607-001', requesterId: requester, departmentId: department, status: 'approved', purpose: '月度生产备料' }),
      requestHeader({ id: request2, requestNo: 'PR-202607-002', requesterId: requester, departmentId: department, status: 'submitted', purpose: '试制与库存补充' }),
    ],
    purchaseRequestItems,
    purchaseInquiries: [
      inquiryHeader({ id: inquiry1, inquiryNo: 'INQ-202607-001', requestId: request1, buyerId: buyer, status: 'quoted' }),
      inquiryHeader({ id: inquiry2, inquiryNo: 'INQ-202607-002', requestId: request2, buyerId: buyer, status: 'sent' }),
    ],
    purchaseInquiryItems,
    priceApprovals: [
      priceApprovalHeader({ id: approval1, approvalNo: 'PA-202607-001', inquiryId: inquiry1, buyerId: buyer, status: 'approved' }),
      priceApprovalHeader({ id: approval2, approvalNo: 'PA-202607-002', inquiryId: inquiry2, buyerId: buyer, status: 'submitted' }),
    ],
    priceApprovalItems,
    purchaseOrders: [
      purchaseOrderHeader({ id: po1, poNo: 'PO-202607-001', supplierId: supplierA, buyerId: buyer, status: 'approved', sourceType: 'priceApproval', sourceId: approval1 }),
      purchaseOrderHeader({ id: po2, poNo: 'PO-202607-002', supplierId: supplierB, buyerId: buyer, status: 'draft', sourceType: 'priceApproval', sourceId: approval1 }),
    ],
    purchaseOrderItems,
    pendingActions: [
      pendingAction({
        id: 'pa-demo-action-1',
        actionType: 'createInquiry',
        sourceType: 'purchaseRequest',
        sourceId: request1,
        title: '请购单 PR-202607-001 已审批，待转询价',
      }),
    ],
  }).state
}

function requestHeader(patch = {}) {
  const stamp = nowText()
  const requestDepartment = patch.requestDepartment || patch.departmentId || firstId(getDepartmentOptions())
  const demandDepartment = patch.demandDepartment || patch.departmentId || requestDepartment
  const purchaseDepartment = patch.purchaseDepartment || defaultPurchaseDepartment()
  return {
    id: patch.id || createId('pr'),
    requestNo: patch.requestNo || createNo('PR'),
    requestDate: patch.requestDate || today(),
    requesterId: patch.requesterId || firstId(getEmployeeOptions()),
    departmentId: patch.departmentId || requestDepartment,
    requestDepartment,
    demandDepartment,
    purchaseDepartment,
    requiredDate: patch.requiredDate || '',
    purpose: patch.purpose || '',
    status: patch.status || 'draft',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    targetModule: patch.targetModule || '',
    targetOrderId: patch.targetOrderId || '',
    targetOrderNo: patch.targetOrderNo || '',
    rootRequestId: patch.rootRequestId || patch.id || '',
    rootRequestNo: patch.rootRequestNo || patch.requestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || displayName('department', requestDepartment),
    rootDemandDepartment: patch.rootDemandDepartment || displayName('department', demandDepartment),
    rootPurchaseDepartment: patch.rootPurchaseDepartment || displayName('department', purchaseDepartment),
    rootRequester: patch.rootRequester || displayName('employee', patch.requesterId),
    rootRequestDate: patch.rootRequestDate || patch.requestDate || today(),
    remark: patch.remark || '',
    createdAt: patch.createdAt || stamp,
    updatedAt: patch.updatedAt || stamp,
  }
}

function buildRequestItem(patch = {}) {
  const snapshot = materialSnapshot(patch.materialId)
  const supplierId = patch.suggestedSupplierId || patch.supplierId || recommendedSupplierId(patch.materialId)
  const price = toNumber(patch.price || patch.unitPrice || supplierPriceSnapshot(patch.materialId, supplierId).price || 0)
  const quantity = toNumber(patch.quantity || patch.qty || patch.planQty || 1)
  return {
    id: patch.id || createId('pri'),
    requestId: patch.requestId || '',
    lineNo: patch.lineNo || 1,
    ...snapshot,
    materialId: patch.materialId || snapshot.materialId || '',
    materialCode: patch.materialCode || snapshot.materialCode || '',
    materialName: patch.materialName || snapshot.materialName || '',
    specification: patch.specification || snapshot.specification || '',
    unit: patch.unit || snapshot.unit || '',
    quantity,
    price,
    amount: toNumber(patch.amount || patch.totalAmount || quantity * price),
    expectedDeliveryDate: patch.expectedDeliveryDate || patch.deliveryDate || patch.requiredDate || '',
    requiredDate: patch.requiredDate || '',
    suggestedSupplierId: supplierId,
    supplierId,
    supplierName: patch.supplierName || getScmDisplayName('supplier', supplierId),
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    sourceLineId: patch.sourceLineId || '',
    rootRequestId: patch.rootRequestId || patch.requestId || '',
    rootRequestNo: patch.rootRequestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || '',
    rootRequester: patch.rootRequester || '',
    rootRequestDate: patch.rootRequestDate || '',
    rootRequestLineId: patch.rootRequestLineId || patch.sourceLineId || patch.id || '',
    purpose: patch.purpose || '',
    remark: patch.remark || '',
  }
}

function inquiryHeader(patch = {}) {
  const stamp = nowText()
  return {
    id: patch.id || createId('inq'),
    inquiryNo: patch.inquiryNo || createNo('INQ'),
    inquiryDate: patch.inquiryDate || today(),
    requestId: patch.requestId || '',
    buyerId: patch.buyerId || firstId(getEmployeeOptions()),
    status: patch.status || 'draft',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    requestDepartment: patch.requestDepartment || '',
    demandDepartment: patch.demandDepartment || '',
    purchaseDepartment: patch.purchaseDepartment || '',
    requester: patch.requester || '',
    candidateSuppliers: patch.candidateSuppliers || [],
    quotationDeadline: patch.quotationDeadline || '',
    inquiryStatus: patch.inquiryStatus || patch.status || 'draft',
    targetModule: patch.targetModule || '',
    targetOrderId: patch.targetOrderId || '',
    targetOrderNo: patch.targetOrderNo || '',
    rootRequestId: patch.rootRequestId || patch.requestId || '',
    rootRequestNo: patch.rootRequestNo || patch.sourceOrderNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || patch.requestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || patch.demandDepartment || '',
    rootPurchaseDepartment: patch.rootPurchaseDepartment || patch.purchaseDepartment || '',
    rootRequester: patch.rootRequester || patch.requester || '',
    rootRequestDate: patch.rootRequestDate || '',
    remark: patch.remark || '',
    createdAt: patch.createdAt || stamp,
    updatedAt: patch.updatedAt || stamp,
  }
}

function buildInquiryItem(patch = {}) {
  const snapshot = materialSnapshot(patch.materialId)
  const price = supplierPriceSnapshot(patch.materialId, patch.supplierId)
  const planDate = lineDemandDate(patch)
  return {
    id: patch.id || createId('inqi'),
    inquiryId: patch.inquiryId || '',
    lineNo: patch.lineNo || 1,
    requestItemId: patch.requestItemId || '',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    sourceLineId: patch.sourceLineId || '',
    rootRequestId: patch.rootRequestId || '',
    rootRequestNo: patch.rootRequestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || '',
    rootPurchaseDepartment: patch.rootPurchaseDepartment || '',
    rootRequester: patch.rootRequester || '',
    rootRequestDate: patch.rootRequestDate || '',
    rootRequestLineId: patch.rootRequestLineId || patch.sourceLineId || '',
    supplierId: patch.supplierId || '',
    supplierName: patch.supplierName || getScmDisplayName('supplier', patch.supplierId),
    ...snapshot,
    quantity: toNumber(patch.quantity || 1),
    price: toNumber(patch.price || patch.quotedPrice || price.quotedPrice || 0),
    amount: toNumber(patch.amount || toNumber(patch.quantity || 1) * toNumber(patch.quotedPrice || price.quotedPrice || 0)),
    requiredDate: planDate,
    demandDate: patch.demandDate || patch.requiredDate || planDate,
    expectedDeliveryDate: planDate,
    planDeliveryDate: patch.planDeliveryDate || patch.plannedArrivalDate || planDate,
    quotedPrice: toNumber(patch.quotedPrice || price.quotedPrice || 0),
    quotedAmount: toNumber(patch.quotedAmount || patch.amount || toNumber(patch.quantity || 1) * toNumber(patch.quotedPrice || price.quotedPrice || 0)),
    quotedDeliveryDate: patch.quotedDeliveryDate || patch.expectedDeliveryDate || '',
    deliveryDays: toNumber(patch.deliveryDays || price.deliveryDays || 0),
    paymentTerms: patch.paymentTerms || price.paymentTerms || '',
    currency: patch.currency || price.currency || 'CNY',
    priceSourceId: patch.priceSourceId || price.priceSourceId || '',
    priceMessage: patch.priceMessage || price.priceMessage || '',
    quoteRemark: patch.quoteRemark || '',
    remark: patch.remark || '',
    status: patch.status || 'draft',
  }
}

function priceApprovalHeader(patch = {}) {
  const stamp = nowText()
  return {
    id: patch.id || createId('pa'),
    approvalNo: patch.approvalNo || createNo('PA'),
    inquiryId: patch.inquiryId || '',
    buyerId: patch.buyerId || firstId(getEmployeeOptions()),
    status: patch.status || 'draft',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    supplierId: patch.supplierId || '',
    supplierName: patch.supplierName || '',
    buyerName: patch.buyerName || '',
    requestDepartment: patch.requestDepartment || patch.rootRequestDepartment || '',
    demandDepartment: patch.demandDepartment || patch.rootDemandDepartment || '',
    purchaseDepartment: patch.purchaseDepartment || patch.rootPurchaseDepartment || '',
    requester: patch.requester || patch.rootRequester || '',
    priceApprovalNo: patch.priceApprovalNo || patch.approvalNo || '',
    priceStatus: patch.priceStatus || patch.status || 'draft',
    priceReason: patch.priceReason || '',
    priceApprover: patch.priceApprover || '',
    targetModule: patch.targetModule || '',
    targetOrderId: patch.targetOrderId || '',
    targetOrderNo: patch.targetOrderNo || '',
    rootRequestId: patch.rootRequestId || '',
    rootRequestNo: patch.rootRequestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || '',
    rootPurchaseDepartment: patch.rootPurchaseDepartment || '',
    rootRequester: patch.rootRequester || '',
    rootRequestDate: patch.rootRequestDate || '',
    remark: patch.remark || '',
    createdAt: patch.createdAt || stamp,
    updatedAt: patch.updatedAt || stamp,
  }
}

function buildPriceApprovalItem(patch = {}) {
  const snapshot = materialSnapshot(patch.materialId)
  const price = supplierPriceSnapshot(patch.materialId, patch.supplierId)
  const planDate = lineDemandDate(patch)
  return {
    id: patch.id || createId('pai'),
    approvalId: patch.approvalId || '',
    lineNo: patch.lineNo || 1,
    inquiryItemId: patch.inquiryItemId || '',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    sourceLineId: patch.sourceLineId || '',
    rootRequestId: patch.rootRequestId || '',
    rootRequestNo: patch.rootRequestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || '',
    rootRequester: patch.rootRequester || '',
    rootRequestDate: patch.rootRequestDate || '',
    rootRequestLineId: patch.rootRequestLineId || patch.sourceLineId || '',
    supplierId: patch.supplierId || '',
    supplierName: patch.supplierName || getScmDisplayName('supplier', patch.supplierId),
    ...snapshot,
    quantity: toNumber(patch.quantity || 1),
    quotedPrice: toNumber(patch.quotedPrice || price.quotedPrice || 0),
    approvedPrice: toNumber(patch.approvedPrice || patch.quotedPrice || price.approvedPrice || 0),
    price: toNumber(patch.price || patch.approvedPrice || patch.quotedPrice || price.approvedPrice || 0),
    amount: toNumber(patch.amount || toNumber(patch.quantity || 1) * toNumber(patch.approvedPrice || patch.quotedPrice || price.approvedPrice || 0)),
    approvedAmount: toNumber(patch.approvedAmount || patch.amount || toNumber(patch.quantity || 1) * toNumber(patch.approvedPrice || patch.quotedPrice || price.approvedPrice || 0)),
    requiredDate: planDate,
    demandDate: patch.demandDate || patch.requiredDate || planDate,
    expectedDeliveryDate: planDate,
    planDeliveryDate: patch.planDeliveryDate || patch.plannedArrivalDate || planDate,
    taxRate: toNumber(patch.taxRate || price.taxRate || 13),
    deliveryDays: toNumber(patch.deliveryDays || price.deliveryDays || 7),
    paymentTerms: patch.paymentTerms || price.paymentTerms || '月结30天',
    priceSourceId: patch.priceSourceId || price.priceSourceId || '',
    priceMessage: patch.priceMessage || price.priceMessage || '',
    remark: patch.remark || '',
  }
}

function purchaseOrderHeader(patch = {}) {
  const stamp = nowText()
  const planDate = patch.earliestArrivalDate || patch.planDeliveryDate || patch.plannedArrivalDate || patch.expectedDeliveryDate || ''
  return {
    id: patch.id || createId('po'),
    poNo: patch.poNo || createNo('PO'),
    orderDate: patch.orderDate || today(),
    supplierId: patch.supplierId || firstId(getEnabledSuppliers()),
    buyerId: patch.buyerId || firstId(getEmployeeOptions()),
    plannedArrivalDate: planDate,
    earliestArrivalDate: planDate,
    totalAmount: toNumber(patch.totalAmount || 0),
    status: patch.status || 'draft',
    sourceType: patch.sourceType || 'manual',
    sourceId: patch.sourceId || '',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    supplierName: patch.supplierName || '',
    buyerName: patch.buyerName || '',
    requestDepartment: patch.requestDepartment || '',
    demandDepartment: patch.demandDepartment || '',
    purchaseDepartment: patch.purchaseDepartment || '',
    planDeliveryDate: planDate,
    orderStatus: patch.orderStatus || patch.status || 'draft',
    issueStatus: patch.issueStatus || (patch.status === 'issued' ? 'issued' : 'notIssued'),
    issuedAt: patch.issuedAt || '',
    issuedBy: patch.issuedBy || '',
    targetModule: patch.targetModule || '',
    targetOrderId: patch.targetOrderId || '',
    targetOrderNo: patch.targetOrderNo || '',
    rootRequestId: patch.rootRequestId || '',
    rootRequestNo: patch.rootRequestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || patch.requestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || patch.demandDepartment || '',
    rootPurchaseDepartment: patch.rootPurchaseDepartment || patch.purchaseDepartment || '',
    rootRequester: patch.rootRequester || '',
    rootRequestDate: patch.rootRequestDate || '',
    actualArrivalDate: patch.actualArrivalDate || '',
    planAmount: toNumber(patch.planAmount || patch.totalAmount || 0),
    actualAmount: toNumber(patch.actualAmount || 0),
    remark: patch.remark || '',
    createdAt: patch.createdAt || stamp,
    updatedAt: patch.updatedAt || stamp,
  }
}

function pendingAction(patch = {}) {
  return {
    id: patch.id || createId('pending'),
    module: 'scm',
    actionType: patch.actionType || '',
    sourceType: patch.sourceType || '',
    sourceId: patch.sourceId || '',
    title: patch.title || '',
    status: patch.status || 'pending',
    createdAt: patch.createdAt || nowText(),
    completedAt: patch.completedAt || '',
    remark: patch.remark || '',
  }
}

function buildPurchaseOrderItem(patch = {}) {
  const snapshot = materialSnapshot(patch.materialId)
  const priceSource = supplierPriceSnapshot(patch.materialId, patch.supplierId)
  const quantity = toNumber(patch.quantity || 1)
  const price = toNumber(patch.price || priceSource.price || 0)
  const planPrice = toNumber(patch.planPrice ?? patch.price ?? patch.unitPrice ?? price)
  const planAmount = toNumber(patch.planAmount ?? patch.amount ?? patch.totalAmount ?? quantity * planPrice)
  const actualPrice = toNumber(patch.actualPrice ?? patch.actualUnitPrice ?? 0)
  const actualAmount = toNumber(patch.actualAmount ?? patch.actualTotalAmount ?? 0)
  const warehouseId = patch.warehouseId || snapshot.defaultWarehouseId || firstId(getEnabledWarehouses())
  const locations = getLocationOptions(warehouseId)
  const locationId = patch.locationId
    || (snapshot.defaultLocationId && locations.some((item) => String(item.id) === String(snapshot.defaultLocationId)) ? snapshot.defaultLocationId : '')
    || firstId(locations)
  const planDate = lineDemandDate(patch)
  return {
    id: patch.id || createId('poi'),
    poId: patch.poId || '',
    lineNo: patch.lineNo || 1,
    sourceItemId: patch.sourceItemId || '',
    sourceModule: patch.sourceModule || '',
    sourceOrderId: patch.sourceOrderId || '',
    sourceOrderNo: patch.sourceOrderNo || '',
    sourceLineId: patch.sourceLineId || patch.sourceItemId || '',
    rootRequestId: patch.rootRequestId || '',
    rootRequestNo: patch.rootRequestNo || '',
    rootRequestDepartment: patch.rootRequestDepartment || '',
    rootDemandDepartment: patch.rootDemandDepartment || '',
    rootPurchaseDepartment: patch.rootPurchaseDepartment || '',
    rootRequester: patch.rootRequester || '',
    rootRequestDate: patch.rootRequestDate || '',
    rootRequestLineId: patch.rootRequestLineId || patch.sourceLineId || patch.sourceItemId || '',
    ...snapshot,
    quantity,
    price,
    amount: Number((quantity * price).toFixed(2)),
    planPrice,
    planAmount,
    actualPrice,
    actualAmount,
    requiredDate: planDate,
    demandDate: patch.demandDate || patch.requiredDate || planDate,
    expectedDeliveryDate: planDate,
    actualDeliveryDate: patch.actualDeliveryDate || '',
    supplierId: patch.supplierId || '',
    supplierName: patch.supplierName || getScmDisplayName('supplier', patch.supplierId),
    taxRate: toNumber(patch.taxRate || priceSource.taxRate || 13),
    deliveryDays: toNumber(patch.deliveryDays || priceSource.deliveryDays || 0),
    paymentTerms: patch.paymentTerms || priceSource.paymentTerms || '',
    currency: patch.currency || priceSource.currency || 'CNY',
    priceSourceId: patch.priceSourceId || priceSource.priceSourceId || '',
    priceMessage: patch.priceMessage || priceSource.priceMessage || '',
    warehouseId,
    locationId,
    planDeliveryDate: patch.planDeliveryDate || patch.plannedArrivalDate || planDate,
    plannedArrivalDate: patch.plannedArrivalDate || patch.planDeliveryDate || planDate,
    remark: patch.remark || '',
  }
}

function migrateOldItems(state) {
  let migrated = false
  if (!state.purchaseRequestItems?.length) {
    state.purchaseRequestItems = (state.purchaseRequests || [])
      .filter((item) => item.materialId || item.quantity)
      .map((item, index) => buildRequestItem({
        id: createId('pri-migrate'),
        requestId: item.id,
        lineNo: index + 1,
        materialId: item.materialId,
        quantity: item.quantity,
        requiredDate: item.requiredDate,
        suggestedSupplierId: item.suggestedSupplierId || item.supplierId,
        purpose: item.purpose,
        remark: item.remark,
      }))
    migrated = state.purchaseRequestItems.length > 0
  }
  if (!state.purchaseInquiryItems?.length) {
    state.purchaseInquiryItems = (state.purchaseInquiries || [])
      .filter((item) => item.materialId || item.quantity)
      .map((item, index) => buildInquiryItem({
        id: createId('inqi-migrate'),
        inquiryId: item.id,
        lineNo: index + 1,
        supplierId: item.supplierId,
        materialId: item.materialId,
        quantity: item.quantity,
        expectedDeliveryDate: item.expectedDeliveryDate,
        quotedPrice: item.quotedPrice,
        quotedDeliveryDate: item.quotedDeliveryDate,
        status: item.status === 'quoted' ? 'quoted' : 'draft',
      }))
    migrated = migrated || state.purchaseInquiryItems.length > 0
  }
  if (!state.priceApprovalItems?.length) {
    state.priceApprovalItems = (state.priceApprovals || [])
      .filter((item) => item.materialId || item.quantity)
      .map((item, index) => buildPriceApprovalItem({
        id: createId('pai-migrate'),
        approvalId: item.id,
        lineNo: index + 1,
        supplierId: item.supplierId,
        materialId: item.materialId,
        quantity: item.quantity,
        quotedPrice: item.quotedPrice,
        approvedPrice: item.approvedPrice,
        taxRate: item.taxRate,
        deliveryDays: item.deliveryDays,
        paymentTerms: item.paymentTerms,
        remark: item.remark,
      }))
    migrated = migrated || state.priceApprovalItems.length > 0
  }
  if (!state.purchaseOrderItems?.length) {
    state.purchaseOrderItems = (state.purchaseOrders || [])
      .filter((item) => item.materialId || item.quantity)
      .map((item, index) => buildPurchaseOrderItem({
        id: createId('poi-migrate'),
        poId: item.id,
        lineNo: index + 1,
        materialId: item.materialId,
        quantity: item.quantity,
        price: item.price,
        amount: item.amount,
        warehouseId: item.warehouseId,
        locationId: item.locationId,
        plannedArrivalDate: item.plannedArrivalDate,
        remark: item.remark,
      }))
    migrated = migrated || state.purchaseOrderItems.length > 0
  }
  return migrated
}

function fillMissing(target, fields = {}) {
  let changed = false
  Object.entries(fields).forEach(([key, value]) => {
    if ((target[key] === undefined || target[key] === null || target[key] === '') && value !== undefined && value !== null && value !== '') {
      target[key] = value
      changed = true
    }
  })
  return changed
}

function repairSourceFields(state) {
  let migrated = false
  state.purchaseRequests.forEach((request) => {
    migrated = fillMissing(request, {
      requestDepartment: request.requestDepartment || request.departmentId,
      demandDepartment: request.demandDepartment || request.departmentId,
      purchaseDepartment: request.purchaseDepartment || defaultPurchaseDepartment(),
      ...requestRootInfo(request),
    }) || migrated
    state.purchaseRequestItems
      .filter((line) => String(line.requestId) === String(request.id))
      .forEach((line) => {
        migrated = fillMissing(line, {
          ...requestRootInfo(request),
          rootRequestLineId: line.rootRequestLineId || line.id,
        }) || migrated
      })
  })
  state.purchaseInquiries.forEach((inquiry) => {
    const request = byId(state.purchaseRequests, inquiry.requestId || inquiry.sourceOrderId)
    const root = request ? requestRootInfo(request) : inheritedRootInfo(inquiry)
    migrated = fillMissing(inquiry, root) || migrated
    state.purchaseInquiryItems
      .filter((line) => String(line.inquiryId) === String(inquiry.id))
      .forEach((line) => {
        const sourceLine = byId(state.purchaseRequestItems, line.requestItemId || line.sourceLineId)
        migrated = fillMissing(line, {
          ...root,
          ...(sourceLine ? inheritedRootInfo(sourceLine, root) : {}),
          sourceModule: line.sourceModule || inquiry.sourceModule || 'purchaseRequest',
          sourceOrderId: line.sourceOrderId || inquiry.sourceOrderId,
          sourceOrderNo: line.sourceOrderNo || inquiry.sourceOrderNo,
          rootRequestLineId: line.rootRequestLineId || sourceLine?.rootRequestLineId || sourceLine?.id || line.sourceLineId,
        }) || migrated
      })
  })
  state.priceApprovals.forEach((approval) => {
    const inquiry = byId(state.purchaseInquiries, approval.inquiryId || approval.sourceOrderId)
    const root = inheritedRootInfo(approval, inquiry || {})
    migrated = fillMissing(approval, {
      ...root,
      requestDepartment: approval.requestDepartment || inquiry?.requestDepartment || root.rootRequestDepartment,
      demandDepartment: approval.demandDepartment || inquiry?.demandDepartment || root.rootDemandDepartment,
      purchaseDepartment: approval.purchaseDepartment || inquiry?.purchaseDepartment || root.rootPurchaseDepartment,
      requester: approval.requester || inquiry?.requester || root.rootRequester,
    }) || migrated
    state.priceApprovalItems
      .filter((line) => String(line.approvalId) === String(approval.id))
      .forEach((line) => {
        const sourceLine = byId(state.purchaseInquiryItems, line.inquiryItemId || line.sourceLineId)
        migrated = fillMissing(line, {
          ...root,
          ...(sourceLine ? inheritedRootInfo(sourceLine, root) : {}),
          sourceModule: line.sourceModule || approval.sourceModule || 'purchaseInquiry',
          sourceOrderId: line.sourceOrderId || approval.sourceOrderId,
          sourceOrderNo: line.sourceOrderNo || approval.sourceOrderNo,
          rootRequestLineId: line.rootRequestLineId || sourceLine?.rootRequestLineId || line.sourceLineId,
        }) || migrated
      })
  })
  state.purchaseOrders.forEach((order) => {
    const approval = byId(state.priceApprovals, order.sourceOrderId || order.sourceId)
    const root = inheritedRootInfo(order, approval || {})
    migrated = fillMissing(order, {
      ...root,
      requestDepartment: order.requestDepartment || approval?.requestDepartment || root.rootRequestDepartment,
      demandDepartment: order.demandDepartment || approval?.demandDepartment || root.rootDemandDepartment,
      purchaseDepartment: order.purchaseDepartment || approval?.purchaseDepartment || root.rootPurchaseDepartment,
    }) || migrated
    state.purchaseOrderItems
      .filter((line) => String(line.poId) === String(order.id))
      .forEach((line) => {
        const sourceLine = byId(state.priceApprovalItems, line.sourceItemId || line.sourceLineId)
        migrated = fillMissing(line, {
          ...root,
          ...(sourceLine ? inheritedRootInfo(sourceLine, root) : {}),
          sourceModule: line.sourceModule || order.sourceModule || 'priceApproval',
          sourceOrderId: line.sourceOrderId || order.sourceOrderId,
          sourceOrderNo: line.sourceOrderNo || order.sourceOrderNo,
          rootRequestLineId: line.rootRequestLineId || sourceLine?.rootRequestLineId || line.sourceLineId,
          planPrice: line.planPrice || line.price,
          planAmount: line.planAmount || line.amount,
          actualPrice: line.actualPrice || 0,
          actualAmount: line.actualAmount || 0,
        }) || migrated
      })
  })
  return migrated
}

function normalizeState(raw) {
  const state = {
    purchaseRequests: [],
    purchaseRequestItems: [],
    purchaseInquiries: [],
    purchaseInquiryItems: [],
    priceApprovals: [],
    priceApprovalItems: [],
    purchaseOrders: [],
    purchaseOrderItems: [],
    pendingActions: [],
    ...(raw || {}),
  }
  let migrated = migrateOldItems(state)
  state.purchaseRequests = state.purchaseRequests.map((item) => requestHeader(item))
  state.purchaseRequestItems = state.purchaseRequestItems.map((item) => buildRequestItem(item))
  state.purchaseInquiries = state.purchaseInquiries.map((item) => inquiryHeader(item))
  state.purchaseInquiryItems = state.purchaseInquiryItems.map((item) => buildInquiryItem(item))
  state.priceApprovals = state.priceApprovals.map((item) => priceApprovalHeader(item))
  state.priceApprovalItems = state.priceApprovalItems.map((item) => buildPriceApprovalItem(item))
  state.purchaseOrders = state.purchaseOrders.map((item) => purchaseOrderHeader(item))
  state.purchaseOrderItems = state.purchaseOrderItems.map((item) => buildPurchaseOrderItem(item))
  state.pendingActions = (state.pendingActions || []).map((item) => pendingAction(item))
  migrated = repairSourceFields(state) || migrated
  state.purchaseOrders.forEach((order) => {
    order.totalAmount = calculateOrderTotal(state, order.id)
    order.planAmount = order.totalAmount
  })
  return { state, migrated }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { state: defaultState(), migrated: false }
    return normalizeState(JSON.parse(raw))
  } catch (error) {
    console.warn('[SCM STORE] fallback to demo state', error)
    return { state: defaultState(), migrated: false }
  }
}

let loaded = loadState()
let state = loaded.state
if (loaded.migrated) persist()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function touch(collection, id) {
  const item = byId(collection, id)
  if (item) item.updatedAt = nowText()
}

function calculateOrderTotal(sourceState, poId) {
  return Number((sourceState.purchaseOrderItems || [])
    .filter((item) => String(item.poId) === String(poId))
    .reduce((sum, item) => sum + toNumber(item.planAmount ?? item.amount), 0)
    .toFixed(2))
}

function replaceItem(collectionName, id, patch, factory) {
  const current = byId(state[collectionName], id)
  if (!current) return null
  Object.assign(current, factory({ ...current, ...patch, id: current.id }))
  persist()
  return clone(current)
}

function removeItem(collectionName, id) {
  const before = state[collectionName].length
  state[collectionName] = state[collectionName].filter((item) => String(item.id) !== String(id))
  persist()
  return before !== state[collectionName].length
}

function result(success, error = '') {
  return { success, error }
}

function moduleNameByTarget(targetType) {
  return {
    purchaseRequest: 'purchaseRequest',
    purchaseInquiry: 'purchaseInquiry',
    priceApproval: 'priceApproval',
    purchaseOrder: 'purchaseOrder',
  }[targetType] || targetType
}

function parentInfo(targetType, parentId) {
  const maps = {
    purchaseRequest: ['purchaseRequests', 'requestNo'],
    purchaseInquiry: ['purchaseInquiries', 'inquiryNo'],
    priceApproval: ['priceApprovals', 'approvalNo'],
    purchaseOrder: ['purchaseOrders', 'poNo'],
  }
  const [collection, noField] = maps[targetType] || []
  const item = byId(state[collection] || [], parentId)
  return { item, no: item?.[noField] || parentId, moduleName: moduleNameByTarget(targetType) }
}

function guardHeaderEdit(targetType, id) {
  const { item, moduleName } = parentInfo(targetType, id)
  if (!item) return result(false, '未找到单据')
  if (!canEditHeader(moduleName, item.status)) return result(false, getReadonlyReason(moduleName, item.status))
  return result(true)
}

function guardLineEdit(targetType, parentId, mode) {
  const { item, moduleName } = parentInfo(targetType, parentId)
  if (!item) return result(false, '未找到单据')
  const allowed = mode === 'add' ? canAddLine(moduleName, item.status) : mode === 'delete' ? canDeleteLine(moduleName, item.status) : canEditLines(moduleName, item.status)
  if (!allowed) return result(false, getReadonlyReason(moduleName, item.status))
  return result(true)
}

const LINE_EDITABLE_FIELDS = {
  purchaseInquiry: ['candidateSuppliers', 'quotedPrice', 'quotedAmount', 'quotationDeadline', 'supplierId', 'supplierName', 'deliveryDate', 'quotedDeliveryDate', 'quoteRemark', 'remark', 'status'],
  priceApproval: ['approvedPrice', 'approvedAmount', 'priceReason', 'priceApprover', 'supplierId', 'supplierName', 'remark'],
  purchaseOrder: ['planPrice', 'planAmount', 'planDeliveryDate', 'plannedArrivalDate', 'supplierId', 'supplierName', 'buyerId', 'buyerName', 'remark', 'warehouseId', 'locationId'],
}

function sanitizeLinePatch(targetType, patch = {}) {
  if (targetType === 'purchaseRequest') return patch
  const allowed = new Set([...(LINE_EDITABLE_FIELDS[targetType] || []), 'id'])
  return Object.fromEntries(Object.entries(patch).filter(([key]) => allowed.has(key)))
}

function sourceLineLockError() {
  return result(false, '该单据来源于上一流程，不能新增或删除来源物料明细。')
}

function consumeConversionFlag(patch = {}) {
  const { __fromConversion, ...cleanPatch } = patch
  return { fromConversion: Boolean(__fromConversion), cleanPatch }
}

function cleanupGeneratedTarget(targetType, targetId) {
  const maps = {
    purchaseInquiry: ['purchaseInquiries', 'purchaseInquiryItems', 'inquiryId'],
    priceApproval: ['priceApprovals', 'priceApprovalItems', 'approvalId'],
    purchaseOrder: ['purchaseOrders', 'purchaseOrderItems', 'poId'],
  }
  const [headerCollection, lineCollection, parentField] = maps[targetType] || []
  if (!headerCollection) return
  state[headerCollection] = state[headerCollection].filter((item) => String(item.id) !== String(targetId))
  state[lineCollection] = state[lineCollection].filter((item) => String(item[parentField]) !== String(targetId))
}

function requestRootInfo(request = {}) {
  return {
    rootRequestId: request.rootRequestId || request.id || '',
    rootRequestNo: request.rootRequestNo || request.requestNo || '',
    rootRequestDepartment: request.rootRequestDepartment || displayName('department', request.requestDepartment || request.departmentId),
    rootDemandDepartment: request.rootDemandDepartment || displayName('department', request.demandDepartment || request.departmentId),
    rootPurchaseDepartment: request.rootPurchaseDepartment || displayName('department', request.purchaseDepartment || defaultPurchaseDepartment()),
    rootRequester: request.rootRequester || displayName('employee', request.requesterId),
    rootRequestDate: request.rootRequestDate || request.requestDate || '',
  }
}

function inheritedRootInfo(header = {}, fallback = {}) {
  return {
    rootRequestId: header.rootRequestId || fallback.rootRequestId || '',
    rootRequestNo: header.rootRequestNo || fallback.rootRequestNo || '',
    rootRequestDepartment: header.rootRequestDepartment || fallback.rootRequestDepartment || '',
    rootDemandDepartment: header.rootDemandDepartment || fallback.rootDemandDepartment || '',
    rootPurchaseDepartment: header.rootPurchaseDepartment || fallback.rootPurchaseDepartment || '',
    rootRequester: header.rootRequester || fallback.rootRequester || '',
    rootRequestDate: header.rootRequestDate || fallback.rootRequestDate || '',
  }
}

function advanceApproval(targetType, id) {
  const { item, moduleName } = parentInfo(targetType, id)
  if (!item) return result(false, '未找到单据')
  if (!canApprove(moduleName, item.status)) return result(false, `当前状态${item.status}不能审核/审批。`)
  const nextStatus = getNextApprovalStatus(moduleName, item.status)
  item.status = nextStatus
  item.updatedAt = nowText()
  persist()
  const action = nextStatus === 'reviewed' ? '审核' : nextStatus === 'rechecked' ? '复核' : nextStatus === 'approved' ? '审批' : '审核流转'
  writeFlowLog(action, {
    sourceModule: targetType,
    sourceOrderId: id,
    sourceOrderNo: sourceNo(targetType, id),
    targetModule: targetType,
    targetOrderNo: sourceNo(targetType, id),
  })
  return ok(nextStatus === 'approved' ? '单据已审批' : `单据已流转为${nextStatus}`)
}

function existingTarget(sourceType, sourceId, targetCollection) {
  return (state[targetCollection] || []).find((item) => item.sourceModule === sourceType && String(item.sourceOrderId) === String(sourceId))
}

function markTarget(sourceType, sourceId, targetModule, targetOrderId, targetOrderNo) {
  const maps = {
    purchaseRequest: 'purchaseRequests',
    purchaseInquiry: 'purchaseInquiries',
    priceApproval: 'priceApprovals',
    purchaseOrder: 'purchaseOrders',
  }
  const item = byId(state[maps[sourceType]] || [], sourceId)
  if (!item) return
  item.targetModule = targetModule
  item.targetOrderId = targetOrderId
  item.targetOrderNo = targetOrderNo
  item.status = 'converted'
  item.updatedAt = nowText()
}

function normalizeSourceLine(item = {}, sourceModule, sourceOrderId, sourceOrderNo) {
  return {
    sourceModule,
    sourceOrderId,
    sourceOrderNo,
    sourceLineId: item.id || item.sourceLineId || item.sourceItemId || '',
    materialId: item.materialId || '',
    materialCode: item.materialCode || '',
    materialName: item.materialName || '',
    spec: item.spec || item.specification || '',
    specification: item.specification || item.spec || '',
    unit: item.unit || '',
    quantity: toNumber(item.quantity ?? item.qty ?? item.planQty),
    price: toNumber(item.price ?? item.unitPrice ?? item.plannedPrice ?? item.approvedPrice ?? item.quotedPrice),
    amount: toNumber(item.amount ?? item.totalAmount),
    expectedDeliveryDate: lineDemandDate(item) || item.plannedArrivalDate || '',
    supplierId: item.supplierId || item.suggestedSupplierId || '',
    supplierName: item.supplierName || getScmDisplayName('supplier', item.supplierId || item.suggestedSupplierId),
    rootRequestId: item.rootRequestId || '',
    rootRequestNo: item.rootRequestNo || '',
    rootRequestDepartment: item.rootRequestDepartment || '',
    rootDemandDepartment: item.rootDemandDepartment || '',
    rootPurchaseDepartment: item.rootPurchaseDepartment || '',
    rootRequester: item.rootRequester || '',
    rootRequestDate: item.rootRequestDate || '',
    rootRequestLineId: item.rootRequestLineId || item.sourceLineId || item.id || '',
    remark: item.remark || item.quoteRemark || '',
  }
}

function validateConvertedLineCount(sourceLines, targetLines) {
  writeFlowLog('转单前明细数量校验', { sourceModule: 'SCM', sourceOrderNo: `来源 ${sourceLines.length} 行`, targetModule: 'SCM', targetOrderNo: `目标 ${targetLines.length} 行` })
  const okCount = sourceLines.length === targetLines.length
  const targetSourceIds = targetLines.map((item) => item.sourceLineId || item.sourceItemId || item.requestItemId || item.inquiryItemId || '')
  const uniqueSourceIds = new Set(targetSourceIds.filter(Boolean))
  const okUniqueSource = uniqueSourceIds.size === targetSourceIds.filter(Boolean).length
  const okContent = sourceLines.every((sourceLine, index) => {
    const targetLine = targetLines[index] || {}
    const sourceId = sourceLine.id || sourceLine.sourceLineId || sourceLine.sourceItemId || ''
    const targetSourceId = targetLine.sourceLineId || targetLine.sourceItemId || targetLine.requestItemId || targetLine.inquiryItemId || ''
    const sourceMaterial = sourceLine.materialCode || sourceLine.materialId || ''
    const targetMaterial = targetLine.materialCode || targetLine.materialId || ''
    return String(targetSourceId) === String(sourceId)
      && String(targetMaterial) === String(sourceMaterial)
      && toNumber(targetLine.quantity) === toNumber(sourceLine.quantity)
  })
  const okAll = okCount && okUniqueSource && okContent
  writeFlowLog(okAll ? '明细继承校验通过' : '明细继承校验失败', {
    sourceModule: 'SCM',
    sourceOrderNo: `来源 ${sourceLines.length} 行`,
    targetModule: 'SCM',
    targetOrderNo: `目标 ${targetLines.length} 行`,
    result: okAll ? '成功' : '失败',
  })
  return okAll ? result(true) : result(false, '明细继承异常：后续单据明细与来源单据不一致。')
}

function ok(message = '') {
  return { success: true, message }
}

function sourceNo(sourceType, sourceId) {
  const maps = {
    purchaseRequest: ['purchaseRequests', 'requestNo'],
    purchaseInquiry: ['purchaseInquiries', 'inquiryNo'],
    priceApproval: ['priceApprovals', 'approvalNo'],
    purchaseOrder: ['purchaseOrders', 'poNo'],
  }
  const [collection, noField] = maps[sourceType] || []
  return byId(state[collection] || [], sourceId)?.[noField] || sourceId
}

function createPendingAction(patch = {}) {
  const existing = (state.pendingActions || []).find((item) => (
    item.status === 'pending'
    && item.actionType === patch.actionType
    && item.sourceType === patch.sourceType
    && String(item.sourceId) === String(patch.sourceId)
  ))
  if (existing) return existing.id
  const item = pendingAction(patch)
  state.pendingActions = [item, ...(state.pendingActions || [])]
  persist()
  writeLog('生成待处理流程', 'pendingAction', item.id, item.title)
  return item.id
}

function completePendingAction(actionType, sourceType, sourceId, remark = '') {
  state.pendingActions = (state.pendingActions || []).map((item) => (
    item.actionType === actionType
    && item.sourceType === sourceType
    && String(item.sourceId) === String(sourceId)
    && item.status === 'pending'
      ? { ...item, status: 'done', completedAt: nowText(), remark: remark || item.remark }
      : item
  ))
  persist()
}

function requireItems(items, label) {
  if (!items.length) return result(false, `${label}必须至少包含一条明细`)
  if (items.some((item) => toNumber(item.quantity) <= 0)) return result(false, `${label}明细数量必须大于0`)
  if (items.some((item) => !item.materialId)) return result(false, `${label}明细必须选择物料`)
  return result(true)
}

function validateOrderItems(poId) {
  const items = getScmPurchaseOrderItems(poId)
  const base = requireItems(items, '采购订单')
  if (!base.success) return base
  if (items.some((item) => toNumber(item.price) <= 0)) return result(false, '采购订单明细价格必须大于0')
  return result(true)
}

export function getScmState() {
  return clone(state)
}

export function resetScmState() {
  state = defaultState()
  persist()
  writeLog('恢复演示数据', 'scm', 'demo')
  return getScmState()
}

export function getPurchaseRequestById(id) { return clone(byId(state.purchaseRequests, id)) }
export function getPurchaseInquiryById(id) { return clone(byId(state.purchaseInquiries, id)) }
export function getPriceApprovalById(id) { return clone(byId(state.priceApprovals, id)) }
export function getScmPurchaseOrderById(id) { return clone(byId(state.purchaseOrders, id)) }

export function getPurchaseRequestItems(requestId) { return clone(normalizeLines(state.purchaseRequestItems, 'requestId', requestId)) }
export function getPurchaseInquiryItems(inquiryId) { return clone(normalizeLines(state.purchaseInquiryItems, 'inquiryId', inquiryId)) }
export function getPriceApprovalItems(approvalId) { return clone(normalizeLines(state.priceApprovalItems, 'approvalId', approvalId)) }
export function getScmPurchaseOrderItems(poId) { return clone(normalizeLines(state.purchaseOrderItems, 'poId', poId)) }
export function getPendingActions(status = '') {
  return clone((state.pendingActions || []).filter((item) => !status || item.status === status))
}
export function cancelPendingAction(id) {
  const action = byId(state.pendingActions, id)
  if (!action) return result(false, '未找到待处理流程')
  Object.assign(action, { status: 'cancelled', completedAt: nowText() })
  persist()
  writeLog('取消待处理流程', 'pendingAction', id, action.title)
  return result(true)
}

export function createPurchaseRequest(patch = {}) {
  const item = requestHeader(patch)
  state.purchaseRequests.unshift(item)
  persist()
  writeLog('新增请购单', 'purchaseRequest', item.id, item.requestNo)
  return item.id
}

export function updatePurchaseRequest(id, patch = {}) {
  const guard = guardHeaderEdit('purchaseRequest', id)
  if (!guard.success && !('status' in patch && Object.keys(patch).length === 1)) return guard
  const item = replaceItem('purchaseRequests', id, patch, requestHeader)
  if (item) writeLog('编辑请购单', 'purchaseRequest', id, item.requestNo)
  return item
}

export function deletePurchaseRequest(id) {
  state.purchaseRequestItems = state.purchaseRequestItems.filter((item) => String(item.requestId) !== String(id))
  const ok = removeItem('purchaseRequests', id)
  if (ok) writeLog('删除请购单', 'purchaseRequest', id)
  return ok
}

export function addPurchaseRequestItem(requestId, patch = {}) {
  const guard = guardLineEdit('purchaseRequest', requestId, 'add')
  if (!guard.success) return guard
  const item = buildRequestItem({ ...patch, requestId, lineNo: getPurchaseRequestItems(requestId).length + 1 })
  state.purchaseRequestItems.push(item)
  touch(state.purchaseRequests, requestId)
  persist()
  writeLog('新增请购明细', 'purchaseRequest', requestId, item.materialName)
  return item.id
}

export function updatePurchaseRequestItem(id, patch = {}) {
  const current = byId(state.purchaseRequestItems, id)
  if (!current) return null
  const guard = guardLineEdit('purchaseRequest', current.requestId, 'edit')
  if (!guard.success) return guard
  const item = replaceItem('purchaseRequestItems', id, patch, buildRequestItem)
  touch(state.purchaseRequests, item.requestId)
  writeLog('编辑请购明细', 'purchaseRequest', item.requestId, item.materialName)
  return item
}

export function deletePurchaseRequestItem(id) {
  const current = byId(state.purchaseRequestItems, id)
  if (!current) return false
  const guard = guardLineEdit('purchaseRequest', current.requestId, 'delete')
  if (!guard.success) return guard
  state.purchaseRequestItems = state.purchaseRequestItems.filter((item) => String(item.id) !== String(id))
  touch(state.purchaseRequests, current.requestId)
  persist()
  writeLog('删除请购明细', 'purchaseRequest', current.requestId, current.materialName)
  return true
}

export function submitPurchaseRequest(id) {
  const request = byId(state.purchaseRequests, id)
  if (!request || !canSubmit('purchaseRequest', request.status)) return result(false, getReadonlyReason('purchaseRequest', request?.status) || '当前状态不能提交。')
  const items = getPurchaseRequestItems(id)
  const ready = requireItems(items, '请购单')
  if (!ready.success) return ready
  request.status = getNextApprovalStatus('purchaseRequest', request.status)
  request.updatedAt = nowText()
  persist()
  writeLog('提交请购单', 'purchaseRequest', id)
  return ok('请购单已提交，等待审批')
}

export function approvePurchaseRequest(id) {
  const items = getPurchaseRequestItems(id)
  const ready = requireItems(items, '请购单')
  if (!ready.success) return ready
  const outcome = advanceApproval('purchaseRequest', id)
  if (!outcome.success) return outcome
  const request = byId(state.purchaseRequests, id)
  if (request.status !== 'approved') return outcome
  createPendingAction({
    actionType: 'createInquiry',
    sourceType: 'purchaseRequest',
    sourceId: id,
    title: `请购单 ${request?.requestNo || sourceNo('purchaseRequest', id)} 已审批，待转询价`,
  })
  writeLog('审批请购单', 'purchaseRequest', id)
  return ok('请购单已审批，已生成待转询价流程')
}

export function closePurchaseRequest(id) {
  updatePurchaseRequest(id, { status: 'closed' })
  writeLog('关闭请购单', 'purchaseRequest', id)
  return result(true)
}

export function createPurchaseInquiry(patch = {}) {
  const item = inquiryHeader(patch)
  state.purchaseInquiries.unshift(item)
  persist()
  writeLog('新增询价单', 'purchaseInquiry', item.id, item.inquiryNo)
  return item.id
}

export function updatePurchaseInquiry(id, patch = {}) {
  const guard = guardHeaderEdit('purchaseInquiry', id)
  if (!guard.success && !('status' in patch && Object.keys(patch).length === 1)) return guard
  const item = replaceItem('purchaseInquiries', id, patch, inquiryHeader)
  if (item) writeLog('编辑询价单', 'purchaseInquiry', id, item.inquiryNo)
  return item
}

export function deletePurchaseInquiry(id) {
  state.purchaseInquiryItems = state.purchaseInquiryItems.filter((item) => String(item.inquiryId) !== String(id))
  const ok = removeItem('purchaseInquiries', id)
  if (ok) writeLog('删除询价单', 'purchaseInquiry', id)
  return ok
}

export function addPurchaseInquiryItem(inquiryId, patch = {}) {
  const { fromConversion, cleanPatch } = consumeConversionFlag(patch)
  if (!fromConversion) {
    writeLog('拦截新增来源明细', 'purchaseInquiry', inquiryId)
    return sourceLineLockError()
  }
  const guard = guardLineEdit('purchaseInquiry', inquiryId, 'edit')
  if (!guard.success) return guard
  const item = buildInquiryItem({ ...cleanPatch, inquiryId, lineNo: getPurchaseInquiryItems(inquiryId).length + 1 })
  state.purchaseInquiryItems.push(item)
  touch(state.purchaseInquiries, inquiryId)
  persist()
  writeLog('新增询价明细', 'purchaseInquiry', inquiryId, item.materialName)
  return item.id
}

export function updatePurchaseInquiryItem(id, patch = {}) {
  const current = byId(state.purchaseInquiryItems, id)
  if (!current) return null
  const guard = guardLineEdit('purchaseInquiry', current.inquiryId, 'edit')
  if (!guard.success) return guard
  const safePatch = sanitizeLinePatch('purchaseInquiry', patch)
  if ('quotedPrice' in safePatch && !('quotedAmount' in safePatch)) safePatch.quotedAmount = toNumber(current.quantity) * toNumber(safePatch.quotedPrice)
  const item = replaceItem('purchaseInquiryItems', id, { ...current, ...safePatch, id }, buildInquiryItem)
  touch(state.purchaseInquiries, item.inquiryId)
  writeLog('编辑询价明细', 'purchaseInquiry', item.inquiryId, item.materialName)
  return item
}

export function deletePurchaseInquiryItem(id) {
  const current = byId(state.purchaseInquiryItems, id)
  if (!current) return false
  writeLog('拦截删除来源明细', 'purchaseInquiry', current.inquiryId, current.materialName)
  return sourceLineLockError()
}

export function sendPurchaseInquiry(id) {
  const items = getPurchaseInquiryItems(id)
  const ready = requireItems(items, '询价单')
  if (!ready.success) return ready
  if (items.some((item) => !item.supplierId)) return result(false, '询价单明细必须选择供应商')
  const inquiry = byId(state.purchaseInquiries, id)
  inquiry.status = 'sent'
  inquiry.updatedAt = nowText()
  persist()
  writeLog('发送询价单', 'purchaseInquiry', id)
  return ok('询价单已发出，等待供应商报价')
}

export function submitPurchaseInquiry(id) {
  const inquiry = byId(state.purchaseInquiries, id)
  if (!inquiry || !canSubmit('purchaseInquiry', inquiry.status)) return result(false, getReadonlyReason('purchaseInquiry', inquiry?.status) || '当前询价单状态不是草稿，不能提报。')
  const items = getPurchaseInquiryItems(id)
  const ready = requireItems(items, '询价单')
  if (!ready.success) return ready
  inquiry.status = getNextApprovalStatus('purchaseInquiry', inquiry.status)
  inquiry.updatedAt = nowText()
  persist()
  writeLog('提交询价单', 'purchaseInquiry', id)
  return result(true)
}

export function confirmInquiryQuote(inquiryId) {
  const items = getPurchaseInquiryItems(inquiryId)
  if (!items.some((item) => toNumber(item.quotedPrice) > 0)) return result(false, '至少一条询价明细有报价后才能确认报价')
  const inquiry = byId(state.purchaseInquiries, inquiryId)
  inquiry.status = 'quoted'
  inquiry.updatedAt = nowText()
  persist()
  createPendingAction({
    actionType: 'createPriceApproval',
    sourceType: 'purchaseInquiry',
    sourceId: inquiryId,
    title: `询价单 ${inquiry?.inquiryNo || sourceNo('purchaseInquiry', inquiryId)} 已报价，待转核价`,
  })
  writeLog('确认询价报价', 'purchaseInquiry', inquiryId)
  return ok('询价单已确认报价，已生成待转核价流程')
}

export function confirmInquiryItemQuote(inquiryId, itemId) {
  const item = byId(state.purchaseInquiryItems, itemId)
  if (!item || String(item.inquiryId) !== String(inquiryId)) return result(false, '未找到询价明细')
  if (toNumber(item.quotedPrice) <= 0) return result(false, '该明细没有有效报价')
  updatePurchaseInquiryItem(itemId, { status: 'quoted' })
  return confirmInquiryQuote(inquiryId)
}

export function approvePurchaseInquiry(id) {
  return advanceApproval('purchaseInquiry', id)
}

export function closePurchaseInquiry(id) {
  updatePurchaseInquiry(id, { status: 'closed' })
  writeLog('关闭询价单', 'purchaseInquiry', id)
  return result(true)
}

export function createPriceApproval(patch = {}) {
  const item = priceApprovalHeader(patch)
  state.priceApprovals.unshift(item)
  persist()
  writeLog('新增核价单', 'priceApproval', item.id, item.approvalNo)
  return item.id
}

export function updatePriceApproval(id, patch = {}) {
  const guard = guardHeaderEdit('priceApproval', id)
  if (!guard.success && !('status' in patch && Object.keys(patch).length === 1)) return guard
  const item = replaceItem('priceApprovals', id, patch, priceApprovalHeader)
  if (item) writeLog('编辑核价单', 'priceApproval', id, item.approvalNo)
  return item
}

export function deletePriceApproval(id) {
  state.priceApprovalItems = state.priceApprovalItems.filter((item) => String(item.approvalId) !== String(id))
  const ok = removeItem('priceApprovals', id)
  if (ok) writeLog('删除核价单', 'priceApproval', id)
  return ok
}

export function addPriceApprovalItem(approvalId, patch = {}) {
  const { fromConversion, cleanPatch } = consumeConversionFlag(patch)
  if (!fromConversion) {
    writeLog('拦截新增来源明细', 'priceApproval', approvalId)
    return sourceLineLockError()
  }
  const guard = guardLineEdit('priceApproval', approvalId, 'edit')
  if (!guard.success) return guard
  const item = buildPriceApprovalItem({ ...cleanPatch, approvalId, lineNo: getPriceApprovalItems(approvalId).length + 1 })
  state.priceApprovalItems.push(item)
  touch(state.priceApprovals, approvalId)
  persist()
  writeLog('新增核价明细', 'priceApproval', approvalId, item.materialName)
  return item.id
}

export function updatePriceApprovalItem(id, patch = {}) {
  const current = byId(state.priceApprovalItems, id)
  if (!current) return null
  const guard = guardLineEdit('priceApproval', current.approvalId, 'edit')
  if (!guard.success) return guard
  const safePatch = sanitizeLinePatch('priceApproval', patch)
  if ('approvedPrice' in safePatch && !('approvedAmount' in safePatch)) safePatch.approvedAmount = toNumber(current.quantity) * toNumber(safePatch.approvedPrice)
  const item = replaceItem('priceApprovalItems', id, { ...current, ...safePatch, id }, buildPriceApprovalItem)
  touch(state.priceApprovals, item.approvalId)
  writeLog('编辑核价明细', 'priceApproval', item.approvalId, item.materialName)
  return item
}

export function deletePriceApprovalItem(id) {
  const current = byId(state.priceApprovalItems, id)
  if (!current) return false
  writeLog('拦截删除来源明细', 'priceApproval', current.approvalId, current.materialName)
  return sourceLineLockError()
}

export function submitPriceApproval(id) {
  const approval = byId(state.priceApprovals, id)
  if (!approval || !canSubmit('priceApproval', approval.status)) return result(false, getReadonlyReason('priceApproval', approval?.status) || '当前状态不能提交。')
  const items = getPriceApprovalItems(id)
  const ready = requireItems(items, '核价单')
  if (!ready.success) return ready
  if (items.some((item) => !item.supplierId || toNumber(item.approvedPrice) <= 0)) return result(false, '核价明细必须包含供应商和有效核准价')
  approval.status = getNextApprovalStatus('priceApproval', approval.status)
  approval.updatedAt = nowText()
  persist()
  writeLog('提交核价单', 'priceApproval', id)
  return result(true)
}

export function approvePriceApproval(id) {
  const ready = validateOrderItemsForPriceApproval(id)
  if (!ready.success) return ready
  const outcome = advanceApproval('priceApproval', id)
  if (!outcome.success) return outcome
  const approval = byId(state.priceApprovals, id)
  if (approval.status !== 'approved') return outcome
  createPendingAction({
    actionType: 'createPurchaseOrder',
    sourceType: 'priceApproval',
    sourceId: id,
    title: `核价单 ${approval?.approvalNo || sourceNo('priceApproval', id)} 已审批，待转采购订单`,
  })
  writeLog('审批核价单', 'priceApproval', id)
  return ok('核价单已审批，已生成待转采购订单流程')
}

export function rejectPriceApproval(id) {
  updatePriceApproval(id, { status: 'rejected' })
  writeLog('驳回核价单', 'priceApproval', id)
  return result(true)
}

export function createScmPurchaseOrder(patch = {}) {
  const item = purchaseOrderHeader(patch)
  state.purchaseOrders.unshift(item)
  persist()
  writeLog('新增采购订单', 'purchaseOrder', item.id, item.poNo)
  return item.id
}

export function updateScmPurchaseOrder(id, patch = {}) {
  const guard = guardHeaderEdit('purchaseOrder', id)
  if (!guard.success && !('status' in patch && Object.keys(patch).length === 1)) return guard
  const item = replaceItem('purchaseOrders', id, patch, purchaseOrderHeader)
  recalculateScmPurchaseOrderAmount(id)
  if (item) writeLog('编辑采购订单', 'purchaseOrder', id, item.poNo)
  return item
}

export function deleteScmPurchaseOrder(id) {
  state.purchaseOrderItems = state.purchaseOrderItems.filter((item) => String(item.poId) !== String(id))
  const ok = removeItem('purchaseOrders', id)
  if (ok) writeLog('删除采购订单', 'purchaseOrder', id)
  return ok
}

export function addScmPurchaseOrderItem(poId, patch = {}) {
  const { fromConversion, cleanPatch } = consumeConversionFlag(patch)
  if (!fromConversion) {
    writeLog('拦截新增来源明细', 'purchaseOrder', poId)
    return sourceLineLockError()
  }
  const guard = guardLineEdit('purchaseOrder', poId, 'edit')
  if (!guard.success) return guard
  const order = byId(state.purchaseOrders, poId)
  const item = buildPurchaseOrderItem({ supplierId: order?.supplierId, ...cleanPatch, poId, lineNo: getScmPurchaseOrderItems(poId).length + 1 })
  state.purchaseOrderItems.push(item)
  recalculateScmPurchaseOrderAmount(poId)
  touch(state.purchaseOrders, poId)
  persist()
  writeLog('新增采购订单明细', 'purchaseOrder', poId, item.materialName)
  return item.id
}

export function updateScmPurchaseOrderItem(id, patch = {}) {
  const current = byId(state.purchaseOrderItems, id)
  if (!current) return null
  const guard = guardLineEdit('purchaseOrder', current.poId, 'edit')
  if (!guard.success) return guard
  const order = byId(state.purchaseOrders, current.poId)
  const safePatch = sanitizeLinePatch('purchaseOrder', patch)
  if ('planPrice' in safePatch) {
    safePatch.price = safePatch.planPrice
    if (!('planAmount' in safePatch)) safePatch.planAmount = toNumber(current.quantity) * toNumber(safePatch.planPrice)
  }
  if ('planAmount' in safePatch) safePatch.amount = safePatch.planAmount
  const item = replaceItem('purchaseOrderItems', id, { ...current, supplierId: order?.supplierId, ...safePatch, id }, buildPurchaseOrderItem)
  recalculateScmPurchaseOrderAmount(item.poId)
  touch(state.purchaseOrders, item.poId)
  writeLog('编辑采购订单明细', 'purchaseOrder', item.poId, item.materialName)
  return item
}

export function deleteScmPurchaseOrderItem(id) {
  const current = byId(state.purchaseOrderItems, id)
  if (!current) return false
  writeLog('拦截删除来源明细', 'purchaseOrder', current.poId, current.materialName)
  return sourceLineLockError()
}

export function recalculateScmPurchaseOrderAmount(poId) {
  const order = byId(state.purchaseOrders, poId)
  if (!order) return 0
  const linePlanDate = earliestDate(normalizeLines(state.purchaseOrderItems, 'poId', poId).map((item) => lineDemandDate(item)))
  order.earliestArrivalDate = linePlanDate
  order.plannedArrivalDate = linePlanDate
  order.planDeliveryDate = linePlanDate
  order.expectedDeliveryDate = linePlanDate
  order.totalAmount = calculateOrderTotal(state, poId)
  persist()
  return order.totalAmount
}

export function submitScmPurchaseOrder(id) {
  const order = byId(state.purchaseOrders, id)
  if (!order || !canSubmit('purchaseOrder', order.status)) return result(false, getReadonlyReason('purchaseOrder', order?.status) || '当前状态不能提交。')
  const ready = validateOrderItems(id)
  if (!ready.success) return ready
  order.status = getNextApprovalStatus('purchaseOrder', order.status)
  order.updatedAt = nowText()
  persist()
  writeLog('提交采购订单', 'purchaseOrder', id)
  writeFlowLog('采购订单提报', {
    sourceModule: 'purchaseOrder',
    sourceOrderId: id,
    sourceOrderNo: order.poNo,
    targetModule: 'purchaseOrder',
    targetOrderNo: order.poNo,
  })
  return result(true)
}

export function approveScmPurchaseOrder(id) {
  const ready = validateOrderItems(id)
  if (!ready.success) return ready
  const order = byId(state.purchaseOrders, id)
  const beforeStatus = order?.status || ''
  const outcome = advanceApproval('purchaseOrder', id)
  if (!outcome.success) return outcome
  const nextOrder = byId(state.purchaseOrders, id)
  const action = beforeStatus === 'submitted' ? '采购订单审核' : beforeStatus === 'reviewed' ? '采购订单复核' : beforeStatus === 'rechecked' ? '采购订单审批' : '采购订单审批流转'
  writeFlowLog(action, {
    sourceModule: 'purchaseOrder',
    sourceOrderId: id,
    sourceOrderNo: nextOrder?.poNo || sourceNo('purchaseOrder', id),
    targetModule: 'purchaseOrder',
    targetOrderNo: nextOrder?.poNo || sourceNo('purchaseOrder', id),
  })
  writeLog('审批采购订单', 'purchaseOrder', id)
  return result(true)
}

function validateOrderItemsForPriceApproval(id) {
  const items = getPriceApprovalItems(id)
  const base = requireItems(items, '核价单')
  if (!base.success) return base
  if (items.some((item) => !item.supplierId || toNumber(item.approvedPrice) <= 0)) return result(false, '核价明细必须包含供应商和有效核准价')
  return result(true)
}

export function issueScmPurchaseOrder(id) {
  const order = byId(state.purchaseOrders, id)
  if (!order || order.status !== 'approved') return result(false, '只有已审批采购订单可以下达。')
  const ready = validateOrderItems(id)
  if (!ready.success) return ready
  order.status = 'issued'
  order.orderStatus = 'issued'
  order.issueStatus = 'issued'
  order.issuedAt = nowText()
  order.issuedBy = order.buyerId || firstId(getEmployeeOptions())
  order.updatedAt = nowText()
  persist()
  writeFlowLog('下达采购订单', {
    sourceModule: 'purchaseOrder',
    sourceOrderId: id,
    sourceOrderNo: order.poNo,
    targetModule: 'WMS采购到货预备',
    targetOrderNo: order.poNo,
  })
  return ok('采购订单已下达，可进入 WMS 收货预备')
}

export function closeScmPurchaseOrder(id) {
  updateScmPurchaseOrder(id, { status: 'closed' })
  writeLog('关闭采购订单', 'purchaseOrder', id)
  return result(true)
}

export function createInquiryFromRequest(requestId) {
  const request = byId(state.purchaseRequests, requestId)
  if (!request || request.status !== 'approved') return null
  const existing = existingTarget('purchaseRequest', requestId, 'purchaseInquiries')
  if (existing) return { success: false, error: `该单据已生成下一单 ${existing.inquiryNo}，不能重复生成。`, targetPath: `/scm/purchase-inquiry/${existing.id}` }
  const requestItems = getPurchaseRequestItems(requestId)
  if (!requestItems.length) return null
  const root = requestRootInfo(request)
  const requestLineDates = requestItems.map((item) => sourcePlanDate(item, request))
  const inquiryId = createPurchaseInquiry({
    requestId,
    status: 'draft',
    sourceModule: 'purchaseRequest',
    sourceOrderId: requestId,
    sourceOrderNo: request.requestNo,
    requestDepartment: root.rootRequestDepartment,
    demandDepartment: root.rootDemandDepartment,
    purchaseDepartment: root.rootPurchaseDepartment,
    requester: root.rootRequester,
    quotationDeadline: earliestDate(requestLineDates) || headerDemandDate(request),
    ...root,
    remark: request.remark,
  })
  const inquiry = byId(state.purchaseInquiries, inquiryId)
  requestItems.forEach((item) => {
    const planDate = sourcePlanDate(item, request)
    addPurchaseInquiryItem(inquiryId, {
    ...normalizeSourceLine(item, 'purchaseRequest', requestId, request.requestNo),
    ...root,
    ...demandDatePatch(planDate),
    rootRequestLineId: item.rootRequestLineId || item.id,
    requestItemId: item.id,
    supplierId: item.suggestedSupplierId,
    materialId: item.materialId,
    quantity: item.quantity,
    deliveryDate: planDate,
    __fromConversion: true,
    })
  })
  const lineCheck = validateConvertedLineCount(requestItems, getPurchaseInquiryItems(inquiryId))
  if (!lineCheck.success) {
    cleanupGeneratedTarget('purchaseInquiry', inquiryId)
    persist()
    return lineCheck
  }
  markTarget('purchaseRequest', requestId, 'purchaseInquiry', inquiryId, inquiry?.inquiryNo || inquiryId)
  persist()
  writeFlowLog('生成询价单', {
    sourceModule: 'purchaseRequest',
    sourceOrderId: requestId,
    sourceOrderNo: request.requestNo,
    targetModule: 'purchaseInquiry',
    targetOrderId: inquiryId,
    targetOrderNo: inquiry?.inquiryNo || inquiryId,
  })
  completePendingAction('createInquiry', 'purchaseRequest', requestId, `生成询价单 ${inquiryId}`)
  return inquiryId
}

export function createPriceApprovalFromInquiry(inquiryId) {
  const inquiry = byId(state.purchaseInquiries, inquiryId)
  if (!inquiry || !['approved', 'completed', 'sent', 'quoted'].includes(inquiry.status)) return null
  const existing = existingTarget('purchaseInquiry', inquiryId, 'priceApprovals')
  if (existing) return { success: false, error: `该单据已生成下一单 ${existing.approvalNo}，不能重复生成。`, targetPath: `/scm/price-approval/${existing.id}` }
  const quotedItems = getPurchaseInquiryItems(inquiryId).filter((item) => toNumber(item.quotedPrice) > 0)
  if (!quotedItems.length) return null
  const root = inheritedRootInfo(inquiry, quotedItems[0])
  const approvalId = createPriceApproval({
    inquiryId,
    buyerId: inquiry.buyerId,
    buyerName: getScmDisplayName('employee', inquiry.buyerId),
    supplierId: quotedItems[0]?.supplierId || '',
    supplierName: getScmDisplayName('supplier', quotedItems[0]?.supplierId),
    sourceModule: 'purchaseInquiry',
    sourceOrderId: inquiryId,
    sourceOrderNo: inquiry.inquiryNo,
    requestDepartment: inquiry.requestDepartment || root.rootRequestDepartment,
    demandDepartment: inquiry.demandDepartment || root.rootDemandDepartment,
    purchaseDepartment: inquiry.purchaseDepartment || root.rootPurchaseDepartment,
    requester: inquiry.requester || root.rootRequester,
    ...root,
    status: 'draft',
    remark: inquiry.remark,
  })
  const approval = byId(state.priceApprovals, approvalId)
  quotedItems.forEach((item) => {
    const planDate = sourcePlanDate(item, inquiry)
    addPriceApprovalItem(approvalId, {
    ...normalizeSourceLine(item, 'purchaseInquiry', inquiryId, inquiry.inquiryNo),
    ...inheritedRootInfo(inquiry, item),
    ...demandDatePatch(planDate),
    inquiryItemId: item.id,
    supplierId: item.supplierId,
    materialId: item.materialId,
    quantity: item.quantity,
    deliveryDate: planDate,
    quotedPrice: item.quotedPrice,
    approvedPrice: item.quotedPrice,
    approvedAmount: toNumber(item.quantity) * toNumber(item.quotedPrice),
    taxRate: item.taxRate,
    deliveryDays: item.deliveryDays,
    paymentTerms: item.paymentTerms,
    priceSourceId: item.priceSourceId,
    __fromConversion: true,
    })
  })
  const lineCheck = validateConvertedLineCount(quotedItems, getPriceApprovalItems(approvalId))
  if (!lineCheck.success) {
    cleanupGeneratedTarget('priceApproval', approvalId)
    persist()
    return lineCheck
  }
  markTarget('purchaseInquiry', inquiryId, 'priceApproval', approvalId, approval?.approvalNo || approvalId)
  persist()
  writeFlowLog('生成核价单', {
    sourceModule: 'purchaseInquiry',
    sourceOrderId: inquiryId,
    sourceOrderNo: inquiry.inquiryNo,
    targetModule: 'priceApproval',
    targetOrderId: approvalId,
    targetOrderNo: approval?.approvalNo || approvalId,
  })
  completePendingAction('createPriceApproval', 'purchaseInquiry', inquiryId, `生成核价单 ${approvalId}`)
  return approvalId
}

export function createPurchaseOrderFromPriceApproval(approvalId) {
  const approval = byId(state.priceApprovals, approvalId)
  if (!approval || approval.status !== 'approved') return null
  const existing = existingTarget('priceApproval', approvalId, 'purchaseOrders')
  if (existing) return { success: false, error: `该单据已生成下一单 ${existing.poNo}，不能重复生成。`, targetPath: `/scm/purchase-order/${existing.id}` }
  const approvalItems = getPriceApprovalItems(approvalId)
  if (!approvalItems.length) return null
  const firstItem = approvalItems[0]
  const supplierId = firstItem?.supplierId || approval.supplierId || ''
  const root = inheritedRootInfo(approval, firstItem)
  const approvalLineDates = approvalItems.map((item) => sourcePlanDate(item, approval))
  const orderPlanDate = earliestDate(approvalLineDates) || headerDemandDate(approval)
  const poId = createScmPurchaseOrder({
    supplierId,
    buyerId: approval.buyerId,
    sourceType: 'priceApproval',
    sourceId: approvalId,
    sourceModule: 'priceApproval',
    sourceOrderId: approvalId,
    sourceOrderNo: approval.approvalNo,
    supplierName: getScmDisplayName('supplier', supplierId),
    buyerName: getScmDisplayName('employee', approval.buyerId),
    requestDepartment: approval.requestDepartment || root.rootRequestDepartment || '',
    demandDepartment: approval.demandDepartment || root.rootDemandDepartment || '',
    purchaseDepartment: approval.purchaseDepartment || root.rootPurchaseDepartment || '',
    plannedArrivalDate: orderPlanDate,
    earliestArrivalDate: orderPlanDate,
    planDeliveryDate: orderPlanDate,
    expectedDeliveryDate: orderPlanDate,
    planAmount: approvalItems.reduce((sum, item) => sum + toNumber(item.approvedAmount || (toNumber(item.quantity) * toNumber(item.approvedPrice))), 0),
    actualAmount: 0,
    ...root,
    status: 'draft',
    remark: approval.remark,
  })
  const po = byId(state.purchaseOrders, poId)
  approvalItems.forEach((item) => {
    const planPrice = toNumber(item.approvedPrice || item.price)
    const planDate = sourcePlanDate(item, approval)
    addScmPurchaseOrderItem(poId, {
      ...normalizeSourceLine(item, 'priceApproval', approvalId, approval.approvalNo),
      ...inheritedRootInfo(approval, item),
      ...demandDatePatch(planDate),
      sourceItemId: item.id,
      sourceLineId: item.id,
      materialId: item.materialId,
      quantity: item.quantity,
      price: planPrice,
      amount: toNumber(item.quantity) * planPrice,
      planPrice,
      planAmount: toNumber(item.quantity) * planPrice,
      plannedArrivalDate: planDate,
      planDeliveryDate: planDate,
      actualPrice: 0,
      actualAmount: 0,
      supplierId: item.supplierId,
      supplierName: item.supplierName || getScmDisplayName('supplier', item.supplierId),
      __fromConversion: true,
    })
  })
  const lineCheck = validateConvertedLineCount(approvalItems, getScmPurchaseOrderItems(poId))
  if (!lineCheck.success) {
    cleanupGeneratedTarget('purchaseOrder', poId)
    persist()
    return lineCheck
  }
  recalculateScmPurchaseOrderAmount(poId)
  markTarget('priceApproval', approvalId, 'purchaseOrder', poId, po?.poNo || poId)
  writeFlowLog('生成采购订单', {
    sourceModule: 'priceApproval',
    sourceOrderId: approvalId,
    sourceOrderNo: approval.approvalNo,
    targetModule: 'purchaseOrder',
    targetOrderId: poId,
    targetOrderNo: po?.poNo || poId,
  })
  completePendingAction('createPurchaseOrder', 'priceApproval', approvalId, `生成采购订单 ${po?.poNo || poId}`)
  return [poId]
}

export function processPendingAction(id) {
  const action = byId(state.pendingActions, id)
  if (!action || action.status !== 'pending') return { success: false, error: '未找到可处理的待处理流程' }
  if (action.actionType === 'createInquiry') {
    const newId = createInquiryFromRequest(action.sourceId)
    if (newId?.success === false) return newId
    return newId ? { success: true, targetPath: `/scm/purchase-inquiry/${newId}` } : { success: false, error: '待转询价处理失败，请确认请购单已审批且包含明细' }
  }
  if (action.actionType === 'createPriceApproval') {
    const newId = createPriceApprovalFromInquiry(action.sourceId)
    if (newId?.success === false) return newId
    return newId ? { success: true, targetPath: `/scm/price-approval/${newId}` } : { success: false, error: '待转核价处理失败，请确认询价单已报价' }
  }
  if (action.actionType === 'createPurchaseOrder') {
    const newIds = createPurchaseOrderFromPriceApproval(action.sourceId)
    if (newIds?.success === false) return newIds
    return newIds?.length ? { success: true, targetPath: `/scm/purchase-order/${newIds[0]}` } : { success: false, error: '待转采购订单处理失败，请确认核价单已审批' }
  }
  return { success: false, error: '未知待处理流程类型' }
}

export function getScmDisplayName(type, id) {
  const collections = {
    employee: getEmployeeOptions(),
    department: getDepartmentOptions(),
    material: getMaterialOptions(),
    supplier: getSupplierOptions(),
    warehouse: getWarehouseOptions(),
    location: getLocationOptions(),
  }
  return optionName(collections[type] || [], id) || id || '-'
}

function batchResult(ids = [], handler, label, noGetter = (id) => id) {
  const resultSet = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const no = noGetter(id)
    try {
      const outcome = handler(id)
      const success = Array.isArray(outcome) ? outcome.length > 0 : outcome === true || Boolean(outcome?.success) || (outcome && outcome.success !== false)
      if (success) {
        resultSet.successCount += 1
        resultSet.successItems.push({ id, no })
      } else {
        const reason = outcome?.error || outcome?.message || '当前状态不允许执行该批量操作。'
        resultSet.failedCount += 1
        resultSet.failedItems.push({ id, no, reason })
        resultSet.failedReason.push(`${no}：${reason}`)
      }
    } catch (error) {
      const reason = error?.message || '批量操作异常'
      resultSet.failedCount += 1
      resultSet.failedItems.push({ id, no, reason })
      resultSet.failedReason.push(`${no}：${reason}`)
    }
  })
  writeLog(label, 'batch', label, `成功 ${resultSet.successCount} 条，失败 ${resultSet.failedCount} 条；${resultSet.failedReason.join('；')}`)
  if (resultSet.failedCount) writeLog('批量操作失败原因', 'batch', label, resultSet.failedReason.join('；'))
  return resultSet
}

function docByModule(moduleName, id) {
  return {
    purchaseRequest: byId(state.purchaseRequests, id),
    purchaseInquiry: byId(state.purchaseInquiries, id),
    priceApproval: byId(state.priceApprovals, id),
    purchaseOrder: byId(state.purchaseOrders, id),
  }[moduleName] || null
}

function docNo(moduleName, id) {
  const doc = docByModule(moduleName, id)
  return doc?.requestNo || doc?.inquiryNo || doc?.approvalNo || doc?.poNo || id
}

function approvalStatusReason(moduleName, status = '') {
  if (status === 'submitted') return ''
  if (status === 'reviewed') return ''
  if (status === 'rechecked') return ''
  if (status === 'draft' || status === 'rejected') return '当前状态不是待审核，不能审核。'
  if (status === 'approved' || status === 'converted' || status === 'issued') return '当前状态已完成当前审批节点，不能重复审核。'
  return '当前状态不符，不能审核/复核/审批。'
}

export function batchSubmitDocuments(moduleName, ids = []) {
  const handlers = {
    purchaseRequest: submitPurchaseRequest,
    purchaseInquiry: submitPurchaseInquiry,
    priceApproval: submitPriceApproval,
    purchaseOrder: submitScmPurchaseOrder,
  }
  return batchResult(ids, (id) => {
    const handler = handlers[moduleName]
    if (!handler) return { success: false, error: '该单据暂不支持批量提报。' }
    const doc = docByModule(moduleName, id)
    if (!doc) return { success: false, error: '未找到单据。' }
    if (!['draft', 'rejected'].includes(doc.status)) return { success: false, error: '当前状态不是草稿或已驳回，不能提报。' }
    return handler(id)
  }, moduleName === 'purchaseOrder' ? '批量提报采购订单' : '批量提报', (id) => docNo(moduleName, id))
}

export function batchApproveDocuments(moduleName, ids = []) {
  const handlers = {
    purchaseRequest: approvePurchaseRequest,
    purchaseInquiry: approvePurchaseInquiry,
    priceApproval: approvePriceApproval,
    purchaseOrder: approveScmPurchaseOrder,
  }
  return batchResult(ids, (id) => {
    const handler = handlers[moduleName]
    if (!handler) return { success: false, error: '该单据暂不支持批量审核/复核/审批。' }
    const doc = docByModule(moduleName, id)
    if (!doc) return { success: false, error: '未找到单据。' }
    if (!['submitted', 'reviewed', 'rechecked'].includes(doc.status)) return { success: false, error: approvalStatusReason(moduleName, doc.status) }
    return handler(id)
  }, '批量审核/复核/审批', (id) => docNo(moduleName, id))
}

export function batchConvertToNext(moduleName, ids = []) {
  const handlers = {
    purchaseRequest: createInquiryFromRequest,
    purchaseInquiry: createPriceApprovalFromInquiry,
    priceApproval: createPurchaseOrderFromPriceApproval,
  }
  const labels = {
    purchaseRequest: '批量生成询价单',
    purchaseInquiry: '批量生成核价单',
    priceApproval: '批量生成采购订单',
  }
  return batchResult(ids, (id) => {
    const handler = handlers[moduleName]
    if (!handler) return { success: false, error: '该单据暂不支持批量生成下游单据。' }
    const outcome = handler(id)
    if (!outcome || outcome.success === false || (Array.isArray(outcome) && !outcome.length)) return { success: false, error: outcome?.error || '当前状态或来源明细不满足生成条件，或已生成下游单据。' }
    return { success: true }
  }, labels[moduleName] || '批量生成下游单据', (id) => docNo(moduleName, id))
}

export function batchIssuePurchaseOrders(ids = []) {
  return batchResult(ids, issueScmPurchaseOrder, '批量下达采购订单', (id) => docNo('purchaseOrder', id))
}
