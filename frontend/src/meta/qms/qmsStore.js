import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import { getEmployeeOptions } from '../manufacturing/manufacturingReferenceService.js'

const STORAGE_KEY = 'qms-state-v1'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function createNo(prefix) {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `${prefix}${stamp}${Math.floor(Math.random() * 90 + 10)}`
}

function toNumber(value) {
  const next = Number(value)
  return Number.isFinite(next) ? next : 0
}

function employeeName(id) {
  const employee = byId(getEmployeeOptions(), id)
  return employee?.name || employee?.raw?.name || ''
}

function lineIncomingInspection(line = {}, index = 0) {
  const receivedQty = toNumber(line.receivedQty ?? line.actualReceiveQty ?? line.plannedReceiveQty)
  const qualifiedQty = toNumber(line.qualifiedQty)
  const concessionQty = toNumber(line.concessionQty)
  const returnQty = toNumber(line.returnQty)
  const scrapQty = toNumber(line.scrapQty)
  const reworkQty = toNumber(line.reworkQty)
  const unqualifiedQty = toNumber(line.unqualifiedQty)
  const inspectorId = line.inspectorId || ''
  return {
    id: line.id || createId('inspline'),
    sourceLineId: line.sourceLineId || '',
    materialId: line.materialId || '',
    materialCode: line.materialCode || '',
    materialName: line.materialName || '',
    spec: line.spec || line.specification || '',
    unit: line.unit || '',
    warehouseId: line.warehouseId || '',
    warehouseName: line.warehouseName || '',
    locationId: line.locationId || '',
    locationName: line.locationName || '',
    batchNo: line.batchNo || '',
    receivedQty,
    pendingInspectQty: toNumber(line.pendingInspectQty ?? receivedQty),
    qualifiedQty,
    unqualifiedQty,
    concessionQty,
    returnQty,
    scrapQty,
    reworkQty,
    inspectResult: line.inspectResult || 'pending',
    defectReason: line.defectReason || '',
    dispositionType: line.dispositionType || inferDispositionType({ qualifiedQty, unqualifiedQty, concessionQty, returnQty, scrapQty, reworkQty }),
    inspectorId,
    inspectorName: line.inspectorName || employeeName(inspectorId),
    actualInspectDate: line.actualInspectDate || '',
    qualityStatus: line.qualityStatus || 'pending',
    inventoryPosted: Boolean(line.inventoryPosted),
    inventoryPostedQty: toNumber(line.inventoryPostedQty),
    inventoryTransactionId: line.inventoryTransactionId || '',
    inventoryTransactionIds: line.inventoryTransactionIds || [],
    inboundPrepared: Boolean(line.inboundPrepared),
    inboundPreparedQty: toNumber(line.inboundPreparedQty),
    inboundPrepareTaskId: line.inboundPrepareTaskId || '',
    remark: line.remark || '',
    lineNo: line.lineNo || index + 1,
  }
}

function inferDispositionType(line = {}) {
  if (toNumber(line.concessionQty) > 0 && (toNumber(line.returnQty) > 0 || toNumber(line.scrapQty) > 0 || toNumber(line.reworkQty) > 0)) return 'mixed'
  if (toNumber(line.concessionQty) > 0) return 'concession'
  if (toNumber(line.returnQty) > 0) return 'return'
  if (toNumber(line.scrapQty) > 0) return 'scrap'
  if (toNumber(line.reworkQty) > 0) return 'rework'
  if (toNumber(line.qualifiedQty) > 0 && toNumber(line.unqualifiedQty) === 0) return 'qualified'
  return 'pending'
}

