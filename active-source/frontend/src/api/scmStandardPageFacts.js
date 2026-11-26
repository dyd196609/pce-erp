import request from './request.js'

export function getScmStandardPageFacts(pageCode, params) {
  return request({
    method: 'GET',
    url: `/api/procurement/scm-page-facts/${encodeURIComponent(pageCode)}/`,
    params,
    meta: { module: 'SCM', factLoad: true, readOnly: true },
  })
}

export function runScmRuntimeAction(action, objectId, data = {}) {
  return request({
    method: 'POST',
    url: `/api/procurement/scm-runtime-actions/${encodeURIComponent(action)}/${encodeURIComponent(objectId)}/`,
    data,
    meta: { module: 'SCM', explicitBusinessAction: true },
  })
}

export function getPurchaseOrderFulfillmentFacts(orderId) {
  return request({
    method: 'GET',
    url: `/api/procurement/purchase-order-fulfillment/${encodeURIComponent(orderId)}/`,
    meta: { module: 'SCM', factLoad: true, readOnly: true },
  })
}

export async function getActivePurchaseOrderSuppliers() {
  const results = []
  let page = 1
  let count = null
  do {
    const response = await request({
      method: 'GET', url: '/api/procurement/suppliers/', params: { page_size: 100, page },
      meta: { module: 'SCM', factLoad: true, readOnly: true },
    })
    const payload = response?.data || response || {}
    const batch = payload.results || (Array.isArray(payload) ? payload : [])
    results.push(...batch)
    count = Number(payload.count ?? results.length)
    page += 1
    if (!batch.length) break
  } while (results.length < count)
  return { data: { count: results.length, results } }
}

export function getActivePurchaseOrderBuyers() {
  return request({
    method: 'GET', url: '/api/pfm/employees/', params: { page_size: 100, status__in: 'active' },
    meta: { module: 'SCM', factLoad: true, readOnly: true },
  })
}

export function getActivePurchaseOrderMaterials() {
  return request({
    method: 'GET',
    url: '/api/masterdata/materials/?page_size=200',
    meta: { module: 'SCM', factLoad: true, readOnly: true },
  })
}

export function createPurchaseOrderFromGateRequest(data, csrfToken = '') {
  return request({
    method: 'POST',
    url: '/api/procurement/purchase-order-gate-creation/',
    data,
    headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
    meta: { module: 'SCM', explicitBusinessAction: true },
  })
}

export function preparePurchaseOrderGateCreation() {
  return request({
    method: 'GET',
    url: '/api/procurement/purchase-order-gate-creation/',
    meta: { module: 'SCM', factLoad: true, readOnly: true },
  })
}

export function resolveProcurementModeRoute(purchaseMode, legalEntityId = '') {
  return request({ method: 'GET', url: '/api/procurement/procurement-mode-routing/',
    params: { purchaseMode, legalEntityId },
    meta: { module: 'SCM', factLoad: true, readOnly: true } })
}

export function inspectPurchaseOrderGateCreation(data, csrfToken = '') {
  return request({
    method: 'POST',
    url: '/api/procurement/purchase-order-gate-creation/',
    data: { ...data, previewOnly: true },
    headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
    meta: { module: 'SCM', factLoad: true, readOnly: true },
  })
}

export function inspectAgreedPricePurchaseOrder(data, csrfToken = '') {
  return inspectPurchaseOrderGateCreation({ ...data, creationMode: 'AGREED_PRICE_CONFIRMATION', purchaseMode: 'AGREED_PRICE' }, csrfToken)
}

export function createAgreedPricePurchaseOrders(data, csrfToken = '') {
  return createPurchaseOrderFromGateRequest({ ...data, creationMode: 'AGREED_PRICE_CONFIRMATION', purchaseMode: 'AGREED_PRICE' }, csrfToken)
}

export function createPurchaseInquiryFromRequest(requestId) {
  return request({
    method: 'POST',
    url: `/api/procurement/purchase-inquiries/from-request/${encodeURIComponent(requestId)}/`,
    meta: { module: 'SCM', explicitBusinessAction: true },
  })
}

export function saveSupplierQuotation(data) {
  return request({ method: 'POST', url: '/api/procurement/supplier-quotations/save/', data,
    meta: { module: 'SCM', explicitBusinessAction: true } })
}

export function submitSupplierQuotation(quotationId) {
  return request({ method: 'POST', url: `/api/procurement/supplier-quotations/${encodeURIComponent(quotationId)}/submit/`,
    meta: { module: 'SCM', explicitBusinessAction: true } })
}

export function getPriceApprovalPreparations() {
  return request({ method: 'GET', url: '/api/procurement/price-approval-preparations/',
    meta: { module: 'SCM', factLoad: true, readOnly: true } })
}

export function createPriceApprovalPreparation(source = {}) {
  const data = typeof source === 'string' ? { sourceComparisonNo: source } : source
  return request({ method: 'POST', url: '/api/procurement/price-approval-preparations/',
    data, meta: { module: 'SCM', explicitBusinessAction: true } })
}

export function transitionPriceApprovalPreparation(preparationId, data = {}) {
  return request({ method: 'POST',
    url: `/api/procurement/price-approval-preparations/${encodeURIComponent(preparationId)}/transition/`,
    data, meta: { module: 'SCM', explicitBusinessAction: true } })
}
