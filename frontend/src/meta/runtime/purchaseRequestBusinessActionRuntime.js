import { evaluatePurchaseRequestActionGuard } from '../process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

export const PURCHASE_REQUEST_BUSINESS_ACTION_VERSION = 'V1.14.2.8.7.8.2'

export const PURCHASE_REQUEST_ACTIONS = Object.freeze({
  submit: Object.freeze({
    action: 'submit',
    label: '提交',
    sourceStatus: 'draft',
    targetStatus: 'submitted',
    permissionCode: 'purchase_request.submit',
  }),
  approve: Object.freeze({
    action: 'approve',
    label: '审批',
    sourceStatus: 'submitted',
    targetStatus: 'approved',
    permissionCode: 'purchase_request.approve',
  }),
})

export function assessPurchaseRequestAction(row = {}, action = '') {
  const definition = PURCHASE_REQUEST_ACTIONS[action]
  if (!definition) return Object.freeze({ allowed: false, code: 'ACTION_NOT_SUPPORTED', reason: '不支持的采购申请业务动作' })
  if (!row?.objectId || !String(row?.requestNo || '').trim()) {
    return Object.freeze({ allowed: false, code: 'OBJECT_REFERENCE_REQUIRED', reason: '采购申请缺少服务端对象标识' })
  }
  const canonicalAction = action === 'submit' ? 'SUBMIT_APPROVAL' : 'APPROVE'
  const stateGuard = evaluatePurchaseRequestActionGuard(row, canonicalAction)
  if (!stateGuard.allowed) {
    const reason = action === 'submit' ? '只有草稿状态采购申请允许提交' : '只有已提交采购申请允许审批'
    return Object.freeze({ allowed: false, code: 'STATUS_NOT_ALLOWED', reason })
  }
  return Object.freeze({ allowed: true, code: 'ACTION_ALLOWED', reason: `${definition.label}校验通过`, definition })
}

export function resolvePurchaseRequestActionFailure(response = {}, action = '') {
  const status = Number(response?.meta?.status || response?.httpStatus || 0)
  const label = PURCHASE_REQUEST_ACTIONS[action]?.label || '操作'
  if (status === 401) return `未登录，无法执行采购申请${label}`
  if (status === 403) return `当前登录身份缺少 ${PURCHASE_REQUEST_ACTIONS[action]?.permissionCode || '采购申请动作'} 权限`
  if (status === 409) return response?.error?.message || `采购申请状态不允许${label}`
  return response?.error?.message || `采购申请${label}失败`
}

export async function executePurchaseRequestBatchAction({ rows = [], action, executor, authenticationReady = true } = {}) {
  const selected = Array.isArray(rows) ? rows : []
  const successes = []
  const failures = []
  if (!authenticationReady) {
    return Object.freeze({ action, totalCount: selected.length, successCount: 0, failureCount: selected.length,
      successes: Object.freeze([]), failures: Object.freeze(selected.map(row => Object.freeze({ requestNo: row?.requestNo || '', reason: `未登录，无法执行采购申请${PURCHASE_REQUEST_ACTIONS[action]?.label || '操作'}` }))), businessWriteCount: 0 })
  }
  for (const row of selected) {
    const assessment = assessPurchaseRequestAction(row, action)
    if (!assessment.allowed) {
      failures.push(Object.freeze({ requestNo: row?.requestNo || '', reason: assessment.reason }))
      continue
    }
    try {
      const response = await executor(row, action)
      if (!response?.success) {
        failures.push(Object.freeze({ requestNo: row.requestNo, reason: resolvePurchaseRequestActionFailure(response, action) }))
        continue
      }
      const statusCode = response?.data?.status || response?.data?.statusCode
      if (statusCode !== PURCHASE_REQUEST_ACTIONS[action].targetStatus) {
        failures.push(Object.freeze({ requestNo: row.requestNo, reason: `${assessment.definition.label}返回状态不符合预期` }))
        continue
      }
      successes.push(Object.freeze({ requestNo: row.requestNo, statusCode }))
    } catch (error) {
      failures.push(Object.freeze({ requestNo: row.requestNo, reason: error?.message || `${assessment.definition.label}失败` }))
    }
  }
  return Object.freeze({
    action,
    totalCount: selected.length,
    successCount: successes.length,
    failureCount: failures.length,
    successes: Object.freeze(successes),
    failures: Object.freeze(failures),
    businessWriteCount: successes.length * 2,
  })
}

export async function validatePurchaseRequestBusinessActionRuntime() {
  const draftRows = [1, 2, 3].map(index => ({ objectId: index, requestNo: `PR-BATCH-${index}`, statusCode: 'draft' }))
  const submittedRows = draftRows.map(row => ({ ...row, statusCode: 'submitted' }))
  const submit = await executePurchaseRequestBatchAction({ rows: draftRows, action: 'submit', executor: async row => ({ success: true, data: { requestNo: row.requestNo, status: 'submitted' } }) })
  const approve = await executePurchaseRequestBatchAction({ rows: submittedRows, action: 'approve', executor: async row => ({ success: true, data: { requestNo: row.requestNo, status: 'approved', approvalStatus: 'approved' } }) })
  const valid = submit.successCount === 3 && submit.businessWriteCount === 6
    && approve.successCount === 3 && approve.businessWriteCount === 6
    && assessPurchaseRequestAction(draftRows[0], 'approve').allowed === false
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', submit, approve })
}
