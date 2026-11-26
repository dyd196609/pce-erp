import { resolvePurchaseInquiryLifecycleStage } from './purchaseInquiryLifecycleStage.js'

const evidence = (code, label, value) => Object.freeze({ code, label, value: value ?? '—' })

export function createPurchaseInquiryLifecycleContext({ entryContext = {}, preparation = null, inquiry = null,
  quotationCount = 0 } = {}) {
  const stage = resolvePurchaseInquiryLifecycleStage({ entryContext, inquiry })
  const currentObject = inquiry ? Object.freeze({ objectType: 'PurchaseInquiry', objectNo: inquiry.inquiryNo,
    statusCode: inquiry.statusCode, statusLabel: inquiry.statusLabel })
    : preparation ? Object.freeze({ objectType: 'InquiryPreparationObject', objectNo: preparation.inquiryPreparationNo,
      statusCode: preparation.status, statusLabel: preparation.statusLabel })
      : Object.freeze({ objectType: 'PurchaseInquiry', objectNo: '尚未选择', statusCode: 'not_selected', statusLabel: '未选择' })
  const allowedActions = inquiry?.statusCode === 'draft' ? ['editInquiry', 'viewInquiry']
    : inquiry ? ['viewInquiry'] : preparation ? ['startInquiry'] : []
  return Object.freeze({
    contextCode: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_CONTEXT',
    businessSource: entryContext.businessSource,
    sourceNo: entryContext.sourceNo,
    preparationNo: preparation?.inquiryPreparationNo || entryContext.preparationNo || '',
    currentObject,
    operationArea: Object.freeze({ code: stage.code, title: `${stage.label}业务运作区`, mode: inquiry ? 'inquiry' : preparation ? 'preparation' : 'browse' }),
    lifecycleStage: stage,
    nextAction: stage.nextAction,
    allowedActions: Object.freeze(allowedActions),
    evidence: Object.freeze([
      evidence('source-trace', '来源链路', `${entryContext.businessSource} / ${entryContext.sourceNo}`),
      evidence('preparation-reference', '询价准备编号', preparation?.inquiryPreparationNo || '无'),
      evidence('material-lines', '物料明细', preparation?.materialLineCount ?? inquiry?.lineCount ?? 0),
      evidence('material-quantity', '物料数量', preparation?.materialQuantity ?? 0),
      evidence('supplier-candidates', '供应商候选', preparation?.supplierCandidateCount ?? inquiry?.supplierCount ?? 0),
      evidence('quotation-count', '报价数量', quotationCount),
    ]),
    protections: Object.freeze({ supplierSent: false, quotationCreated: false, purchaseOrderCreated: false, paymentCreated: false }),
  })
}

export function validatePurchaseInquiryLifecycleContext(context = {}) {
  const valid = context.contextCode === 'SCM_PURCHASE_INQUIRY_LIFECYCLE_CONTEXT'
    && Boolean(context.businessSource) && Boolean(context.sourceNo) && Boolean(context.currentObject?.objectType)
    && Boolean(context.operationArea?.code) && Boolean(context.lifecycleStage?.code)
    && Boolean(context.nextAction) && Array.isArray(context.evidence) && context.evidence.length >= 6
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
