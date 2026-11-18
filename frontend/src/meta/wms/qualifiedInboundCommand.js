import { getEnabledWarehouses, getLocationOptions } from '../manufacturing/manufacturingReferenceService.js'
import { runBusinessFlowTransaction } from '../process/businessFlowTransactionCoordinator.js'
import { getScmState } from '../scm/scmStore.js'
import { evaluateScmInboundQuantity } from '../schema/scm/scmInboundQuantityRule.js'
import {
  applyInspectionInventoryPostResult,
  getIncomingInspectionById,
  getQmsState,
  saveQmsState,
} from '../qms/qmsStore.js'
import {
  applyPurchaseReceiveInventoryPostResult,
  getPurchaseReceiveById,
  getPurchaseReceiveState,
  listPurchaseReceives,
  savePurchaseReceiveState,
} from './purchaseReceiveStore.js'
import {
  completeWarehouseTask,
  getWarehouseTaskBusinessType,
  getWmsState,
  receiveQualifiedInspectionToInventory,
  saveWmsState,
} from './wmsStore.js'

export const QUALIFIED_INBOUND_COMMAND_VERSION = 'V1.14.2.8.4.7.23'

function fail(errorCode, message, failedStep = 'precheck', extra = {}) {
  return { ok: false, success: false, status: 'failed', errorCode, message, error: message, failedStep, rollbackResult: 'not_required', ...extra }
}

function transactionError(errorCode, message, failedStep) {
  const error = new Error(message)
  error.errorCode = errorCode
  error.failedStep = failedStep
  return error
}

function findTask(taskId) {
  return (getWmsState().warehouseTasks || []).find((item) => String(item.id) === String(taskId)) || null
}

function findTaskTransactions(task) {
  return (getWmsState().inventoryTransactions || []).filter((item) => (
    String(item.sourceWarehouseTaskId || '') === String(task.id)
    || (String(item.sourceInspectionId || '') === String(task.sourceInspectionId || task.sourceId)
      && item.transactionType === 'purchaseInspectionIn')
  ))
}

function findPurchaseReceive(task) {
  return getPurchaseReceiveById(task.sourceReceiveId)
    || listPurchaseReceives().find((item) => String(item.receiveNo) === String(task.sourceReceiveNo))
    || null
}

function validateReference(task) {
  const warehouse = getEnabledWarehouses().find((item) => String(item.id) === String(task.warehouseId))
  if (!warehouse) return fail('warehouse_not_found', `未找到仓库 ${task.warehouseId}。`)
  const location = getLocationOptions(task.warehouseId).find((item) => String(item.id) === String(task.locationId))
  if (!location) return fail('location_not_found', `库位 ${task.locationId} 不属于仓库 ${task.warehouseId}。`)
  return { ok: true, warehouse, location }
}

