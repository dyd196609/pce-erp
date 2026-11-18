const REVIEWED_STATUS_LABEL = '已评审'

function numericId(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function responseErrorValue(response) {
  const error = response?.error
  if (error && typeof error === 'object') return error
  if (typeof error === 'string') return { message: error }
  return {}
}

function failureCategory(httpStatus) {
  if (httpStatus === 0) return '请求未发送或网络中断'
  if (httpStatus === 400 || httpStatus === 422) return '输入或业务校验未通过'
  if (httpStatus === 401) return '登录认证已失效'
  if (httpStatus === 403) return '正式评审权限被拒绝'
  if (httpStatus === 409) return '业务状态或幂等冲突'
  if (httpStatus >= 500) return '服务端事务处理失败'
  return '工程资料版本正式评审未成功'
}

export class EngineeringDocumentReviewSubmissionError extends Error {
  constructor({ code, message, httpStatus = 0, category, details = {} }) {
    super(message)
    this.name = 'EngineeringDocumentReviewSubmissionError'
    this.code = code
    this.httpStatus = Number(httpStatus) || 0
    this.category = category || failureCategory(this.httpStatus)
    this.details = details
    const statusText = this.httpStatus ? `HTTP ${this.httpStatus}；` : ''
    this.userMessage = `${this.category}（${statusText}错误码 ${this.code}）：${this.message}`
  }
}

export function reviewSubmissionFailureFromResponse(response) {
  const error = responseErrorValue(response)
  const httpStatus = Number(
    response?.meta?.status
    ?? response?.factLoadFacts?.httpStatus
    ?? response?.httpStatus
    ?? 0,
  ) || 0
  const code = String(
    error.code
    || response?.errorCode
    || response?.factLoadFacts?.errorCode
    || (httpStatus ? `HTTP_${httpStatus}` : 'ENGINEERING_DOCUMENT_REVIEW_REQUEST_FAILED'),
  )
  const message = String(
    error.message
    || response?.errorMessage
    || response?.factLoadFacts?.errorMessage
    || '服务端未确认工程资料版本正式评审成功。',
  )
  return new EngineeringDocumentReviewSubmissionError({
    code,
    message,
    httpStatus,
    details: error.details || {},
  })
}

export function reviewSubmissionFailureFromThrown(error) {
  if (error instanceof EngineeringDocumentReviewSubmissionError) return error
  const response = error?.response
  if (response) {
    return reviewSubmissionFailureFromResponse({
      success: false,
      error: response.data?.error || { code: error.code, message: error.message },
      meta: { status: response.status },
      factLoadFacts: response.data?.factLoadFacts,
    })
  }
  return new EngineeringDocumentReviewSubmissionError({
    code: String(error?.code || 'NETWORK_READ_FAILED'),
    message: String(error?.message || '请求未发送或网络连接失败。'),
    httpStatus: 0,
  })
}

function assertCommittedResult(response, versionId) {
  const result = response?.data?.result
  const version = result?.engineeringDocumentVersion
  const workflow = result?.workflow
  const transition = result?.businessStateTransition
  const valid = (
    numericId(version?.engineeringDocumentVersionId) === numericId(versionId)
    && version?.status === 'reviewed'
    && workflow?.statusCode === 'approved'
    && numericId(workflow?.instanceId)
    && numericId(workflow?.decisionId)
    && numericId(transition?.id)
    && transition?.fromState === 'draft'
    && transition?.toState === 'reviewed'
    && numericId(transition?.workflowInstanceId) === numericId(workflow?.instanceId)
    && numericId(result?.writeRequestId)
    && numericId(result?.auditId)
  )
  if (!valid) {
    throw new EngineeringDocumentReviewSubmissionError({
      code: 'ENGINEERING_DOCUMENT_REVIEW_SUCCESS_CONTRACT_INVALID',
      message: '请求返回成功，但未同时返回已提交的版本状态、Workflow决定、状态转换、审计和写入请求证据。',
      httpStatus: Number(response?.meta?.status) || 200,
    })
  }
  return result
}

function assertFormalReadback(row, versionId, result) {
  const readback = row?.reviewPreflight?.reviewReadback
  const workflow = result.workflow
  const valid = (
    numericId(row?.engineeringDocumentVersionId) === numericId(versionId)
    && row?.documentVersionStatusLabel === REVIEWED_STATUS_LABEL
    && readback?.completed === true
    && readback?.projectionState === 'workflow_approved'
    && readback?.projectionConsistent === true
    && numericId(readback?.workflowInstanceId) === numericId(workflow.instanceId)
    && numericId(readback?.decisionId) === numericId(workflow.decisionId)
    && numericId(readback?.businessStateTransitionId) === numericId(result.businessStateTransition.id)
  )
  if (!valid) {
    throw new EngineeringDocumentReviewSubmissionError({
      code: 'ENGINEERING_DOCUMENT_REVIEW_READBACK_MISMATCH',
      message: '服务端曾返回评审成功，但刷新后未回读到同一版本的已评审状态和一致的Workflow、Decision及状态转换事实；不得宣称评审完成。',
      httpStatus: 200,
      details: { versionId, result, readback: row || null },
    })
  }
  return readback
}

export async function submitEngineeringDocumentVersionReview({
  versionId,
  confirmSubmission,
  requestReview,
  refreshFacts,
  getFormalReadback,
  isSubmitting = () => false,
  setSubmitting = () => {},
}) {
  if (isSubmitting()) return { duplicateSuppressed: true }
  setSubmitting(true)
  try {
    await confirmSubmission()
    let response
    try {
      response = await requestReview()
    } catch (error) {
      throw reviewSubmissionFailureFromThrown(error)
    }
    if (!response || response.success !== true) {
      throw reviewSubmissionFailureFromResponse(response)
    }
    const result = assertCommittedResult(response, versionId)
    await refreshFacts()
    const row = getFormalReadback()
    const readback = assertFormalReadback(row, versionId, result)
    return { response, result, row, readback, duplicateSuppressed: false }
  } finally {
    setSubmitting(false)
  }
}
