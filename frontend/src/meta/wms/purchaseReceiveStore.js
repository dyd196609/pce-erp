import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getEmployeeOptions,
  getEnabledWarehouses,
  getLocationOptions,
} from '../manufacturing/manufacturingReferenceService.js'
import {
  getScmPurchaseOrderItems,
  getScmState,
  getScmDisplayName,
} from '../scm/scmStore.js'
import { isReceivablePurchaseOrderStatus } from '../scm/scmDocumentRules.js'
import {
  getWarehouseTaskById,
} from './wmsStore.js'
import { createIncomingInspectionFromPurchaseReceive } from '../qms/qmsStore.js'

const STORAGE_KEY = 'wms-purchase-receive-state-v1'

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

function diffDays(actualDate, expectedDate) {
  if (!actualDate || !expectedDate) return 0
  const actual = new Date(actualDate)
  const expected = new Date(expectedDate)
  if (Number.isNaN(actual.getTime()) || Number.isNaN(expected.getTime())) return 0
  return Math.ceil((actual.getTime() - expected.getTime()) / 86400000)
}

function writeReceiveMetricLogs(receive) {
  if (toNumber(receive.totalShortageQty) > 0) writePurchaseReceiveLog('短交记录', { targetId: receive.id, targetNo: receive.receiveNo, result: receive.totalShortageQty })
  if (toNumber(receive.totalOverQty) > 0) writePurchaseReceiveLog('超交记录', { targetId: receive.id, targetNo: receive.receiveNo, result: receive.totalOverQty })
  if (toNumber(receive.totalDamageQty) > 0) writePurchaseReceiveLog('破损记录', { targetId: receive.id, targetNo: receive.receiveNo, result: receive.totalDamageQty })
  if (receive.settlementReady) writePurchaseReceiveLog('标记 settlementReady', { targetId: receive.id, targetNo: receive.receiveNo })
  if (receive.supplierEvaluationReady) writePurchaseReceiveLog('标记 supplierEvaluationReady', { targetId: receive.id, targetNo: receive.receiveNo })
  if (receive.buyerPerformanceReady) writePurchaseReceiveLog('标记 buyerPerformanceReady', { targetId: receive.id, targetNo: receive.receiveNo })
}

function recalculateReceive(payload = {}) {
  return purchaseReceive({
    ...payload,
    updatedAt: nowText(),
  })
}

function validateReceive(receive, { requireActual = false } = {}) {
  const errors = []
  const lines = receive.lines || []
  lines.forEach((line, index) => {
    const lineLabel = `第${index + 1}行`
    const actualQty = toNumber(line.actualReceiveQty)
    const damageQty = toNumber(line.damageQty)
    const overQty = toNumber(line.overQty)
    if (actualQty < 0) errors.push(`${lineLabel}实际收货数量不能小于0`)
    if (damageQty > actualQty) errors.push(`${lineLabel}破损数量不能大于实际收货数量`)
    if (overQty > 0 && !line.exceptionReason) errors.push(`${lineLabel}存在超交，必须填写异常原因`)
  })
  if (requireActual && !lines.some((line) => toNumber(line.actualReceiveQty) > 0)) {
    errors.push('提交收货预备至少需要一行实际收货数量大于0')
  }
  return errors
}

