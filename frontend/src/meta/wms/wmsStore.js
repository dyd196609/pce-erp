import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  getEmployeeOptions,
  getEnabledMaterials,
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
  applyInspectionInventoryPostResult,
  getIncomingInspectionById,
  getQmsState,
  writeQmsLog,
} from '../qms/qmsStore.js'

const STORAGE_KEY = 'wms-state-v1'

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

function firstId(collection) {
  return collection[0]?.id || ''
}

function byId(collection, id) {
  return (collection || []).find((item) => String(item.id) === String(id)) || null
}

function writeLog(action, targetType, targetId, detail = '') {
  addOperationLog({
    module: 'WMS库存管理',
    action,
    targetType,
    targetId,
    detail,
  })
}

function materialSnapshot(materialId) {
  const item = byId(getEnabledMaterials(), materialId) || {}
  const raw = item.raw || {}
  return {
    materialId: item.id || materialId || '',
    materialCode: item.code || raw.code || item.id || '',
    materialName: raw.name || item.name || '',
    specification: raw.specification || raw.model || raw.spec || '',
    unit: raw.unit || raw.unitName || raw.baseUnit || raw.purchaseUnit || '',
    safetyStock: toNumber(raw.safetyStock || 0),
    maxStock: toNumber(raw.maxStock || 0),
  }
}

function warehouseSnapshot(warehouseId) {
  const item = byId(getEnabledWarehouses(), warehouseId) || {}
  return {
    warehouseId: item.id || warehouseId || '',
    warehouseName: item.raw?.name || item.name || '',
  }
}

function locationSnapshot(warehouseId, locationId) {
  const item = byId(getLocationOptions(warehouseId), locationId) || {}
  return {
    locationId: item.id || locationId || '',
    locationName: item.raw?.name || item.name || '',
  }
}

function defaultLocationId(warehouseId) {
  return firstId(getLocationOptions(warehouseId))
}

function balanceStatus(quantity, safetyStock, maxStock, lockedQuantity = 0) {
  if (lockedQuantity > 0 && quantity <= lockedQuantity) return 'locked'
  if (maxStock > 0 && quantity > maxStock) return 'overStock'
  if (safetyStock > 0 && quantity < safetyStock) return 'lowStock'
  return 'normal'
}

function inventoryBalance(payload = {}) {
  const material = materialSnapshot(payload.materialId)
  const warehouseId = payload.warehouseId || firstId(getEnabledWarehouses())
  const locationId = payload.locationId || defaultLocationId(warehouseId)
  const warehouse = warehouseSnapshot(warehouseId)
  const location = locationSnapshot(warehouseId, locationId)
  const quantity = toNumber(payload.quantity)
  const lockedQuantity = toNumber(payload.lockedQuantity ?? payload.lockedQty)
  const safetyStock = toNumber(payload.safetyStock ?? material.safetyStock)
  const maxStock = toNumber(payload.maxStock ?? material.maxStock)
  return {
    id: payload.id || createId('inv'),
    ...material,
    ...warehouse,
    ...location,
    batchNo: payload.batchNo || 'BATCH-DEFAULT',
    qualityStatus: payload.qualityStatus || 'qualified',
    quantity,
    availableQuantity: Math.max(0, quantity - lockedQuantity),
    availableQty: Math.max(0, quantity - lockedQuantity),
    lockedQuantity,
    lockedQty: lockedQuantity,
    safetyStock,
    maxStock,
    sourceModule: payload.sourceModule || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    productionDate: payload.productionDate || today(),
    expiryDate: payload.expiryDate || '',
    lastTransactionAt: payload.lastTransactionAt || '',
    status: payload.status || balanceStatus(quantity, safetyStock, maxStock, lockedQuantity),
    remark: payload.remark || '',
  }
}

function inventoryTransaction(payload = {}) {
  const material = materialSnapshot(payload.materialId)
  const warehouse = warehouseSnapshot(payload.warehouseId)
  const location = locationSnapshot(payload.warehouseId, payload.locationId)
  return {
    id: payload.id || createId('txn'),
    transactionNo: payload.transactionNo || createNo('TXN'),
    transactionType: payload.transactionType || 'opening',
    transactionDate: payload.transactionDate || today(),
    ...material,
    ...warehouse,
    ...location,
    batchNo: payload.batchNo || 'BATCH-DEFAULT',
    quantity: toNumber(payload.quantity),
    beforeQuantity: toNumber(payload.beforeQuantity),
    beforeQty: toNumber(payload.beforeQty ?? payload.beforeQuantity),
    afterQuantity: toNumber(payload.afterQuantity),
    afterQty: toNumber(payload.afterQty ?? payload.afterQuantity),
    qualityStatus: payload.qualityStatus || 'qualified',
    sourceModule: payload.sourceModule || 'wms',
    sourceType: payload.sourceType || 'manual',
    sourceId: payload.sourceId || '',
    sourceNo: payload.sourceNo || '',
    sourceInspectionId: payload.sourceInspectionId || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceReceiveId: payload.sourceReceiveId || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourcePurchaseOrderId: payload.sourcePurchaseOrderId || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    supplierId: payload.supplierId || '',
    supplierName: payload.supplierName || '',
    buyerId: payload.buyerId || '',
    buyerName: payload.buyerName || '',
    operator: payload.operator || firstId(getEmployeeOptions()),
    remark: payload.remark || '',
    createdAt: payload.createdAt || nowText(),
  }
}

