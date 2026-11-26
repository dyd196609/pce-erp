<template>
  <section v-if="operationRow" class="operation-zone" data-acceptance-id="purchase-request-original-operation-zone">
    <div><h3>采购申请操作区域</h3><p>当前对象：{{ operationRow.requestNo }} · {{ operationRow.statusLabel }}</p></div>
    <div class="operation-buttons">
      <template v-for="action in visibleActions(operationRow)" :key="action.code">
        <el-button :type="action.type" :data-original-action="action.code" :data-process-action="purchaseRequestActionCodes[action.code] || undefined" @click="runAction(action.code, operationRow)">{{ action.label }}</el-button>
      </template>
    </div>
  </section>

  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1240px" destroy-on-close
    :data-purchase-mode="form.purchaseMode || 'STANDARD'" data-acceptance-id="purchase-request-form">
    <el-form label-width="120px" :disabled="viewOnly" data-original-schema="configs.request">
      <el-alert v-if="form.purchaseMode==='AGREED_PRICE'" title="既定价格采购申请审批后进入既定价格确认，不进入询价、比价或核价。"
        type="info" :closable="false" show-icon data-acceptance-id="agreed-price-flow-boundary" />
      <div class="form-grid" data-acceptance-id="purchase-request-header">
        <el-form-item v-for="field in configs.request.headerFields" :key="field.key" :label="field.label" :required="field.required" :class="{ 'form-span': field.type === 'textarea' }">
          <el-tree-select v-if="field.type === 'tree-select'" v-model="form[field.key]" :data="providerOptions(field)"
            filterable clearable check-strictly default-expand-all value-key="id" :props="organizationTreeProps"
            :data-provider="field.provider" :placeholder="`请选择${field.label}`" @change="handleHeaderFieldChange(field.key)" />
          <el-select v-else-if="field.type === 'select'" v-model="form[field.key]" filterable clearable
            :loading="providerLoading[field.provider]" :data-provider="field.provider" :placeholder="`请选择${field.label}`" @change="handleHeaderFieldChange(field.key)">
            <el-option v-for="option in providerOptions(field)" :key="option.id" :label="option.name" :value="option.id" />
          </el-select>
          <el-date-picker v-else-if="field.type === 'date'" v-model="form[field.key]" type="date" value-format="YYYY-MM-DD" :placeholder="`请选择${field.label}`" />
          <el-input v-else-if="field.type === 'textarea'" v-model="form[field.key]" type="textarea" :rows="2" />
          <el-input v-else v-model="form[field.key]" :disabled="field.readonly" />
        </el-form-item>
      </div>

      <div class="detail-heading">
        <div><h3>明细行</h3><span>原主从式单行明细编辑器</span></div>
        <el-button v-if="!viewOnly" type="primary" @click="startAddDetail">新增明细</el-button>
      </div>
      <el-table :data="detailRows" border stripe max-height="360" data-acceptance-id="purchase-request-material-lines" data-material-source="MaterialMaster">
        <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
        <el-table-column v-for="column in configs.request.detailColumns" :key="column.key" :prop="column.key" :label="column.label" :min-width="column.width || 120" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :disabled="viewOnly" @click="startEditDetail(row)">编辑明细</el-button>
            <el-button size="small" :disabled="viewOnly" @click="copyDetail(row)">复制</el-button>
            <el-button size="small" type="danger" :disabled="viewOnly" @click="deleteDetail(row)">删除明细</el-button>
          </template>
        </el-table-column>
      </el-table>

      <section v-if="detailEditorVisible" class="detail-editor">
        <h3>{{ detailForm.rowKey ? '编辑明细' : '添加明细' }}</h3>
        <div class="form-grid">
          <el-form-item v-for="field in configs.request.detailFields" :key="field.key" :label="field.label" :required="field.required">
            <el-select v-if="field.type === 'select'" v-model="detailForm[field.key]" filterable clearable
              :loading="providerLoading[field.provider]" :data-provider="field.provider" :placeholder="`请选择${field.label}`" @change="handleDetailFieldChange(field.key)">
              <el-option v-for="option in providerOptions(field)" :key="option.id" :label="option.name" :value="option.id" />
            </el-select>
            <el-date-picker v-else-if="field.type === 'date'" v-model="detailForm[field.key]" type="date" value-format="YYYY-MM-DD" :placeholder="`请选择${field.label}`" />
            <el-input-number v-else-if="field.type === 'number'" v-model="detailForm[field.key]" :min="field.min ?? 0" :precision="field.precision || 0" />
            <el-input v-else-if="field.type === 'textarea'" v-model="detailForm[field.key]" type="textarea" :rows="2" />
            <el-input v-else v-model="detailForm[field.key]" :disabled="field.readonly" />
          </el-form-item>
        </div>
        <div class="editor-actions"><el-button type="primary" @click="saveDetail">保存明细</el-button><el-button @click="cancelDetail">取消</el-button></div>
      </section>
    </el-form>
    <template #footer><el-button @click="dialogVisible=false">{{ viewOnly ? '关闭' : '取消' }}</el-button><el-button v-if="!viewOnly" type="primary" :loading="saving" :data-process-action="purchaseRequestActionCodes.save" @click="saveCurrent">保存采购申请</el-button></template>
  </el-dialog>

  <el-dialog v-model="workflowVisible" :title="workflowTitle" width="900px" append-to-body>
    <template v-if="workflowRow">
      <div class="approval-facts"><span>审批状态：<strong>{{ readPurchaseRequestState(workflowRow).approvalStatus }}</strong></span><span>业务状态：<strong>{{ readPurchaseRequestState(workflowRow).businessLifecycleState }}</strong></span><span>当前节点：<strong>{{ workflowRow.approvalCurrentNode }}</strong></span><span>审批人：<strong>{{ workflowRow.approvalCurrentApprover }}</strong></span><span>结果：<strong>{{ workflowRow.approvalResult || '待审批' }}</strong></span></div>
      <div v-if="workflowMode==='preparation'" class="preparation-summary" data-acceptance-id="inquiry-preparation-created">
        <span>准备编号：<strong>{{ inquiryPreparation?.inquiryPreparationNo }}</strong></span>
        <span>来源采购申请：<strong>{{ inquiryPreparation?.sourceRequestNo }}</strong></span>
        <span>状态：<strong>{{ inquiryPreparation?.statusLabel }}</strong></span>
        <span>供应商候选：<strong>{{ inquiryPreparation?.supplierCandidates?.length || 0 }}</strong></span>
      </div>
      <el-table v-if="workflowMode==='eligibility'||workflowMode==='preparation'" :data="workflowMode==='preparation' ? inquiryPreparation?.inquiryLines || [] : workflowRow.inquiryEligibility?.items || []" border empty-text="当前没有可询价明细">
        <el-table-column prop="materialCode" label="物料编码" /><el-table-column prop="materialName" label="物料名称" /><el-table-column prop="quantity" label="数量" /><el-table-column prop="requiredDate" label="需求日期" />
      </el-table>
      <el-table v-else-if="workflowMode==='history'" :data="workflowRow.approvalHistory || []" border empty-text="暂无审批记录">
        <el-table-column prop="nodeName" label="审批节点" /><el-table-column prop="actor" label="操作人" /><el-table-column prop="comment" label="动作" /><el-table-column prop="createdAt" label="时间" />
      </el-table>
      <p class="no-write">{{ workflowMode==='preparation' ? '询价准备对象已生成；正式询价、报价任务及供应商发送均未创建。' : '资格判断不会自动创建正式询价对象。' }}</p>
    </template>
    <template #footer><el-button @click="workflowVisible=false">关闭</el-button><el-button v-if="workflowMode==='preparation'" type="primary" data-acceptance-id="view-inquiry-preparation" data-process-handoff="PURCHASE_REQUEST_TO_INQUIRY_PREPARATION" @click="viewInquiryPreparation">查看询价准备</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, inject, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { purchaseRequestApi } from '@/api/purchaseRequest.js'
