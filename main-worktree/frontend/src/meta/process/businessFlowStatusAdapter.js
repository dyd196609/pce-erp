import { terminalPaymentApplicationNotice } from './purchasePayablePaymentActionRegistry.js'

export const BUSINESS_FLOW_STATUS_ADAPTER_VERSION = 'V1.14.2'

export function getRecordNo(record = {}, field = '') {
  return record?.[field]
    || record?.documentNo
    || record?.transactionNo
    || record?.payablePrepareNo
    || record?.payableCheckNo
    || record?.settlementNo
    || record?.invoicePrepareNo
    || record?.apDraftNo
    || record?.payableConfirmNo
    || record?.paymentApplicationNo
    || ''
}

export function getRecordAmount(record = {}) {
  return Number(record.totalPayableAmount
    ?? record.totalCheckedAmount
    ?? record.settlementAmount
    ?? record.totalInvoiceAmount
    ?? record.confirmedPayableAmount
    ?? record.payableAmount
    ?? record.applicationAmount
    ?? record.amount
    ?? 0)
}

export function isPositiveAmount(record = {}) {
  return getRecordAmount(record) > 0
}

export function getRecordStatus(record = {}) {
  return record.payableStatus
    || record.checkStatus
    || record.settlementStatus
    || record.invoicePrepareStatus
    || record.apStatus
    || record.payableConfirmStatus
    || record.paymentApplicationStatus
    || record.status
    || ''
}

export function buildSourceWritebackPatch(action = {}, target = {}) {
  const targetNo = getRecordNo(target, action.targetNoField)
  const stamp = new Date().toISOString()
  return {
    downstreamActionCode: action.actionCode,
    downstreamObjectType: action.targetObjectType,
    downstreamObjectNo: targetNo,
    downstreamObjectId: target.id || '',
    downstreamGeneratedAt: stamp,
    flowWritebackStatus: 'written_back',
    nextStepReleaseStatus: action.actionCode === 'CREATE_PAYMENT_APPLICATION' ? 'terminal_locked' : 'released',
  }
}

export function buildTargetSourcePatch(action = {}, source = {}) {
  return {
    sourceObjectType: action.sourceObjectType,
    sourceObjectNo: getRecordNo(source, action.sourceNoField),
    sourceObjectId: source.id || '',
    sourceBusinessRoute: action.outputRoutePath,
    createdFromActionCode: action.actionCode,
    sourceLinkStatus: 'linked',
  }
}

export function evaluateNextStepRelease(action = {}, result = {}) {
  if (action.actionCode === 'CREATE_PAYMENT_APPLICATION') {
    return {
      released: false,
      reason: terminalPaymentApplicationNotice,
      conditions: [
        { label: '付款申请已创建', passed: Boolean(result.targetNo) },
        { label: '付款申请审批与付款指令准备未接入', passed: false },
      ],
    }
  }

  const released = Boolean(result.targetNo)
    && result.sourceWritebackStatus === 'written_back'
    && result.flowLinkStatus === 'linked'
    && result.rollbackStatus !== 'rolled_back'
    && result.cleanupRequired === false

  return {
    released,
    reason: released ? `已形成${action.targetObjectName}，可以进入${action.nextStepName}。` : `尚未形成有效${action.targetObjectName}，暂不能进入${action.nextStepName}。`,
    conditions: [
      { label: '目标对象已创建或复用', passed: Boolean(result.targetNo) },
      { label: '来源状态已回写', passed: result.sourceWritebackStatus === 'written_back' },
      { label: '流程关联已记录', passed: result.flowLinkStatus === 'linked' },
      { label: '无需回滚或清理', passed: result.rollbackStatus !== 'rolled_back' && result.cleanupRequired === false },
    ],
  }
}
