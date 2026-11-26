export const SCM_UNIFIED_LIST_ACTION_CONTRACT_VERSION = 'V1.14.2.8.18.13'

export const SCM_SUPPLIER_QUOTE_LIST_ACTIONS = Object.freeze([
  Object.freeze({ actionCode: 'SAVE_SUPPLIER_QUOTE', actionName: '填写报价',
    allowedStates: Object.freeze(['supplier_quote_collecting']) }),
])
export const SCM_PURCHASE_INQUIRY_LIST_ACTIONS = Object.freeze([
  Object.freeze({ actionCode: 'VIEW_PURCHASE_INQUIRY', actionName: '查看询价', allowedStates: Object.freeze(['*']) }),
  Object.freeze({ actionCode: 'EDIT_PURCHASE_INQUIRY', actionName: '编辑询价', allowedStates: Object.freeze(['draft']) }),
])
export const SCM_QUOTE_COMPARISON_LIST_ACTIONS = Object.freeze([
  Object.freeze({ actionCode: 'OPEN_PRICE_APPROVAL_PREPARATION', actionName: '进入核价准备',
    allowedStates: Object.freeze(['comparison_completed']) }),
])
export const SCM_PRICE_APPROVAL_LIST_ACTIONS = Object.freeze([
  Object.freeze({ actionCode: 'OPEN_MANUAL_REVIEW', actionName: '查看核价',
    allowedStates: Object.freeze(['draft', 'reviewing', 'completed']) }),
  Object.freeze({ actionCode: 'CONFIRM_QUOTATION', actionName: '确认报价', buttonType: 'success',
    allowedStates: Object.freeze(['completed']), visibleWhen: row => row?.canArchive === true }),
  Object.freeze({ actionCode: 'VIEW_EFFECTIVE_PRICE', actionName: '查看有效价格',
    allowedStates: Object.freeze(['completed']), visibleWhen: row => row?.archiveStatus === 'ARCHIVED' }),
  Object.freeze({ actionCode: 'VIEW_ARCHIVE_BLOCK_REASON', actionName: '查看阻断原因', buttonType: 'warning',
    allowedStates: Object.freeze(['completed']), visibleWhen: row => (
      row?.archiveStatus === 'MAPPING_PENDING' || row?.archiveStatus === 'NOT_ALLOWED'
    ) }),
])

export const SCM_PRICE_ARCHIVE_STATUS_OPTIONS = Object.freeze([
  Object.freeze({ label: '待确认报价', value: 'PENDING_CONFIRMATION' }),
  Object.freeze({ label: '确认处理中', value: 'PROCESSING' }),
  Object.freeze({ label: '已生成有效价格', value: 'ARCHIVED' }),
  Object.freeze({ label: '映射待处理', value: 'MAPPING_PENDING' }),
  Object.freeze({ label: '不允许归档', value: 'NOT_ALLOWED' }),
  Object.freeze({ label: '归档失败', value: 'FAILED' }),
])
