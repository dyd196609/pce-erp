const editFields = ['decision', 'evidenceClass', 'basis']
const same = (left, right) => editFields.every(field => left?.[field] === right?.[field])

export function changedExecutionRows(rows, originalRows) {
  const old = new Map(originalRows.map(row => [row.stepId, row]))
  return rows.filter(row => !same(row, old.get(row.stepId)))
}

export function executionFieldIssues(rows, originalRows) {
  const old = new Map(originalRows.map(row => [row.stepId, row]))
  const issues = []
  for (const row of changedExecutionRows(rows, originalRows)) {
    const previous = old.get(row.stepId)
    const add = (field, message) => issues.push({ stepId: row.stepId, sequence: row.sequence, operationName: row.operationName, field, message: `第${row.sequence}步“${row.operationName}”：${message}` })
    if (!['REQUIRED', 'NOT_APPLICABLE', 'PENDING'].includes(row.decision)) add('decision', '请选择执行、不执行或待核定。')
    if (!['USER_CONFIRMED', 'TEST_ASSUMPTION', 'UNRESOLVED'].includes(row.evidenceClass)) add('evidenceClass', '请选择依据性质。')
    if (typeof row.basis !== 'string' || !row.basis.trim()) add('basis', '依据文字不能为空；尚未确定时可明确填写待核定事项。')
    if (row.decision !== 'PENDING' && row.evidenceClass === 'UNRESOLVED') add('evidenceClass', '执行状态已选执行或不执行，依据性质仍为“依据待核定”；请明确测试假设或业务依据，或把执行状态保留为待核定。')
    if (previous && (row.decision !== previous.decision || row.evidenceClass !== previous.evidenceClass) && String(row.basis ?? '').trim() === String(previous.basis ?? '').trim()) add('basis', '执行状态或依据性质已修改，依据文字仍是上次保存内容；请补充本次选择的具体依据，不会自动改成业务确认。')
  }
  return issues
}

export function draftErrorMessage(error) {
  const data = error?.response?.data
  const value = data?.message || data?.errorMessage || data?.error?.message || error?.message
  return typeof value === 'string' ? value : '服务端未完成保存核对，请保留输入并查看具体错误。'
}

// Keeps one immutable request key until a successful authoritative readback.
// Form data belongs to the caller and is never cleared or changed here.
export function createExecutionDraftSaver({ post, read, makeKey, assertIdentity, onState = () => {} }) {
  let pending = null
  let busy = false
  const emit = (status, extra = {}) => onState({ status, pending: Boolean(pending), ...extra })
  return {
    get hasPendingRequest() { return Boolean(pending) },
    async save({ arrangement, rows, originalRows, objectId = null, reason }) {
      if (busy) return { ok: false, message: '正在保存或核对结果，请勿重复操作。' }
      busy = true
      let phase = 'validation'
      const hadPendingRequest = Boolean(pending)
      try {
        assertIdentity(arrangement.requestIdentity)
        const fieldErrors = executionFieldIssues(rows, originalRows)
        if (fieldErrors.length) throw Object.assign(new Error('请核对下列工序字段；输入已保留，尚未提交。'), { fieldErrors })
        if (!String(reason || '').trim()) throw new Error('请填写保存按钮旁的“本次办理说明”；输入已保留，尚未提交。')
        const decisions = changedExecutionRows(rows, originalRows).map(row => ({ stepId: row.stepId, decision: row.decision, basis: row.basis, evidenceClass: row.evidenceClass, baselineItemId: objectId || null }))
        if (!decisions.length) throw new Error('没有工序字段发生变化，无需重复保存。')
        const body = { action: 'save', arrangementId: arrangement.id, decisions, expectedEditVersion: arrangement.editVersion, reason }
        const fingerprint = JSON.stringify(body)
        if (pending && pending.fingerprint !== fingerprint) throw new Error('上次提交结果尚未核实，请先核对该请求；不会以新请求覆盖未核实的结果。')
        if (!pending) pending = { fingerprint, payload: { ...JSON.parse(fingerprint), idempotencyKey: makeKey() }, source: { bomVersionId: arrangement.bomVersionId, routingVersionId: arrangement.routingVersionId, arrangementRevision: arrangement.arrangementRevision } }
        phase = 'sending'
        emit('saving')
        const result = await post(pending.payload)
        phase = 'readback'
        emit('verifying')
        const loaded = await read(arrangement.id, objectId)
        const value = loaded.arrangement
        if (!value) throw new Error('保存请求已返回，但服务端回读未取得安排；本地输入仍保留，请核对上次请求。')
        assertIdentity(value.requestIdentity)
        if (value.id !== arrangement.id || Object.entries(pending.source).some(([field, expected]) => value[field] !== expected)) throw new Error('保存后回读的来源或版本与原安排不一致，未替换本地输入，请核对。')
        if (value.editVersion !== result.editVersion) throw new Error('保存后安排又发生并发更新，编辑序号与提交结果不同；本地输入仍保留，请核对服务端。')
        for (const row of pending.payload.decisions) {
          const saved = value.steps.find(step => step.stepId === row.stepId)
          if (!saved || !same(saved, row) || (saved.baselineItemId || null) !== row.baselineItemId) throw new Error('保存后的工序回读与提交内容不一致；未显示保存成功，本地输入仍保留。')
        }
        pending = null
        const message = `保存成功，已从服务端重新读取；编辑序号${value.editVersion}，安排自身修订${value.arrangementRevision}，物料清单及标准路线版本保持。`
        emit('success', { message })
        return { ok: true, loaded, result, message }
      } catch (error) {
        const status = Number(error?.response?.status)
        if (!hadPendingRequest && phase === 'sending' && [400, 401, 403, 409, 422].includes(status)) pending = null
        const fieldErrors = error.fieldErrors || error?.response?.data?.fieldErrors || []
        const message = draftErrorMessage(error)
        emit(pending ? 'unverified' : 'error', { message, fieldErrors })
        return { ok: false, message, fieldErrors, pending: Boolean(pending) }
      } finally { busy = false }
    },
  }
}
