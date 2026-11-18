export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_VERSION = 'V1.14.2.8.7.0'

export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW = Object.freeze({
  viewCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW',
  version: FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_VERSION,
  viewStatus: 'validation_ready',
  audience: 'purchase_business_user',
  factSource: 'server',
  presentationMode: 'read_only',
  sections: Object.freeze([
    Object.freeze({ sectionCode: 'evidence', title: '报价证据', explanation: '核对报价、供应商、币种和交期证据' }),
    Object.freeze({ sectionCode: 'comparison', title: '比较与核价准备', explanation: '核对比较结果和人工评审准备状态' }),
    Object.freeze({ sectionCode: 'entry_boundary', title: '审批准入边界', explanation: '核对准入与创建冻结结果' }),
    Object.freeze({ sectionCode: 'safety', title: '安全保护', explanation: '确认验证不等于生产操作' }),
  ]),
  businessViewMeansBusinessExecution: false,
  operationValidationMeansProductionOperation: false,
  approvalObjectCreated: false,
  workflowStarted: false,
  approvalTaskCreated: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalBusinessView(model = FORMAL_PRICE_APPROVAL_BUSINESS_VIEW) {
  const valid = model.viewCode === 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW'
    && model.viewStatus === 'validation_ready' && model.audience === 'purchase_business_user'
    && model.factSource === 'server' && model.presentationMode === 'read_only' && model.sections.length === 4
    && model.businessViewMeansBusinessExecution === false && model.operationValidationMeansProductionOperation === false
    && model.approvalObjectCreated === false && model.workflowStarted === false && model.approvalTaskCreated === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
