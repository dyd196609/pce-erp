import { readOperationExecutionMode } from './operationExecutionMode.js'
import { readPceFactLoadEnvelope } from './pceFactLoadContract.js'
export const COMPLETION_DIRECTORY_CONTRACT = 'PCE-OPERATION-COMPLETION-DIRECTORY-V1'
export const COMPLETION_DIRECTORY_API = '/api/planning/operation-completions/directory/'
const requireFact = (ok, message) => { if (!ok) throw new Error(message) }
const positive = value => Number.isSafeInteger(value) && value > 0
const text = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const decimal = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)
// A distinct summary contract. No detail validator or write gate is weakened.
export function validateOperationCompletionDirectory(response, expected = {}) {
 const { data, factLoadFacts } = readPceFactLoadEnvelope(response, COMPLETION_DIRECTORY_API, '工序目录')
 requireFact(factLoadFacts.factLoadStatus !== 'read_failed', factLoadFacts.errorMessage)
 const facts=data.operationCompletionFacts, actor=facts?.currentActorEvidence
 requireFact(facts?.contractVersion===COMPLETION_DIRECTORY_CONTRACT && facts.moduleCode==='production-operation-completion'
   && facts.factSource==='server' && facts.currentStateSource==='server' && facts.selectedTask===null
   && facts.writeEligibilityIncluded===false && !facts.availableActions && !expected.taskId, '目录摘要身份或只读合同不一致。')
 requireFact(positive(actor?.userId) && positive(actor?.companyId) && text(actor?.username)
   && facts.companyId===actor.companyId && (!expected.userId || actor.userId===expected.userId)
   && (!expected.companyId || actor.companyId===expected.companyId), '目录账号或公司身份不一致。')
 requireFact(Array.isArray(facts.tasks) && data.resultCount===facts.tasks.length, '目录数量未完整核实。')
 const ids=new Set()
 for (const row of facts.tasks) {
  const view=row.viewQualification, progress=row.recordProgress, overall=row.overallCompletion
  requireFact(positive(row.taskId) && row.id===row.taskId && !ids.has(row.taskId) && positive(row.workOrderId)
    && ['no','workOrderNo','operationName','workshopName','workCenterName'].every(k=>text(row[k]))
    && Number.isSafeInteger(row.frozenSequence) && positive(row.version)
    && hash(row.sourceSnapshotHash) && hash(row.assignmentHash), '目录任务身份或来源缺失。')
  ids.add(row.taskId)
  requireFact(view?.allowed===true && view.actorId===actor.userId && view.companyId===actor.companyId
    && view.taskId===row.taskId && view.scope==='NATIVE_COMPLETION_READER' && view.writeEligibilityIncluded===false
    && !row.availableActions && !row.completionV3 && !row.completionFact, '目录查看范围或详情边界不一致。')
  requireFact(typeof row.formalFactsComplete==='boolean' && typeof row.completionProven==='boolean'
    && Number.isSafeInteger(row.completionProjectionVersion) && row.completionProjectionVersion>=0
    && ['unrequested','pending_review','completed'].includes(row.completionStatusCode) && text(row.completionStatusLabel)
    && overall?.source==='verified_completion_projection' && overall.statusCode===row.completionStatusCode
    && overall.statusLabel===row.completionStatusLabel && overall.completionProven===row.completionProven
    && row.completionProven===(row.completionStatusCode==='completed'), '目录正式状态未核实。')
  requireFact(typeof progress?.submitted==='boolean' && typeof progress?.reviewed==='boolean'
    && text(progress.submissionLabel) && text(progress.reviewLabel)
    && (progress.submitted ? positive(progress.recordId) : progress.recordId===null)
    && progress.submitted===(row.completionStatusCode!=='unrequested')
    && progress.reviewed===row.completionProven
    && (!progress.reviewed || text(row.reviewerLabel)), '目录提交、审核或实际审核人未核实。')
  const mode=readOperationExecutionMode(row)
  if(row.quantityApplicable && row.formalFactsComplete) requireFact(['workloadQuantity','reportedQuantity','remainingQuantity'].every(k=>decimal(row[k]))
    && text(row.workloadUomLabel) && Number.isSafeInteger(row.quantityPrecision) && row.quantityPrecision>=0, '目录数量或单位未核实。')
  if(mode.nonquantified) requireFact(['workloadQuantity','reportedQuantity','remainingQuantity','quantityPrecision','workloadUomLabel'].every(k=>row[k]===null)
    && row.referenceWorkload && typeof row.referenceWorkload==='object', '不可统计目录不得伪造数量。')
 }
 for(const key of ['apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts']) requireFact(
   JSON.stringify(data[key]?.operationCompletionFacts)===JSON.stringify(facts) && data[key]?.resultCount===data.resultCount,
   '目录五表面事实不一致。')
 return {facts,factLoadFacts,serverSurface:data.strictFacts}
}