function firstId(collection) {
  return collection[0]?.id || ''
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function defaultWarehouseId() {
  return firstId(getEnabledWarehouses())
}

function defaultLocationId(warehouseId) {
  return firstId(getLocationOptions(warehouseId))
}

function employeeName(id) {
  const employee = byId(getEmployeeOptions(), id)
  return employee?.name || employee?.raw?.name || ''
}

export function writePurchaseReceiveLog(action, payload = {}) {
  addOperationLog({
    module: 'WMS采购收货预备',
    action,
    targetType: payload.targetType || 'purchaseReceive',
    targetId: payload.targetId || payload.targetNo || '',
    detail: [
      `来源模块：${payload.sourceModule || 'WMS'}`,
      `来源单据：${payload.sourceNo || '-'}`,
      `目标单据：${payload.targetNo || '-'}`,
      `操作结果：${payload.result || '成功'}`,
    ].join('；'),
  })
}

function receiveLine(payload = {}, index = 0) {
  const planned = toNumber(payload.plannedReceiveQty ?? payload.plannedQuantity ?? payload.quantity ?? payload.orderedQty)
  const actual = toNumber(payload.actualReceiveQty)
  const damageQty = toNumber(payload.damageQty)
  const actualPrice = toNumber(payload.actualPrice || payload.planPrice || payload.price)
  const actualAmount = Number((actual * actualPrice).toFixed(2))
  const expectedDeliveryDate = payload.expectedDeliveryDate || payload.plannedArrivalDate || ''
  const actualReceiveDate = payload.actualReceiveDate || ''
  const delayDays = diffDays(actualReceiveDate, expectedDeliveryDate)
  const shortageQty = Math.max(planned - actual, 0)
  const overQty = Math.max(actual - planned, 0)
  const pending = Math.max(actual - damageQty, 0)
  const planAmount = toNumber(payload.planAmount || payload.amount || planned * toNumber(payload.planPrice || payload.price))
  return {
    id: payload.id || createId('recvline'),
    materialId: payload.materialId || '',
    materialCode: payload.materialCode || '',
    materialName: payload.materialName || '',
    spec: payload.spec || payload.specification || '',
    unit: payload.unit || '',
    orderedQty: toNumber(payload.orderedQty ?? payload.quantity ?? payload.plannedQuantity),
    plannedReceiveQty: planned,
    actualReceiveQty: actual,
    pendingInspectQty: toNumber(pending),
    qualifiedQty: toNumber(payload.qualifiedQty),
    unqualifiedQty: toNumber(payload.unqualifiedQty),
    orderQty: toNumber(payload.orderQty ?? payload.orderedQty ?? payload.quantity ?? payload.plannedQuantity),
    shortageQty,
    overQty,
    damageQty,
    sourceLineId: payload.sourceLineId || payload.sourceItemId || '',
    sourceOrderNo: payload.sourceOrderNo || '',
    sourceOrderLineNo: payload.sourceOrderLineNo || payload.lineNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    rootRequestDepartment: payload.rootRequestDepartment || payload.requestDepartment || '',
    rootDemandDepartment: payload.rootDemandDepartment || payload.demandDepartment || '',
    planPrice: toNumber(payload.planPrice || payload.price),
    planAmount,
    actualPrice,
    actualAmount,
    amountVariance: Number((actualAmount - planAmount).toFixed(2)),
    expectedDeliveryDate,
    actualReceiveDate,
    deliveryDelayDays: delayDays,
    onTimeDelivery: delayDays <= 0,
    qualityStatus: payload.qualityStatus || 'pending',
    deliveryNoteNo: payload.deliveryNoteNo || '',
    carrierName: payload.carrierName || '',
    vehicleNo: payload.vehicleNo || '',
    packageStatus: payload.packageStatus || 'normal',
    receiveRemark: payload.receiveRemark || '',
    exceptionReason: payload.exceptionReason || '',
    batchNo: payload.batchNo || `BATCH-${today().replace(/-/g, '')}`,
    locationId: payload.locationId || '',
    locationName: payload.locationName || '',
    remark: payload.remark || '',
    lineNo: payload.lineNo || index + 1,
  }
}

function purchaseReceive(payload = {}) {
  const stamp = nowText()
  const warehouseId = payload.warehouseId || defaultWarehouseId()
  const locationId = payload.locationId || defaultLocationId(warehouseId)
  const receiverId = payload.receiverId || firstId(getEmployeeOptions())
  const lines = (payload.lines || []).map((line, index) => receiveLine({
    locationId,
    locationName: getScmDisplayName('location', locationId),
    ...line,
  }, index))
  const totalOrderQty = lines.reduce((sum, line) => sum + toNumber(line.orderedQty), 0)
  const totalActualReceiveQty = lines.reduce((sum, line) => sum + toNumber(line.actualReceiveQty), 0)
  const totalShortageQty = lines.reduce((sum, line) => sum + toNumber(line.shortageQty), 0)
  const totalOverQty = lines.reduce((sum, line) => sum + toNumber(line.overQty), 0)
  const totalDamageQty = lines.reduce((sum, line) => sum + toNumber(line.damageQty), 0)
  const totalPlanAmount = lines.reduce((sum, line) => sum + toNumber(line.planAmount), 0)
  const totalActualAmount = lines.reduce((sum, line) => sum + toNumber(line.actualAmount), 0)
  const status = payload.status || 'prepared'
  const useBlankPlanDate = payload.sourceType === 'scmPurchaseOrder'
  const plannedArrivalDate = payload.plannedArrivalDate || payload.expectedReceiveDate || (useBlankPlanDate ? '' : today())
  const expectedReceiveDate = payload.expectedReceiveDate || (useBlankPlanDate ? plannedArrivalDate : today())
  return {
    id: payload.id || createId('recv'),
    receiveNo: payload.receiveNo || createNo('PRV'),
    sourceType: payload.sourceType || '',
    sourceOrderId: payload.sourceOrderId || '',
    sourceOrderNo: payload.sourceOrderNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    requestDepartment: payload.requestDepartment || '',
    demandDepartment: payload.demandDepartment || '',
    purchaseDepartment: payload.purchaseDepartment || '',
    rootRequestNo: payload.rootRequestNo || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || payload.sourceOrderNo || '',
    plannedArrivalDate,
    warehouseId,
    warehouseName: payload.warehouseName || getScmDisplayName('warehouse', warehouseId),
    receiverId,
    receiverName: payload.receiverName || employeeName(receiverId),
    expectedReceiveDate,
    actualReceiveDate: payload.actualReceiveDate || '',
    actualArrivalDate: payload.actualArrivalDate || payload.actualReceiveDate || '',
    deliveryNoteNo: payload.deliveryNoteNo || '',
    carrierName: payload.carrierName || '',
    vehicleNo: payload.vehicleNo || '',
    packageStatus: payload.packageStatus || 'normal',
    receiveRemark: payload.receiveRemark || '',
    exceptionReason: payload.exceptionReason || '',
    deliveryDelayDays: toNumber(payload.deliveryDelayDays ?? diffDays(payload.actualArrivalDate || payload.actualReceiveDate, payload.plannedArrivalDate || payload.expectedReceiveDate)),
    onTimeDelivery: payload.onTimeDelivery ?? diffDays(payload.actualArrivalDate || payload.actualReceiveDate, payload.plannedArrivalDate || payload.expectedReceiveDate) <= 0,
    totalOrderQty,
    totalActualReceiveQty,
    totalShortageQty,
    totalOverQty,
    totalDamageQty,
    totalPlanAmount: Number(totalPlanAmount.toFixed(2)),
    totalActualAmount: Number(totalActualAmount.toFixed(2)),
    amountVariance: Number((totalActualAmount - totalPlanAmount).toFixed(2)),
    receiveAccuracyRate: totalOrderQty ? Number((totalActualReceiveQty / totalOrderQty).toFixed(4)) : 0,
    deliveryAccuracyRate: lines.length ? Number((lines.filter((line) => line.onTimeDelivery).length / lines.length).toFixed(4)) : 0,
    qualityExceptionFlag: lines.some((line) => toNumber(line.damageQty) > 0 || line.exceptionReason),
    settlementReady: payload.settlementReady ?? status === 'received',
    supplierEvaluationReady: payload.supplierEvaluationReady ?? status === 'received',
    buyerPerformanceReady: payload.buyerPerformanceReady ?? status === 'received',
    status,
    remark: payload.remark || '',
    lines,
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function defaultState() {
  return { purchaseReceives: [] }
}

function normalizeState(raw = {}) {
  return {
    purchaseReceives: (raw.purchaseReceives || []).map((item) => purchaseReceive(item)),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[PURCHASE RECEIVE STORE] fallback to empty state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function createReceive(payload = {}, logPayload = {}) {
  const receive = purchaseReceive(payload)
  state.purchaseReceives.unshift(receive)
  persist()
  writePurchaseReceiveLog('创建采购收货预备单', {
    ...logPayload,
    targetId: receive.id,
    targetNo: receive.receiveNo,
  })
  if (payload.sourceType === 'scmPurchaseOrder') {
    writePurchaseReceiveLog('生成采购收货预备单', {
      ...logPayload,
      targetId: receive.id,
      targetNo: receive.receiveNo,
    })
  }
  return { success: true, receiveId: receive.id, receiveNo: receive.receiveNo }
}

export function getPurchaseReceiveState() {
  return clone(state)
}

export function savePurchaseReceiveState(nextState) {
  state = normalizeState(nextState)
  persist()
  writePurchaseReceiveLog('保存采购收货预备状态', { targetType: 'purchaseReceiveState', targetId: 'state' })
  return getPurchaseReceiveState()
}

export function resetPurchaseReceiveState() {
  state = defaultState()
  persist()
  writePurchaseReceiveLog('恢复采购收货预备演示数据', { targetType: 'purchaseReceiveState', targetId: 'demo' })
  return getPurchaseReceiveState()
}

export function listPurchaseReceives() {
  return clone(state.purchaseReceives)
}

export function getPurchaseReceiveById(id) {
  return clone(byId(state.purchaseReceives, id))
}

export function createPurchaseReceiveFromWarehouseTask(taskId) {
  const task = typeof taskId === 'object' ? taskId : getWarehouseTaskById(taskId)
  if (!task?.id) return { success: false, error: '未找到仓库任务。' }
  if (task.taskType !== 'purchaseReceive') return { success: false, error: '只有采购收货类仓库任务可以生成收货预备单。' }
  const existing = state.purchaseReceives.find((item) => item.sourceType === 'warehouseTask' && item.sourceOrderId === task.id && item.status !== 'cancelled')
  if (existing) {
    writePurchaseReceiveLog('拦截重复生成采购收货预备单', {
      sourceModule: 'WMS仓库任务',
      sourceNo: task.taskNo,
      targetId: existing.id,
      targetNo: existing.receiveNo,
      result: '已生成采购收货预备单，不能重复生成。',
    })
    return { success: false, error: '已生成采购收货预备单，不能重复生成。' }
  }
  return createReceive({
    sourceType: 'warehouseTask',
    sourceOrderId: task.id,
    sourceOrderNo: task.taskNo,
    supplierName: task.sourceType === 'scmPurchaseOrder' ? getScmDisplayName('supplier', getScmState().purchaseOrders.find((order) => order.id === task.sourceId)?.supplierId) : '',
    warehouseId: task.warehouseId,
    warehouseName: task.warehouseName,
    expectedReceiveDate: today(),
    remark: '由仓库收货任务生成，仅形成采购收货预备，不直接增加库存。',
    lines: [{
      materialId: task.materialId,
      materialCode: task.materialCode,
      materialName: task.materialName,
      spec: task.specification,
      unit: task.unit,
      orderedQty: task.plannedQuantity,
      plannedReceiveQty: task.plannedQuantity,
      actualReceiveQty: task.completedQuantity || 0,
      locationId: task.locationId,
      locationName: task.locationName,
    }],
  }, {
    sourceModule: 'WMS仓库任务',
    sourceNo: task.taskNo,
  })
}

export function createPurchaseReceiveFromScmPurchaseOrder(poId) {
  const order = getScmState().purchaseOrders.find((item) => String(item.id) === String(poId))
  if (!order || !isReceivablePurchaseOrderStatus(order.status)) return { success: false, error: '只有已审批、已下达或部分收货的采购订单可以生成采购收货预备单。' }
  const items = getScmPurchaseOrderItems(poId).filter((item) => item.materialCode || item.materialName)
  if (!items.length) return { success: false, error: '采购订单没有明细，不能生成采购收货预备单。' }
  const orderPlanDate = items
    .map((item) => item.planDeliveryDate || item.plannedArrivalDate || item.expectedDeliveryDate || item.deliveryDate)
    .filter(Boolean)
    .sort()[0] || order.planDeliveryDate || order.plannedArrivalDate || order.expectedDeliveryDate || ''
  const existing = state.purchaseReceives.find((item) => item.sourceType === 'scmPurchaseOrder' && item.sourceOrderId === poId && item.status !== 'cancelled')
  if (existing) {
    writePurchaseReceiveLog('拦截重复生成采购收货预备单', {
      sourceModule: 'SCM采购订单',
      sourceNo: order.poNo,
      targetId: existing.id,
      targetNo: existing.receiveNo,
      result: '已生成采购收货预备单，不能重复生成。',
    })
    return { success: false, error: '已生成采购收货预备单，不能重复生成。' }
  }
  const warehouseId = items[0]?.warehouseId || defaultWarehouseId()
  return createReceive({
    sourceType: 'scmPurchaseOrder',
    sourceOrderId: order.id,
    sourceOrderNo: order.poNo,
    supplierId: order.supplierId,
    supplierName: getScmDisplayName('supplier', order.supplierId),
    buyerId: order.buyerId,
    buyerName: getScmDisplayName('employee', order.buyerId),
    requestDepartment: order.rootRequestDepartment || order.requestDepartment,
    demandDepartment: order.rootDemandDepartment || order.demandDepartment,
    purchaseDepartment: order.rootPurchaseDepartment || order.purchaseDepartment,
    rootRequestNo: order.rootRequestNo,
    sourcePurchaseOrderNo: order.poNo,
    plannedArrivalDate: orderPlanDate,
    warehouseId,
    warehouseName: getScmDisplayName('warehouse', warehouseId),
    receiverId: order.buyerId,
    expectedReceiveDate: orderPlanDate,
    remark: '由SCM已审批采购订单生成，仅形成采购收货预备，不直接增加库存。',
    lines: items.map((item) => ({
      materialId: item.materialId,
      materialCode: item.materialCode,
      materialName: item.materialName,
      spec: item.specification,
      unit: item.unit,
      orderedQty: item.quantity,
      orderQty: item.quantity,
      plannedReceiveQty: item.quantity,
      actualReceiveQty: 0,
      sourceLineId: item.sourceLineId || item.sourceItemId || item.id,
      sourceOrderNo: order.poNo,
      sourceOrderLineNo: item.lineNo,
      rootRequestNo: item.rootRequestNo || order.rootRequestNo,
      rootRequestDepartment: item.rootRequestDepartment || order.rootRequestDepartment || order.requestDepartment,
      rootDemandDepartment: item.rootDemandDepartment || order.rootDemandDepartment || order.demandDepartment,
      planPrice: item.planPrice || item.price,
      planAmount: item.planAmount || item.amount,
      actualPrice: item.actualPrice || 0,
      actualAmount: item.actualAmount || 0,
      expectedDeliveryDate: item.expectedDeliveryDate || item.planDeliveryDate || item.plannedArrivalDate || '',
      locationId: item.locationId,
      locationName: getScmDisplayName('location', item.locationId),
      remark: item.remark,
    })),
  }, {
    sourceModule: 'SCM采购订单',
    sourceNo: order.poNo,
  })
}

export function updatePurchaseReceive(id, payload = {}) {
  const current = byId(state.purchaseReceives, id)
  if (!current || current.status === 'cancelled' || current.status === 'received' || current.status === 'inspectionPrepared') return null
  Object.assign(current, recalculateReceive({ ...current, ...payload, id: current.id, status: payload.status || current.status }))
  persist()
  writePurchaseReceiveLog('修改采购收货预备单', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
  })
  return clone(current)
}

export function beginEditPurchaseReceive(id) {
  const current = byId(state.purchaseReceives, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前采购收货预备单不可编辑。' }
  if (current.status === 'received' || current.status === 'inspectionPrepared') return { success: false, error: '已收货单据不可自由编辑。' }
  if (current.status === 'prepared') current.status = 'receiving'
  current.updatedAt = nowText()
  persist()
  writePurchaseReceiveLog('编辑收货信息', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
  })
  return { success: true, receive: clone(current) }
}

export function savePurchaseReceiveDraft(id, payload = {}) {
  const current = byId(state.purchaseReceives, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前采购收货预备单不可保存。' }
  if (current.status === 'received' || current.status === 'inspectionPrepared') return { success: false, error: '已收货单据不可自由编辑。' }
  const next = recalculateReceive({
    ...current,
    ...payload,
    id: current.id,
    status: current.status === 'prepared' ? 'receiving' : current.status,
  })
  const errors = validateReceive(next)
  if (errors.length) {
    writePurchaseReceiveLog('收货数量校验失败', {
      sourceNo: current.sourceOrderNo,
      targetId: current.id,
      targetNo: current.receiveNo,
      result: errors.join('；'),
    })
    return { success: false, error: errors.join('；') }
  }
  Object.assign(current, next)
  persist()
  writePurchaseReceiveLog('保存收货预备', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
  })
  writePurchaseReceiveLog('收货金额计算', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
    result: current.totalActualAmount,
  })
  writeReceiveMetricLogs(current)
  return { success: true, receive: clone(current) }
}

export function submitPurchaseReceive(id, payload = {}) {
  const current = byId(state.purchaseReceives, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前采购收货预备单不可提交。' }
  if (current.status === 'received' || current.status === 'inspectionPrepared') return { success: false, error: '当前采购收货预备单已完成收货。' }
  const actualArrivalDate = payload.actualArrivalDate || current.actualArrivalDate || today()
  const next = recalculateReceive({
    ...current,
    ...payload,
    id: current.id,
    status: 'received',
    actualReceiveDate: payload.actualReceiveDate || current.actualReceiveDate || actualArrivalDate,
    actualArrivalDate,
    settlementReady: true,
    supplierEvaluationReady: true,
    buyerPerformanceReady: true,
  })
  const errors = validateReceive(next, { requireActual: true })
  if (errors.length) {
    writePurchaseReceiveLog('收货数量校验失败', {
      sourceNo: current.sourceOrderNo,
      targetId: current.id,
      targetNo: current.receiveNo,
      result: errors.join('；'),
    })
    return { success: false, error: errors.join('；') }
  }
  Object.assign(current, next)
  persist()
  writePurchaseReceiveLog('提交收货预备', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
  })
  writePurchaseReceiveLog('收货金额计算', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
    result: current.totalActualAmount,
  })
  writeReceiveMetricLogs(current)
  return { success: true, receive: clone(current) }
}

export function cancelPurchaseReceive(id) {
  const current = byId(state.purchaseReceives, id)
  if (!current || current.status === 'cancelled') return { success: false, error: '当前采购收货预备单不可取消。' }
  current.status = 'cancelled'
  current.updatedAt = nowText()
  persist()
  writePurchaseReceiveLog('取消采购收货预备单', {
    sourceNo: current.sourceOrderNo,
    targetId: current.id,
    targetNo: current.receiveNo,
  })
  return { success: true }
}

export function markPurchaseReceivePrepared(id) {
  return updatePurchaseReceive(id, { status: 'prepared' })
}

export function markPurchaseReceiveReceived(id) {
  return submitPurchaseReceive(id, { actualReceiveDate: today() })
}

export function createInspectionPreviewFromPurchaseReceive(id) {
  const receive = byId(state.purchaseReceives, id)
  if (!receive || receive.status === 'cancelled') return { success: false, error: '当前采购收货预备单不可生成来料检验预备。' }
  const outcome = createIncomingInspectionFromPurchaseReceive(clone(receive))
  if (!outcome.success) return outcome
  if (outcome.existed) {
    writePurchaseReceiveLog('拦截重复生成来料检验单', {
      sourceModule: 'WMS采购收货预备',
      sourceNo: receive.receiveNo,
      targetId: outcome.inspectionId,
      targetNo: outcome.inspectionNo,
      result: '已生成来料检验单，不能重复生成。',
    })
    return { success: false, error: '已生成来料检验单，不能重复生成。' }
  }
  receive.status = 'inspectionPrepared'
  receive.updatedAt = nowText()
  persist()
  writePurchaseReceiveLog('采购收货预备单生成来料检验预备单', {
    sourceModule: 'WMS采购收货预备',
    sourceNo: receive.receiveNo,
    targetId: outcome.inspectionId,
    targetNo: outcome.inspectionNo,
    result: outcome.existed ? '已存在，未重复生成' : '成功',
  })
  return outcome
}

function purchaseReceiveBatchResult(ids = [], handler, label) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const receive = byId(state.purchaseReceives, id)
    const no = receive?.receiveNo || id
    const outcome = handler(id, receive)
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
  writePurchaseReceiveLog(label, {
    targetType: 'batch',
    targetId: label,
    result: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}`,
  })
  if (result.failedCount) writePurchaseReceiveLog('批量操作失败原因', { targetType: 'batch', targetId: label, result: result.failedReason.join('；') })
  return result
}

export function batchSubmitPurchaseReceives(ids = []) {
  return purchaseReceiveBatchResult(ids, (id, receive) => {
    if (!receive) return { success: false, error: '未找到采购收货预备单。' }
    if (!['prepared', 'receiving'].includes(receive.status)) return { success: false, error: '只有 prepared / receiving 状态才能提交收货预备。' }
    return submitPurchaseReceive(id, receive)
  }, '批量提交收货预备')
}

export function batchCreateIncomingInspectionsFromReceives(ids = []) {
  return purchaseReceiveBatchResult(ids, (id, receive) => {
    if (!receive) return { success: false, error: '未找到采购收货预备单。' }
    if (['prepared', 'receiving'].includes(receive.status)) {
      writePurchaseReceiveLog('批量生成来料检验跳过未提交收货记录', { targetType: 'purchaseReceive', targetId: id, targetNo: receive.receiveNo, result: '请先提交收货预备。' })
      return { success: false, error: '请先提交收货预备。' }
    }
    if (receive.status === 'inspectionPrepared') {
      writePurchaseReceiveLog('批量生成来料检验跳过已生成检验记录', { targetType: 'purchaseReceive', targetId: id, targetNo: receive.receiveNo, result: '已生成来料检验，不能重复生成。' })
      return { success: false, error: '已生成来料检验，不能重复生成。' }
    }
    if (receive.status !== 'received') return { success: false, error: '当前状态不符，不能生成来料检验。' }
    const outcome = createInspectionPreviewFromPurchaseReceive(id)
    return outcome
  }, '批量生成来料检验')
}

export function batchCreatePurchaseReceivesFromPurchaseOrders(ids = []) {
  return purchaseReceiveBatchResult(ids, (id) => {
    const existing = state.purchaseReceives.find((item) => item.sourceType === 'scmPurchaseOrder' && String(item.sourceOrderId) === String(id) && item.status !== 'cancelled')
    if (existing) {
      writePurchaseReceiveLog('批量生成采购收货预备单跳过已生成记录', { targetType: 'scmPurchaseOrder', targetId: id, targetNo: existing.sourceOrderNo || id, result: '已生成采购收货预备单，已跳过。' })
      return { success: false, error: '已生成采购收货预备单，已跳过。' }
    }
    return createPurchaseReceiveFromScmPurchaseOrder(id)
  }, '批量生成采购收货预备单')
}
