export const PURCHASE_INQUIRY_LIFECYCLE_STAGE_VERSION = 'V1.14.2.8.7.13'

export const PURCHASE_INQUIRY_LIFECYCLE_STAGES = Object.freeze([
  Object.freeze({ code: 'browse_only', label: '询价浏览', statusLabel: '未选择询价对象', nextAction: '选择已有询价' }),
  Object.freeze({ code: 'preparation_ready', label: '询价准备', statusLabel: '询价准备完成', nextAction: '启动询价' }),
  Object.freeze({ code: 'inquiry_draft', label: '正式询价', statusLabel: '草稿', nextAction: '编辑询价' }),
  Object.freeze({ code: 'inquiry_view', label: '正式询价', statusLabel: '查看中', nextAction: '查看询价' }),
])

export function resolvePurchaseInquiryLifecycleStage({ entryContext = {}, inquiry = null } = {}) {
  if (inquiry?.statusCode === 'draft') return PURCHASE_INQUIRY_LIFECYCLE_STAGES[2]
  if (inquiry) return Object.freeze({ ...PURCHASE_INQUIRY_LIFECYCLE_STAGES[3], statusLabel: inquiry.statusLabel || '查看中' })
  if (entryContext.entryType === 'purchase_request_preparation') return PURCHASE_INQUIRY_LIFECYCLE_STAGES[1]
  return PURCHASE_INQUIRY_LIFECYCLE_STAGES[0]
}

export function validatePurchaseInquiryLifecycleStage(stage = {}) {
  const valid = Boolean(stage.code) && Boolean(stage.label) && Boolean(stage.statusLabel) && Boolean(stage.nextAction)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
