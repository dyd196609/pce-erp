export const PURCHASE_INQUIRY_TASK_MODEL_VERSION = 'V1.14.2.8.6.0'

export const PURCHASE_INQUIRY_TASK_MODEL = Object.freeze({
  modelCode: 'SCM_PURCHASE_INQUIRY_TASK_MODEL',
  version: PURCHASE_INQUIRY_TASK_MODEL_VERSION,
  objectCode: 'SCM_PURCHASE_INQUIRY_TASK',
  runtimeOnly: true,
  persistenceMode: 'memory_only',
  statuses: Object.freeze(['ready', 'editing', 'completed', 'cancelled']),
  tasks: Object.freeze([
    Object.freeze({ taskCode: 'review_business_summary', label: '核对业务摘要', page: '/scm/purchase-inquiry' }),
    Object.freeze({ taskCode: 'maintain_basic_information', label: '维护基本信息', page: '/scm/purchase-inquiry/create' }),
    Object.freeze({ taskCode: 'select_suppliers', label: '选择供应商', page: '/scm/purchase-inquiry/create' }),
    Object.freeze({ taskCode: 'maintain_inquiry_lines', label: '维护询价明细', page: '/scm/purchase-inquiry/create' }),
  ]),
  allowedActions: Object.freeze(['createInquiryObject', 'editDraft', 'cancelDraft']),
  forbiddenActions: Object.freeze([
    'createPurchaseOrder',
    'sendSupplier',
    'payment',
    'inventoryAction',
    'warehouseAction',
    'workflowAction',
    'approvalAction',
  ]),
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validatePurchaseInquiryTaskModel(model = PURCHASE_INQUIRY_TASK_MODEL) {
  const requiredTasks = ['maintain_basic_information', 'select_suppliers', 'maintain_inquiry_lines']
  const taskCodes = new Set(model.tasks?.map((task) => task.taskCode))
  const valid = model.runtimeOnly === true
    && model.persistenceMode === 'memory_only'
    && requiredTasks.every((task) => taskCodes.has(task))
    && ['createPurchaseOrder', 'sendSupplier', 'payment', 'inventoryAction'].every((action) => model.forbiddenActions.includes(action))
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
