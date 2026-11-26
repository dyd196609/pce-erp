import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import {parse} from '@vue/compiler-sfc'
import {compile} from '@vue/compiler-dom'
import {renderToString} from '@vue/server-renderer'
import {paginatePceEnterpriseRows,resolvePceEnterprisePageJump,PCE_ENTERPRISE_LIST_SHELL_DEFAULTS} from '../../src/meta/runtime/pceEnterpriseListContract.js'
import {mesWorkOrderFilter} from '../../src/meta/runtime/mesTestProcessNavigation.js'
const source=fs.readFileSync(new URL('../../src/meta/components/OperationReportContent.vue',import.meta.url),'utf8'),template=parse(source).descriptor.template.content
const render=Function('Vue',compile(template,{mode:'function'}).code)(Vue)
const native=JSON.parse(fs.readFileSync(process.env.PCE_PACK1_EVIDENCE+'/NATIVE_REPORT_RESPONSE.json','utf8')).data
const nullQuantities=JSON.parse(fs.readFileSync(process.env.PCE_PACK1_EVIDENCE+'/NONQUANTIFIED_SERVICE_QUANTITY.json','utf8'))
async function html({nonquantified=false,readState='loaded',writeState='idle',blockingCode='',disabledReason=''}={}){
 const facts=structuredClone(native.operationReportFacts),selected=facts.selectedTask
 if(nonquantified)Object.assign(selected,nullQuantities,{quantityApplicable:false,referenceWorkload:{quantity:null,uomLabel:null},executionModeLabel:'必经但不统计实际量',reports:[],executionConfirmation:null})
 const state={facts,taskId:String(selected.taskId),readState,writeState,quantity:'',reason:'',serverSurface:native.strictFacts}
 const ctx={state,selected,displayFacts:facts,compactViewport:false,taskArea:null,authenticationRequired:false,route:{fullPath:'/planning/operation-reports'},busy:false,pending:writeState==='readback_pending',visibleReadMs:null,readCycle:1,reportAction:{enabled:false,displayName:nonquantified?'登记实际经过':'提交本次报工'},submission:{enabled:false,blockingCode,disabledReason},controller:{},table:{filteredRows:facts.tasks,filters:{},selectedRows:[]},rows:facts.tasks,listContract:{},OPERATION_REPORT_PAGE:{},OPERATION_REPORT_FILTERS:[],OPERATION_REPORT_FORM_VERSION:'original',selectTask(){},viewTask(){},showOriginalRecords(){},returnToTasks(){},learningOpen:false,learning:{write(){}},onLearningToggle(){}}
 const app=Vue.createSSRApp({render,setup:()=>ctx})
 app.component('MesExecutionContext',{render:()=>null});app.component('PceEnterpriseListTable',{render:()=>null});app.component('PceBusinessStatus',{props:['statusLabel'],render(){return Vue.h('span',this.statusLabel)}});app.component('router-link',{props:['to'],render(){return Vue.h('a',{},this.$slots.default?.())}})
 return renderToString(app)
}
test('shared pagination validates all boundaries, authoritative full result total and default sizes',()=>{
 assert.deepEqual([...PCE_ENTERPRISE_LIST_SHELL_DEFAULTS.pageSizes],[10,20,50,100]);assert.equal(PCE_ENTERPRISE_LIST_SHELL_DEFAULTS.defaultPageSize,20)
 for(const size of [10,20,50,100])for(const count of [0,1,19,20,21,105])for(const page of [1,2,999]){const r=paginatePceEnterpriseRows(Array.from({length:count},(_,id)=>({id})),page,size);assert.equal(r.total,count);assert(r.rows.length<=size);assert(r.currentPage<=r.totalPages)}
 for(const value of ['',null,'abc','-1','0','1.5','4','1','Infinity','2e0'])assert.equal(resolvePceEnterprisePageJump(value,3,1),null)
 assert.equal(resolvePceEnterprisePageJump(' 2 ',3,1),2)
})
test('normal work-order navigation only passes validated original query',()=>{assert.deepEqual(mesWorkOrderFilter({query:{workOrderId:'3'}}),{workOrderId:3});assert.throws(()=>mesWorkOrderFilter({query:{workOrderId:'-1'}}))})
test('actual template preserves original quantities and differentiates nonquantified nulls',async()=>{
 const q=await html();assert(q.includes(native.operationReportFacts.selectedTask.workloadQuantity));assert(q.includes('aria-label="本次实际完成数量"'))
 const n=await html({nonquantified:true});assert(n.includes('本工序不单独统计实际完成数量'));assert(n.includes('无工程参考量'));assert(!n.includes('aria-label="本次实际完成数量"'));assert(n.includes('本次实际经过登记原因'))
})
test('actual result template distinguishes validation, failed reads, unknown and verified results',async()=>{
 assert((await html({blockingCode:'QUANTITY_REQUIRED',disabledReason:'请输入本次实际完成数量。'})).includes('字段校验未通过：请输入本次实际完成数量。'))
 assert((await html({readState:'read_failed',writeState:'verified'})).includes('读取失败，当前事实与资格未知'))
 assert(!(await html({readState:'read_failed',writeState:'verified'})).includes('提交成功，原服务已独立'))
 assert((await html({writeState:'readback_pending'})).includes('查询原记录'))
 assert((await html({writeState:'verified'})).includes('报工成功：已查询原记录并确认保存'))
})