export function getQualifiedInboundTaskActionState(taskId) {
  const task = findTask(taskId)
  if (!task) return fail('task_not_found', '未找到仓库任务。')
  const transactions = findTaskTransactions(task)
  if (task.status === 'done' && transactions.length === 1) {
    return { ok: true, allowed: false, alreadyCompleted: true, reason: '该仓库任务已确认入库。', task, inventoryTransaction: transactions[0] }
  }
  if (getWarehouseTaskBusinessType(task) !== 'qualifiedInboundPrepare') return fail('task_type_invalid', '只有检验合格入库预备任务可以确认入库。')
  if (task.status !== 'pending') return fail('task_status_invalid', '只有待确认入库状态可以执行正式入库。')
  if (transactions.length) return fail('inventory_transaction_conflict', '当前仓库任务已经存在正式入库流水。')
  const inspection = getIncomingInspectionById(task.sourceInspectionId || task.sourceId)
  if (!inspection) return fail('inspection_not_found', '未找到来源来料检验单。')
  if (inspection.status !== 'inboundPrepared' || inspection.inventoryPosted) return fail('inspection_status_invalid', '来源来料检验单不是待确认入库状态。')
  const inspectionLines = inspection.lines || []
  const inspectionQualified = inspectionLines.length > 0
    && inspectionLines.every((line) => line.inspectResult === 'qualified' || Number(line.qualifiedQty || 0) > 0)
  if (!inspectionQualified) return fail('inspection_result_invalid', '来源来料检验结论不是合格。')
  const qualifiedQty = (inspection.lines || []).reduce((sum, line) => (
    sum + Number(line.qualifiedQty || 0) + Number(line.concessionQty || 0)
  ), 0)
  const quantityRule = evaluateScmInboundQuantity({
    warehousePlanQuantity: task.plannedQuantity,
    completedQuantity: task.completedQuantity,
    qualifiedQuantity: qualifiedQty,
  })
  if (!quantityRule.allowed) return fail('task_quantity_invalid', `仓库计划数量、完成数量与检验合格数量不符合入库条件：${quantityRule.reasons.join('；')}`, 'precheck', {
    quantityFacts: quantityRule,
  })
  const purchaseReceive = findPurchaseReceive(task)
  if (!purchaseReceive) return fail('purchase_receive_not_found', '未找到来源采购收货预备单。')
  if (purchaseReceive.inventoryPosted) return fail('purchase_receive_already_posted', '来源采购收货预备已经完成入库。')
  const order = (getScmState().purchaseOrders || []).find((item) => String(item.id) === String(task.sourcePurchaseOrderId) || String(item.poNo) === String(task.sourcePurchaseOrderNo))
  if (!order) return fail('purchase_order_not_found', '未找到来源采购订单。')
  const reference = validateReference(task)
  if (!reference.ok) return reference
  return {
    ok: true,
    allowed: true,
    alreadyCompleted: false,
    reason: '',
    quantityFacts: quantityRule,
    task,
    inspection,
    purchaseReceive,
    order,
    ...reference,
  }
}

