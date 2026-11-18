const RELEASED_STATUS_LABEL = '已发布'

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
  if (httpStatus === 400 || httpStatus === 422) return '输入或发布准入未通过'
  if (httpStatus === 401) return '登录认证已失效'
  if (httpStatus === 403) return '工程资料版本发布权限被拒绝'
  if (httpStatus === 409) return '业务状态或幂等冲突'
  if (httpStatus >= 500) return '服务端发布事务处理失败'
  return '工程资料版本正式发布未成功'
}

export class EngineeringDocumentReleaseSubmissionError extends Error {
  constructor({ code, message, httpStatus = 0, category, details = {} }) {
    super(message)
    this.name = 'EngineeringDocumentReleaseSubmissionError'
    this.code = code
    this.httpStatus = Number(httpStatus) || 0
    this.category = category || failureCategory(this.httpStatus)
    this.details = details
    const statusText = this.httpStatus ? `HTTP ${this.httpStatus}；` : ''
    this.userMessage = `${this.category}（${statusText}错误码 ${this.code}）：${this.message}`
  }
}

function failureFromResponse(response) {
  const error = responseErrorValue(response)
  const httpStatus = Number(
    response?.meta?.status
    ?? response?.factLoadFacts?.httpStatus
    ?? response?.httpStatus
    ?? 0,
  ) || 0
  return new EngineeringDocumentReleaseSubmissionError({
    code: String(
      error.code
      || response?.errorCode
      || response?.factLoadFacts?.errorCode
      || (httpStatus ? `HTTP_${httpStatus}` : 'ENGINEERING_DOCUMENT_RELEASE_REQUEST_FAILED'),
    ),
    message: String(
      error.message
      || response?.errorMessage
      || response?.factLoadFacts?.errorMessage
      || '服务端未确认工程资料版本正式发布成功。',
    ),
    httpStatus,
    details: error.details || {},
  })
}

function failureFromThrown(error) {
  if (error instanceof EngineeringDocumentReleaseSubmissionError) return error
  const response = error?.response
  if (response) {
    return failureFromResponse({
      success: false,
      error: response.data?.error || { code: error.code, message: error.message },
      meta: { status: response.status },
      factLoadFacts: response.data?.factLoadFacts,
    })
  }
  return new EngineeringDocumentReleaseSubmissionError({
    code: String(error?.code || 'NETWORK_READ_FAILED'),
    message: String(error?.message || '请求未发送或网络连接失败。'),
    httpStatus: 0,
  })
}

function assertCommittedResult(response, versionId) {
  const result = response?.data?.result
  const version = result?.engineeringDocumentVersion
  const transition = result?.businessStateTransition
  const valid = (
    numericId(version?.engineeringDocumentVersionId) === numericId(versionId)
    && version?.status === 'released'
    && numericId(transition?.id)
    && transition?.fromState === 'reviewed'
    && transition?.toState === 'released'
    && numericId(result?.writeRequestId)
    && numericId(result?.auditId)
    && result?.manufacturingReleaseExecuted === false
  )
  if (!valid) {
    throw new EngineeringDocumentReleaseSubmissionError({
      code: 'ENGINEERING_DOCUMENT_RELEASE_SUCCESS_CONTRACT_INVALID',
      message: '请求返回成功，但未同时返回版本状态、状态转换、审计、写入请求和制造发布隔离证据。',
      httpStatus: Number(response?.meta?.status) || 200,
    })
  }
  return result
}

function assertFormalReadback(row, versionId, result) {
  const readback = row?.documentReleasePreflight?.releaseReadback
  const valid = (
    numericId(row?.engineeringDocumentVersionId) === numericId(versionId)
    && row?.documentVersionStatusLabel === RELEASED_STATUS_LABEL
    && readback?.completed === true
    && numericId(readback?.businessStateTransitionId)
      === numericId(result.businessStateTransition.id)
    && numericId(readback?.writeRequestId) === numericId(result.writeRequestId)
    && readback?.manufacturingReleaseExecuted === false
  )
  if (!valid) {
    throw new EngineeringDocumentReleaseSubmissionError({
      code: 'ENGINEERING_DOCUMENT_RELEASE_READBACK_MISMATCH',
      message: '服务端曾返回发布成功，但刷新后未回读到同一版本的正式发布事实；不得宣称发布完成。',
      httpStatus: 200,
      details: { versionId, result, readback: row || null },
    })
  }
  return readback
}

export async function submitEngineeringDocumentVersionRelease({
  versionId,
  confirmSubmission,
  requestRelease,
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
      response = await requestRelease()
    } catch (error) {
      throw failureFromThrown(error)
    }
    if (!response || response.success !== true) {
      throw failureFromResponse(response)
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