function validateInspectionResult(inspection = {}) {
  const errors = []
  const lines = inspection.lines || []
  let hasResult = false
  lines.forEach((line, index) => {
    const label = `第${index + 1}行`
    const qualifiedQty = toNumber(line.qualifiedQty)
    const unqualifiedQty = toNumber(line.unqualifiedQty)
    const concessionQty = toNumber(line.concessionQty)
    const returnQty = toNumber(line.returnQty)
    const scrapQty = toNumber(line.scrapQty)
    const reworkQty = toNumber(line.reworkQty)
    const receivedQty = toNumber(line.receivedQty)
    if (qualifiedQty < 0) errors.push(`${label}合格数量不能小于0`)
    if (unqualifiedQty < 0) errors.push(`${label}不合格数量不能小于0`)
    if (concessionQty < 0) errors.push(`${label}让步接收数量不能小于0`)
    if (returnQty < 0) errors.push(`${label}退货数量不能小于0`)
    if (scrapQty < 0) errors.push(`${label}报废数量不能小于0`)
    if (reworkQty < 0) errors.push(`${label}返工数量不能小于0`)
    if (qualifiedQty + unqualifiedQty > receivedQty) errors.push(`${label}合格数量与不合格数量合计不能大于收货数量`)
    if (concessionQty + returnQty + scrapQty + reworkQty > unqualifiedQty) errors.push(`${label}不合格处理数量合计不能大于不合格数量`)
    if (line.inspectResult && line.inspectResult !== 'pending') hasResult = true
  })
  if (!hasResult) errors.push('至少要有一行填写检验结果')
  return errors
}

function summarizeInspectionStatus(inspection = {}) {
  const lines = inspection.lines || []
  const inboundQty = lines.reduce((sum, line) => sum + toNumber(line.qualifiedQty) + toNumber(line.concessionQty), 0)
  const rejectedQty = lines.reduce((sum, line) => sum + toNumber(line.returnQty) + toNumber(line.scrapQty) + toNumber(line.reworkQty), 0)
  const receivedQty = lines.reduce((sum, line) => sum + toNumber(line.receivedQty), 0)
  if (inboundQty <= 0 && rejectedQty > 0) return 'rejected'
  if (inspection.inventoryPostStatus === 'inboundPrepared') return 'inboundPrepared'
  if (inboundQty > 0 && inboundQty < receivedQty) return 'partiallyReleased'
  if (inboundQty > 0) return 'inventoryPosted'
  return 'inspected'
}