function warehouseTask(payload = {}) {
  const material = materialSnapshot(payload.materialId)
  const warehouse = warehouseSnapshot(payload.warehouseId)
  const location = locationSnapshot(payload.warehouseId, payload.locationId)
  const businessType = payload.businessType
    || (payload.taskType === 'qualifiedInboundPrepare' || payload.sourceType === 'incomingInspection' ? 'qualifiedInboundPrepare'
      : payload.taskType === 'purchaseReceive' || payload.sourceType === 'scmPurchaseOrder' ? 'purchaseReceivePrepare'
        : payload.taskType || 'warehouseTask')
  const businessStatus = payload.businessStatus || ({
    purchaseReceivePrepare: '待收货',
    incomingInspection: '待检验',
    qualifiedInboundPrepare: payload.status === 'done' ? '已入库' : '待确认入库',
    inventoryPosting: '库存入库',
  }[businessType] || '')
  return {
    id: payload.id || createId('task'),
    taskNo: payload.taskNo || createNo('WT'),
    taskType: payload.taskType || 'purchaseReceive',
    businessType,
    businessStatus,
    sourceType: payload.sourceType || '',
    sourceId: payload.sourceId || '',
    sourceNo: payload.sourceNo || '',
    sourceLineId: payload.sourceLineId || '',
    sourceLineNo: payload.sourceLineNo || '',
    sourceInspectionId: payload.sourceInspectionId || '',
    sourceInspectionNo: payload.sourceInspectionNo || '',
    sourceReceiveId: payload.sourceReceiveId || '',
    sourceReceiveNo: payload.sourceReceiveNo || '',
    sourcePurchaseOrderId: payload.sourcePurchaseOrderId || '',
    sourcePurchaseOrderNo: payload.sourcePurchaseOrderNo || '',
    rootRequestNo: payload.rootRequestNo || '',
    ...material,
    ...warehouse,
    ...location,
    plannedQuantity: toNumber(payload.plannedQuantity),
    completedQuantity: toNumber(payload.completedQuantity),
    status: payload.status || 'pending',
    operatorId: payload.operatorId || firstId(getEmployeeOptions()),
    createdAt: payload.createdAt || nowText(),
    completedAt: payload.completedAt || '',
    remark: payload.remark || '',
  }
}

function stockWarning(payload = {}) {
  return {
    id: payload.id || createId('warn'),
    warningType: payload.warningType || 'lowStock',
    materialId: payload.materialId || '',
    warehouseId: payload.warehouseId || '',
    locationId: payload.locationId || '',
    batchNo: payload.batchNo || '',
    title: payload.title || '',
    content: payload.content || '',
    level: payload.level || 'yellow',
    status: payload.status || 'open',
    createdAt: payload.createdAt || nowText(),
    handledAt: payload.handledAt || '',
    handlerId: payload.handlerId || '',
    remark: payload.remark || '',
  }
}

function sourceData() {
  const materials = getEnabledMaterials()
  const warehouses = getEnabledWarehouses()
  const employees = getEmployeeOptions()
  return { materials, warehouses, employees }
}

function defaultState() {
  const { materials, warehouses, employees } = sourceData()
  const balances = []
  const transactions = []
  const tasks = []
  const warnings = []
  const materialFallback = materials[0]?.id || ''
  const warehouseFallback = warehouses[0]?.id || ''
  const operator = employees[0]?.id || ''

  for (let index = 0; index < 30; index += 1) {
    const material = materials[index % Math.max(1, materials.length)]
    const warehouse = warehouses[index % Math.max(1, warehouses.length)]
    const warehouseId = warehouse?.id || warehouseFallback
    const locations = getLocationOptions(warehouseId)
    const locationId = locations[index % Math.max(1, locations.length)]?.id || defaultLocationId(warehouseId)
    const baseSafety = toNumber(material?.raw?.safetyStock || 20)
    const baseMax = toNumber(material?.raw?.maxStock || 300)
    const quantity = index % 7 === 0 ? Math.max(1, baseSafety - 2) : index % 11 === 0 ? baseMax + 20 : 40 + index * 6
    balances.push(inventoryBalance({
      id: `inv-demo-${index + 1}`,
      materialId: material?.id || materialFallback,
      warehouseId,
      locationId,
      batchNo: `BATCH-${String(index + 1).padStart(3, '0')}`,
      quantity,
      safetyStock: baseSafety,
      maxStock: baseMax,
      lastTransactionAt: nowText(),
      remark: '演示库存余额',
    }))
  }

  for (let index = 0; index < 50; index += 1) {
    const balance = balances[index % balances.length]
    const quantity = index % 2 === 0 ? 5 + index : -(1 + (index % 9))
    const beforeQuantity = Math.max(0, balance.quantity - quantity)
    transactions.push(inventoryTransaction({
      id: `txn-demo-${index + 1}`,
      transactionNo: `TXN-202607-${String(index + 1).padStart(3, '0')}`,
      transactionType: index % 2 === 0 ? 'opening' : 'manualOut',
      transactionDate: today(),
      materialId: balance.materialId,
      warehouseId: balance.warehouseId,
      locationId: balance.locationId,
      batchNo: balance.batchNo,
      quantity,
      beforeQuantity,
      afterQuantity: beforeQuantity + quantity,
      sourceModule: 'wms',
      sourceType: 'demo',
      sourceId: balance.id,
      sourceNo: balance.batchNo,
      operator,
      remark: '演示库存流水',
    }))
  }

  for (let index = 0; index < 10; index += 1) {
    const balance = balances[index % balances.length]
    tasks.push(warehouseTask({
      id: `task-demo-${index + 1}`,
      taskNo: `WT-202607-${String(index + 1).padStart(3, '0')}`,
      taskType: index % 3 === 0 ? 'purchaseReceive' : index % 3 === 1 ? 'move' : 'count',
      sourceType: 'demo',
      sourceId: balance.id,
      sourceNo: balance.batchNo,
      materialId: balance.materialId,
      warehouseId: balance.warehouseId,
      locationId: balance.locationId,
      plannedQuantity: 10 + index,
      completedQuantity: index % 4 === 0 ? 10 + index : 0,
      status: index % 4 === 0 ? 'done' : 'pending',
      operatorId: operator,
      completedAt: index % 4 === 0 ? nowText() : '',
      remark: '演示仓库任务',
    }))
  }

  balances.slice(0, 10).forEach((balance, index) => {
    const type = balance.status === 'overStock' ? 'overStock' : balance.status === 'lowStock' ? 'lowStock' : index % 2 === 0 ? 'nearExpiry' : 'lowStock'
    warnings.push(stockWarning({
      id: `warn-demo-${index + 1}`,
      warningType: type,
      materialId: balance.materialId,
      warehouseId: balance.warehouseId,
      locationId: balance.locationId,
      batchNo: balance.batchNo,
      title: `${balance.materialName} 库存预警`,
      content: `当前库存 ${balance.quantity}，安全库存 ${balance.safetyStock}，最高库存 ${balance.maxStock}`,
      level: type === 'overStock' || type === 'lowStock' ? 'red' : 'yellow',
      status: index % 5 === 0 ? 'handled' : 'open',
    }))
  })

  return {
    inventoryBalances: balances,
    inventoryTransactions: transactions,
    warehouseTasks: tasks,
    stockWarnings: warnings,
  }
}

