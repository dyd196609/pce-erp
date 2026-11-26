export const FINISHED_GOODS_PAGE=Object.freeze({moduleId:'production-finished-goods-handover',pageCode:'production-finished-goods-handover',moduleCode:'MES',businessObject:'ProductionFinishedGoodsTransfer',title:'成品交接入库',route:'/planning/finished-goods-handovers',routeName:'ProductionFinishedGoodsHandover',component:'src/meta/pages/FinishedGoodsPage.vue',version:'PCE-TEST-FG-V1',formalModel:'planning.ProductionFinishedGoodsTransfer+procurement.WarehouseInbound+InventoryLot+InventoryBalance+InventoryTransaction',apiUrl:'/api/planning/finished-goods-handovers/',factContractVersion:'PCE-TEST-PRODUCTION-FINISHED-GOODS-V1'})
export const FINISHED_GOODS_ROUTE_META=Object.freeze({pageCode:FINISHED_GOODS_PAGE.pageCode,moduleCode:'MES',canonicalModuleId:FINISHED_GOODS_PAGE.moduleId,businessObject:FINISHED_GOODS_PAGE.businessObject,formalModel:FINISHED_GOODS_PAGE.formalModel,componentKey:FINISHED_GOODS_PAGE.component,dataAdapter:FINISHED_GOODS_PAGE.apiUrl,requiresServerAuthentication:true})
export const FINISHED_GOODS_FILTERS=Object.freeze([{field:'no',label:'成品交接单编号',filterType:'text'},{field:'workOrderNo',label:'生产工单编号',filterType:'text'},{field:'statusLabel',label:'成品交接入库状态',filterType:'select',options:[],optionsProvider:{source:'server',factKey:'finishedGoodsFacts.filterOptions.statusLabels'}}])
export const FINISHED_GOODS_SEARCH_FIELDS=Object.freeze(['no','workOrderNo','productName','warehouseName','receiverName','statusLabel'])
export const FINISHED_GOODS_ACTIONS=Object.freeze(Object.fromEntries([
 ['prepare','确认整批成品备交','production.finished_goods.prepare','production.operation.handover.prepare','prepare/'],
 ['dispatch','确认成品实际交出','production.finished_goods.dispatch','production.operation.handover.dispatch','{objectId}/dispatch/'],
 ['cancel','取消未交出成品备交','production.finished_goods.cancel','production.operation.handover.cancel','{objectId}/cancel/'],
 ['receive','确认整批成品接收并测试入库','warehouse.production.test_putaway','warehouse.production.test_putaway','{objectId}/receive/'],
].map(([key,displayName,actionCode,permission,suffix])=>[key,Object.freeze({key,displayName,actionName:displayName,actionId:actionCode,actionCode,moduleCode:FINISHED_GOODS_PAGE.moduleId,actionType:'command',handlerType:'emit',scope:'single',singleOrBatch:'single',permission,requiredPermission:permission,serverPermission:permission,role:[],allowedRoles:[],roleSource:'server',organizationScope:'legal_entity',serverValidator:'planning.finished_goods_service.execute_finished_goods',allowedStatuses:['open','prepared','in_transit','received','cancelled'],serverEligibilityCheck:true,requiresEligibility:true,executionAvailabilitySource:'availableActions',httpMethod:'POST',apiPathTemplate:FINISHED_GOODS_PAGE.apiUrl+suffix})])))
export const FINISHED_GOODS_GOVERNANCE=Object.freeze({pageCode:FINISHED_GOODS_PAGE.pageCode,version:FINISHED_GOODS_PAGE.version,frameworkVersion:'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',returnModuleCode:'MES',purpose:'真实末道班组长按全单独审及接收证明整批交出；指定仓管独立接收并生成同用途原生库存账。',allowed:['本人末道成品备交和实际交出','指定仓管接收同用途库存','既有独审人员整单只读追溯'],forbidden:['缺少完整正式来源或跨用途库存消费','代替其他员工履职','修改冻结工单、原排程占用或重复入库'],flowSteps:['工序报工','产出确认及交接','独立审核完工','成品交接入库'],currentFlowStep:'成品交接入库',navigation:{previous:{label:'按职责进入与历史验收',pageUrl:'/planning/mes-test-execution'},current:{label:FINISHED_GOODS_PAGE.title,pageCode:FINISHED_GOODS_PAGE.pageCode,pageUrl:FINISHED_GOODS_PAGE.route},next:{label:'本轮终点：核对同用途入库原账及回执',pageUrl:FINISHED_GOODS_PAGE.route}}})

// Server-verified parent purpose selects an exact registered contract. The TEST
// receive contract remains intact and cannot authorize formal putaway.
export const FINISHED_GOODS_FORMAL_ACTIONS=Object.freeze({...FINISHED_GOODS_ACTIONS,
 receive:Object.freeze({...FINISHED_GOODS_ACTIONS.receive,
  displayName:'确认正式用途成品接收入库',actionName:'确认正式用途成品接收入库',
  actionId:'warehouse.production.putaway',actionCode:'warehouse.production.putaway',
  permission:'warehouse.production.putaway',requiredPermission:'warehouse.production.putaway',serverPermission:'warehouse.production.putaway'})})

export function resolveFinishedGoodsPageState(route={}){
 if(route.path!==FINISHED_GOODS_PAGE.route || route.name!==FINISHED_GOODS_PAGE.routeName)throw new Error('PAGE IDENTITY MISMATCH: 成品交接路径不一致')
 for(const [key,value] of Object.entries(FINISHED_GOODS_ROUTE_META))if(route.meta?.[key]!==value)throw new Error('PAGE IDENTITY MISMATCH: '+key)
 const filters={}
 for(const [key,value] of Object.entries(route.query||{})){if(!['workOrderId','transferId'].includes(key)||typeof value!=='string'||! /^[1-9]\d*$/.test(value)||!Number.isSafeInteger(Number(value)))throw new Error('PAGE IDENTITY MISMATCH: 成品对象定位不合法');filters[key]=Number(value)}
 return Object.freeze({domain:'MES',moduleId:FINISHED_GOODS_PAGE.moduleId,mode:'view',recordId:filters.transferId??filters.workOrderId??null,filters:Object.freeze(filters),identity:FINISHED_GOODS_PAGE})
}