function firstId(collection) {
  return collection[0]?.id || ''
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

export function writeQmsLog(action, payload = {}) {
  addOperationLog({
    module: 'QMS来料检验预备',
    action,
    targetType: payload.targetType || 'incomingInspection',
    targetId: payload.targetId || payload.targetNo || '',
    detail: [
      `来源模块：${payload.sourceModule || 'WMS采购收货预备'}`,
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `操作结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

function incomingInspection(payload = {}) {
  const stamp = nowText()
  const inspectorId = payload.inspectorId || firstId(getEmployeeOptions())
  return {
    id: payload.id || createId('insp'),
    inspectionNo: payload.inspectionNo || createNo('IQC'),
    sourceType: payload.sourceType || 'purchaseReceive',
    sourceReceiveId: payload.sourceReceiveId || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourceOrderId: payload.sourceOrderId || '',
    sourceOrderNo: payload.sourceOrderNo || '',
    sourcePurchaseOrderId: payload.sourcePurchaseOrderId || payload.sourceOrderId || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || payload.sourceOrderNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    warehouseId: payload.warehouseId || '',
    warehouseName: payload.warehouseName || '',
    inspectorId,
    inspectorName: payload.inspectorName || employeeName(inspectorId),
    status: payload.status || 'pending',
    plannedInspectDate: payload.plannedInspectDate || today(),
    actualInspectDate: payload.actualInspectDate || '',
    inventoryPosted: Boolean(payload.inventoryPosted),
    inventoryPostedAt: payload.inventoryPostedAt || '',
    inventoryTransactionIds: payload.inventoryTransactionIds || [],
    inventoryPostStatus: payload.inventoryPostStatus || 'notPosted',
    inventoryPostMessage: payload.inventoryPostMessage || '',
    inboundPreparedAt: payload.inboundPreparedAt || '',
    inboundPrepareTaskIds: payload.inboundPrepareTaskIds || [],
    remark: payload.remark || '',
    lines: (payload.lines || []).map((line, index) => lineIncomingInspection(line, index)),
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function defaultState() {
  return { incomingInspections: [] }
}

function normalizeState(raw = {}) {
  return {
    incomingInspections: (raw.incomingInspections || []).map((item) => incomingInspection(item)),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[QMS STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function getQmsState() {
  return clone(state)
}

export function saveQmsState(nextState) {
  state = normalizeState(nextState)
  persist()
  writeQmsLog('保存QMS状态', { targetType: 'qmsState', targetId: 'state' })
  return getQmsState()
}

export function resetQmsState() {
  state = defaultState()
  persist()
  writeQmsLog('恢复QMS演示数据', { targetType: 'qmsState', targetId: 'demo' })
  return getQmsState()
}

export function listIncomingInspections() {
  return clone(state.incomingInspections)
}

export function getIncomingInspectionById(id) {
  return clone(byId(state.incomingInspections, id))
}

export function createIncomingInspectionFromPurchaseReceive(receive = {}) {
  if (!receive?.id) return { success: false, error: '未找到采购收货预备单。' }
  if (!Array.isArray(receive.lines) || !receive.lines.length) return { success: false, error: '采购收货预备单没有明细，不能生成来料检验预备单。' }
  const existing = state.incomingInspections.find((item) => item.sourceReceiveId === receive.id && item.status !== 'cancelled')
  if (existing) return { success: true, inspectionId: existing.id, inspectionNo: existing.inspectionNo, existed: true }

  const inspection = incomingInspection({
    sourceReceiveId: receive.id,
    sourceReceiveNo: receive.receiveNo,
    sourceOrderId: receive.sourceOrderId,
    sourceOrderNo: receive.sourceOrderNo,
    sourcePurchaseOrderId: receive.sourceOrderId,
    sourcePurchaseOrderNo: receive.sourcePurchaseOrderNo || receive.sourceOrderNo,
    rootRequestNo: receive.rootRequestNo,
    buyerId: receive.buyerId,
    buyerName: receive.buyerName,
    supplierId: receive.supplierId,
    supplierName: receive.supplierName,
    warehouseId: receive.warehouseId,
    warehouseName: receive.warehouseName,
    plannedInspectDate: today(),
    remark: '由采购收货预备单生成，仅登记待检信息，不直接入库。',
    lines: receive.lines.map((line) => ({
      materialId: line.materialId,
      materialCode: line.materialCode,
      materialName: line.materialName,
      spec: line.spec,
      unit: line.unit,
      sourceLineId: line.sourceLineId,
      warehouseId: line.warehouseId || receive.warehouseId,
      warehouseName: receive.warehouseName,
      locationId: line.locationId,
      locationName: line.locationName,
      batchNo: line.batchNo,
      receivedQty: line.actualReceiveQty || line.plannedReceiveQty,
      pendingInspectQty: line.pendingInspectQty || line.actualReceiveQty || line.plannedReceiveQty,
      qualifiedQty: 0,
      unqualifiedQty: 0,
      inspectResult: 'pending',
      dispositionType: 'pending',
      qualityStatus: 'pending',
      remark: line.remark,
    })),
  })
  state.incomingInspections.unshift(inspection)
  persist()
  writeQmsLog('创建来料检验预备单', {
    sourceNo: receive.receiveNo,
    targetId: inspection.id,
    targetNo: inspection.inspectionNo,
  })
  return { success: true, inspectionId: inspection.id, inspectionNo: inspection.inspectionNo }
}

export function startIncomingInspection(id) {
  const current = byId(state.incomingInspections, id)
  if (!current || current.status !== 'pending') return { success: false, error: '只有待检状态可以开始检验。' }
  current.status = 'inspecting'
  current.updatedAt = nowText()
  persist()
  writeQmsLog('开始检验', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo })
  writeQmsLog('进入检验填写模式', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo })
  return { success: true, inspection: clone(current) }
}

export function saveIncomingInspectionResult(id, payload = {}) {
  const current = byId(state.incomingInspections, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前检验单不可保存。' }
  if (!['pending', 'inspecting'].includes(current.status)) return { success: false, error: '已提交或已入库的检验单不可随意修改。' }
  const next = incomingInspection({
    ...current,
    ...payload,
    id: current.id,
    status: 'inspecting',
    updatedAt: nowText(),
  })
  Object.assign(current, next)
  persist()
  writeQmsLog('保存检验结果', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo })
  return { success: true, inspection: clone(current) }
}

export function submitIncomingInspectionResult(id, payload = {}) {
  const current = byId(state.incomingInspections, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前检验单不可提交。' }
  if (current.status !== 'inspecting') return { success: false, error: '只有检验中状态可以提交检验结果。' }
  const actualInspectDate = payload.actualInspectDate || current.actualInspectDate || today()
  const next = incomingInspection({
    ...current,
    ...payload,
    id: current.id,
    status: 'inspected',
    actualInspectDate,
    updatedAt: nowText(),
    lines: (payload.lines || current.lines || []).map((line) => ({
      ...line,
      actualInspectDate: line.actualInspectDate || actualInspectDate,
      inspectorId: line.inspectorId || payload.inspectorId || current.inspectorId,
      dispositionType: line.dispositionType || inferDispositionType(line),
    })),
  })
  const errors = validateInspectionResult(next)
  if (errors.length) {
    writeQmsLog('检验数量校验失败', {
      sourceNo: current.sourceReceiveNo,
      targetId: current.id,
      targetNo: current.inspectionNo,
      result: errors.join('；'),
    })
    return { success: false, error: errors.join('；') }
  }
  next.lines.forEach((line) => {
    line.dispositionType = line.dispositionType === 'pending' ? inferDispositionType(line) : line.dispositionType
    line.qualityStatus = toNumber(line.concessionQty) > 0 ? 'concession'
      : toNumber(line.returnQty) > 0 ? 'returnPending'
        : toNumber(line.scrapQty) > 0 ? 'scrapped'
          : toNumber(line.reworkQty) > 0 ? 'reworkPending'
            : toNumber(line.unqualifiedQty) > 0 ? 'unqualified'
              : 'qualified'
    if (toNumber(line.concessionQty) > 0) writeQmsLog('让步接收', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo, result: line.concessionQty })
    if (toNumber(line.returnQty) > 0) writeQmsLog('退货处理', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo, result: line.returnQty })
    if (toNumber(line.scrapQty) > 0) writeQmsLog('报废处理', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo, result: line.scrapQty })
    if (toNumber(line.reworkQty) > 0) writeQmsLog('返工处理', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo, result: line.reworkQty })
  })
  Object.assign(current, next)
  persist()
  writeQmsLog('提交检验结果', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo })
  return { success: true, inspection: clone(current) }
}

export function applyInspectionInventoryPostResult(id, payload = {}) {
  const current = byId(state.incomingInspections, id)
  if (!current) return { success: false, error: '未找到来料检验单。' }
  const transactionIds = payload.inventoryTransactionIds || []
  current.inventoryPosted = transactionIds.length > 0 || Boolean(payload.inventoryPosted)
  current.inventoryPostedAt = current.inventoryPosted ? nowText() : current.inventoryPostedAt
  current.inventoryTransactionIds = Array.from(new Set([...(current.inventoryTransactionIds || []), ...transactionIds]))
  current.inventoryPostStatus = payload.inventoryPostStatus || (current.inventoryPosted ? 'posted' : 'noInventory')
  current.inventoryPostMessage = payload.inventoryPostMessage || ''
  current.inboundPreparedAt = payload.inboundPreparedAt || current.inboundPreparedAt
  current.inboundPrepareTaskIds = Array.from(new Set([...(current.inboundPrepareTaskIds || []), ...(payload.inboundPrepareTaskIds || [])]))
  current.status = payload.status || summarizeInspectionStatus(current)
  ;(payload.lines || []).forEach((postedLine) => {
    const line = byId(current.lines, postedLine.id)
    if (!line) return
    line.inventoryPosted = postedLine.inventoryPosted ?? line.inventoryPosted
    line.inventoryPostedQty = toNumber(postedLine.inventoryPostedQty ?? line.inventoryPostedQty)
    line.inventoryTransactionId = postedLine.inventoryTransactionId || line.inventoryTransactionId
    line.inventoryTransactionIds = Array.from(new Set([...(line.inventoryTransactionIds || []), ...(postedLine.inventoryTransactionIds || [])]))
    line.inboundPrepared = postedLine.inboundPrepared ?? line.inboundPrepared
    line.inboundPreparedQty = toNumber(postedLine.inboundPreparedQty ?? line.inboundPreparedQty)
    line.inboundPrepareTaskId = postedLine.inboundPrepareTaskId || line.inboundPrepareTaskId
    line.qualityStatus = postedLine.qualityStatus || line.qualityStatus
  })
  current.updatedAt = nowText()
  persist()
  writeQmsLog('查看入库结果', { sourceNo: current.sourceReceiveNo, targetId: current.id, targetNo: current.inspectionNo, result: current.inventoryPostStatus })
  return { success: true, inspection: clone(current) }
}

export function updateIncomingInspection(id, payload = {}) {
  const current = byId(state.incomingInspections, id)
  if (!current || current.status === 'cancelled') return null
  Object.assign(current, incomingInspection({ ...current, ...payload, id: current.id, updatedAt: nowText() }))
  persist()
  writeQmsLog('修改来料检验预备单', {
    sourceNo: current.sourceReceiveNo,
    targetId: current.id,
    targetNo: current.inspectionNo,
  })
  return clone(current)
}

export function cancelIncomingInspection(id) {
  const current = byId(state.incomingInspections, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前检验预备单不可取消。' }
  current.status = 'cancelled'
  current.updatedAt = nowText()
  persist()
  writeQmsLog('取消来料检验预备单', {
    sourceNo: current.sourceReceiveNo,
    targetId: current.id,
    targetNo: current.inspectionNo,
  })
  return { success: true }
}

export function markIncomingInspectionInspecting(id) {
  return startIncomingInspection(id)
}

export function markIncomingInspectionInspected(id) {
  return submitIncomingInspectionResult(id, { actualInspectDate: today() })
}

function qmsBatchResult(ids = [], handler, label) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const inspection = byId(state.incomingInspections, id)
    const no = inspection?.inspectionNo || id
    const outcome = handler(id, inspection)
    if (outcome?.success) {
      result.successCount += 1
      result.successItems.push({ id, no })
    } else {
      const reason = outcome?.error || '当前状态不允许执行该批量操作。'
      result.failedCount += 1
      result.failedItems.push({ id, no, reason })
      result.failedReason.push(`${no}：${reason}`)
    }
  })
  writeQmsLog(label, { targetType: 'batch', targetId: label, result: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writeQmsLog('批量操作失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchStartInspections(ids = []) {
  return qmsBatchResult(ids, (id) => startIncomingInspection(id), '批量开始检验')
}

export function batchSubmitInspectionResults(ids = []) {
  return qmsBatchResult(ids, (id, inspection) => {
    if (!inspection) return { success: false, error: '未找到来料检验单。' }
    const hasData = (inspection.lines || []).some((line) => (
      toNumber(line.qualifiedQty) > 0
      || toNumber(line.unqualifiedQty) > 0
      || toNumber(line.concessionQty) > 0
      || toNumber(line.returnQty) > 0
      || toNumber(line.scrapQty) > 0
      || toNumber(line.reworkQty) > 0
    ))
    if (!hasData) return { success: false, error: '未填写检验数量或处理数量，已跳过。' }
    return submitIncomingInspectionResult(id, inspection)
  }, '批量提交检验结果')
}
