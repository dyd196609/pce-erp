import {MES_TEST_NODES} from './mesTestProcessNavigation.js'
export const MES_ENTRY_PAGE=Object.freeze({moduleId:'mes-test-execution-entry',pageCode:'mes-test-execution-entry',moduleCode:'MES',businessObject:'MesTestExecutionRead',title:MES_TEST_NODES[0].nodeName,route:'/planning/mes-test-execution',routeName:'MesTestExecutionEntry',component:'src/meta/pages/MesExecutionEntryPage.vue',version:'PCE-MES-READ-ENTRY-V1',formalModel:'planning.ProductionWorkshopTask',apiUrl:'/api/planning/mes-test-entry/'})
export const MES_ENTRY_META=Object.freeze({pageCode:MES_ENTRY_PAGE.pageCode,moduleCode:'MES',canonicalModuleId:MES_ENTRY_PAGE.moduleId,businessObject:MES_ENTRY_PAGE.businessObject,formalModel:MES_ENTRY_PAGE.formalModel,componentKey:MES_ENTRY_PAGE.component,dataAdapter:MES_ENTRY_PAGE.apiUrl,requiresServerAuthentication:true})
export const MES_ENTRY_FILTERS=[{field:'no',label:'工序任务编号',filterType:'text'},{field:'operationName',label:'工序名称',filterType:'text'},{field:'workOrderNo',label:'生产工单编号',filterType:'text'}]
export const MES_ENTRY_SEARCH=['no','workOrderNo','operationName','employeeName','statusLabel']
export function resolveMesExecutionEntryState(route={}){
 if(route.path!==MES_ENTRY_PAGE.route||route.name!==MES_ENTRY_PAGE.routeName)throw new Error('PAGE IDENTITY MISMATCH: MES职责入口路径不一致')
 for(const [key,value] of Object.entries(MES_ENTRY_META))if(route.meta?.[key]!==value)throw new Error('PAGE IDENTITY MISMATCH: MES职责入口 '+key)
 const q=route.query||{}
 if(Object.keys(q).some(x=>!['workOrderId','directory'].includes(x))||q.workOrderId!==undefined&&(typeof q.workOrderId!=='string'||! /^[1-9]\d*$/.test(q.workOrderId)||!Number.isSafeInteger(Number(q.workOrderId)))||q.directory!==undefined&&q.directory!=='all'||q.workOrderId&&q.directory)throw new Error('PAGE IDENTITY MISMATCH: 工单或授权目录定位不合法')
 return Object.freeze({domain:'MES',moduleId:MES_ENTRY_PAGE.moduleId,mode:'view',recordId:q.workOrderId||null,filters:Object.freeze({...q}),identity:MES_ENTRY_PAGE})
}
export const MES_ENTRY_GOVERNANCE={pageCode:MES_ENTRY_PAGE.pageCode,version:MES_ENTRY_PAGE.version,frameworkVersion:'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',returnModuleCode:'MES',purpose:'按有效公司身份、本人任务、独审或指定仓管职责读取历史与准确验收入口。',allowed:['本人执行历史','授权独审任务追溯','本人指定成品交接入库'],forbidden:['全公司工程主数据扩权','恢复已完成任务写入','重复办理已完成业务'],flowSteps:['按职责进入','核对历史事实','人工验收'],currentFlowStep:'按职责进入',navigation:{previous:{label:'业务流程中心',pageUrl:'/process-center'},current:{label:MES_ENTRY_PAGE.title,pageUrl:MES_ENTRY_PAGE.route},next:{label:'选择服务端授权入口',pageUrl:MES_ENTRY_PAGE.route}}}
