import { createOperationHandoverState,createGovernedHandoverController,validateGovernedHandoverResponse } from './operationHandover.js'
import { FINISHED_GOODS_PAGE as P,FINISHED_GOODS_ACTIONS,FINISHED_GOODS_FORMAL_ACTIONS } from './finishedGoodsContract.js'
export { createOperationHandoverState as createFinishedGoodsState }
export function resolveFinishedGoodsAction(facts,key){
 const registered=(facts?.usagePurpose==='PRODUCTION_USE'?FINISHED_GOODS_FORMAL_ACTIONS:FINISHED_GOODS_ACTIONS)[key],action=facts?.availableActions?.[key]
 if(!registered || !action || ['actionCode','displayName','requiredPermission','serverValidator','httpMethod'].some(k=>action[k]!==registered[k]) || typeof action.enabled!=='boolean' || typeof action.disabledReason!=='string')throw new Error('成品动作登记与服务端合同不一致。')
 const id=key==='prepare'?facts.selectedWorkOrder?.id:facts.selectedTransfer?.id
 const path=registered.apiPathTemplate.includes('{objectId}')?(id?registered.apiPathTemplate.replace('{objectId}',String(id)):null):registered.apiPathTemplate
 if(action.apiPath!==path || action.requestObjectId!==(id??null))throw new Error('成品动作未绑定本次准确来源对象。')
 return {...registered,...action,objectId:id??null}
}
export function validateFinishedGoods(response,expected){
 const loaded=validateGovernedHandoverResponse(response,expected,{apiUrl:P.apiUrl,factKey:'finishedGoodsFacts',contractVersion:P.factContractVersion,moduleCode:P.moduleId,listField:'transfers',label:P.title})
 const f=loaded.facts
 if(!['TEST_BUSINESS','PRODUCTION_USE','MIXED_AUTHORIZED'].includes(f.usagePurpose) || !Array.isArray(f.workOrderOptions) || !Array.isArray(f.destinationChoices) || !Array.isArray(f.receiverChoices))throw new Error('原生用途、职责目录或目标资源事实未完整读取。')
 if(f.usagePurpose==='MIXED_AUTHORIZED' && (f.selectedWorkOrder || f.selectedTransfer || Object.values(f.availableActions||{}).some(a=>a.enabled)))throw new Error('跨单目录不能推断具体单据用途或授予写入。')
 if(f.usagePurpose==='PRODUCTION_USE' && (f.selectedWorkOrder?.usagePurpose!=='PRODUCTION_USE' || f.selectedTransfer && f.selectedTransfer.usagePurpose!=='PRODUCTION_USE'))throw new Error('正式用途必须同源绑定本工单及成品单。')
 for(const row of f.transfers)if(!/^[a-f0-9]{64}$/.test(row.sourceSnapshotHash) || !row.stateMachineConsistent || !row.conversionBasis || !Array.isArray(row.sourceWorkloadRanges))throw new Error('成品来源、转化依据或原生状态证明不完整。')
 if(expected.transferId && f.selectedTransfer?.id!==expected.transferId || expected.workOrderId && f.selectedWorkOrder?.id!==expected.workOrderId)throw new Error('当前读取与明确对象定位不一致。')
 for(const key of Object.keys(FINISHED_GOODS_ACTIONS))resolveFinishedGoodsAction(f,key)
 return loaded
}
export function createFinishedGoodsController(options){return createGovernedHandoverController({...options,apiUrl:P.apiUrl,domain:'finishedGoods',validator:validateFinishedGoods,resolveAction:resolveFinishedGoodsAction})}
