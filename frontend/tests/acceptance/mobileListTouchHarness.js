// Synthetic presentation data only; no service, authentication or business writes.
import {createApp,h,ref} from 'vue'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus,{ElTableColumn} from 'element-plus'
import 'element-plus/dist/index.css'
import Table from '../../src/meta/components/PceEnterpriseListTable.vue'
import {createPceEnterpriseListContract} from '../../src/meta/runtime/pceEnterpriseListContract.js'
const scenario=new URL(location.href).searchParams.get('scenario'),narrow=scenario==='no-overflow',freeze=scenario==='task-freeze'
const rows=ref(Array.from({length:narrow?3:105},(_,id)=>({id:id+1,no:freeze?`SIM-WT-20261112-${String(id+1).padStart(10,'0')}`:`合成任务-${id+1}`,operation:`合成工序-${id+1}`,status:'只读合成样本',stationLabel:`样本岗位-${id+1}`,sourceLabel:`隔离来源行-${id+1}`})))
const table=ref(null)
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]})
const app=createApp({render:()=>h('main',{style:freeze?'padding-top:100px':''},[
 ...(freeze?[h('header',{style:'position:fixed;inset:0 0 auto;height:52px;background:#eff6ff;z-index:20'},'模拟账户栏（非业务账户）'),h('div',{style:'position:fixed;top:52px;left:0;right:0;height:44px;background:white;z-index:20'},'模拟页面固定标题')]:[]),
 h('h1','隔离触控与分页样本'),h('p','合成数据，不代表业务事实。'),h(Table,{ref:table,contract:createPceEnterpriseListContract({pageCode:'mobile-touch-fixture',title:'隔离列表',moduleCode:'TEST'}),pageId:'mobile-touch-fixture',tableId:'mobile-touch-table',rows:rows.value,tableRows:rows.value,filters:{no:''},filterSchema:[{field:'no',label:'合成任务编号',filterType:'text'}],primaryField:'no',primaryLabel:'合成任务编号',primaryWidth:narrow?120:168,compactFreezePrimary:freeze,showActionColumn:!narrow,minWidth:narrow?'100%':freeze?'1200px':'1800px',viewportMaxHeight:freeze?'':360},narrow?{}:{columns:()=>[h(ElTableColumn,{prop:'operation',label:'合成工序',width:180}),h(ElTableColumn,{prop:'status',label:'样本状态',width:240}),...(freeze?[h(ElTableColumn,{prop:'no',label:'样本完整标识',width:300}),h(ElTableColumn,{prop:'stationLabel',label:'合成岗位说明',width:300}),h(ElTableColumn,{prop:'sourceLabel',label:'隔离来源说明',width:300})]:[])]}),h('p',{style:freeze?'padding:30px 0 110vh':'padding:30px 0'},'夹具结束；在列表外可上下滚动。')])})
app.use(router).use(ElementPlus);router.isReady().then(()=>app.mount('#harness'))
