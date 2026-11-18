// Presentation only for LIST-AUTHORITATIVE-FIELDS-20261116-R1-HANDOFF.
// No qualification, permissions, dates, quantities, number parsing or state writes.
export const fieldText = value => value === null || value === undefined || value === '' ? '未提供' : String(value)
const present = value => value !== null && value !== undefined && value !== ''
export const HOME_CONTEXT_COLUMNS = Object.freeze([
 {field:'workOrderNoDisplay',label:'生产工单编号',width:210},
 {field:'workOrderNameDisplay',label:'独立工单名称',width:200},
 {field:'operationNameDisplay',label:'工序名称（原冻结）',width:200},
 {field:'productNameDisplay',label:'品名（原成品来源）',width:240},
])
export function homeContextDisplay(row){
 const display=key=>row.contextFieldStatus?.[key]==='NOT_PROVIDED'?'未提供':fieldText(row[key])
 return {workOrderNoDisplay:display('workOrderNo'),workOrderNameDisplay:display('workOrderName'),operationNameDisplay:display('operationName'),productNameDisplay:display('productName')}
}
export function sourceDocumentTypeText(row){
 if(row.sourceDocumentTypeStatus==='UNKNOWN_TYPE')return '未知类型'
 if(row.sourceDocumentTypeStatus==='NOT_PROVIDED')return '未提供'
 return present(row.sourceDocumentTypeLabel)?String(row.sourceDocumentTypeLabel):'类型说明未提供'
}
export const sourceDocumentIdLabel = row => row.sourceDocumentType==='SalesOrderItem'?'来源订单行ID':'来源对象ID'
// Reuse the existing PlanningCenterPage Chinese type mapping. Never infer by planNo.
const planNames=Object.freeze({ProductionPlan:'生产计划',PurchasePlan:'采购计划'})
export function supplyPlanTypeText(row){
 if(!present(row.planNo)&&row.sourceSelectionRequired===true)return '多来源尚待选择'
 if(!present(row.planType))return '未提供'
 return planNames[row.planType]||'未知计划类型'
}
export function supplyPlanNumberText(row){
 if(present(row.planNo))return String(row.planNo)
 return row.sourceSelectionRequired===true?'多来源尚待选择':'未提供（无所选计划编号）'
}
export function sourceSelectionText(row){
 if(present(row.sourceSelectionMessage))return String(row.sourceSelectionMessage)
 return row.sourceSelectionRequired===true?'多来源尚待选择':row.sourceSelectionRequired===false?'当前无需选择来源':'选择要求未提供'
}
export const ROLE_STATE_TEXT='未提供（无独立启停状态）'
export const ROLE_STATE_NOTICE='账号用于登录；角色是一组工作权限。本系统未提供角色单独的启用／停用状态。账号是否启用、当前能查看和办理哪些事项，分别按原记录显示。'
export const ROLE_STATE_TRACE='独立角色启停状态未由原合同提供；账号启用、任职有效期、角色范围分配和实际授权有效性是不同事实。权限配置不等于当前授权有效，本页不推导角色状态或新增角色启停动作。'