import { getAuthenticationHeaders } from '@/api/request.js'
import { assessPurchaseRequestSubmit, resolvePurchaseRequestSubmitFailure } from '@/meta/runtime/purchaseRequestSubmitSelectionRuntime.js'
import { assessPurchaseRequestAction, executePurchaseRequestBatchAction, resolvePurchaseRequestActionFailure } from '@/meta/runtime/purchaseRequestBusinessActionRuntime.js'
import { createInquiryPreparation, createInquiryPreparationsBatch, findInquiryPreparationBySource } from '@/meta/runtime/inquiryPreparationRuntime.js'
import { PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY, purchaseRequestProviders } from '@/meta/scm/purchaseRequestProviderRuntimeRegistry.js'
import { PURCHASE_REQUEST_BUTTON_ACTION_CODES, resolvePurchaseRequestActionContract } from '@/meta/process/scm/purchaseRequest/purchaseRequestActionContracts.js'
import { readPurchaseRequestState } from '@/meta/process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

defineOptions({ name: 'ScmPurchaseRequestOriginalBusinessRegion' })
const props=defineProps({operationRow:{type:Object,default:null},createTitle:{type:String,default:''}})
const emit=defineEmits(['refreshed','authentication-required','inquiry-preparation-created','approval-required','procurement-mode-routed'])
const dialogVisible=ref(false),viewOnly=ref(false),saving=ref(false),editingId=ref(null)
const workflowVisible=ref(false),workflowRow=ref(null),workflowMode=ref('history'),inquiryPreparation=ref(null)
const providerRuntime=inject(PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY,purchaseRequestProviders)
const purchaseRequestActionCodes=PURCHASE_REQUEST_BUTTON_ACTION_CODES
const employees=computed(()=>providerRuntime.providers.employeeProvider),departments=computed(()=>providerRuntime.providers.departmentProvider),projects=computed(()=>providerRuntime.providers.projectProvider),costCenters=computed(()=>providerRuntime.providers.costCenterProvider),expenseCategories=computed(()=>providerRuntime.providers.expenseCategoryProvider),budgetCategories=computed(()=>providerRuntime.providers.budgetCategoryProvider),materials=computed(()=>providerRuntime.providers.materialProvider),suppliers=computed(()=>providerRuntime.providers.supplierProvider)
const providerLoading=providerRuntime.loading,providerErrors=providerRuntime.errors
const detailRows=ref([]),detailEditorVisible=ref(false)
const today=()=>new Date().toISOString().slice(0,10)
let rowSequence=0
const form=reactive({})
const detailForm=reactive({})
const workflowTitle=computed(()=>workflowMode.value==='preparation'?'询价准备对象':workflowMode.value==='eligibility'?'转询价资格':'采购申请审批')
const dialogTitle=computed(()=>viewOnly.value?'查看采购申请':editingId.value?'编辑采购申请':props.createTitle||(form.purchaseMode==='AGREED_PRICE'?'新建既定价格采购申请':'新增采购申请'))
const optionName=(row,keys)=>keys.map(key=>row[key]).filter(Boolean).join(' / ')
const employeeOptions=()=>employees.value.map(row=>({...row,name:optionName(row,['employeeNo','name','departmentName'])}))
const departmentOptions=()=>departments.value.map(row=>({...row,name:optionName(row,['code','name'])}))
const organizationTreeProps={label:'name',children:'children'}
const organizationTreeOptions=()=>{const byId=new Map(departments.value.map(row=>[String(row.id),{...row,name:optionName(row,['code','name']),children:[]}]))
  const roots=[]
  departments.value.forEach(row=>{const node=byId.get(String(row.id));const parent=byId.get(String(row.parentId));if(parent){parent.children.push(node);return}node.name=optionName({...row,companyPath:row.companyName},['companyPath','code','name']);roots.push(node)})
  return roots}
