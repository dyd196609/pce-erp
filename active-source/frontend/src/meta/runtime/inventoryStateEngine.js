import { writeDatabase } from '../data/databaseLayer.js'
import { emitBusinessEvent } from './enterpriseEventStream.js'

const inventoryUpdates = []

function skuFromRecord(record = {}) {
  const material = String(record.materialList || record.materialId || record.skuId || 'SKU-RUNTIME')
  const first = material.split(/[;, ]/).find(Boolean)
  return first?.startsWith('SKU') ? first : first?.replace('MAT', 'SKU') || 'SKU-RUNTIME'
}

export function updateStock(record = {}, context = {}) {
  const quantity = Number(record.quantity || record.stockQuantity || 0)
  const next = {
    id: record.inventoryId || record.id || Number(String(skuFromRecord(record)).replace(/\D/g, '')) || Date.now(),
    skuId: skuFromRecord(record),
    stockQuantity: Math.max(0, Number(record.currentStock ?? 0) - quantity),
    warehouseLocation: record.warehouseLocation || 'Runtime-WH',
    reorderLevel: Number(record.reorderLevel || 100),
    batchNumber: record.batchNumber || `BATCH-${new Date().toISOString().slice(0, 10)}`,
    expiryDate: record.expiryDate || new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
    workflow_state: 'in_stock',
    sourceTransactionId: context.transactionId,
  }
  const data = writeDatabase('inventory', next, context)
  const update = { ...next, data, status: 'UPDATED' }
  inventoryUpdates.unshift(update)
  if (inventoryUpdates.length > 100) inventoryUpdates.length = 100
  emitBusinessEvent({
    type: 'inventory.updated',
    module: 'inventory',
    payload: update,
    correlationId: context.transactionId,
  })
  return update
}

export function deductStock(record = {}, context = {}) {
  return updateStock(record, context)
}

export function syncWarehouse(update = {}, context = {}) {
  const synced = {
    ...update,
    warehouseSync: 'SYNCED',
    syncedAt: Date.now(),
  }
  writeDatabase('inventory', synced, context)
  return synced
}

export function getInventoryStateSnapshot() {
  return {
    inventoryState: 'ACTIVE',
    updates: [...inventoryUpdates],
    warehouseSyncHealth: inventoryUpdates.every((item) => item.status === 'UPDATED') ? 100 : 85,
  }
}
