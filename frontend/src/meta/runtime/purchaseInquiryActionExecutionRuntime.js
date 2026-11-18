import { evaluateActionExecutionAcceptance } from '../process/runtime/actionExecutionAcceptanceFramework.js'
import { evaluatePurchaseInquiryPageAction } from '../process/scm/purchaseInquiry/purchaseInquiryPageActionContract.js'
import { ensurePurchaseInquiryRuntimeDraft, listPurchaseInquiryRuntimeObjects } from './purchaseInquiryRuntime.js'
import { executePurchaseInquiryNextAction } from './purchaseInquiryNextActionRuntime.js'

export const PURCHASE_INQUIRY_ACTION_EXECUTION_RUNTIME_VERSION = 'V1.14.2.8.18.5'
const CONTEXT_KEY = 'pce.scm.purchase-inquiry.action-execution.v11428185'
const memoryContexts = new Map()
const storage = () => typeof window !== 'undefined' ? window.sessionStorage : null

export const PURCHASE_INQUIRY_ACTION_TARGETS = Object.freeze({
  VIEW_PURCHASE_INQUIRY: Object.freeze({ buttonCode: 'view-purchase-inquiry', pageCode: 'purchase-inquiry-detail',
    pageName: '询价详情', route: inquiryNo => `/scm/purchase-inquiry/detail/${encodeURIComponent(inquiryNo)}` }),
  EDIT_PURCHASE_INQUIRY: Object.freeze({ buttonCode: 'edit-purchase-inquiry', pageCode: 'purchase-inquiry-edit',
    pageName: '编辑询价', route: inquiryNo => `/scm/purchase-inquiry/edit/${encodeURIComponent(inquiryNo)}` }),
  PREPARE_SUPPLIER_QUOTE: Object.freeze({ buttonCode: 'prepare-supplier-quote', pageCode: 'purchase-inquiry-acceptance',
    pageName: '询价下一流程验收', route: inquiryNo => `/scm/purchase-inquiry/acceptance/${encodeURIComponent(inquiryNo)}` }),
})

function writeContext(context) {
  memoryContexts.set(context.objectId, context)
  try { storage()?.setItem(CONTEXT_KEY, JSON.stringify(context)) } catch { /* memory fallback */ }
}

export function executePurchaseInquiryAction({ inquiry = {}, actionCode = '' } = {}) {
  const target = PURCHASE_INQUIRY_ACTION_TARGETS[actionCode]
  const nextExecution = actionCode === 'PREPARE_SUPPLIER_QUOTE'
    ? executePurchaseInquiryNextAction(inquiry, actionCode) : null
  const contractDecision = actionCode === 'PREPARE_SUPPLIER_QUOTE'
    ? { allowed: nextExecution?.allowed === true }
    : evaluatePurchaseInquiryPageAction(inquiry, actionCode)
  if (!target || !contractDecision.allowed) return Object.freeze({ result: 'FAIL', allowed: false, actionCode })
  const runtimeInquiry = actionCode === 'PREPARE_SUPPLIER_QUOTE' ? nextExecution.inquiry
    : actionCode === 'EDIT_PURCHASE_INQUIRY' ? ensurePurchaseInquiryRuntimeDraft(inquiry) : inquiry
  const context = Object.freeze({ contextId: `PI-ACTION-${actionCode}-${inquiry.inquiryNo}`,
    actionCode, objectType: 'PurchaseInquiry', objectId: inquiry.inquiryNo, inquiry: runtimeInquiry,
    route: target.route(inquiry.inquiryNo), targetPageCode: target.pageCode, targetPageName: target.pageName,
    quotePreparationContext: nextExecution?.quotePreparationContext || null,
    createdAt: new Date().toISOString(), productionDataWritten: false })
  writeContext(context)
  const acceptance = evaluateActionExecutionAcceptance({ ...context, buttonCode: target.buttonCode,
    contractCode: actionCode === 'PREPARE_SUPPLIER_QUOTE'
      ? 'SCM_PURCHASE_INQUIRY_NEXT_ACTION_CONTRACT' : 'SCM_PURCHASE_INQUIRY_PAGE_ACTION_CONTRACT',
    contractAllowed: contractDecision.allowed })
  return Object.freeze({ result: acceptance.valid ? 'PASS' : 'FAIL', allowed: acceptance.valid,
    actionCode, route: context.route, context, acceptance })
}

export function loadPurchaseInquiryActionExecutionContext(inquiryNo = '') {
  const memory = memoryContexts.get(inquiryNo)
  if (memory) return memory
  try {
    const persisted = JSON.parse(storage()?.getItem(CONTEXT_KEY) || 'null')
    if (persisted?.objectId === inquiryNo) return Object.freeze(persisted)
  } catch { /* use runtime object fallback */ }
  const inquiry = listPurchaseInquiryRuntimeObjects().find(item => item.inquiryNo === inquiryNo)
  return inquiry ? Object.freeze({ contextId: `PI-RUNTIME-${inquiryNo}`, actionCode: 'DIRECT_RUNTIME_LOAD',
    objectType: 'PurchaseInquiry', objectId: inquiryNo, inquiry, productionDataWritten: false }) : null
}
