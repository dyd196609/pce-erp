import { test, expect } from '@playwright/test'
import { checkpointPath } from '../helpers/goldenCheckpoint.js'
import {
  getInventoryTransactionSourceContext,
  getSourceInspectionNoField,
  getSourcePurchaseOrderNoField,
  getSourcePurchaseReceiveNoField,
  getSourceWarehouseTaskNoField,
  getWarehouseTaskDetail,
  getWarehouseTaskNoField,
} from '../helpers/wmsDetailLocators.js'

const ORIGIN = process.env.PCE_BASE_URL || 'http://localhost:5173'
const FIXTURE_TRANSACTION_ID = 'txn-fixture-source-context-001'
const FIXTURE_TASK_ID = 'task-fixture-001'

test('库存流水详情以真实字段展示来源业务信息并精确返回仓库任务', async ({ browser }) => {
  const context = await browser.newContext({
    storageState: checkpointPath('qualified_inbound_ready', 'storage-state.json'),
  })
  await context.addInitScript(({ transactionId, taskId }) => {
    const key = 'wms-state-v1'
    const state = JSON.parse(localStorage.getItem(key) || '{}')
    state.warehouseTasks = [
      {
        id: taskId,
        taskNo: 'WT-FIXTURE-001',
        taskType: 'qualifiedInbound',
        businessType: 'qualifiedInboundPrepare',
        businessStatus: '待确认入库',
        status: 'pending',
        plannedQuantity: 1,
        completedQuantity: 0,
      },
      ...(state.warehouseTasks || []).filter((item) => item.id !== taskId),
    ]
    state.inventoryTransactions = [
      {
        id: transactionId,
        transactionNo: 'TXN-FIXTURE-001',
        transactionDate: '2026-07-22',
        transactionType: 'purchaseInspectionIn',
        materialName: '只读夹具物料',
        warehouseName: '只读夹具仓库',
        locationName: '只读夹具库位',
        quantity: 1,
        beforeQuantity: 0,
        afterQuantity: 1,
        sourceWarehouseTaskId: taskId,
        sourceWarehouseTaskNo: 'WT-FIXTURE-001',
        sourceInspectionNo: 'IQC-FIXTURE-001',
        sourcePurchaseReceiveNo: 'PRV-FIXTURE-001',
        sourceReceiveNo: 'PRV-FIXTURE-001',
        sourcePurchaseOrderNo: 'PO-FIXTURE-001',
      },
      ...(state.inventoryTransactions || []).filter((item) => item.id !== transactionId),
    ]
    localStorage.setItem(key, JSON.stringify(state))
  }, { transactionId: FIXTURE_TRANSACTION_ID, taskId: FIXTURE_TASK_ID })
  const page = await context.newPage()
  try {
    await page.goto(`${ORIGIN}/#/wms/inventory-transaction/${FIXTURE_TRANSACTION_ID}`, { waitUntil: 'networkidle' })
    const sourceContext = getInventoryTransactionSourceContext(page)
    await expect(sourceContext).toBeVisible()
    await expect(getSourceWarehouseTaskNoField(page)).toHaveText('WT-FIXTURE-001')
    await expect(getSourceInspectionNoField(page)).toHaveText('IQC-FIXTURE-001')
    await expect(getSourcePurchaseReceiveNoField(page)).toHaveText('PRV-FIXTURE-001')
    await expect(getSourcePurchaseOrderNoField(page)).toHaveText('PO-FIXTURE-001')
    await sourceContext.getByTestId('inventory-transaction-view-source-warehouse-task').click()
    await expect(page).toHaveURL(new RegExp(`#\/wms\/warehouse-task\/${FIXTURE_TASK_ID}$`))
    const taskDetail = getWarehouseTaskDetail(page)
    await expect(taskDetail).toHaveCount(1)
    const taskNo = getWarehouseTaskNoField(page)
    await expect(taskNo).toHaveCount(1)
    await expect(taskNo).toHaveText('WT-FIXTURE-001')
  } finally {
    await context.close()
  }
})
