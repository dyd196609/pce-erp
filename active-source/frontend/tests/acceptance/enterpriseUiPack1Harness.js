// Isolated test harness. These synthetic rows never become business facts or API responses.
import {createApp,h,ref,reactive,computed} from 'vue'
import {createRouter,createMemoryHistory} from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import Table from '../../src/meta/components/PceEnterpriseListTable.vue'
import {createPceEnterpriseListContract} from '../../src/meta/runtime/pceEnterpriseListContract.js'
const rows=ref(Array.from({length:105},(_,id)=>({id:id+1,no:`合成行-${id+1}`}))),filters=reactive({no:''}),visible=ref(true),table=ref(null)
const filtered=computed(()=>rows.value.filter(r=>r.no.includes(filters.no)))
window.pack1Harness={rows,filters,visible,table}
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]})
const app=createApp({render:()=>h('main',[h('h1','公共组件合成行验证'),visible.value?h(Table,{ref:table,contract:createPceEnterpriseListContract({pageCode:'pack1-fixture',title:'分页隔离测试',moduleCode:'TEST'}),pageId:'pack1-fixture',tableId:'pack1-fixture-table',rows:rows.value,tableRows:filtered.value,filters,filterSchema:[{field:'no',label:'合成编号',filterType:'text'}],primaryField:'no',primaryLabel:'合成编号',minWidth:'1480px'}):null])})
app.use(router).use(ElementPlus);router.isReady().then(()=>app.mount('#harness'))