function normalizeState(raw = {}) {
  return {
    inventoryBalances: (raw.inventoryBalances || []).map((item) => inventoryBalance(item)),
    inventoryTransactions: (raw.inventoryTransactions || []).map((item) => inventoryTransaction(item)),
    warehouseTasks: (raw.warehouseTasks || []).map((item) => warehouseTask(item)),
    stockWarnings: (raw.stockWarnings || []).map((item) => stockWarning(item)),
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[WMS STORE] fallback to demo state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function replace(collectionName, id, factory, payload = {}) {
  const current = byId(state[collectionName], id)
  if (!current) return null
  Object.assign(current, factory({ ...current, ...payload, id: current.id }))
  persist()
  return clone(current)
}

function remove(collectionName, id) {
  const before = state[collectionName].length
  state[collectionName] = state[collectionName].filter((item) => String(item.id) !== String(id))
  persist()
  return before !== state[collectionName].length
}

export function getWmsState() {
  return clone(state)
}

export function saveWmsState(nextState) {
  state = normalizeState(nextState)
  persist()
  writeLog('保存WMS状态', 'wms', 'state')
  return getWmsState()
}

export function resetWmsState() {
  state = defaultState()
  persist()
  writeLog('恢复WMS演示数据', 'wms', 'demo')
  return getWmsState()
}

export function getInventoryBalances() { return clone(state.inventoryBalances) }
export function getInventoryBalanceById(id) { return clone(byId(state.inventoryBalances, id)) }
export function getInventoryByMaterial(materialId) { return clone(state.inventoryBalances.filter((item) => String(item.materialId) === String(materialId))) }
export function getInventoryByWarehouse(warehouseId) { return clone(state.inventoryBalances.filter((item) => String(item.warehouseId) === String(warehouseId))) }
export function getInventoryByLocation(locationId) { return clone(state.inventoryBalances.filter((item) => String(item.locationId) === String(locationId))) }
export function findInventoryBalance(materialId, warehouseId, locationId, batchNo = 'BATCH-DEFAULT') {
  return clone(state.inventoryBalances.find((item) => (
    String(item.materialId) === String(materialId)
    && String(item.warehouseId) === String(warehouseId)
    && String(item.locationId) === String(locationId)
    && String(item.batchNo || '') === String(batchNo || 'BATCH-DEFAULT')
  )) || null)
}

export function getInventoryBalanceKey(materialId, warehouseId, locationId, batchNo = 'BATCH-DEFAULT', qualityStatus = 'qualified') {
  return [materialId || '', warehouseId || '', locationId || '', batchNo || 'BATCH-DEFAULT', qualityStatus || 'qualified'].map(String).join('|')
}

export function createInventoryBalance(payload = {}) {
  const item = inventoryBalance(payload)
  state.inventoryBalances.unshift(item)
  persist()
  writeLog('创建库存余额', 'inventoryBalance', item.id, item.materialName)
  return item.id
}

export function updateInventoryBalance(id, payload = {}) {
  const item = replace('inventoryBalances', id, inventoryBalance, payload)
  if (item) writeLog('更新库存余额', 'inventoryBalance', id, item.materialName)
  return item
}

export function deleteInventoryBalance(id) {
  const ok = remove('inventoryBalances', id)
  if (ok) writeLog('删除库存余额', 'inventoryBalance', id)
  return ok
}

export function getInventoryTransactions() { return clone(state.inventoryTransactions) }
export function getInventoryTransactionById(id) { return clone(byId(state.inventoryTransactions, id)) }
export function createInventoryTransaction(payload = {}) {
  const item = inventoryTransaction(payload)
  state.inventoryTransactions.unshift(item)
  persist()
  writeLog('创建库存流水', 'inventoryTransaction', item.id, item.transactionNo)
  return item.id
}
export function getTransactionsByMaterial(materialId) { return clone(state.inventoryTransactions.filter((item) => String(item.materialId) === String(materialId))) }
export function getTransactionsBySource(sourceType, sourceId) {
  return clone(state.inventoryTransactions.filter((item) => String(item.sourceType) === String(sourceType) && String(item.sourceId) === String(sourceId)))
}

export function recalculateInventoryStatus(balanceId) {
  const balance = byId(state.inventoryBalances, balanceId)
  if (!balance) return null
  balance.status = balanceStatus(balance.quantity, balance.safetyStock, balance.maxStock, balance.lockedQuantity)
  balance.availableQuantity = Math.max(0, toNumber(balance.quantity) - toNumber(balance.lockedQuantity))
  persist()
  return clone(balance)
}

export function applyInventoryTransaction(payload = {}) {
  const materialId = payload.materialId
  const warehouseId = payload.warehouseId
  const locationId = payload.locationId || defaultLocationId(warehouseId)
  const batchNo = payload.batchNo || 'BATCH-DEFAULT'
  let balance = state.inventoryBalances.find((item) => (
    String(item.materialId) === String(materialId)
    && String(item.warehouseId) === String(warehouseId)
    && String(item.locationId) === String(locationId)
    && String(item.batchNo) === String(batchNo)
    && String(item.qualityStatus || 'qualified') === String(payload.qualityStatus || 'qualified')
  ))
  if (!balance) {
    const id = createInventoryBalance({ materialId, warehouseId, locationId, batchNo, quantity: 0, qualityStatus: payload.qualityStatus || 'qualified' })
    balance = byId(state.inventoryBalances, id)
  }
  const beforeQuantity = toNumber(balance.quantity)
  const quantity = toNumber(payload.quantity)
  const afterQuantity = beforeQuantity + quantity
  if (afterQuantity < 0) return { success: false, error: '库存不足，不能形成负库存。' }
  Object.assign(balance, inventoryBalance({
    ...balance,
    quantity: afterQuantity,
    lastTransactionAt: nowText(),
  }))
  const transaction = inventoryTransaction({
    ...payload,
    materialId,
    warehouseId,
    locationId,
    batchNo,
    beforeQuantity,
    afterQuantity,
    quantity,
  })
  state.inventoryTransactions.unshift(transaction)
  persist()
  writeLog('应用库存流水', 'inventoryBalance', balance.id, `${transaction.transactionNo} / ${quantity}`)
  return { success: true, balance: clone(balance), transaction: clone(transaction) }
}

export function updateInventoryBalanceFromInspectionLine(inspection, line, postType = 'purchaseInspectionIn') {
  const quantity = postType === 'concessionIn' ? toNumber(line.concessionQty) : toNumber(line.qualifiedQty)
  if (quantity <= 0) return { success: false, error: '入库数量必须大于0。' }
  const warehouseId = line.warehouseId || inspection.warehouseId
  const locationId = line.locationId || defaultLocationId(warehouseId)
  const batchNo = line.batchNo || 'BATCH-DEFAULT'
  const qualityStatus = postType === 'concessionIn' ? 'concession' : 'qualified'
  let balance = state.inventoryBalances.find((item) => (
    getInventoryBalanceKey(item.materialId, item.warehouseId, item.locationId, item.batchNo, item.qualityStatus)
    === getInventoryBalanceKey(line.materialId, warehouseId, locationId, batchNo, qualityStatus)
  ))
  const beforeQuantity = toNumber(balance?.quantity)
  if (!balance) {
    balance = inventoryBalance({
      materialId: line.materialId,
      warehouseId,
      locationId,
      batchNo,
      qualityStatus,
      quantity: 0,
      sourceModule: 'qms',
      sourceInspectionNo: inspection.inspectionNo,
      sourceReceiveNo: inspection.sourceReceiveNo,
      sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
      rootRequestNo: inspection.rootRequestNo,
    })
    state.inventoryBalances.unshift(balance)
  }
  const afterQuantity = beforeQuantity + quantity
  Object.assign(balance, inventoryBalance({
    ...balance,
    quantity: afterQuantity,
    availableQuantity: afterQuantity - toNumber(balance.lockedQuantity),
    availableQty: afterQuantity - toNumber(balance.lockedQuantity),
    qualityStatus,
    lastTransactionAt: nowText(),
    sourceModule: 'qms',
    sourceInspectionNo: inspection.inspectionNo,
    sourceReceiveNo: inspection.sourceReceiveNo,
    sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
    rootRequestNo: inspection.rootRequestNo,
    updatedAt: nowText(),
  }))
  writeLog('更新库存余额', 'inventoryBalance', balance.id, `${inspection.inspectionNo} / ${line.materialName} / ${quantity}`)
  writeQmsLog('更新库存余额', {
    sourceModule: 'QMS来料检验',
    sourceNo: inspection.inspectionNo,
    targetId: balance.id,
    targetNo: balance.batchNo,
    result: quantity,
  })
  return { success: true, balance: clone(balance), beforeQuantity, afterQuantity, quantity, qualityStatus }
}

export function createInventoryTransactionFromInspectionLine(inspection, line, postType = 'purchaseInspectionIn', balanceResult = {}) {
  const quantity = toNumber(balanceResult.quantity || (postType === 'concessionIn' ? line.concessionQty : line.qualifiedQty))
  const transaction = inventoryTransaction({
    transactionType: postType,
    transactionDate: today(),
    materialId: line.materialId,
    warehouseId: line.warehouseId || inspection.warehouseId,
    locationId: line.locationId || defaultLocationId(line.warehouseId || inspection.warehouseId),
    batchNo: line.batchNo || 'BATCH-DEFAULT',
    qualityStatus: balanceResult.qualityStatus || (postType === 'concessionIn' ? 'concession' : 'qualified'),
    quantity,
    beforeQuantity: balanceResult.beforeQuantity,
    afterQuantity: balanceResult.afterQuantity,
    sourceModule: 'qms',
    sourceType: 'incomingInspection',
    sourceId: inspection.id,
    sourceNo: inspection.inspectionNo,
    sourceInspectionId: inspection.id,
    sourceInspectionNo: inspection.inspectionNo,
    sourceReceiveId: inspection.sourceReceiveId,
    sourceReceiveNo: inspection.sourceReceiveNo,
    sourcePurchaseOrderId: inspection.sourcePurchaseOrderId || inspection.sourceOrderId,
    sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
    rootRequestNo: inspection.rootRequestNo,
    supplierId: inspection.supplierId,
    supplierName: inspection.supplierName,
    buyerId: inspection.buyerId,
    buyerName: inspection.buyerName,
    remark: postType === 'concessionIn' ? 'QMS让步接收入库' : 'QMS采购检验合格入库',
  })
  state.inventoryTransactions.unshift(transaction)
  writeLog('生成库存流水', 'inventoryTransaction', transaction.id, `${transaction.transactionNo} / ${inspection.inspectionNo}`)
  writeQmsLog('生成库存流水', {
    sourceModule: 'QMS来料检验',
    sourceNo: inspection.inspectionNo,
    targetId: transaction.id,
    targetNo: transaction.transactionNo,
    result: quantity,
  })
  return clone(transaction)
}

export function receiveQualifiedInspectionToInventory(inspectionId) {
  const inspection = getIncomingInspectionById(inspectionId)
  if (!inspection) return { success: false, error: '未找到来料检验单。' }
  if (inspection.inventoryPosted) {
    writeQmsLog('拦截重复入库', {
      sourceModule: 'QMS来料检验',
      sourceNo: inspection.inspectionNo,
      targetId: inspection.id,
      targetNo: inspection.inspectionNo,
      result: '该检验单已生成库存入库，不能重复入库。',
    })
    return { success: false, error: '该检验单已生成库存入库，不能重复入库。' }
  }
  if (inspection.status !== 'inboundPrepared') return { success: false, error: '只有已生成检验合格入库预备后，才能确认入库。' }
  const transactionIds = []
  const postedLines = []
  let hasRejectedOnly = false
  ;(inspection.lines || []).forEach((line) => {
    if (line.inventoryPosted) return
    const lineTransactionIds = []
    const qualifiedQty = toNumber(line.qualifiedQty)
    const concessionQty = toNumber(line.concessionQty)
    if (qualifiedQty > 0) {
      const balanceResult = updateInventoryBalanceFromInspectionLine(inspection, line, 'purchaseInspectionIn')
      if (balanceResult.success) {
        const transaction = createInventoryTransactionFromInspectionLine(inspection, line, 'purchaseInspectionIn', balanceResult)
        transactionIds.push(transaction.id)
        lineTransactionIds.push(transaction.id)
      }
    }
    if (concessionQty > 0) {
      const balanceResult = updateInventoryBalanceFromInspectionLine(inspection, line, 'concessionIn')
      if (balanceResult.success) {
        const transaction = createInventoryTransactionFromInspectionLine(inspection, line, 'concessionIn', balanceResult)
        transactionIds.push(transaction.id)
        lineTransactionIds.push(transaction.id)
      }
    }
    if (toNumber(line.returnQty) > 0) writeQmsLog('退货处理', { sourceModule: 'QMS来料检验', sourceNo: inspection.inspectionNo, targetId: inspection.id, targetNo: inspection.inspectionNo, result: line.returnQty })
    if (toNumber(line.scrapQty) > 0) writeQmsLog('报废处理', { sourceModule: 'QMS来料检验', sourceNo: inspection.inspectionNo, targetId: inspection.id, targetNo: inspection.inspectionNo, result: line.scrapQty })
    if (toNumber(line.reworkQty) > 0) writeQmsLog('返工处理', { sourceModule: 'QMS来料检验', sourceNo: inspection.inspectionNo, targetId: inspection.id, targetNo: inspection.inspectionNo, result: line.reworkQty })
    if (!lineTransactionIds.length && toNumber(line.unqualifiedQty) > 0) hasRejectedOnly = true
    postedLines.push({
      id: line.id,
      inventoryPosted: lineTransactionIds.length > 0,
      inventoryPostedQty: qualifiedQty + concessionQty,
      inventoryTransactionId: lineTransactionIds[0] || '',
      inventoryTransactionIds: lineTransactionIds,
      qualityStatus: concessionQty > 0 ? 'concession' : qualifiedQty > 0 ? 'qualified' : hasRejectedOnly ? 'returnPending' : line.qualityStatus,
    })
  })
  if (!transactionIds.length) {
    applyInspectionInventoryPostResult(inspection.id, {
      inventoryPosted: false,
      inventoryPostStatus: 'rejected',
      inventoryPostMessage: '全部不合格且无让步接收，未生成库存入库。',
      status: 'rejected',
      lines: postedLines,
    })
    return { success: true, inventoryTransactionIds: [], status: 'rejected', message: '全部不合格且无让步接收，未生成库存入库。' }
  }
  persist()
  const status = 'inventoryPosted'
  applyInspectionInventoryPostResult(inspection.id, {
    inventoryPosted: true,
    inventoryTransactionIds: transactionIds,
    inventoryPostStatus: 'posted',
    inventoryPostMessage: `已生成 ${transactionIds.length} 条库存流水。`,
    status,
    lines: postedLines,
  })
  writeLog('合格入库', 'incomingInspection', inspection.id, `${inspection.inspectionNo} / ${transactionIds.length} 条流水`)
  writeQmsLog('确认入库', {
    sourceModule: 'QMS来料检验',
    sourceNo: inspection.inspectionNo,
    targetId: inspection.id,
    targetNo: inspection.inspectionNo,
    result: `${transactionIds.length} 条库存流水`,
  })
  writeQmsLog('合格入库', {
    sourceModule: 'QMS来料检验',
    sourceNo: inspection.inspectionNo,
    targetId: inspection.id,
    targetNo: inspection.inspectionNo,
    result: `${transactionIds.length} 条库存流水`,
  })
  return { success: true, inventoryTransactionIds: transactionIds, status }
}

export function canCreateInboundPrepareFromInspectionLine(line = {}) {
  return toNumber(line.qualifiedQty) + toNumber(line.concessionQty) > 0
    && line.inventoryPosted !== true
    && line.inboundPrepared !== true
}

export function getInboundPreparablesFromInspections() {
  return (getQmsState().incomingInspections || [])
    .filter((inspection) => ['inspected', 'partiallyReleased', 'inboundPrepared'].includes(inspection.status))
    .flatMap((inspection) => (inspection.lines || [])
      .filter((line) => canCreateInboundPrepareFromInspectionLine(line))
      .map((line) => ({
        inspectionId: inspection.id,
        inspectionNo: inspection.inspectionNo,
        sourceReceiveId: inspection.sourceReceiveId,
        sourceReceiveNo: inspection.sourceReceiveNo,
        sourcePurchaseOrderId: inspection.sourcePurchaseOrderId || inspection.sourceOrderId,
        sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
        rootRequestNo: inspection.rootRequestNo,
        supplierId: inspection.supplierId,
        supplierName: inspection.supplierName,
        buyerId: inspection.buyerId,
        buyerName: inspection.buyerName,
        line,
        inboundQty: toNumber(line.qualifiedQty) + toNumber(line.concessionQty),
      })))
}

export function createInboundPrepareTaskFromInspection(inspectionId) {
  const inspection = getIncomingInspectionById(inspectionId)
  if (!inspection) return { success: false, error: '未找到来料检验单。' }
  if (inspection.inventoryPosted || inspection.status === 'inventoryPosted') {
    writeQmsLog('拦截重复生成检验合格入库预备', {
      sourceModule: 'QMS来料检验',
      sourceNo: inspection.inspectionNo,
      targetId: inspection.id,
      targetNo: inspection.inspectionNo,
      result: '已确认入库，不能重复生成检验合格入库预备。',
    })
    return { success: false, error: '已确认入库，不能重复生成检验合格入库预备。' }
  }
  if (inspection.status === 'inboundPrepared' || (inspection.inboundPrepareTaskIds || []).length) {
    writeQmsLog('拦截重复生成检验合格入库预备', {
      sourceModule: 'QMS来料检验',
      sourceNo: inspection.inspectionNo,
      targetId: inspection.id,
      targetNo: inspection.inspectionNo,
      result: '已生成检验合格入库预备，不能重复生成。',
    })
    return { success: false, error: '已生成检验合格入库预备，不能重复生成。' }
  }
  if (inspection.status !== 'inspected') {
    writeQmsLog('拦截未检验物料生成入库预备', {
      sourceModule: 'QMS来料检验',
      sourceNo: inspection.inspectionNo,
      targetId: inspection.id,
      targetNo: inspection.inspectionNo,
      result: '只有已检验状态可以生成检验合格入库预备。',
    })
    return { success: false, error: '只有已检验状态可以生成检验合格入库预备。' }
  }
  const eligibleLines = (inspection.lines || []).filter((line) => canCreateInboundPrepareFromInspectionLine(line))
  if (!eligibleLines.length) {
    writeQmsLog('拦截未检验物料生成入库预备', {
      sourceModule: 'QMS来料检验',
      sourceNo: inspection.inspectionNo,
      targetId: inspection.id,
      targetNo: inspection.inspectionNo,
      result: '没有合格或让步接收的可入库数量。',
    })
    return { success: false, error: '没有合格或让步接收的可入库数量，不能生成检验合格入库预备。' }
  }
  const createdIds = []
  const preparedLines = eligibleLines.map((line) => {
    const existing = state.warehouseTasks.find((task) => (
      task.sourceType === 'incomingInspection'
      && String(task.sourceId) === String(inspection.id)
      && String(task.sourceLineId) === String(line.id)
      && task.businessType === 'qualifiedInboundPrepare'
      && task.status !== 'cancelled'
    ))
    if (existing) {
      return {
        id: line.id,
        inboundPrepared: true,
        inboundPreparedQty: toNumber(line.qualifiedQty) + toNumber(line.concessionQty),
        inboundPrepareTaskId: existing.id,
      }
    }
    const taskId = createWarehouseTask({
      taskType: 'qualifiedInboundPrepare',
      businessType: 'qualifiedInboundPrepare',
      businessStatus: '待确认入库',
      sourceType: 'incomingInspection',
      sourceId: inspection.id,
      sourceNo: inspection.inspectionNo,
      sourceLineId: line.id,
      sourceLineNo: line.lineNo,
      sourceInspectionId: inspection.id,
      sourceInspectionNo: inspection.inspectionNo,
      sourceReceiveId: inspection.sourceReceiveId,
      sourceReceiveNo: inspection.sourceReceiveNo,
      sourcePurchaseOrderId: inspection.sourcePurchaseOrderId || inspection.sourceOrderId,
      sourcePurchaseOrderNo: inspection.sourcePurchaseOrderNo || inspection.sourceOrderNo,
      rootRequestNo: inspection.rootRequestNo,
      materialId: line.materialId,
      warehouseId: line.warehouseId || inspection.warehouseId,
      locationId: line.locationId,
      plannedQuantity: toNumber(line.qualifiedQty) + toNumber(line.concessionQty),
      completedQuantity: 0,
      status: 'pending',
      operatorId: inspection.inspectorId,
      remark: '由QMS已检验合格/让步接收数量生成的检验合格入库预备，确认入库前不增加库存。',
    })
    createdIds.push(taskId)
    return {
      id: line.id,
      inboundPrepared: true,
      inboundPreparedQty: toNumber(line.qualifiedQty) + toNumber(line.concessionQty),
      inboundPrepareTaskId: taskId,
    }
  })
  applyInspectionInventoryPostResult(inspection.id, {
    inventoryPosted: false,
    inventoryPostStatus: 'inboundPrepared',
    inventoryPostMessage: `已生成 ${createdIds.length} 条检验合格入库预备。`,
    inboundPreparedAt: nowText(),
    inboundPrepareTaskIds: createdIds,
    status: 'inboundPrepared',
    lines: preparedLines,
  })
  persist()
  writeQmsLog('生成检验合格入库预备', {
    sourceModule: 'QMS来料检验',
    sourceNo: inspection.inspectionNo,
    targetId: inspection.id,
    targetNo: inspection.inspectionNo,
    result: `${createdIds.length} 条预备任务`,
  })
  writeLog('修正仓库任务业务类型', 'warehouseTask', inspection.id, 'qualifiedInboundPrepare / 检验合格入库预备')
  return { success: true, taskIds: createdIds, inspectionId: inspection.id, inspectionNo: inspection.inspectionNo }
}

export function getWarehouseTaskBusinessType(task = {}) {
  if (task.businessType) return task.businessType
  if (task.taskType === 'purchaseReceive') return 'purchaseReceivePrepare'
  if (task.taskType === 'qualifiedInboundPrepare') return 'qualifiedInboundPrepare'
  if (task.sourceType === 'incomingInspection') return 'qualifiedInboundPrepare'
  if (task.sourceType === 'scmPurchaseOrder') return 'purchaseReceivePrepare'
  return task.taskType || 'warehouseTask'
}

function wmsBatchResult(ids = [], handler, label, noGetter = (id) => id) {
  const result = { total: ids.length, successCount: 0, failedCount: 0, successItems: [], failedItems: [], failedReason: [] }
  ids.forEach((id) => {
    const no = noGetter(id)
    const outcome = handler(id)
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
  writeLog(label, 'batch', label, `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}`)
  if (result.failedCount) writeLog('批量操作失败原因', 'batch', label, result.failedReason.join('；'))
  return result
}

export function batchCreateWarehouseTasksFromPurchaseOrders(ids = []) {
  return wmsBatchResult(ids, (id) => {
    const existing = state.warehouseTasks.find((task) => task.sourceType === 'scmPurchaseOrder' && String(task.sourceId) === String(id) && task.status !== 'cancelled')
    if (existing) {
      writeLog('批量生成仓库收货任务跳过已生成记录', 'purchaseOrder', id, '已生成仓库收货任务，已跳过。')
      return { success: false, error: '已生成仓库收货任务，已跳过。' }
    }
    return createPurchaseReceiveTaskFromScmPurchaseOrder(id)
  }, '批量生成仓库收货任务', (id) => {
    const order = getScmState().purchaseOrders.find((item) => String(item.id) === String(id))
    return order?.poNo || id
  })
}

export function batchCompleteWarehouseTasks(ids = []) {
  return wmsBatchResult(ids, (id) => {
    const task = byId(state.warehouseTasks, id)
    if (!task) return { success: false, error: '未找到仓库任务。' }
    if (!['pending', 'processing'].includes(task.status)) return { success: false, error: '只有待处理或处理中任务可以完成。' }
    return completeWarehouseTask(id)
  }, '批量完成任务', (id) => byId(state.warehouseTasks, id)?.taskNo || id)
}

export function batchCancelWarehouseTasks(ids = []) {
  return wmsBatchResult(ids, (id) => {
    const task = byId(state.warehouseTasks, id)
    if (!task) return { success: false, error: '未找到仓库任务。' }
    if (['done', 'cancelled'].includes(task.status)) return { success: false, error: '已完成或已取消任务不能重复取消。' }
    return cancelWarehouseTask(id)
  }, '批量取消任务', (id) => byId(state.warehouseTasks, id)?.taskNo || id)
}

export function batchPostInboundFromWarehouseTasks(ids = []) {
  return wmsBatchResult(ids, (id) => {
    const task = byId(state.warehouseTasks, id)
    if (!task) return { success: false, error: '未找到仓库任务。' }
    if (getWarehouseTaskBusinessType(task) !== 'qualifiedInboundPrepare') return { success: false, error: '只有检验合格入库预备任务可以确认入库。' }
    const inspection = getIncomingInspectionById(task.sourceInspectionId || task.sourceId)
    if (!inspection || inspection.status !== 'inboundPrepared') return { success: false, error: '来源检验单不是已生成入库预备状态。' }
    return receiveQualifiedInspectionToInventory(inspection.id)
  }, '批量确认入库', (id) => byId(state.warehouseTasks, id)?.taskNo || id)
}

export function increaseInventory(payload = {}) {
  return applyInventoryTransaction({ ...payload, quantity: Math.abs(toNumber(payload.quantity)), transactionType: payload.transactionType || 'manualIn' })
}

export function decreaseInventory(payload = {}) {
  return applyInventoryTransaction({ ...payload, quantity: -Math.abs(toNumber(payload.quantity)), transactionType: payload.transactionType || 'manualOut' })
}

export function lockInventory(payload = {}) {
  const balance = byId(state.inventoryBalances, payload.balanceId)
  if (!balance) return { success: false, error: '未找到库存余额。' }
  const quantity = Math.abs(toNumber(payload.quantity))
  if (quantity > balance.availableQuantity) return { success: false, error: '可用库存不足，不能锁定。' }
  balance.lockedQuantity = toNumber(balance.lockedQuantity) + quantity
  recalculateInventoryStatus(balance.id)
  writeLog('锁定库存', 'inventoryBalance', balance.id, quantity)
  return { success: true, balance: clone(balance) }
}

export function unlockInventory(payload = {}) {
  const balance = byId(state.inventoryBalances, payload.balanceId)
  if (!balance) return { success: false, error: '未找到库存余额。' }
  balance.lockedQuantity = Math.max(0, toNumber(balance.lockedQuantity) - Math.abs(toNumber(payload.quantity)))
  recalculateInventoryStatus(balance.id)
  writeLog('解锁库存', 'inventoryBalance', balance.id, payload.quantity)
  return { success: true, balance: clone(balance) }
}

export function getWarehouseTasks() { return clone(state.warehouseTasks) }
export function getWarehouseTaskById(id) { return clone(byId(state.warehouseTasks, id)) }
export function createWarehouseTask(payload = {}) {
  const item = warehouseTask(payload)
  state.warehouseTasks.unshift(item)
  persist()
  writeLog('创建仓库任务', 'warehouseTask', item.id, item.taskNo)
  return item.id
}
export function updateWarehouseTask(id, payload = {}) {
  const item = replace('warehouseTasks', id, warehouseTask, payload)
  if (item) writeLog('更新仓库任务', 'warehouseTask', id, item.taskNo)
  return item
}
export function completeWarehouseTask(id) {
  const task = byId(state.warehouseTasks, id)
  if (!task || ['done', 'cancelled'].includes(task.status)) return { success: false, error: '当前任务不可完成。' }
  Object.assign(task, { status: 'done', completedQuantity: task.plannedQuantity, completedAt: nowText() })
  persist()
  writeLog('完成仓库任务', 'warehouseTask', id, task.taskNo)
  return { success: true }
}
export function cancelWarehouseTask(id) {
  const task = byId(state.warehouseTasks, id)
  if (!task || ['done', 'cancelled'].includes(task.status)) return { success: false, error: '当前任务不可取消。' }
  Object.assign(task, { status: 'cancelled', completedAt: nowText() })
  persist()
  writeLog('取消仓库任务', 'warehouseTask', id, task.taskNo)
  return { success: true }
}

export function getStockWarnings() { return clone(state.stockWarnings) }
export function generateStockWarnings() {
  const generated = []
  state.inventoryBalances.forEach((balance) => {
    const warningType = balance.status === 'lowStock' ? 'lowStock' : balance.status === 'overStock' ? 'overStock' : ''
    if (!warningType) return
    const exists = state.stockWarnings.some((item) => item.status === 'open' && String(item.materialId) === String(balance.materialId) && String(item.batchNo) === String(balance.batchNo) && item.warningType === warningType)
    if (exists) return
    generated.push(stockWarning({
      warningType,
      materialId: balance.materialId,
      warehouseId: balance.warehouseId,
      locationId: balance.locationId,
      batchNo: balance.batchNo,
      title: `${balance.materialName} ${warningType === 'lowStock' ? '低库存' : '超库存'}预警`,
      content: `当前库存 ${balance.quantity}，安全库存 ${balance.safetyStock}，最高库存 ${balance.maxStock}`,
      level: warningType === 'lowStock' ? 'red' : 'yellow',
    }))
  })
  state.stockWarnings = [...generated, ...state.stockWarnings]
  persist()
  writeLog('生成库存预警', 'stockWarning', 'batch', `${generated.length} 条`)
  return clone(generated)
}
export function handleStockWarning(id, payload = {}) {
  const warning = byId(state.stockWarnings, id)
  if (!warning) return { success: false, error: '未找到库存预警。' }
  Object.assign(warning, { ...payload, status: 'handled', handledAt: nowText() })
  persist()
  writeLog('处理库存预警', 'stockWarning', id, warning.title)
  return { success: true }
}
export function ignoreStockWarning(id) {
  const warning = byId(state.stockWarnings, id)
  if (!warning) return { success: false, error: '未找到库存预警。' }
  Object.assign(warning, { status: 'ignored', handledAt: nowText() })
  persist()
  writeLog('忽略库存预警', 'stockWarning', id, warning.title)
  return { success: true }
}

export function getReceivableScmPurchaseOrders() {
  const tasks = state.warehouseTasks.filter((task) => task.sourceType === 'scmPurchaseOrder' && task.status !== 'cancelled')
  const receivableOrders = getScmState().purchaseOrders
    .filter((order) => isReceivablePurchaseOrderStatus(order.status))
    .filter((order) => !tasks.some((task) => String(task.sourceId) === String(order.id)))
    .map((order) => {
      const items = getScmPurchaseOrderItems(order.id)
      const orderPlanDate = items
        .map((item) => item.planDeliveryDate || item.plannedArrivalDate || item.expectedDeliveryDate || item.deliveryDate)
        .filter(Boolean)
        .sort()[0] || order.planDeliveryDate || order.plannedArrivalDate || order.expectedDeliveryDate || ''
      const validItems = items
        .filter((item) => item.materialCode || item.materialName)
        .map((item) => ({
          ...item,
          expectedDeliveryDate: item.expectedDeliveryDate || item.planDeliveryDate || item.plannedArrivalDate || '',
          plannedArrivalDate: item.plannedArrivalDate || item.planDeliveryDate || item.expectedDeliveryDate || '',
          sourceOrderNo: order.poNo,
          sourceOrderLineNo: item.lineNo,
          requestDepartment: item.rootRequestDepartment || order.rootRequestDepartment || order.requestDepartment || '',
          demandDepartment: item.rootDemandDepartment || order.rootDemandDepartment || order.demandDepartment || '',
          purchaseDepartment: item.rootPurchaseDepartment || order.rootPurchaseDepartment || order.purchaseDepartment || '',
          pendingQty: Math.max(0, toNumber(item.quantity) - toNumber(item.receivedQty)),
          planPrice: toNumber(item.planPrice || item.price),
          planAmount: toNumber(item.planAmount || item.amount),
          actualPrice: toNumber(item.actualPrice),
          actualAmount: toNumber(item.actualAmount),
        }))
      return {
        ...order,
        expectedDeliveryDate: order.expectedDeliveryDate || orderPlanDate,
        planDeliveryDate: order.planDeliveryDate || orderPlanDate,
        plannedArrivalDate: orderPlanDate,
        supplierName: getScmDisplayName('supplier', order.supplierId),
        buyerName: getScmDisplayName('employee', order.buyerId),
        departmentName: getScmDisplayName('department', order.departmentId),
        requestDepartment: order.rootRequestDepartment || order.requestDepartment || '',
        demandDepartment: order.rootDemandDepartment || order.demandDepartment || '',
        purchaseDepartment: order.rootPurchaseDepartment || order.purchaseDepartment || '',
        receiveStage: order.status === 'issued' ? '已下达待收货' : '已审批未下达（兼容）',
        lineCount: validItems.length,
        totalQuantity: validItems.reduce((sum, item) => sum + toNumber(item.quantity), 0),
        receivableQuantity: validItems.reduce((sum, item) => sum + toNumber(item.pendingQty), 0),
        receivableQty: validItems.reduce((sum, item) => sum + toNumber(item.pendingQty), 0),
        planAmount: toNumber(order.planAmount || validItems.reduce((sum, item) => sum + toNumber(item.planAmount), 0)),
        actualAmount: toNumber(order.actualAmount),
        items: validItems,
      }
    })
    .filter((order) => order.lineCount > 0 && order.receivableQuantity > 0)
  writeLog('采购订单进入 WMS 到货预备', 'purchaseOrder', 'receivable', `${receivableOrders.length} 张待收货采购订单`)
  return receivableOrders
}

export function createPurchaseReceiveTaskFromScmPurchaseOrder(poId) {
  const order = getScmState().purchaseOrders.find((item) => String(item.id) === String(poId))
  if (!order || !isReceivablePurchaseOrderStatus(order.status)) return { success: false, error: '只有已审批、已下达或部分收货的采购订单可以生成收货任务。' }
  const items = getScmPurchaseOrderItems(poId).filter((item) => item.materialCode || item.materialName)
  if (!items.length) return { success: false, error: '采购订单没有明细，不能生成收货任务。' }
  const existing = state.warehouseTasks.find((task) => task.sourceType === 'scmPurchaseOrder' && String(task.sourceId) === String(poId) && task.status !== 'cancelled')
  if (existing) return { success: false, error: '已生成仓库收货任务，不能重复生成。' }
  const createdIds = items.map((item) => createWarehouseTask({
    taskType: 'purchaseReceive',
    sourceType: 'scmPurchaseOrder',
    sourceId: poId,
    sourceNo: order.poNo,
    sourceLineId: item.sourceLineId || item.sourceItemId || item.id,
    sourceLineNo: item.lineNo,
    rootRequestNo: item.rootRequestNo || order.rootRequestNo,
    materialId: item.materialId,
    warehouseId: item.warehouseId,
    locationId: item.locationId,
    plannedQuantity: item.quantity,
    completedQuantity: 0,
    status: 'pending',
    operatorId: order.buyerId,
    remark: '由SCM采购订单生成的收货预备任务，本步骤不增加库存。',
  }))
  writeLog('SCM采购订单生成收货任务', 'purchaseOrder', poId, `${order.poNo} / ${createdIds.length} 条任务`)
  return { success: true, taskIds: createdIds }
}
