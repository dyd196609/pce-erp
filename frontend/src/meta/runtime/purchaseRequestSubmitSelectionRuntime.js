import { evaluatePurchaseRequestActionGuard } from '../process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

export const PURCHASE_REQUEST_SUBMIT_SELECTION_VERSION = 'V1.14.2.8.7.8.1'
export const PURCHASE_REQUEST_ROW_KEY = 'requestNo'

export function normalizePurchaseRequestSelection(selection = []) {
  const selectedByRequestNo = new Map()
  for (const row of Array.isArray(selection) ? selection : []) {
    const requestNo = String(row?.requestNo || '').trim()
    if (requestNo && !selectedByRequestNo.has(requestNo)) selectedByRequestNo.set(requestNo, row)
  }
  return Object.freeze([...selectedByRequestNo.values()])
}

export function assessPurchaseRequestSubmit(row = {}) {
  if (!row?.objectId) {
    return Object.freeze({ allowed: false, code: 'PURCHASE_REQUEST_ID_REQUIRED', reason: '采购申请缺少服务端对象标识，无法提交' })
  }
  if (!evaluatePurchaseRequestActionGuard(row, 'SUBMIT_APPROVAL').allowed) {
    return Object.freeze({ allowed: false, code: 'PURCHASE_REQUEST_NOT_DRAFT', reason: '只有草稿状态采购申请允许提交审批' })
  }
  return Object.freeze({ allowed: true, code: 'PURCHASE_REQUEST_SUBMIT_ALLOWED', reason: '草稿采购申请允许由已登录用户提交' })
}

export function resolvePurchaseRequestSubmitFailure(response = {}) {
  const status = Number(response?.meta?.status || response?.httpStatus || 0)
  if (status === 401) return '登录状态已失效，请重新登录后提交采购申请'
  if (status === 403) return '当前登录身份没有采购申请提交权限，请重新登录或联系系统管理员'
  if (status === 409) return response?.error?.message || '采购申请状态已变化，请刷新列表后重试'
  return response?.error?.message || '采购申请提交失败，请刷新后重试'
}

export function validatePurchaseRequestSubmitSelectionRuntime() {
  const secondRow = { objectId: 2, requestNo: 'PR202608020008', statusCode: 'draft' }
  const oneSelected = normalizePurchaseRequestSelection([secondRow])
  const currentPage = [
    { objectId: 1, requestNo: 'PR202608020007', statusCode: 'draft' },
    secondRow,
    { objectId: 3, requestNo: 'PR202608020009', statusCode: 'submitted' },
  ]
  const allSelected = normalizePurchaseRequestSelection(currentPage)
  const valid = PURCHASE_REQUEST_ROW_KEY === 'requestNo'
    && oneSelected.length === 1 && oneSelected[0].requestNo === 'PR202608020008'
    && allSelected.length === currentPage.length
    && assessPurchaseRequestSubmit(secondRow).allowed === true
    && assessPurchaseRequestSubmit({ ...secondRow, statusCode: 'submitted' }).allowed === false
    && resolvePurchaseRequestSubmitFailure({ meta: { status: 403 } }).includes('权限')
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', singleSelectedCount: oneSelected.length, selectAllCount: allSelected.length })
}
