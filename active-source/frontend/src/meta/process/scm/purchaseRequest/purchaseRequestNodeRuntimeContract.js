import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_REQUEST_NODE_CODE = 'scm-purchase-request'
export const PURCHASE_INQUIRY_ENTRY_NODE_CODE = 'scm-purchase-inquiry-entry'

export const PURCHASE_REQUEST_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_REQUEST_NODE_CODE,
  nodeName: '采购申请',
  inputObject: 'PurchaseRequest',
  outputObject: 'InquiryPreparationBatch',
  actions: [
    'SAVE_PURCHASE_REQUEST',
    'SUBMIT_PURCHASE_REQUEST',
    'APPROVE_PURCHASE_REQUEST',
    'GENERATE_INQUIRY_PREPARATION',
  ],
  stateModel: 'PURCHASE_REQUEST_RUNTIME_STATE',
  nextNode: PURCHASE_INQUIRY_ENTRY_NODE_CODE,
})

// 只声明交接目标，不接管或修改询价页面的节点实现。
export const PURCHASE_INQUIRY_HANDOFF_TARGET = Object.freeze({
  nodeCode: PURCHASE_INQUIRY_ENTRY_NODE_CODE,
  nodeName: '采购询价入口',
  inputObject: 'InquiryPreparationBatch',
  pageCode: 'purchase-inquiry',
  pageUrl: '/scm/purchase-inquiry',
})

