// One six-node projection for the process centre and in-page navigation.
export const MES_TEST_NODES=Object.freeze([
 ['mes-test-own-start','本单任务目录与开工记录','mes-test-execution-entry','/planning/mes-test-execution'],
 ['mes-test-report','本人分次报工','production-operation-report','/planning/operation-reports'],
 ['mes-test-output','部分产出确认','production-operation-handover','/planning/operation-handovers?subview=output'],
 ['mes-test-handover','工序批次交接与实际接收','production-operation-handover','/planning/operation-handovers'],
 ['mes-test-review','独立审核完工','production-operation-completion','/planning/operation-completions'],
 ['mes-test-finished-goods','成品交接入库','production-finished-goods-handover','/planning/finished-goods-handovers'],
].map(([nodeCode,nodeName,pageCode,pageUrl])=>Object.freeze({nodeCode,nodeName,pageCode,pageUrl})))
export function mesReadContext(facts){
 if(!facts)return null
 const row=facts.selectedTask||facts.selectedCustodySource||null
 const order=facts.selectedWorkOrder,transfer=facts.selectedTransfer
 const taskRows=facts.tasks||facts.taskOptions||[]
 const ids=[...new Set(taskRows.map(x=>x.workOrderId).filter(Boolean))]
 return {handoverDirection:facts.readDirection || null,transferId:transfer?.id||null,workOrderId:order?.id||row?.workOrderId||transfer?.workOrderId||(ids.length===1?ids[0]:null),
  workOrderNo:order?.no||row?.workOrderNo||transfer?.workOrderNo||(ids.length===1?taskRows[0]?.workOrderNo:null),
  taskId:row?.taskId||row?.id||order?.terminalTaskId||null,taskNo:row?.no||row?.taskNo||order?.terminalTaskNo||null}
}
export function mesNodeIndex(route){
 if(route.path==='/planning/operation-handovers')return route.query?.subview==='output'?2:3
 return MES_TEST_NODES.findIndex(x=>x.pageUrl.split('?')[0]===route.path)
}
export function mesNodeUrl(node,context={}){
 const [path,query='']=node.pageUrl.split('?'),params=new URLSearchParams(query)
 if(node.pageCode==='mes-test-execution-entry'&&context?.workOrderId)params.set('workOrderId',String(context.workOrderId))
 else if(node.pageCode==='production-finished-goods-handover'){if(context?.transferId)params.set('transferId',String(context.transferId));else if(node.nodeCode==='mes-test-handover')params.set('direction',context?.handoverDirection || 'outgoing')
 if(context?.workOrderId)params.set('workOrderId',String(context.workOrderId))}
 else if(node.pageCode!=='mes-test-execution-entry'&&context?.taskId)params.set('taskId',String(context.taskId))
 if(node.nodeCode==='mes-test-handover')params.set('direction',context?.handoverDirection || 'outgoing')
 if(context?.workOrderId)params.set('workOrderId',String(context.workOrderId))
 return path+(params.size?'?'+params:'')
}
export function mesWorkOrderFilter(route){
 const raw=route.query?.workOrderId
 if(raw===undefined)return {}
 if(typeof raw!=='string'||! /^[1-9]\d*$/.test(raw)||!Number.isSafeInteger(Number(raw)))throw Error('PAGE IDENTITY MISMATCH: 测试工单定位不合法')
 return {workOrderId:Number(raw)}
}
export function mesPageGovernance(base,route,context){
 const index=mesNodeIndex(route),current=MES_TEST_NODES[index]
 if(!current)return base
 const target=node=>({label:node.nodeName,pageUrl:mesNodeUrl(node,context)})
 return {...base,flowSteps:MES_TEST_NODES.map(x=>x.nodeName),currentFlowStep:current.nodeName,
  navigation:{previous:index?target(MES_TEST_NODES[index-1]):{label:'业务流程中心',pageUrl:'/process-center?module=MES'},
   current:target(current),next:index<5?target(MES_TEST_NODES[index+1]):{label:'本轮终点：读取原成品及入库回执',pageUrl:mesNodeUrl(current,context)}}}
}
