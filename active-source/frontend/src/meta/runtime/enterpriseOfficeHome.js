import {sourceDocumentTypeText,sourceDocumentIdLabel,fieldText,supplyPlanTypeText,ROLE_STATE_TEXT} from './authoritativeFieldPresentation.js'
// Read-only presentation of the original authorized services. No business writes.
export const OFFICE_ROLES = Object.freeze([
  {key:'planning',label:'计划人员'}, {key:'management',label:'管理人员'}, {key:'system',label:'系统维护'},
])
export const isOfficeRole = role => OFFICE_ROLES.some(item=>item.key===role)
export function defaultOfficeRole(profile){
  const codes=profile?.permissionCodes||[]
  return codes.includes('*')?'system':codes.includes('planning.view')?'planning':codes.includes('sales.order.view')?'management':''
}
const planUrl = id => `/planning/requirements?section=work-order-reception&productionPlanId=${encodeURIComponent(id)}`
// One presentation contract drives headers, filters and CSV. These fields are
// copied from the existing authorized responses, never parsed out of context.
const column=(field,label,width=180)=>Object.freeze({field,label,width})
export const OFFICE_RECORD_COLUMN_CONTRACTS=Object.freeze({
  demands:Object.freeze([column('no','需求编号',210),column('sourceTypeLabel','需求来源类别'),column('sourceDocumentTypeDisplay','来源对象类型',210),column('sourceDocumentIdDisplay','来源对象ID（订单行等）',200),column('sourceDocumentNo','来源单据编号（父订单等）',210),column('salesOrderNo','销售订单编号',210),column('materialName','物料名称',240),column('statusLabel','需求状态',170)]),
  plans:Object.freeze([column('no','生产计划编号',210),column('planTypeDisplay','供应计划类型'),column('demandNo','需求编号',210),column('materialName','物料名称',240),column('statusLabel','生产计划状态',170)]),
  workOrders:Object.freeze([column('no','生产工单编号',210),column('productionPlanNo','生产计划编号',210),column('quantityLabel','工单数量与单位'),column('statusLabel','工单状态',170)]),
  orders:Object.freeze([column('no','销售订单编号',210),column('customerName','客户名称',240),column('departmentName','销售部门名称'),column('statusLabel','销售订单状态',170)]),
  users:Object.freeze([column('no','登录账号',210),column('employeeName','员工姓名'),column('statusLabel','账号启用状态',170)]),
  roles:Object.freeze([column('no','角色编码',210),column('roleName','角色名称',240),column('statusLabel','独立角色启停状态（未提供）',230)]),
  departments:Object.freeze([column('no','部门编码',210),column('departmentName','部门名称',240),column('statusLabel','部门状态',170)]),
})
export function officeRecordColumns(kind){
  const columns=OFFICE_RECORD_COLUMN_CONTRACTS[kind]
  if(!columns)throw new Error('OFFICE_RECORD_KIND_UNDECLARED')
  return columns
}
// Group membership comes from the original role_groups read contract. It is a
// display type only; never derive an object type from the number or its prefix.
export function homeRecordTypeLabel(row,{groupKey,recordMode=false,handovers=false}={}){
  if(row.kind)return ({start:'工序任务',report:'工序任务',completionReplacement:'工序任务',review:'工序任务',handover:'工序交接单',finishedGoods:'成品交接单'})[row.kind]||'记录类型未提供'
  if(handovers)return '工序交接单'
  if(groupKey==='warehouse')return '成品交接单'
  if(recordMode&&['production','reviewer','workshop'].includes(groupKey))return '工序任务'
  return '记录类型未提供'
}
const source = (key,title,url,field) => ({key,title,url,field})
export function officeSources(role){
  if(role==='planning') return [source('planning','订单需求与生产计划','/api/planning/facts/','demands'),source('workOrders','授权已下达工单','/api/planning/work-order-workshop-reception/','workshopReceptionFacts')]
  if(role==='management') return [{...source('orders','授权订单','/api/sales/facts/','orders'),params:{officeDirectory:1}},source('workOrders','授权已下达工单','/api/planning/work-order-workshop-reception/','workshopReceptionFacts')]
  if(role==='system') return [source('system','组织与权限基础','/api/access-control/foundation/','users')]
  return []
}
export function readResult(spec,response){
  const status=Number(response?.meta?.status||response?.data?.httpStatus||response?.status||0)
  const failed=response?.success!==true
  if(failed) return {...spec,state:status===403?'permission_denied':status===401?'authentication_required':'read_failed',total:null,rows:[],message:response?.error?.message||'原服务读取失败，记录及数量未知。',errorCode:response?.error?.code||'READ_FAILED'}
  const data=response.data
  if(!data || (spec.key==='workOrders' ? !Array.isArray(data.workshopReceptionFacts?.workOrderOptions) : !Array.isArray(data[spec.field]))) return {...spec,state:'service_unavailable',total:null,rows:[],message:'原服务未提供约定的完整目录，数量未知。'}
  if((spec.key==='planning'&&!Array.isArray(data.requirements))||(spec.key==='system'&&(!Array.isArray(data.roles)||!Array.isArray(data.departments)))||data.pagination||data.next) return {...spec,state:'service_unavailable',total:null,rows:[],message:'目录合同不完整或仅返回分页数据，完整数量尚未取得。'}
  return {...spec,state:'loaded',data,total:spec.key==='workOrders'?data.workshopReceptionFacts.workOrderOptions.length:data[spec.field].length,message:''}
}
const text=value=>value===null||value===undefined||value===''?'未提供':String(value)
const accountState=value=>value===true?'启用':value===false?'停用':'账号启用状态未提供'
const row=(kind,id,no,context,status,pageUrl,original,fields={})=>({id:`${kind}:${id}`,no:text(no),context:text(context),statusLabel:status||`${officeRecordColumns(kind).at(-1).label}未提供`,pageUrl,original,...fields})
export function projectOfficeRecords(result,kind){
  if(result.state!=='loaded')return []
  const d=result.data
  if(kind==='demands')return d.demands.map(x=>row(kind,x.id,x.demandNo,`${x.salesOrderNo||'原订单号未提供'} · ${x.materialName||'名称未提供'}`,x.statusLabel,`/planning/requirements${x.salesOrderNo?'?orderNo='+encodeURIComponent(x.salesOrderNo):''}`,{需求来源类别:fieldText(x.sourceTypeLabel),来源对象类型:sourceDocumentTypeText(x),[sourceDocumentIdLabel(x)]:fieldText(x.sourceDocumentId),来源单据编号:fieldText(x.sourceDocumentNo),销售订单编号:x.salesOrderNo||'未提供',需求数量:text(x.requiredQty),计量单位:x.uomCode||'未提供',客户要求日期:x.requiredDate||'未提供',需求部门名称:x.departmentName||'未提供'},
    {sourceTypeLabel:text(x.sourceTypeLabel),sourceDocumentTypeDisplay:sourceDocumentTypeText(x),sourceDocumentIdDisplay:fieldText(x.sourceDocumentId),sourceDocumentNo:text(x.sourceDocumentNo),salesOrderNo:text(x.salesOrderNo),materialName:text(x.materialName)}))
  if(kind==='plans')return [...new Map(d.requirements.filter(x=>x.planType==='ProductionPlan'&&x.planId&&x.planNo).map(x=>[x.planId,row(kind,x.planId,x.planNo,`${x.demandNo} · ${x.materialName||'名称未提供'}`,x.planStatusLabel,planUrl(x.planId),{供应计划类型:supplyPlanTypeText(x),需求编号:x.demandNo,计划数量:text(x.planQty),数量口径:'原计划量；单位以原计划详情为准，不汇总',要求日期:x.requiredDate||'未提供',计划开始:'进入原排程核实，首页未取得',计划完成:'进入原排程核实，首页未取得'},
    {planTypeDisplay:supplyPlanTypeText(x),demandNo:text(x.demandNo),materialName:text(x.materialName)})])).values()]
  if(kind==='orders')return d.orders.map(x=>row(kind,x.id,x.orderNo,`${x.customerName||'客户未提供'} · ${x.departmentName||'部门未提供'}`,x.statusLabel,`/sales/orders?search=${encodeURIComponent(x.orderNo)}`,{订单日期:x.orderDate||'未提供',客户要求交期:x.requiredDate||'未提供',企业承诺交期:x.deliveryFacts?.committedDeliveryDate||'未提供',计划完成时间:x.deliveryFacts?.plannedCompletionDate||'未提供',数量口径:'订单各行按原单位查看，不合计为生产完成量'},
    {customerName:text(x.customerName),departmentName:text(x.departmentName)}))
  if(kind==='workOrders')return d.workshopReceptionFacts.workOrderOptions.map(x=>row(kind,x.workOrderId,x.workOrderNo,x.productionPlanNo,x.statusLabel,planUrl(x.productionPlanId),{生产计划编号:x.productionPlanNo,工单数量与单位:x.quantityLabel||'未提供'},
    {productionPlanNo:text(x.productionPlanNo),quantityLabel:text(x.quantityLabel)}))
  if(kind==='users')return d.users.map(x=>row(kind,x.id,x.username,x.realName||x.employee?.fullName||'未关联姓名',accountState(x.isActive),`/organization?tab=users&search=${encodeURIComponent(x.username)}`,{公司标识:x.companyId,员工姓名:x.employee?.fullName||'未关联',角色:(x.authorities||[]).map(a=>a.roleName||a.roleCode).join('、')||'未提供',账号启用状态:accountState(x.isActive)},
    {employeeName:text(x.employee?.fullName)}))
  if(kind==='roles')return d.roles.map(x=>row(kind,x.id,x.code,x.name,ROLE_STATE_TEXT,`/organization?tab=roles&search=${encodeURIComponent(x.code)}`,{角色名称:x.name,独立角色启停状态:ROLE_STATE_TEXT,权限项目数:Array.isArray(x.permissionCodes)?x.permissionCodes.length:'未提供'},{roleName:text(x.name)}))
  if(kind==='departments')return d.departments.map(x=>row(kind,x.id,x.code,x.name,x.statusLabel,`/organization?tab=departments&search=${encodeURIComponent(x.code)}`,{公司名称:x.companyName||'未提供',上级部门名称:x.parentName||'未提供',部门负责人姓名:x.leaderEmployeeName||'未提供'},{departmentName:text(x.name)}))
  return []
}
export function officeOrderReadTiming(orderId, started, taskId = null) {
  const orderPath = `/api/sales/orders/${orderId}/`
  const directoryPaths = new Set(['/api/sales/facts/', '/api/planning/work-order-workshop-reception/'])
  const nav = performance.getEntriesByType('navigation')[0]
  const resources = performance.getEntriesByType('resource').flatMap(entry => {
    const url = new URL(entry.name)
    if (url.origin !== window.location.origin) return []
    let phase
    if (url.pathname === orderPath && entry.startTime >= started &&
        url.searchParams.get('includeProgressFacts') === '1' &&
        url.searchParams.get('progressTaskId') === taskId) phase = 'detail'
    else if (directoryPaths.has(url.pathname) && taskId === null) phase = 'directory'
    else if (url.pathname.startsWith('/api/auth/') && taskId === null) phase = 'session'
    else if (url.pathname === '/api/access-control/profile/' && taskId === null) phase = 'profile'
    else return []
    return [{ phase, path: url.pathname, startMs: entry.startTime, requestMs: entry.requestStart,
      responseMs: entry.responseEnd, serverMs: entry.serverTiming.find(value => value.name === 'routing-read')?.duration }]
  })
  return { timeOrigin: performance.timeOrigin, started, captured: performance.now(),
    navigationType: nav?.type, domInteractive: nav?.domInteractive, resources: resources.slice(-12) }
}

export async function loadOfficeFacts(role,request){
  const results=await Promise.all(officeSources(role).map(async spec=>{
    try{return readResult(spec,await request({url:spec.url,method:'GET',params:spec.params,timeout:120000,meta:{module:'SYSTEM',readOnly:true,factLoad:true}}))}
    catch(e){return readResult(spec,{success:false,status:e.response?.status,error:{code:'READ_FAILED',message:'原服务暂未读到，记录及数量未知。请刷新。'}})}
  }))
  return {role,results,readAt:new Date().toISOString(),businessWrites:0}
}
