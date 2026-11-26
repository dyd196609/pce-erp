import { createProcessNodeRuntimeContract } from '../../contract/processNodeRuntimeContract.js'

export const PURCHASE_INQUIRY_NODE_CODE = 'SCM_PURCHASE_INQUIRY'
export const PURCHASE_INQUIRY_PREPARATION_SOURCE_NODE_CODE = 'SCM_PURCHASE_INQUIRY_PREPARATION'

export const PURCHASE_INQUIRY_NODE_RUNTIME_CONTRACT = createProcessNodeRuntimeContract({
  nodeCode: PURCHASE_INQUIRY_NODE_CODE,
  nodeName: '采购询价',
  inputObject: 'InquiryPreparationBatch',
  outputObject: 'PurchaseInquiry',
  actions: [
    'START_PURCHASE_INQUIRY',
    'EDIT_PURCHASE_INQUIRY',
    'SAVE_PURCHASE_INQUIRY',
  ],
  stateModel: 'PURCHASE_INQUIRY_RUNTIME_STATE',
  nextNode: null,
})

// 入站来源只描述采购申请交付的准备批次，不接管采购申请节点实现。
export const PURCHASE_INQUIRY_PREPARATION_HANDOFF_SOURCE = Object.freeze({
  nodeCode: PURCHASE_INQUIRY_PREPARATION_SOURCE_NODE_CODE,
  nodeName: '询价准备交付',
  inputObject: 'PurchaseRequest',
  outputObject: 'InquiryPreparationBatch',
  nextNode: PURCHASE_INQUIRY_NODE_CODE,
  handoffActionOwner: 'target',
})

