export async function submitManufacturingOutputGeneration({ confirm, request, refresh, readback,
  isSubmitting, setSubmitting }) {
  if (isSubmitting()) return { duplicateSuppressed: true }
  setSubmitting(true)
  try {
    await confirm()
    const response = await request()
    if (response?.success !== true) {
      const error = response?.error || {}
      throw new Error(`HTTP ${response?.meta?.status ?? 0}；${error.code || 'REQUEST_FAILED'}：${error.message || '服务端未确认制造输出生成成功。'}`)
    }
    const result = response.data?.result
    if (!result?.row?.id || result.row.statusCode !== 'draft' || !result.auditId
      || !result.writeRequestId || !result.initializationTransitionId || result.manufacturingReleaseExecuted !== false) {
      throw new Error('MANUFACTURING_OUTPUT_SUCCESS_CONTRACT_INVALID：生成响应没有完整草稿、写入请求、审计和初始化事实。')
    }
    await refresh()
    const candidate = readback()
    const proof = candidate?.output?.generationReadback
    const selectedOutputCount = candidate?.selectedOutputCount ?? candidate?.outputCount
    const selected = candidate?.selection
    if (candidate?.output?.id !== result.row.id || candidate.output.statusCode !== 'draft'
      || selectedOutputCount !== 1 || !proof?.completed || proof.writeRequestId !== result.writeRequestId
      || (selected?.engineeringDocumentVersionId != null
        && (selected.engineeringDocumentVersionId !== result.row.engineeringDocumentVersionId
          || candidate.output.engineeringDocumentVersionId !== result.row.engineeringDocumentVersionId))
      || (selected?.predecessorOutputId != null
        && (selected.predecessorOutputId !== result.row.predecessorOutputId
          || candidate.output.predecessorOutputId !== result.row.predecessorOutputId))
      || proof.auditId !== result.auditId || proof.initializationTransitionId !== result.initializationTransitionId) {
      throw new Error('MANUFACTURING_OUTPUT_READBACK_MISMATCH：服务端响应与刷新后的正式制造输出事实不一致，请核实；不得重复生成。')
    }
    return { result, candidate }
  } finally {
    setSubmitting(false)
  }
}

export async function submitManufacturingOutputRelease({ confirm, request, refresh, readback,
  isSubmitting, setSubmitting }) {
  if (isSubmitting()) return { duplicateSuppressed: true }
  setSubmitting(true)
  try {
    await confirm()
    const response = await request()
    if (response?.success !== true) {
      const error = response?.error || {}
      throw new Error(`HTTP ${response?.meta?.status ?? 0}；${error.code || 'REQUEST_FAILED'}：${error.message || '服务端未确认制造发布成功。'}`)
    }
    const result = response.data?.result
    if (!result?.row?.id || result.row.statusCode !== 'released_to_manufacturing' || !result.auditId
      || !result.writeRequestId || !result.businessStateTransitionId || !result.releaseReadback?.completed) {
      throw new Error('MANUFACTURING_RELEASE_SUCCESS_CONTRACT_INVALID：发布响应没有完整状态转换、请求和审计事实。')
    }
    await refresh()
    const candidate = readback()
    const proof = candidate?.manufacturingRelease?.releaseReadback
    if (candidate?.output?.id !== result.row.id || candidate.output.statusCode !== 'released_to_manufacturing'
      || !proof?.completed || proof.writeRequestId !== result.writeRequestId || proof.auditId !== result.auditId
      || proof.businessStateTransitionId !== result.businessStateTransitionId) {
      throw new Error('MANUFACTURING_RELEASE_READBACK_MISMATCH：发布回执与正式状态回读不一致；请核实，不得重复发布。')
    }
    return { result, candidate }
  } finally { setSubmitting(false) }
}
