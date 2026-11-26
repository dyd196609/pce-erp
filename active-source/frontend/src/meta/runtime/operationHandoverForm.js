// This module constructs explicit user intent. It never calculates available
// stock, production, custody or permission. Every such displayed fact is native.
const id = (value, label) => { const result = Number(value); if (!Number.isSafeInteger(result) || result < 1) throw new Error(`请选择${label}。`); return result }
const exactText = (value, label) => { const result = String(value ?? '').trim(); if (!result) throw new Error(`请填写${label}。`); return result }
const quantity = value => { const result = exactText(value, '本次真实数量'); if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(result)) throw new Error('本次数量须为规范十进制文本，不能使用科学计数或负数。'); return result }
export function decimalIntentAtoms(value, precision) {
  const decimal = quantity(value), [whole, fraction = ''] = decimal.split('.')
  if (!Number.isSafeInteger(precision) || precision < 0 || precision > 12 || fraction.length > precision) throw new Error('本次输入超出正式单位精度；不会四舍五入、补齐或截断。')
  return BigInt(whole + fraction.padEnd(precision, '0'))
}
const slices = rows => rows.filter(row => row.selected).map(row => ({ sliceId: id(row.sliceId, '真实份额'), expectedVersion: row.expectedVersion, quantity: quantity(row.quantity) }))
const inputSlices = (rows,precision) => rows.filter(row => row.selected).map(row => {
  const begin=decimalIntentAtoms(row.outputRangeStart,precision),end=decimalIntentAtoms(row.outputRangeEnd,precision)
  if(end<=begin)throw new Error('请明确本来源实际对应的新产出准确区间，终点必须大于起点。')
  return { sliceId: id(row.sliceId, '真实投入份额'), expectedVersion: row.expectedVersion, quantity: quantity(row.quantity),
    evidenceReference: exactText(row.evidenceReference, '真实投入范围依据'), outputRange:{startAtom:String(begin),endAtom:String(end)} }
})
export function emptyHandoverForm() {
  return { key: '', reason: '', occurredAt: '', batchLabel: '', scopeReference: '', scopeRange: '', quantity: '',
    sourceWorkCenterId: '', rangeTargetMode:'', reportAllocations: [], inputAllocations: [], rangeAllocations: [], deliveries: [], receipts: [],
    inputPurpose: { enabled: false, taskId: '', operationId: '', workCenterId: '', reference: '' }, decision: '',
    previousHandoverId: '', exceptionId: '', exceptionKind: '', resolution: '', evidenceReference: '', sliceId: '',
    actualCustodianWorkCenterId: '', holderReference: '', allocationId: '', matchedAllocationId: '', confirmationReference: '', outputId: '', correctionSign: '', expectedVersion: null,
    expectedSourceSnapshotHash: null, formContext: null }
}
export function newHandoverDelivery() { return { targetWorkCenterId: '', targetOperationId: '', destinationKind: '', destinationReference: '', purpose: '', sliceAllocations: [] } }
export function buildHandoverPayload(facts, form) {
  const key = form.key, task = facts.selectedTask || facts.selectedCustodySource, header = facts.selectedHandover, account = facts.selectedQuantityAccount, exception = facts.selectedException
  const reason = exactText(form.reason, '本次真实原因'), output = facts.selectedOutput
  const outputPrecision=account?.uom?.decimalPlaces
  const occurredAt = () => exactText(form.occurredAt, '实际发生时间（含时区）')
  const headerExpected = () => ({ expectedVersion: header?.version, expectedSourceSnapshotHash: header?.sourceSnapshotHash })
  const taskExpected = () => { if (!task?.expectations) throw new Error('本次任务未取得完整正式提交期望，不能按目录或旧事实补齐。'); return {...task.expectations} }
  if (['confirm', 'excess.report'].includes(key)) {
    if (task?.quantityApplicable !== true) throw new Error('本工序无独立统计量，不能填写本节点产量或用工程参考量创建产出。')
    const manifest = { reference: exactText(form.scopeReference, '批次清单引用'), range: exactText(form.scopeRange, '准确实物范围') }
    if (key==='confirm' && form.inputPurpose.enabled) manifest.inputPurpose = { taskId: id(form.inputPurpose.taskId, '投入目标任务'),
      operationId: id(form.inputPurpose.operationId, '投入目标工序'), workCenterId: id(form.inputPurpose.workCenterId, '投入目标工作中心'), reference: exactText(form.inputPurpose.reference, '投入用途依据') }
    const payload = { ...taskExpected(), reason, occurredAt: occurredAt(), batchLabel: exactText(form.batchLabel, '真实批次标识'), scopeManifest: manifest }
    const inputs = key==='confirm' ? inputSlices(form.inputAllocations,outputPrecision) : []; if (inputs.length) payload.inputAllocations = inputs
    if (key === 'excess.report') payload.quantity = quantity(form.quantity)
    else {
      payload.reportAllocations = form.reportAllocations.filter(row => row.selected).map(row => {
        const begin = BigInt(row.startAtom), count = decimalIntentAtoms(row.quantity, row.quantityPrecision)
        if (count <= 0n) throw new Error('本次确认分量必须大于0。')
        return { reportId: id(row.reportId, '正式报工'), startAtom: String(begin), endAtom: String(begin + count) }
      })
      if (!payload.reportAllocations.length) throw new Error('请明确选择正式报工的真实未定位范围并填写本次确认量。')
    }
    return payload
  }
  if (key === 'excess.review') {
    if(!Number.isSafeInteger(output?.workflowVersion)||!Number.isSafeInteger(output?.approvalTaskVersion))throw new Error('所选产出尚未取得正式独立审核对象，请重新读取准确声明。')
    if (!['approve', 'reject'].includes(form.decision)) throw new Error('请选择本次超产事实的确认或拒绝意见。')
    if(form.decision==='approve' && facts.availableActions?.[key]?.approvalReady===false)throw new Error(facts.availableActions[key].approvalDisabledReason || '本次服务端尚未允许确认该超产事实；可核查或明确拒绝。')
    return { expectedVersion: output?.version, expectedSourceSnapshotHash: output?.sourceSnapshotHash,
      expectedWorkflowVersion: output?.workflowVersion, expectedApprovalTaskVersion: output?.approvalTaskVersion,
      decision: form.decision, reason }
  }
  if(key==='range.release') {
    if(Array.isArray(facts.custodyContexts) && Number(form.sourceWorkCenterId)!==facts.selectedCustodyWorkCenterId)throw new Error('请先明确读取当前真实保管中心，再填写本次范围用途。')
    const ranges=slices(form.rangeAllocations);if(!ranges.length)throw new Error('请选择当前在手真实份额并填写本次明确释放的范围量。')
    if(!['center','task'].includes(form.rangeTargetMode))throw new Error('请明确本工单责任中心范围，或真实已派后序定量投入任务；不会自动创建任务。')
    return {taskId:id(task?.taskId ?? task?.id,'原定量来源任务'),sourceWorkCenterId:id(form.sourceWorkCenterId,'实际保管工作中心'),
      expectedSourceSnapshotHash:task.expectations?.expectedSourceSnapshotHash || task.sourceSnapshotHash,
      expectedAccountSnapshotHash:account?.accountSnapshotHash || facts.custodyAccountSnapshotHash,
      targetTaskId:form.rangeTargetMode==='task'?id(form.inputPurpose.taskId,'真实后序目标任务'):null,
      targetOperationId:form.inputPurpose.operationId?id(form.inputPurpose.operationId,'真实目标工序'):null,
      targetWorkCenterId:id(form.inputPurpose.workCenterId,'真实目标工作中心'),scopeReference:exactText(form.inputPurpose.reference,'本次真实范围用途依据'),
      sliceAllocations:ranges,occurredAt:occurredAt(),reason}
  }
  if (['prepare', 'forward', 'return'].includes(key)) {
    if (Array.isArray(facts.custodyContexts) && Number(form.sourceWorkCenterId)!==facts.selectedCustodyWorkCenterId) {
      throw new Error('请先在“读取当前保管职责范围”明确实际交出中心并重新读取，不能按原中心资格切换其他保管方。')
    }
    if (!form.deliveries.length) throw new Error('请明确至少一个真实去处。')
    const payload = { taskId: id(task?.taskId ?? task?.id, '原定量来源任务'), sourceWorkCenterId: id(form.sourceWorkCenterId, '实际交出工作中心'),
      expectedSourceSnapshotHash: task.expectations?.expectedSourceSnapshotHash || task.sourceSnapshotHash,
      expectedAccountSnapshotHash: account?.accountSnapshotHash || facts.custodyAccountSnapshotHash,
      occurredAt: occurredAt(), reason, deliveries: form.deliveries.map(row => {
        if (!['production', 'storage'].includes(row.destinationKind)) throw new Error('请选择生产去处或受托暂存。')
        const allocations = slices(row.sliceAllocations); if (!allocations.length) throw new Error('每个去处都须明确真实份额和本次数量。')
        return { targetWorkCenterId: id(row.targetWorkCenterId, '目标工作中心'),
          ...(row.targetOperationId ? { targetOperationId: id(row.targetOperationId, '目标工序') } : {}),
          destinationKind: row.destinationKind, destinationReference: row.destinationReference.trim(), purpose: row.purpose.trim(), sliceAllocations: allocations }
      }) }
    if (form.previousHandoverId) payload.previousHandoverId = id(form.previousHandoverId, '原关联物流单')
    return payload
  }
  if (['dispatch', 'cancel'].includes(key)) return { ...headerExpected(), occurredAt: occurredAt(), reason }
  if (key === 'receive') {
    const receipts = form.receipts.filter(row => row.selected).map(row => {
      if (!['partial', 'scope_closed_short'].includes(row.intent)) throw new Error('每个收讫分量须明确继续等待或本范围已核完。')
      return { allocationId: id(row.allocationId, '原物流分量'), expectedVersion: row.expectedVersion, quantity: quantity(row.quantity), intent: row.intent }
    })
    if (!receipts.length) throw new Error('请明确本次实际收讫分量。')
    return { ...headerExpected(), receipts, occurredAt: occurredAt(), reason }
  }
  if (key === 'input.confirm') {
    const inputs = inputSlices(form.inputAllocations,outputPrecision); if (!inputs.length) throw new Error('请明确真实投入份额及范围依据，不能按已开工推定投入。')
    return { outputId: id(output?.id,'本次闭合关联产出'), expectedVersion: output.version,
      expectedSourceSnapshotHash: output.sourceSnapshotHash, inputAllocations: inputs, occurredAt: occurredAt(), reason }
  }
  if (['exception.confirm','correct'].includes(key)) {
    if (!exception) throw new Error('请先只读定位准确关联异常。')
    if(!Number.isSafeInteger(exception.workflowVersion)||!Number.isSafeInteger(exception.approvalTaskVersion))throw new Error('所选原记录不是具备正式独立审核对象的处置提案；请核对服务端说明并先登记准确处置提案。')
    if (key === 'correct' && exception.kind !== 'OUTPUT_CORRECTION') throw new Error('产出更正只接受正式产出关联更正异常，不能改写其他批次。')
    if (!['approve','reject'].includes(form.decision)) throw new Error('请选择明确确认或拒绝本次关联处置。')
    if(form.decision==='approve' && facts.availableActions?.[key]?.approvalReady===false)throw new Error(facts.availableActions[key].approvalDisabledReason || '本次服务端尚未允许确认该关联处置；可核查或明确拒绝。')
    return { expectedVersion: exception.version, expectedSourceSnapshotHash: exception.sourceSnapshotHash,
      expectedWorkflowVersion: exception.workflowVersion, expectedApprovalTaskVersion: exception.approvalTaskVersion,
      exceptionId: exception.id, decision: form.decision, occurredAt: occurredAt(), reason }
  }
  if (key === 'exception.submit') {
    const payload = { taskId:id(task?.taskId ?? task?.id,'准确来源任务'), workCenterId:id(form.sourceWorkCenterId,'本次实际责任工作中心'), occurredAt:occurredAt(), reason }
    if (exception) return {...payload,exceptionId:exception.id,confirmationReference:exactText(form.confirmationReference,'本责任方准确范围确认依据')}
    const kinds=['LOSS','LOCATE_SHORT','RECEIPT_CORRECTION','OUTPUT_CORRECTION','UNMATCHED_CLAIM']
    if (!kinds.includes(form.exceptionKind)) throw new Error('请选择已开放的真实异常类型。')
    Object.assign(payload,{kind:form.exceptionKind,quantity:quantity(form.quantity),evidenceReference:exactText(form.evidenceReference,'真实原始依据'),proposal:{}})
    if (header) payload.handoverId=header.id
    if (form.allocationId) payload.allocationId=id(form.allocationId,'原物流分量')
    if (form.sliceId) {const slice=facts.slices?.find(row=>row.id===Number(form.sliceId)); if(!slice)throw new Error('原份额未在本次事实中核实。');payload.sliceId=slice.id;payload.expectedSliceVersion=slice.version;payload.outputId=slice.outputId}
    if (form.exceptionKind==='LOCATE_SHORT') payload.proposal={holderWorkCenterId:id(form.actualCustodianWorkCenterId,'实际保管工作中心'),holderReference:exactText(form.holderReference,'实际保管范围标识')}
    if (['RECEIPT_CORRECTION','OUTPUT_CORRECTION'].includes(form.exceptionKind))payload.proposal={direction:'decrease'}
    if (form.exceptionKind==='UNMATCHED_CLAIM')payload.proposal={matchedAllocationId:id(form.matchedAllocationId,'待匹配真实原物流分量')}
    return payload
  }
  throw new Error('此动作尚未取得完整正式表单合同，不能提交。')
}
