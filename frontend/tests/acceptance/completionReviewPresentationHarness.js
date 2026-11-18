// Isolated synthetic rows only. No API, user, permission or business-state writes.
import {createApp,h,ref} from 'vue'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus,{ElTableColumn} from 'element-plus'
import 'element-plus/dist/index.css'
import Table from '../../src/meta/components/PceEnterpriseListTable.vue'
import {createPceEnterpriseListContract} from '../../src/meta/runtime/pceEnterpriseListContract.js'
const narrow=new URL(location.href).searchParams.has('noOverflow'),chosen=ref(''),rows=Array.from({length:narrow?2:105},(_,i)=>({id:i+1,no:`SIM-REVIEW-${String(i+1).padStart(28,'0')}`,source:`合成来源中心-${i+1}`,target:`合成去向-${i+1}`,quantity:'6.707520',scope1:'合成工单范围',scope2:'合成历史范围',scope3:'合成追溯依据',status:'隔离合成呈现，非业务记录'}))
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]})
const app=createApp({render:()=>h('main',[
 h('header',{style:'position:fixed;inset:0 0 auto;height:52px;background:#eff6ff;z-index:20'},'模拟账户栏（非业务账户）'),h('div',{style:'position:fixed;top:52px;left:0;right:0;height:44px;background:white;z-index:20'},'模拟固定页面标题'),h('h1','隔离独审列表呈现样本'),h('p','105条合成呈现数据；不写数据库，不代表服务闭环。'),
 h(Table,{contract:createPceEnterpriseListContract({pageCode:'completion-review-presentation-fixture',title:'隔离独审呈现',moduleCode:'TEST'}),pageId:'completion-review-presentation-fixture',tableId:'completion-review-fixture',rows,tableRows:rows,filters:{no:""},filterSchema:[{field:"no",label:"合成审核任务",filterType:"text"}],primaryField:'no',primaryLabel:'任务编号',primaryWidth:215,compactFreezePrimary:true,compactShowIndex:false,compactPrimaryWidth:120,showActionColumn:!narrow,minWidth:narrow?'100%':'2000px'},narrow?{}:{columns:()=>[h(ElTableColumn,{prop:'source',label:'来源中心',width:180}),h(ElTableColumn,{prop:'target',label:'目标中心',width:180}),h(ElTableColumn,{prop:'quantity',label:'来源单位原量',width:140}),h(ElTableColumn,{prop:'status',label:'正式状态（合成）',width:260}),h(ElTableColumn,{prop:"scope1",label:"合成工单范围说明",width:350}),h(ElTableColumn,{prop:"scope2",label:"合成历史范围说明",width:350}),h(ElTableColumn,{prop:"scope3",label:"合成追溯依据",width:350})],actions:({row})=>h('button',{onClick:()=>chosen.value=row.no},'查看任务')}),h('output',{'data-chosen':''},chosen.value),h('p',{style:'padding:30px 0 110vh'},'表格结束；表头不得跟随到此区域。')
])});app.use(router).use(ElementPlus);router.isReady().then(()=>app.mount('#harness'))




