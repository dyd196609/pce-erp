import { buildPurchaseOrderCreationEligibility } from './purchaseOrderCreationEligibility.js'
import { evaluateScmInboundQuantity } from '../schema/scm/scmInboundQuantityRule.js'

export const SCM_RUNTIME_CONSISTENCY_GUARD_VERSION = 'V1.14.2.8.4.12'

function issue(code, message, source = {}) {
  return Object.freeze({ code, severity: 'business_error', message, source: { ...source }, autoFixed: false })
}

export function evaluateScmRuntimeConsistency(snapshot = {}) {
  const requests = snapshot.purchaseRequests || []
  const inquiries = snapshot.purchaseInquiries || []
  const approvals = snapshot.priceApprovals || []
  const eligibilities = snapshot.purchaseOrderCreationEligibilities || []
  const inspections = snapshot.incomingInspections || []
  const tasks = snapshot.warehouseTasks || []
  const issues = []

  requests.filter((item) => item.status === 'converted').forEach((request) => {
    const inquiry = inquiries.find((item) => String(item.requestId || item.sourceOrderId) === String(request.id))
    const approval = inquiry && approvals.find((item) => String(item.inquiryId || item.sourceOrderId) === String(inquiry.id))
    if (!approval) issues.push(issue(
      'SCM-RUNTIME-001',
      '业务异常：采购申请已转单，但未找到对应核价对象。',
      { requestId: request.id, requestNo: request.requestNo || '', status: request.status },
    ))
  })

  inquiries.filter((item) => item.status === 'approved').forEach((inquiry) => {
    const eligibility = eligibilities.find((item) => String(item.sourceInquiryId) === String(inquiry.id))
    if (!eligibility) issues.push(issue(
      'SCM-RUNTIME-002',
      '需要生成采购订单资格。',
      { inquiryId: inquiry.id, inquiryNo: inquiry.inquiryNo || '', status: inquiry.status },
    ))
  })

  tasks.filter((task) => task.businessType === 'qualifiedInboundPrepare' || task.taskType === 'qualifiedInboundPrepare').forEach((task) => {
    const inspection = inspections.find((item) => String(item.id) === String(task.sourceInspectionId || task.sourceId))
    const qualifiedQuantity = (inspection?.lines || []).reduce((sum, line) => sum + Number(line.qualifiedQty || 0) + Number(line.concessionQty || 0), 0)
    const plan = Number(task.plannedQuantity || 0)
    const completed = Number(task.completedQuantity || 0)
    const quantityRule = evaluateScmInboundQuantity({ warehousePlanQuantity: plan, completedQuantity: completed, qualifiedQuantity })
    if (!inspection || !quantityRule.allowed) {
      issues.push(issue(
        'SCM-RUNTIME-003',
        '数量链异常。',
        { taskId: task.id, plannedQuantity: plan, completedQuantity: completed, qualifiedQuantity },
      ))
    }
  })

  return Object.freeze({
    version: SCM_RUNTIME_CONSISTENCY_GUARD_VERSION,
    result: issues.length ? 'FAIL' : 'PASS',
    issues: Object.freeze(issues),
    autoRepairPerformed: false,
  })
}

export function evaluateScmPageRuntimeConsistency(snapshot = {}, pageCode = '', maxRecords = 100) {
  const bounded = Math.max(1, Math.min(Number(maxRecords) || 100, 500))
  const inspectRequestChain = pageCode === 'purchase-request'
  const inspectInquiryChain = pageCode === 'purchase-inquiry'
  const inspectInboundChain = pageCode === 'inventory-balances'
  const scopedSnapshot = {
    purchaseRequests: inspectRequestChain ? (snapshot.purchaseRequests || []).slice(0, bounded) : [],
    purchaseInquiries: inspectRequestChain || inspectInquiryChain
      ? (snapshot.purchaseInquiries || []).slice(0, bounded)
      : [],
    priceApprovals: inspectRequestChain ? (snapshot.priceApprovals || []).slice(0, bounded) : [],
    purchaseOrderCreationEligibilities: inspectInquiryChain
      ? (snapshot.purchaseOrderCreationEligibilities || []).slice(0, bounded)
      : [],
    incomingInspections: inspectInboundChain ? (snapshot.incomingInspections || []).slice(0, bounded) : [],
    warehouseTasks: inspectInboundChain ? (snapshot.warehouseTasks || []).slice(0, bounded) : [],
  }
  return Object.freeze({
    ...evaluateScmRuntimeConsistency(scopedSnapshot),
    scope: 'current_page',
    pageCode,
    maxRecords: bounded,
    fullScmScanPerformed: false,
  })
}

export function previewPurchaseOrderEligibility(inquiry, inquiryItems, existing = null) {
  return buildPurchaseOrderCreationEligibility({ inquiry, inquiryItems, existing, now: inquiry?.updatedAt || inquiry?.createdAt || '' })
}