export async function confirmQualifiedInboundWarehouseTask(input = {}) {
  const taskId = input.taskId || ''
  const precheck = getQualifiedInboundTaskActionState(taskId)
  if (precheck.alreadyCompleted) {
    return {
      ok: true,
      success: true,
      status: 'already_completed',
      taskId: precheck.task.id,
      taskNo: precheck.task.taskNo,
      completedQuantity: precheck.task.completedQuantity,
      inventoryTransaction: precheck.inventoryTransaction,
      payableGenerated: false,
    }
  }
  if (!precheck.ok || !precheck.allowed) return precheck

  const result = await runBusinessFlowTransaction({
    participants: [
      { name: 'wms', getState: getWmsState, saveState: saveWmsState },
      { name: 'qms', getState: getQmsState, saveState: saveQmsState },
      { name: 'purchaseReceive', getState: getPurchaseReceiveState, saveState: savePurchaseReceiveState },
    ],
    operation: async () => {
      const inventoryResult = receiveQualifiedInspectionToInventory(precheck.inspection.id, { warehouseTask: precheck.task })
      if (!inventoryResult.success) throw transactionError('inventory_write_failed', inventoryResult.error || '库存写入失败。', 'inventory')
      const transactions = findTaskTransactions(precheck.task)
      if (transactions.length !== 1) throw transactionError('inventory_transaction_invalid', '正式入库流水数量不是1。', 'inventory_transaction_validation')
      const transaction = transactions[0]
      const taskResult = completeWarehouseTask(precheck.task.id, {
        qualifiedInboundConfirmed: true,
        inventoryTransactionId: transaction.id,
        inventoryTransactionNo: transaction.transactionNo,
        inventoryTransactionIds: [transaction.id],
      })
      if (!taskResult.success) throw transactionError('task_completion_failed', taskResult.error || '仓库任务完成失败。', 'warehouse_task')
      const receiveResult = applyPurchaseReceiveInventoryPostResult(precheck.purchaseReceive.id, {
        receiveNo: precheck.purchaseReceive.receiveNo,
        inventoryTransactionId: transaction.id,
        inventoryTransactionNo: transaction.transactionNo,
        inventoryTransactionIds: [transaction.id],
        inboundWarehouseTaskId: precheck.task.id,
        inboundWarehouseTaskNo: precheck.task.taskNo,
      })
      if (!receiveResult.success) throw transactionError('purchase_receive_writeback_failed', receiveResult.error || '采购收货状态回写失败。', 'purchase_receive')

      const wms = getWmsState()
      const task = (wms.warehouseTasks || []).find((item) => String(item.id) === String(precheck.task.id))
      const balance = (wms.inventoryBalances || []).find((item) => item.materialId === precheck.task.materialId && item.warehouseId === precheck.task.warehouseId && item.locationId === precheck.task.locationId)
      const inspection = getIncomingInspectionById(precheck.inspection.id)
      const purchaseReceive = getPurchaseReceiveById(precheck.purchaseReceive.id)
      const plannedQuantity = Number(precheck.quantityFacts.warehousePlanQuantity)
      const postedQuantity = Number(transaction.quantity || 0)
      if (task?.status !== 'done' || Number(task.completedQuantity) !== plannedQuantity) throw transactionError('task_final_validation_failed', '仓库任务最终状态校验失败。', 'final_validation')
      if (postedQuantity !== plannedQuantity || Number(balance?.quantity) !== Number(transaction.afterQuantity)) throw transactionError('balance_final_validation_failed', '库存余额最终校验失败。', 'final_validation')
      if (!inspection?.inventoryPosted || inspection.status !== 'inventoryPosted') throw transactionError('qms_final_validation_failed', 'QMS入库状态最终校验失败。', 'final_validation')
      if (!purchaseReceive?.inventoryPosted) throw transactionError('receive_final_validation_failed', '采购收货入库状态最终校验失败。', 'final_validation')
      return {
        ok: true,
        success: true,
        status: 'completed',
        taskId: task.id,
        taskNo: task.taskNo,
        completedQuantity: task.completedQuantity,
        inventoryBalance: balance,
        inventoryTransaction: transaction,
        inspection,
        purchaseReceive,
        payableGenerated: false,
      }
    },
  })
  if (!result.success) {
    return {
      ok: false,
      success: false,
      status: 'failed',
      errorCode: result.errorCode,
      message: result.error,
      error: result.error,
      failedStep: result.failedStep,
      rollbackResult: result.rollbackStatus,
    }
  }
  return result
}

export async function batchConfirmQualifiedInboundWarehouseTasks(taskIds = []) {
  const result = {
    operationName: '批量确认入库',
    total: taskIds.length,
    successCount: 0,
    failedCount: 0,
    successItems: [],
    failedItems: [],
    failedReason: [],
  }
  for (const taskId of taskIds) {
    const precheck = getQualifiedInboundTaskActionState(taskId)
    if (!precheck.allowed) {
      const reason = precheck.message || precheck.reason || '数量或质量状态不符合入库条件。'
      result.failedCount += 1
      result.failedItems.push({ id: taskId, reason })
      result.failedReason.push(`${taskId}：${reason}`)
      continue
    }
    const outcome = await confirmQualifiedInboundWarehouseTask({
      taskId,
      warehouseId: precheck.task.warehouseId,
      locationId: precheck.task.locationId,
      operatorId: precheck.task.operatorId,
    })
    if (outcome.success) {
      result.successCount += 1
      result.successItems.push({ id: taskId, transactionNo: outcome.inventoryTransaction?.transactionNo || '' })
    } else {
      const reason = outcome.message || outcome.error || '确认入库失败。'
      result.failedCount += 1
      result.failedItems.push({ id: taskId, reason })
      result.failedReason.push(`${taskId}：${reason}`)
    }
  }
  return result
}
