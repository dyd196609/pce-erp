export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION_VERSION = 'V1.14.2.8.7.1'

const viewItem = (itemCode, businessQuestion, evidenceLabel, judgementLabel, boundaryLabel) => Object.freeze({
  itemCode, businessQuestion, evidenceLabel, judgementLabel, boundaryLabel,
  factSource: 'server', presentationMode: 'read_only', userActionEnabled: false,
})

export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION',
  version: FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION_VERSION,
  optimizationStatus: 'user_acceptance_ready',
  audience: 'purchase_business_user',
  layoutSequence: Object.freeze(['business_question', 'evidence', 'judgement', 'boundary']),
  items: Object.freeze([
    viewItem('quotation_evidence', '供应商报价证据是否完整？', '报价、供应商、币种、交期', '证据完整性', '不生成审批对象'),
    viewItem('comparison_preparation', '报价比较是否支持人工核价判断？', '比较结果、核价准备、阻断原因', '人工评审准备状态', '不自动选择供应商'),
    viewItem('approval_entry', '是否具备进入价格审批验证的条件？', '准入评估、创建冻结、治理摘要', '验证准入状态', '不启动 Workflow'),
    viewItem('zero_write', '本次验证是否保持零业务影响？', '写入计数、生产写入、数据库状态', '安全保护状态', '不创建任务或写数据库'),
  ]),
  itemCount: 4,
  businessViewMeansBusinessExecution: false,
  userAcceptanceMeansOperationApproval: false,
  approvalObjectCreated: false,
  workflowStarted: false,
  approvalTaskCreated: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalBusinessViewOptimization(model = FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION'
    && model.optimizationStatus === 'user_acceptance_ready' && model.audience === 'purchase_business_user'
    && model.layoutSequence.join('|') === 'business_question|evidence|judgement|boundary'
    && model.itemCount === 4 && model.items.length === 4
    && model.items.every((item) => item.factSource === 'server' && item.presentationMode === 'read_only' && item.userActionEnabled === false)
    && model.businessViewMeansBusinessExecution === false && model.userAcceptanceMeansOperationApproval === false
    && model.approvalObjectCreated === false && model.workflowStarted === false && model.approvalTaskCreated === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
