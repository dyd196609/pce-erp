export const PURCHASE_ORDER_CREATION_ENTRY_HANDOFF_VERSION_V11428425 = 'V1.14.2.8.4.25'

export function buildPurchaseOrderCreationEntryHandoffV11428425(admissionResult = {}) {
  if (admissionResult.objectType !== 'PurchaseOrderAdmissionResult'
    || admissionResult.status !== 'READY_FOR_PURCHASE_ORDER'
    || admissionResult.purchaseOrderCreationAllowed !== true
    || admissionResult.purchaseOrderCreated !== false) {
    throw new Error('PURCHASE_ORDER_ADMISSION_READY_RESULT_REQUIRED')
  }
  return Object.freeze({
    objectType: 'PurchaseOrderCreationEntry',
    entryId: `POCE-${admissionResult.admissionResultId}`,
    sourceObjectType: admissionResult.objectType,
    sourceObjectId: admissionResult.admissionResultId,
    gateId: admissionResult.gateId,
    entryRoute: '/scm/purchase-order/create',
    status: 'ENTRY_READY',
    statusLabel: '可人工进入采购订单创建',
    createActionCode: 'CREATE_PURCHASE_ORDER',
    createActionExecuted: false,
    purchaseOrderCreated: false,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    automaticPurchaseOrderCreation: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
