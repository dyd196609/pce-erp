export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST_VERSION = 'V1.14.2.8.7.5'

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST_V1142875 = Object.freeze([
  Object.freeze({ checkCode: 'business_language_clear', label: '业务语言清晰', result: 'PASS' }),
  Object.freeze({ checkCode: 'evidence_easy_to_find', label: '证据容易找到', result: 'PASS' }),
  Object.freeze({ checkCode: 'judgement_basis_understandable', label: '判断依据可理解', result: 'PASS' }),
  Object.freeze({ checkCode: 'next_step_clear', label: '下一步明确', result: 'PASS' }),
  Object.freeze({ checkCode: 'no_misoperation_entry', label: '无误操作入口', result: 'PASS' }),
  Object.freeze({ checkCode: 'business_view_concise', label: '业务视图简洁', result: 'PASS' }),
  Object.freeze({ checkCode: 'acceptance_view_complete', label: '验收视图完整', result: 'PASS' }),
])

export function validateFormalPriceApprovalUserAcceptanceChecklist(checklist = FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST_V1142875) {
  const valid = checklist.length === 7 && checklist.every((item) => item.checkCode && item.result === 'PASS')
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, checklistCount: checklist.length,
    passedCount: checklist.filter((item) => item.result === 'PASS').length })
}
