export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST_VERSION = 'V1.14.2.8.7.6.2'

export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST = Object.freeze([
  Object.freeze({ code: 'business_language_clear', label: '业务语言是否清晰', result: 'NOT_REVIEWED' }),
  Object.freeze({ code: 'quotation_evidence_findable', label: '报价证据是否容易找到', result: 'NOT_REVIEWED' }),
  Object.freeze({ code: 'price_comparison_understandable', label: '价格比较是否容易理解', result: 'NOT_REVIEWED' }),
  Object.freeze({ code: 'approval_preparation_clear', label: '审批准备状态是否明确', result: 'NOT_REVIEWED' }),
  Object.freeze({ code: 'next_step_clear', label: '下一步提示是否清楚', result: 'NOT_REVIEWED' }),
  Object.freeze({ code: 'no_misoperation_entry', label: '没有误操作入口', result: 'NOT_REVIEWED' }),
  Object.freeze({ code: 'view_responsibility_clear', label: 'Business View 与 Acceptance View 职责清楚', result: 'NOT_REVIEWED' }),
])

export function validateFormalPriceApprovalHumanAcceptanceExecutionChecklist(checklist = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_EXECUTION_CHECKLIST) {
  const valid = checklist.length === 7 && checklist.every(item => Boolean(item.code) && Boolean(item.label)
    && ['PASS', 'FAIL', 'NOT_REVIEWED'].includes(item.result))
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, checklistCount: checklist.length })
}