const projectOptions=()=>projects.value.map(row=>({...row,name:optionName(row,['code','name','stage'])}))
const costCenterOptions=()=>costCenters.value.map(row=>({...row,name:optionName(row,['code','name','departmentName'])}))
const expenseOptions=()=>expenseCategories.value.map(row=>({...row,name:optionName(row,['code','name'])}))
const budgetOptions=()=>budgetCategories.value.map(row=>({...row,name:optionName(row,['code','name'])}))
const materialOptions=()=>materials.value.map(row=>({...row,name:optionName(row,['code','name','specification','unit'])}))
const supplierOptions=()=>suppliers.value.map(row=>({...row,name:optionName(row,['code','name'])}))
const controlProviders=Object.freeze({
  employeeProvider:computed(employeeOptions),departmentProvider:computed(organizationTreeOptions),projectProvider:computed(projectOptions),costCenterProvider:computed(costCenterOptions),expenseCategoryProvider:computed(expenseOptions),budgetCategoryProvider:computed(budgetOptions),materialProvider:computed(materialOptions),supplierProvider:computed(supplierOptions),
})
function providerOptions(field){return field.provider ? controlProviders[field.provider]?.value||[] : field.options?.()||[]}

// 以下 configs.request、snapshotMaterial、preferredSupplierId、handleHeaderFieldChange、
// handleDetailFieldChange 与主从明细编辑器直接源自 ScmPage.vue 原采购申请业务区。
const configs={request:{
  headerFields:[
    {key:'requestNo',label:'请购单号',readonly:true},{key:'requestDate',label:'请购日期',type:'date',required:true},
    {key:'requesterEmployeeId',label:'请购人',type:'select',required:true,provider:'employeeProvider'},
    {key:'departmentId',label:'请购部门',type:'tree-select',required:true,provider:'departmentProvider'},
    {key:'usageDepartmentId',label:'需求部门',type:'tree-select',required:true,provider:'departmentProvider'},
    {key:'purchaseDepartmentId',label:'采购部门',type:'tree-select',required:true,provider:'departmentProvider'},
    {key:'requiredDate',label:'需求日期',type:'date',required:true},
    // R4-R8 已存在的企业模型字段保留为同一 schema 的扩展字段，不属于原字段。
    {key:'projectId',label:'项目',type:'select',required:true,provider:'projectProvider'},{key:'costCenterId',label:'成本中心',type:'select',required:true,provider:'costCenterProvider'},
    {key:'expenseCategoryId',label:'费用类别',type:'select',required:true,provider:'expenseCategoryProvider'},{key:'budgetCategoryId',label:'预算类别',type:'select',required:true,provider:'budgetCategoryProvider'},
    {key:'requestType',label:'申请类型',type:'select',required:true,options:()=>[{id:'production',name:'生产需求'},{id:'stock_replenishment',name:'库存补充'},{id:'engineering',name:'工程需求'},{id:'equipment',name:'设备需求'},{id:'other',name:'其他需求'}]},
    {key:'sourceType',label:'来源对象',type:'select',required:true,options:()=>[{id:'ManualRequest',name:'人工申请'},{id:'PDEManufacturingInput',name:'PDE制造输入'},{id:'MRPRequirement',name:'MRP需求'},{id:'InventoryReplenishment',name:'库存补充'}]},
    {key:'applicationReason',label:'申请原因',type:'textarea'},{key:'purchasePurpose',label:'采购用途',type:'textarea'},
    {key:'technicalDescription',label:'技术说明',type:'textarea'},{key:'deliveryRequirements',label:'交付要求',type:'textarea'},{key:'noteDescription',label:'备注说明',type:'textarea'},
  ],
  detailColumns:[{key:'materialCode',label:'物料编码'},{key:'materialName',label:'物料名称'},{key:'specification',label:'规格型号'},{key:'unit',label:'单位'},{key:'quantity',label:'数量'},{key:'requiredDate',label:'需求日期'},{key:'suggestedSupplierName',label:'建议供应商',width:160},{key:'remark',label:'备注'}],
  detailFields:[
    {key:'materialId',label:'物料',type:'select',required:true,provider:'materialProvider'},{key:'materialCode',label:'物料编码',readonly:true},{key:'materialName',label:'物料名称',readonly:true},{key:'specification',label:'规格型号',readonly:true},{key:'unit',label:'单位',readonly:true},{key:'materialCategory',label:'物料分类',readonly:true},{key:'purchaseAttribute',label:'采购属性',readonly:true},
    {key:'quantity',label:'数量',type:'number',min:0.0001,precision:4,required:true},{key:'requiredDate',label:'需求日期',type:'date',required:true},{key:'suggestedSupplierId',label:'建议供应商',type:'select',provider:'supplierProvider'},
    {key:'demandReason',label:'需求原因'},{key:'technicalRequirements',label:'技术要求'},{key:'brandRequirements',label:'品牌要求'},{key:'substituteRequirement',label:'替代要求'},{key:'purchaseRemark',label:'采购备注'},{key:'remark',label:'备注',type:'textarea'},
  ],
  listActions:[{code:'submit',label:'提交',type:'success'},{code:'approve',label:'审批',type:'primary'},{code:'convert',label:'生成询价准备',type:'primary'},{code:'close',label:'关闭'}],
}}

