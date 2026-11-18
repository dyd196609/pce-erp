export const getWarehouseTaskDetail = (page) => page.locator('[data-pce-section="warehouse-task-detail"]')
export const getWarehouseTaskNoField = (page) => getWarehouseTaskDetail(page).getByTestId('warehouse-task-detail-task-no')
export const getWarehouseTaskStatusField = (page) => getWarehouseTaskDetail(page).getByTestId('warehouse-task-detail-status')
export const getWarehouseTaskBusinessStatusField = (page) => getWarehouseTaskDetail(page).getByTestId('warehouse-task-detail-business-status')
export const getWarehouseTaskCompletedQuantityField = (page) => getWarehouseTaskDetail(page).getByTestId('warehouse-task-detail-completed-quantity')

export const getInventoryTransactionDetail = (page) => page.locator('[data-pce-section="inventory-transaction-detail"]')
export const getInventoryTransactionNoField = (page) => getInventoryTransactionDetail(page).getByTestId('inventory-transaction-detail-transaction-no')
export const getInventoryTransactionTypeField = (page) => getInventoryTransactionDetail(page).getByTestId('inventory-transaction-detail-transaction-type')
export const getInventoryTransactionQuantityField = (page) => getInventoryTransactionDetail(page).getByTestId('inventory-transaction-detail-quantity')

export const getInventoryTransactionSourceContext = (page) => page.locator('[data-pce-section="inventory-transaction-source-context"]')
export const getSourceWarehouseTaskNoField = (page) => getInventoryTransactionSourceContext(page).getByTestId('inventory-transaction-source-warehouse-task-no')
export const getSourceInspectionNoField = (page) => getInventoryTransactionSourceContext(page).getByTestId('inventory-transaction-source-inspection-no')
export const getSourcePurchaseReceiveNoField = (page) => getInventoryTransactionSourceContext(page).getByTestId('inventory-transaction-source-purchase-receive-no')
export const getSourcePurchaseOrderNoField = (page) => getInventoryTransactionSourceContext(page).getByTestId('inventory-transaction-source-purchase-order-no')

