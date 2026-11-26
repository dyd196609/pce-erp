const LIST_ROUTES = {
  wms: {
    purchaseReceivePreview: '/wms/purchase-receive-preview',
    purchaseReceives: '/wms/purchase-receives',
    warehouseTasks: '/wms/warehouse-tasks',
    inventoryBalances: '/wms/inventory-balances',
    inventoryTransactions: '/wms/inventory-transactions',
    stockWarnings: '/wms/stock-warnings',
  },
  qms: {
    incomingInspections: '/qms/incoming-inspections',
  },
  scm: {
    purchaseRequests: '/scm/purchase-requests',
    purchaseInquiries: '/scm/purchase-inquiries',
    priceApprovals: '/scm/price-approvals',
    purchaseOrders: '/scm/purchase-orders',
  },
}

const PARENT_ROUTES = {
  wms: '/wms',
  qms: '/qms',
  scm: '/scm',
}

function normalize(value = '') {
  return String(value || '').toLowerCase()
}

function purchaseOrderRoute(id) {
  return id ? `/scm/purchase-order/${id}` : '/scm/purchase-orders'
}

function purchaseRequestRoute(id) {
  return id ? `/scm/purchase-request/${id}` : '/scm/purchase-requests'
}

function purchaseInquiryRoute(id) {
  return id ? `/scm/purchase-inquiry/${id}` : '/scm/purchase-inquiries'
}

function priceApprovalRoute(id) {
  return id ? `/scm/price-approval/${id}` : '/scm/price-approvals'
}

function purchaseReceiveRoute(id) {
  return id ? `/wms/purchase-receive/${id}` : '/wms/purchase-receives'
}

function incomingInspectionRoute(id) {
  return id ? `/qms/incoming-inspection/${id}` : '/qms/incoming-inspections'
}

function warehouseTaskRoute(id) {
  return id ? `/wms/warehouse-task/${id}` : '/wms/warehouse-tasks'
}

export function getListRoute(moduleName, pageType) {
  return LIST_ROUTES[moduleName]?.[pageType] || PARENT_ROUTES[moduleName] || '/'
}

export function getParentRoute(moduleName) {
  return PARENT_ROUTES[moduleName] || '/'
}

export function getSourceRoute(record = {}) {
  const sourceModule = normalize(record.sourceModule)
  const sourceType = normalize(record.sourceType)
  if (record.sourceReceiveId || sourceType.includes('purchasereceive') || sourceModule.includes('采购收货')) {
    return purchaseReceiveRoute(record.sourceReceiveId)
  }
  if (sourceType.includes('warehousetask') || sourceModule.includes('仓库任务')) {
    return warehouseTaskRoute(record.sourceOrderId || record.sourceId)
  }
  if (record.sourceInspectionId || sourceType.includes('inspection') || sourceModule.includes('qms')) {
    return incomingInspectionRoute(record.sourceInspectionId)
  }
  if (sourceModule.includes('purchaserequest') || sourceModule.includes('请购')) {
    return purchaseRequestRoute(record.sourceOrderId || record.sourceId)
  }
  if (sourceModule.includes('purchaseinquiry') || sourceModule.includes('询价')) {
    return purchaseInquiryRoute(record.sourceOrderId || record.sourceId)
  }
  if (sourceModule.includes('priceapproval') || sourceModule.includes('核价')) {
    return priceApprovalRoute(record.sourceOrderId || record.sourceId)
  }
  if (
    record.sourceOrderId
    || sourceType.includes('scmpurchaseorder')
    || sourceType.includes('purchaseorder')
    || sourceModule.includes('purchaseorder')
    || sourceModule.includes('采购订单')
  ) {
    return purchaseOrderRoute(record.sourceOrderId || record.id)
  }
  if (record.poId || record.poNo) return purchaseOrderRoute(record.poId || record.id)
  return ''
}

export function getSourceButtonLabel(record = {}) {
  const sourceModule = normalize(record.sourceModule)
  const sourceType = normalize(record.sourceType)
  if (record.sourceReceiveId || sourceType.includes('purchasereceive') || sourceModule.includes('采购收货')) return '查看来源收货单'
  if (sourceType.includes('warehousetask') || sourceModule.includes('仓库任务')) return '查看来源单据'
  if (record.sourceInspectionId || sourceType.includes('inspection') || sourceModule.includes('qms')) return '查看来源检验单'
  if (sourceModule.includes('purchaserequest') || sourceModule.includes('请购')) return '查看来源请购单'
  if (sourceModule.includes('purchaseinquiry') || sourceModule.includes('询价')) return '查看来源询价单'
  if (sourceModule.includes('priceapproval') || sourceModule.includes('核价')) return '查看来源核价单'
  if (record.sourceOrderId || record.poId || record.poNo || sourceType.includes('purchaseorder') || sourceModule.includes('采购订单')) return '查看来源采购订单'
  return '查看来源单据'
}

export function hasSourceRoute(record = {}) {
  return Boolean(getSourceRoute(record))
}

export function goList(router, moduleName, pageType) {
  router.push(getListRoute(moduleName, pageType))
}

export function goParent(router, moduleName) {
  router.push(getParentRoute(moduleName))
}

export function goSource(router, record = {}, notify) {
  const route = getSourceRoute(record)
  if (!route) {
    notify?.('未找到来源单据', 'warning')
    return false
  }
  router.push(route)
  return true
}