function emptyHeader(){return{requestNo:'',requestDate:today(),purchaseMode:'STANDARD',requesterEmployeeId:null,departmentId:null,usageDepartmentId:null,purchaseDepartmentId:null,requiredDate:'',projectId:null,costCenterId:null,expenseCategoryId:null,budgetCategoryId:null,requestType:'production',sourceType:'ManualRequest',applicationReason:'',purchasePurpose:'',technicalDescription:'',deliveryRequirements:'',noteDescription:''}}
function emptyDetail(){return{rowKey:null,lineNo:detailRows.value.length+1,materialId:null,materialCode:'',materialName:'',specification:'',unit:'',materialCategory:'',purchaseAttribute:'',quantity:1,requiredDate:form.requiredDate||'',suggestedSupplierId:null,suggestedSupplierCode:'',suggestedSupplierName:'',demandReason:'',technicalRequirements:'',brandRequirements:'',substituteRequirement:'',purchaseRemark:'',remark:''}}
function resetObject(target,value){Object.keys(target).forEach(key=>delete target[key]);Object.assign(target,value)}
async function loadReferences(){await providerRuntime.initPurchaseRequestProviders();const failed=Object.entries(providerErrors).filter(([,message])=>message);if(failed.length)ElMessage.warning(`部分基础资料不可用：${failed.map(([code])=>code).join('、')}`)}
function snapshotMaterial(materialId){const item=materials.value.find(option=>String(option.id)===String(materialId))||{};return{materialId:item.id||materialId||null,materialCode:item.code||'',materialName:item.name||'',specification:item.specification||'',unit:item.unit||'',materialCategory:item.category||'',purchaseAttribute:item.purchaseAttribute||''}}
function preferredSupplierId(){return suppliers.value[0]?.id||null}
function handleHeaderFieldChange(key){if(key==='requesterEmployeeId'){const employee=employees.value.find(item=>String(item.id)===String(form.requesterEmployeeId));const department=departments.value.find(item=>String(item.id)===String(employee?.departmentId)||item.name===employee?.departmentName);if(department){form.departmentId=department.id;if(!form.usageDepartmentId)form.usageDepartmentId=department.id}}if(key==='projectId'){const project=projects.value.find(item=>String(item.id)===String(form.projectId));if(project?.recommendedCostCenterId)form.costCenterId=project.recommendedCostCenterId}}
function handleDetailFieldChange(key){if(key==='materialId'){Object.assign(detailForm,snapshotMaterial(detailForm.materialId));detailForm.suggestedSupplierId=preferredSupplierId(detailForm.materialId);const supplier=suppliers.value.find(item=>String(item.id)===String(detailForm.suggestedSupplierId));Object.assign(detailForm,{suggestedSupplierCode:supplier?.code||'',suggestedSupplierName:supplier?.name||''})}if(key==='suggestedSupplierId'){const supplier=suppliers.value.find(item=>String(item.id)===String(detailForm.suggestedSupplierId));Object.assign(detailForm,{suggestedSupplierCode:supplier?.code||'',suggestedSupplierName:supplier?.name||''})}}
function startAddDetail(){resetObject(detailForm,emptyDetail());detailEditorVisible.value=true}
function startEditDetail(row){resetObject(detailForm,{...row});detailEditorVisible.value=true}
function cancelDetail(){detailEditorVisible.value=false;resetObject(detailForm,{})}
function saveDetail(){if(!detailForm.materialId||!detailForm.requiredDate||Number(detailForm.quantity)<=0){ElMessage.warning('请选择物料并填写有效数量和需求日期');return}if(detailForm.rowKey){const index=detailRows.value.findIndex(row=>row.rowKey===detailForm.rowKey);detailRows.value.splice(index,1,{...detailForm})}else detailRows.value.push({...detailForm,rowKey:++rowSequence,lineNo:detailRows.value.length+1});renumber();cancelDetail()}
function copyDetail(row){detailRows.value.push({...row,rowKey:++rowSequence,lineNo:detailRows.value.length+1});renumber()}
function deleteDetail(row){detailRows.value=detailRows.value.filter(item=>item.rowKey!==row.rowKey);renumber()}
function renumber(){detailRows.value=detailRows.value.map((row,index)=>({...row,lineNo:index+1}))}
function normalizeRow(row,index){return{...emptyDetail(),...row,rowKey:++rowSequence,lineNo:index+1,quantity:Number(row.quantity||1)}}
function headerPayload(){return{requestDate:form.requestDate,purchaseMode:form.purchaseMode,requestType:form.requestType,requesterEmployeeId:form.requesterEmployeeId,departmentId:form.departmentId,usageDepartmentId:form.usageDepartmentId,purchaseDepartmentId:form.purchaseDepartmentId,projectId:form.projectId,costCenterId:form.costCenterId,expenseCategoryId:form.expenseCategoryId,budgetCategoryId:form.budgetCategoryId,sourceType:form.sourceType,requiredDate:form.requiredDate||null,applicationReason:form.applicationReason,purchasePurpose:form.purchasePurpose,technicalDescription:form.technicalDescription,deliveryRequirements:form.deliveryRequirements,noteDescription:form.noteDescription,items:detailRows.value.map(row=>({materialId:row.materialId,quantity:String(row.quantity),requiredDate:row.requiredDate,demandReason:row.demandReason,suggestedSupplierId:row.suggestedSupplierId||null,technicalRequirements:row.technicalRequirements,brandRequirements:row.brandRequirements,substituteRequirement:row.substituteRequirement,purchaseRemark:row.purchaseRemark,remark:row.remark}))}}
function validateHeader(){const missing=configs.request.headerFields.find(field=>field.required&&!form[field.key]);if(missing)throw new Error(`请填写必填项：${missing.label}`);if(!detailRows.value.length)throw new Error('请至少保存一条明细')}
async function saveCurrent(){const actionContract=resolvePurchaseRequestActionContract('save');if(!actionContract)throw new Error('SAVE_PURCHASE_REQUEST_ACTION_CONTRACT_REQUIRED');saving.value=true;try{validateHeader();if(!authenticationReady()){emit('authentication-required',{action:editingId.value?'update':'create'});throw new Error('当前登录身份已失效，请重新登录后保存采购申请')}const response=editingId.value?await purchaseRequestApi.update(editingId.value,headerPayload()):await purchaseRequestApi.create(headerPayload());if(!response?.success)throw new Error(response?.error?.message||'保存失败');const saved=response.data;if(!saved?.requestNo||!Array.isArray(saved.items)||!saved.requester||!saved.department||!saved.status)throw new Error('PURCHASE_REQUEST_CREATE_RESPONSE_INCOMPLETE');dialogVisible.value=false;ElMessage.success(`采购申请 ${saved.requestNo} 已保存到服务端`);emit('refreshed',saved);emit('procurement-mode-routed',saved);return saved}catch(error){ElMessage.error(error?.message||'保存失败');return null}finally{saving.value=false}}
async function openCreate(purchaseMode='STANDARD'){await loadReferences();editingId.value=null;viewOnly.value=false;resetObject(form,{...emptyHeader(),purchaseMode});detailRows.value=[];startAddDetail();dialogVisible.value=true}
async function openEdit(row){await loadReferences();editingId.value=row.objectId;viewOnly.value=false;resetObject(form,{...emptyHeader(),...row,requesterEmployeeId:row.requesterEmployeeId,departmentId:row.departmentId,usageDepartmentId:row.usageDepartmentId,purchaseDepartmentId:row.purchaseDepartmentId,projectId:row.projectId,costCenterId:row.costCenterId,expenseCategoryId:row.expenseCategoryId,budgetCategoryId:row.budgetCategoryId});detailRows.value=(row.items||[]).map(normalizeRow);cancelDetail();dialogVisible.value=true}
async function openView(row){await openEdit(row);viewOnly.value=true}
function visibleActions(row){const definitions=configs.request.listActions;const state=readPurchaseRequestState(row);if(state.approvalStatus==='draft')return definitions.filter(action=>['submit','close'].includes(action.code));if(state.approvalStatus==='submitted')return definitions.filter(action=>['approve','close'].includes(action.code));if(row.purchaseMode!=='STANDARD'&&state.approvalStatus==='approved')return definitions.filter(action=>action.code==='close');if(state.approvalStatus==='approved'&&['approved','inquiry_preparation_ready'].includes(state.businessLifecycleState))return definitions.filter(action=>['convert','close'].includes(action.code));return[]}
function authenticationReady(){return Boolean(getAuthenticationHeaders().Authorization)}
async function transition(row,method,title){try{if(method==='submit'){const assessment=assessPurchaseRequestSubmit(row);if(!assessment.allowed)throw new Error(assessment.reason)}if(method==='submit'||method==='approve'){const assessment=assessPurchaseRequestAction(row,method);if(!assessment.allowed)throw new Error(assessment.reason);if(!authenticationReady()){emit('authentication-required',{action:method,requestNo:row.requestNo});throw new Error(resolvePurchaseRequestActionFailure({meta:{status:401}},method))}}await ElMessageBox.confirm(`确认${title}采购申请 ${row.requestNo}？`,title,{type:'warning'});const response=await purchaseRequestApi[method](row.objectId);if(!response?.success)throw new Error(method==='submit'?resolvePurchaseRequestSubmitFailure(response):method==='approve'?resolvePurchaseRequestActionFailure(response,method):(response?.error?.message||`${title}失败`));ElMessage.success(`${title}成功`);emit('refreshed');return response}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error?.message||`${title}失败`);return null}}
async function runBatchAction(action,rows=[]){const label=action==='submit'?'批量提交':action==='approve'?'批量审批':'批量生成询价准备';try{if(!rows.length)throw new Error('请先选择采购申请');if(action==='convert'){await ElMessageBox.confirm(`确认对已选择的 ${rows.length} 条采购申请执行${label}？`,label,{type:'warning'});const result=createInquiryPreparationsBatch(rows);if(result.outputCount)emit('refreshed');if(result.result==='PASS')ElMessage.success(`${label}成功 ${result.outputCount} 条`);else ElMessage.warning(`${label}完成：成功 ${result.outputCount} 条，失败 ${result.failures.length} 条`);return result}if(!authenticationReady()){emit('authentication-required',{action,requestNos:rows.map(row=>row.requestNo)});throw new Error(resolvePurchaseRequestActionFailure({meta:{status:401}},action))}await ElMessageBox.confirm(`确认对已选择的 ${rows.length} 条采购申请执行${label}？`,label,{type:'warning'});const result=await executePurchaseRequestBatchAction({rows,action,authenticationReady:true,executor:(row,method)=>purchaseRequestApi[method](row.objectId)});if(result.successCount)emit('refreshed');if(result.failureCount){const reasons=result.failures.map(item=>`${item.requestNo}：${item.reason}`).join('；');ElMessage.warning(`${label}完成：成功 ${result.successCount} 条，失败 ${result.failureCount} 条。${reasons}`)}else ElMessage.success(`${label}成功 ${result.successCount} 条`);return result}catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error?.message||`${label}失败`);return null}}
function runAction(code,row){if(code==='close')return transition(row,'close','关闭');const actionContract=resolvePurchaseRequestActionContract(code);if(!actionContract)throw new Error(`PURCHASE_REQUEST_ACTION_CONTRACT_REQUIRED:${code}`);if(code==='submit')return transition(row,'submit','提交');if(code==='approve'){emit('approval-required',{businessObjectId:row.requestNo,objectId:row.objectId});return{result:'NAVIGATE_TO_APPROVAL_RUNTIME'}}if(row.purchaseMode!=='STANDARD'){ElMessage.warning(row.purchaseMode==='AGREED_PRICE'?'既定价格采购审批后应进入既定价格确认，禁止生成询价准备。':'直接采购授权来源不得进入普通询价准备。');return{result:'FAIL',reason:'NON_STANDARD_INQUIRY_FORBIDDEN'}}const existing=findInquiryPreparationBySource(row.requestNo);const result=existing?{result:'PASS',object:existing,created:false,idempotent:true}:createInquiryPreparation(row);if(result.result!=='PASS'){const reason=result.assessment?.reasons?.join('、')||'询价准备生成条件不满足';ElMessage.error(`无法生成询价准备：${reason}`);workflowRow.value=row;workflowMode.value='eligibility';workflowVisible.value=true;return result}inquiryPreparation.value=result.object;workflowRow.value=row;workflowMode.value='preparation';workflowVisible.value=true;ElMessage.success(result.created?'询价准备已生成':'询价准备已存在，可直接查看');return result}
function viewInquiryPreparation(){workflowVisible.value=false;emit('inquiry-preparation-created',inquiryPreparation.value)}
function showWorkflow(row,mode='history'){workflowRow.value=row;workflowMode.value=mode;workflowVisible.value=true}
defineExpose({openCreate,openEdit,openView,runAction,runBatchAction,showWorkflow,configs,snapshotMaterial,preferredSupplierId})
</script>

<style scoped>
.operation-zone{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:14px;padding:14px;border:1px solid #bfdbfe;border-radius:10px;background:#eff6ff}.operation-zone h3{margin:0 0 4px}.operation-zone p{margin:0}.operation-buttons{display:flex;flex-wrap:wrap;gap:8px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 16px}.form-span{grid-column:1/-1}.form-grid :deep(.el-select),.form-grid :deep(.el-date-editor),.form-grid :deep(.el-input-number){width:100%}.detail-heading{display:flex;align-items:center;justify-content:space-between;margin:18px 0 10px}.detail-heading h3{margin:0}.detail-heading span{color:#64748b}.detail-editor{margin-top:16px;padding:16px;border:1px solid #dbe4ee;border-radius:8px;background:#f8fafc}.editor-actions{display:flex;justify-content:flex-end;gap:8px}.approval-facts,.preparation-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:16px}.approval-facts span,.preparation-summary span{padding:12px;background:#f8fafc}.no-write{color:#166534;font-weight:700}
</style>
