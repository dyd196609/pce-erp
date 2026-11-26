export const SCM_STATE_RULE_REGISTRY_VERSION = 'V1.14.2.8.4.12'

export const SCM_DOCUMENT_STATE_MATRIX = Object.freeze({
  purchaseRequest: Object.freeze({
    draft: Object.freeze({ mayCreateInquiry: false, mayCreatePriceApproval: false, terminal: false }),
    approved: Object.freeze({ mayCreateInquiry: true, mayCreatePriceApproval: false, terminal: false }),
    converted: Object.freeze({ mayCreateInquiry: false, mayCreatePriceApproval: true, downstreamRequired: true, terminal: false }),
    closed: Object.freeze({ mayCreateInquiry: false, mayCreatePriceApproval: false, terminal: true }),
  }),
  purchaseInquiry: Object.freeze({
    draft: Object.freeze({ mayCreateEligibility: false, mayCreatePriceApproval: false, terminal: false }),
    approved: Object.freeze({ mayCreateEligibility: true, mayCreatePriceApproval: true, downstreamRequired: true, terminal: false }),
    quoted: Object.freeze({ mayCreateEligibility: true, mayCreatePriceApproval: true, downstreamRequired: true, terminal: false }),
    closed: Object.freeze({ mayCreateEligibility: false, mayCreatePriceApproval: false, terminal: true }),
  }),
  priceApproval: Object.freeze({
    draft: Object.freeze({ mayCreatePurchaseOrder: false, phase: 'not_started' }),
    reviewing: Object.freeze({ mayCreatePurchaseOrder: false, phase: 'processing' }),
    processing: Object.freeze({ mayCreatePurchaseOrder: false, phase: 'processing' }),
    submitted: Object.freeze({ mayCreatePurchaseOrder: false, phase: 'processing' }),
    reviewed: Object.freeze({ mayCreatePurchaseOrder: false, phase: 'processing' }),
    rechecked: Object.freeze({ mayCreatePurchaseOrder: false, phase: 'processing' }),
    approved: Object.freeze({ mayCreatePurchaseOrder: true, phase: 'completed' }),
    completed: Object.freeze({ mayCreatePurchaseOrder: true, phase: 'completed' }),
    converted: Object.freeze({ mayCreatePurchaseOrder: false, downstreamRequired: true, phase: 'completed' }),
  }),
  purchaseOrder: Object.freeze({
    draft: Object.freeze({ mayReceive: false }),
    approved: Object.freeze({ mayReceive: false }),
    issued: Object.freeze({ mayReceive: true }),
    partial_received: Object.freeze({ mayReceive: true }),
    partiallyReceived: Object.freeze({ mayReceive: true }),
    completed: Object.freeze({ mayReceive: false, terminal: true }),
    closed: Object.freeze({ mayReceive: false, terminal: true }),
    fullyReceived: Object.freeze({ mayReceive: false, terminal: true }),
  }),
  quality: Object.freeze({
    pending: Object.freeze({ mayInbound: false }),
    qualified: Object.freeze({ mayInbound: true }),
    inboundPrepared: Object.freeze({ mayInbound: true }),
    rejected: Object.freeze({ mayInbound: false, terminal: true }),
  }),
  inbound: Object.freeze({
    planned: Object.freeze({ mayComplete: true }),
    pending: Object.freeze({ mayComplete: true }),
    completed: Object.freeze({ mayComplete: false, terminal: true }),
    done: Object.freeze({ mayComplete: false, terminal: true }),
  }),
})

export const SCM_ACTION_STATE_RULES = Object.freeze({
  submitPurchaseRequest: Object.freeze(['draft', 'rejected']),
  approvePurchaseRequest: Object.freeze(['submitted', 'reviewed', 'rechecked']),
  convertRequest: Object.freeze(['approved']),
  closePurchaseRequest: Object.freeze(['draft', 'submitted', 'reviewed', 'rechecked', 'approved']),
  sendPurchaseInquiry: Object.freeze(['draft']),
  confirmInquiryQuote: Object.freeze(['sent']),
  convertInquiry: Object.freeze(['approved', 'quoted']),
  closePurchaseInquiry: Object.freeze(['draft', 'sent', 'quoted', 'approved']),
  submitPriceApproval: Object.freeze(['draft', 'rejected']),
  approvePriceApproval: Object.freeze(['submitted', 'reviewed', 'rechecked']),
  rejectPriceApproval: Object.freeze(['submitted', 'reviewed', 'rechecked']),
  convertApproval: Object.freeze(['approved']),
  submitScmPurchaseOrder: Object.freeze(['draft']),
  approveScmPurchaseOrder: Object.freeze(['submitted', 'reviewed', 'rechecked']),
  issueScmPurchaseOrder: Object.freeze(['approved', 'converted']),
  goToWmsReceivePreview: Object.freeze(['issued', 'partiallyReceived']),
  closeScmPurchaseOrder: Object.freeze(['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted', 'issued']),
})

export function getScmDocumentStateRule(documentType, status) {
  return SCM_DOCUMENT_STATE_MATRIX[documentType]?.[status] || null
}

export function isScmActionAllowed(actionCode, status) {
  const statuses = SCM_ACTION_STATE_RULES[actionCode]
  return !statuses || statuses.includes(status)
}

export function evaluateScmStateCombination(documentType, status, capability) {
  const rule = getScmDocumentStateRule(documentType, status)
  if (!rule) return { result: 'FAIL', reason: `未登记状态：${documentType}.${status}` }
  if (!(capability in rule)) return { result: 'FAIL', reason: `状态未声明能力：${capability}` }
  return { result: 'PASS', allowed: Boolean(rule[capability]), reason: '' }
}
