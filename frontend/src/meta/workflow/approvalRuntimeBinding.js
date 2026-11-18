import { createApprovalInstance, executeApprovalAction, writeApprovalResultToBusinessObject } from './approvalRuntime.js'
import { getApprovalContract, getApprovalFlowConfig } from './approvalFlowConfigStore.js'

export const APPROVAL_RUNTIME_BINDING_VERSION='V1.14.2.8.18.10.3.2'
export const APPROVAL_RUNTIME_001=Object.freeze({ruleCode:'APPROVAL-RUNTIME-001',
  chain:Object.freeze(['ApprovalConfiguration','ApprovalPolicy','ApprovalInstance','ApprovalTask','ApprovalResult','BusinessStateWriteback'])})

const clone=value=>JSON.parse(JSON.stringify(value))
const STORAGE_KEY='pce-approval-runtime-bindings-v114281032'
function readBindings(){try{return JSON.parse(globalThis.localStorage?.getItem(STORAGE_KEY)||'{}')}catch{return{}}}
function writeBindings(bindings){globalThis.localStorage?.setItem(STORAGE_KEY,JSON.stringify(bindings))}
export function createApprovalPolicy(moduleName='purchaseRequest'){
  const configuration=getApprovalFlowConfig(moduleName)
  const contract=getApprovalContract(moduleName)
  if(!configuration?.enabled)throw new Error('APPROVAL_CONFIGURATION_DISABLED')
  return Object.freeze({policyCode:`POLICY_${contract.approvalContractCode}`,moduleName,
    configurationId:configuration.id,configurationUpdatedAt:configuration.updatedAt,
    gateCount:contract.gateCount,gates:contract.gates,contract})
}
export function createBoundApprovalRuntime({moduleName='purchaseRequest',businessObjectId,submittedBy='system',submittedAt}={}){
  const policy=createApprovalPolicy(moduleName)
  const instance=createApprovalInstance({contract:policy.contract,businessObjectId,submittedBy,submittedAt})
  const tasks=policy.gates.map(gate=>Object.freeze({taskId:`${instance.approvalInstanceId}:${gate.gateCode}`,
    approvalInstanceId:instance.approvalInstanceId,gateCode:gate.gateCode,level:gate.level,
    approverRole:gate.approverRole,status:gate.level===1?'pending':'waiting'}))
  return Object.freeze({configuration:Object.freeze({id:policy.configurationId,moduleName,gateCount:policy.gateCount}),
    policy,instance,tasks:Object.freeze(tasks),result:null,writeback:null})
}
export function executeBoundApprovalTask(binding,{action='APPROVE',actorId='approver',actorRole='',at}={}){
  if(binding?.result)return Object.freeze({...binding,idempotent:true})
  const active=binding.tasks.find(task=>task.level===binding.instance.currentGate)
  if(!active||active.status!=='pending')throw new Error('APPROVAL_TASK_NOT_PENDING')
  const execution=executeApprovalAction(binding.instance,binding.policy.contract,{action,actorId,actorRole,at})
  const tasks=binding.tasks.map(task=>task.taskId===active.taskId?{...task,status:action==='REJECT'?'rejected':'completed',actorId,actorRole,completedAt:at||new Date().toISOString()}
    :(!execution.completed&&task.level===execution.instance.currentGate?{...task,status:'pending'}:task))
  return Object.freeze({...clone(binding),instance:execution.instance,tasks:Object.freeze(tasks),
    result:execution.instance.approvalResult,idempotent:execution.idempotent})
}
export function writeBoundApprovalResult(binding,businessObject={}){
  if(!binding?.result)throw new Error('APPROVAL_RUNTIME_NOT_COMPLETED')
  const writeback=writeApprovalResultToBusinessObject(binding.instance,businessObject)
  return Object.freeze({...clone(binding),writeback,result:binding.result,businessObject:writeback.object})
}
export function saveBoundApprovalRuntime(binding){
  const bindings=readBindings();bindings[binding.instance.businessObjectId]=clone(binding);writeBindings(bindings);return clone(binding)
}
export function loadBoundApprovalRuntime(businessObjectId){return clone(readBindings()[String(businessObjectId)]||null)}
export function ensureBoundApprovalRuntime(payload={}){
  const existing=loadBoundApprovalRuntime(payload.businessObjectId)
  if(existing)return existing
  return saveBoundApprovalRuntime(createBoundApprovalRuntime(payload))
}
export function listBoundApprovalRuntimes(){return Object.values(readBindings()).map(clone)}
