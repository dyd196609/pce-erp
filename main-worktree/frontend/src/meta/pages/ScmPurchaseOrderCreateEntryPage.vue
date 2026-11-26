<template>
  <main class="direct-workbench" data-page-code="purchase-order-create" data-purchase-mode="DIRECT">
    <header class="page-heading">
      <div><h1>直接采购工作台</h1><p>DIRECT（直接采购）从当前有效 SupplierMaterialPrice（供应商物料价格）选择采购对象，一次录入形成来源申请与统一采购订单。</p></div>
      <PceBusinessStatus status-code="DIRECT" status-label="直接采购" source="server" />
    </header>
    <el-alert v-if="!authorization.allowed" :title="authorization.reason || '正在校验直接采购授权'"
      type="error" :closable="false" show-icon data-acceptance-id="direct-purchase-authorization-denied" />
    <template v-else>
      <section class="panel" data-acceptance-id="direct-purchase-header">
        <div class="section-title"><strong>01 选择供应商</strong><span>采购方式：DIRECT（直接采购，只读）</span></div>
        <div class="grid three">
          <el-form-item label="采购方式"><el-input model-value="直接采购" readonly /></el-form-item>
          <el-form-item label="供应商" required><el-select v-model="form.supplierId" filterable
            data-acceptance-id="direct-supplier-select" @change="supplierChanged">
            <el-option v-for="row in suppliers" :key="row.id" :label="`${row.code} / ${row.name}`" :value="row.id" />
          </el-select></el-form-item>
          <el-form-item label="采购日期" required><el-date-picker v-model="form.orderDate" type="date" value-format="YYYY-MM-DD" @change="invalidateGate" /></el-form-item>
          <el-form-item label="采购员" required><el-select v-model="form.buyerEmployeeId" filterable placeholder="请选择正式人员档案中的采购员" @change="invalidateGate">
            <el-option v-for="row in buyers" :key="row.id" :value="row.id" :label="`${row.employee_no} / ${row.full_name} / ${row.position}`" />
          </el-select></el-form-item>
          <el-form-item label="交付地址"><el-input v-model="form.deliveryAddress" @input="invalidateGate" /></el-form-item>
          <el-form-item label="正式价格对象"><el-input :model-value="`${currentPrices.length} 条 CURRENT（当前适用）`" readonly /></el-form-item>
        </div>
        <el-form-item label="订单备注"><el-input v-model="form.remark" type="textarea" :rows="2" @input="invalidateGate" /></el-form-item>
        <el-alert v-if="form.supplierId && priceLoaded && !currentPrices.length"
          title="当前供应商暂无 CURRENT 正式价格；仍可添加物料明细，缺价行将由 PurchaseOrderGate 明确阻断。"
          type="warning" :closable="false" show-icon />
      </section>

      <section class="panel" data-acceptance-id="direct-purchase-lines">
        <div class="section-title"><div><strong>02 选择正式采购价格对象</strong>
          <p>每行只选择一次价格记录；供应商、物料和执行价格均由该正式记录确定。</p></div>
          <el-button type="primary" :disabled="!form.supplierId"
            data-process-action="ADD_DIRECT_PURCHASE_LINE" @click="addLine">添加采购明细</el-button></div>
        <el-table :data="lines" border row-key="rowKey">
          <el-table-column type="index" label="序号" width="65" fixed="left" />
          <el-table-column label="物料" min-width="250">
            <template #default="{row}"><el-select v-model="row.materialId" filterable placeholder="请选择正式物料主档"
              :data-acceptance-id="`direct-line-${row.rowKey}-material`" @change="materialChanged(row)">
              <el-option v-for="material in materials" :key="material.id" :value="material.id"
                :disabled="selectedMaterialByOtherLine(material.id,row)" :label="`${material.code} / ${material.name}`" />
            </el-select></template>
          </el-table-column>
          <el-table-column label="SupplierMaterialPrice（供应商物料价格）" min-width="420">
            <template #default="{row}"><el-select v-model="row.priceId" filterable
              :disabled="!row.materialId" no-data-text="暂无有效正式价格" @change="priceChanged(row)">
              <el-option v-for="price in priceCandidates(row)" :key="price.sourceId" :value="price.sourceId"
                :disabled="selectedByOtherLine(price.sourceId,row)"
                :label="`${price.priceNo} | ${price.materialCode} / ${price.materialName} | ${price.specification} / ${price.unit} | ${price.unitPrice} ${price.currency} | 税率${price.taxRate}% | ${price.effectiveDate}~${price.expiryDate||'长期'} | ${price.versionStatusLabel}`" />
            </el-select><div v-if="row.materialId && !priceCandidates(row).length" class="missing-price"
              :data-acceptance-id="`direct-line-${row.rowKey}-missing-price`">暂无有效正式价格</div></template>
          </el-table-column>
          <el-table-column label="规格 / 单位" min-width="170"><template #default="{row}">{{ specificationText(row) }}</template></el-table-column>
          <el-table-column label="数量" width="145"><template #default="{row}"><el-input-number v-model="row.quantity" :min="0.01" :precision="2" @input="invalidateGate" @change="invalidateGate" /></template></el-table-column>
          <el-table-column label="含税单价" width="125"><template #default="{row}">{{ selectedPrice(row)?.unitPrice || '-' }}</template></el-table-column>
          <el-table-column label="税率" width="90"><template #default="{row}">{{ selectedPrice(row)?.taxRate ?? '-' }}%</template></el-table-column>
          <el-table-column label="币种" width="80"><template #default="{row}">{{ selectedPrice(row)?.currency || '-' }}</template></el-table-column>
          <el-table-column label="价格来源" min-width="150"><template #default="{row}">{{ selectedPrice(row)?.sourceTypeLabel || '-' }}</template></el-table-column>
          <el-table-column label="计划到货日期" width="180"><template #default="{row}"><el-date-picker v-model="row.expectedDate" type="date" value-format="YYYY-MM-DD" @change="invalidateGate" /></template></el-table-column>
          <el-table-column label="明细备注" min-width="170"><template #default="{row}"><el-input v-model="row.remark" @input="invalidateGate" /></template></el-table-column>
          <el-table-column label="行金额" width="125"><template #default="{row}">{{ lineAmount(row) }}</template></el-table-column>
          <el-table-column label="操作" width="80" fixed="right"><template #default="{row}"><el-button type="danger" link @click="removeLine(row)">删除</el-button></template></el-table-column>
        </el-table>
      </section>

      <section class="panel" data-acceptance-id="direct-purchase-preview">
        <div class="section-title"><strong>03 订单预览</strong><span>{{ lines.length }} 条明细</span></div>
        <el-descriptions :column="4" border><el-descriptions-item label="采购方式">DIRECT（直接采购）</el-descriptions-item>
          <el-descriptions-item label="供应商">{{ supplierText }}</el-descriptions-item><el-descriptions-item label="订单总数量">{{ totalQuantity }}</el-descriptions-item>
          <el-descriptions-item label="订单总金额">{{ totalAmount }} {{ currencyText }}</el-descriptions-item></el-descriptions>
        <el-table :data="previewLines" border><el-table-column prop="lineNo" label="行" width="60" />
          <el-table-column prop="material" label="物料" /><el-table-column prop="quantity" label="数量" width="90" />
          <el-table-column prop="priceNo" label="价格记录编号" min-width="260" /><el-table-column prop="taxRate" label="税率" width="80" />
          <el-table-column prop="arrival" label="计划到货日期" width="130" /><el-table-column prop="amount" label="金额" width="120" /></el-table>
      </section>

      <section class="panel" data-acceptance-id="direct-purchase-gate">
        <div class="section-title"><strong>04 PurchaseOrderGate（采购订单准入门禁）</strong><div class="status-pair"><PceBusinessStatus :status-code="effectiveGateStatus" :status-label="gateStatusLabel" source="runtime" /><PceBusinessStatus :status-code="createState" :status-label="businessStatusLabel" source="runtime" /></div></div>
        <el-alert :title="stateMessage" :type="stateAlertType" :closable="false" show-icon
          data-acceptance-id="direct-create-state" :data-create-state="createState" />
        <el-alert v-if="gateError" :title="gateError" type="error" :closable="false" show-icon />
        <el-button v-if="missingPriceLines.length && manualPriceAuthorized" plain type="primary"
          data-process-action="MAINTAIN_SUPPLIER_MATERIAL_PRICE" @click="router.push('/foundation/erp/supplier-material-prices')">维护供应商物料价格</el-button>
        <el-alert v-if="createError" :title="createError" type="error" :closable="false" show-icon data-acceptance-id="direct-create-error" />
        <el-table v-if="gateChecks.length" :data="gateChecks" border><el-table-column prop="checkName" label="检查项目" width="220" />
          <el-table-column prop="currentValue" label="当前值" min-width="260" /><el-table-column prop="result" label="结果" width="90" />
          <el-table-column prop="reason" label="中文说明" min-width="360" /></el-table>
        <div class="gate-action-bar" data-acceptance-id="direct-bottom-action-bar">
          <div class="action-cell action-left"><el-button type="primary" :loading="inspecting" :disabled="!canInspect"
            data-process-action="INSPECT_DIRECT_PURCHASE_GATE" @click="inspectGate">执行 Gate 准入检查</el-button></div>
          <PcePurchaseOrderHumanConfirmation v-model="humanConfirmed" :disabled="effectiveGateStatus!=='PASS'||creating"
            acceptance-id="direct-human-confirmation-card" checkbox-acceptance-id="direct-human-confirmation"
            confirmation-text="我已核对供应商、全部价格记录、数量和计划到货日期" @change="humanConfirmationChanged" />
          <div class="action-cell action-right"><el-button type="success" :loading="creating" :disabled="!canCreate"
            data-process-action="CREATE_DIRECT_PURCHASE_ORDER" data-acceptance-id="direct-create-button"
            :data-create-state="createState" @click="createOrder">{{ creating ? '正在创建采购订单……' : '创建直接采购订单' }}</el-button></div>
        </div>
        <p class="reason">{{ blockingReason }}</p>
      </section>
      <section v-if="createdOrder" class="panel" data-acceptance-id="direct-purchase-success">
        <el-result icon="success" title="直接采购订单创建成功"
          :sub-title="`${createdOrder.objectNo}，共 ${createdOrder.itemCount} 条明细；来源采购申请 ${createdOrder.sourcePurchaseRequestNo||'已生成'}`">
          <template #extra><el-button type="primary" @click="router.push(`/scm/purchase-order/${createdOrder.objectId}`)">进入正式采购订单详情</el-button></template>
        </el-result>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed,onMounted,reactive,ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PcePurchaseOrderHumanConfirmation from '@/meta/components/PcePurchaseOrderHumanConfirmation.vue'
import { createPurchaseOrderFromGateRequest,getActivePurchaseOrderBuyers,getActivePurchaseOrderMaterials,getActivePurchaseOrderSuppliers,inspectPurchaseOrderGateCreation,preparePurchaseOrderGateCreation } from '@/api/scmStandardPageFacts.js'
import { loadSupplierMaterialPrices } from '@/meta/providers/supplierMaterialPriceRuntimeProvider.js'

const router=useRouter(),today=new Date().toISOString().slice(0,10),future=()=>new Date(Date.now()+7*86400000).toISOString().slice(0,10)
const authorization=ref({allowed:false,reason:'正在校验直接采购授权…'}),csrfToken=ref(''),suppliers=ref([]),buyers=ref([]),materials=ref([]),priceCatalog=ref([]),priceLoaded=ref(false),lines=ref([]),sequence=ref(0)
const form=reactive({supplierId:null,orderDate:today,buyerEmployeeId:null,deliveryAddress:'',remark:''})
const gateStatus=ref('WAITING'),gateChecks=ref([]),gateError=ref(''),createError=ref(''),admissionToken=ref(''),humanConfirmed=ref(false),inspecting=ref(false),creating=ref(false),createdOrder=ref(null),idempotencyKey=ref('')
const selectedSupplier=computed(()=>suppliers.value.find(row=>String(row.id)===String(form.supplierId))||null)
const supplierText=computed(()=>selectedSupplier.value?`${selectedSupplier.value.code} / ${selectedSupplier.value.name}`:'-')
const currentPrices=computed(()=>priceCatalog.value.filter(row=>row.isCurrentApplicable===true))
const missingPriceLines=computed(()=>lines.value.filter(row=>row.materialId&&!priceCandidates(row).length))
const missingPriceMessage=computed(()=>`暂无有效正式价格：${missingPriceLines.value.map((row,index)=>`第${lines.value.indexOf(row)+1}行 ${materialText(row)}`).join('；')}。PurchaseOrderGate 已阻断。`)
const effectiveGateStatus=computed(()=>missingPriceLines.value.length?'BLOCKED':gateStatus.value)
const manualPriceAuthorized=computed(()=>authorization.value.allowed===true)
const gateStatusLabel=computed(()=>({WAITING:'待执行准入检查',PASS:'准入检查通过',BLOCKED:'准入检查未通过'}[effectiveGateStatus.value]))
const validLines=computed(()=>lines.value.length>0&&lines.value.every(row=>selectedPrice(row)&&Number(row.quantity)>0&&row.expectedDate))
const orderComplete=computed(()=>Boolean(authorization.value.allowed&&selectedSupplier.value&&form.orderDate&&form.buyerEmployeeId&&validLines.value))
const canInspect=computed(()=>orderComplete.value&&!createdOrder.value&&!inspecting.value&&!creating.value)
const canCreate=computed(()=>canInspect.value&&effectiveGateStatus.value==='PASS'&&Boolean(admissionToken.value)&&humanConfirmed.value&&!creating.value)
const createState=computed(()=>{if(createdOrder.value)return'CREATED';if(creating.value)return'CREATING';if(createError.value)return'CREATE_FAILED';if(missingPriceLines.value.length)return'GATE_FAILED';if(!orderComplete.value)return'ORDER_INCOMPLETE';if(gateStatus.value==='BLOCKED')return'GATE_FAILED';if(gateStatus.value!=='PASS'||!admissionToken.value)return'GATE_REQUIRED';if(!humanConfirmed.value)return'HUMAN_CONFIRMATION_REQUIRED';return'READY_TO_CREATE'})
const stateMessage=computed(()=>missingPriceLines.value.length?missingPriceMessage.value:({ORDER_INCOMPLETE:'请先完成订单信息。',GATE_REQUIRED:'请先执行采购订单准入检查。',GATE_FAILED:gateError.value||'采购订单准入检查未通过。',HUMAN_CONFIRMATION_REQUIRED:'准入检查已通过，请勾选人工确认。',READY_TO_CREATE:'准入检查和人工确认均已完成，可以创建采购订单。',CREATING:'正在创建采购订单……',CREATE_FAILED:'创建失败，请核对服务端错误后重试。',CREATED:`采购订单 ${createdOrder.value?.objectNo||''} 已创建。`}[createState.value]))
const stateAlertType=computed(()=>({ORDER_INCOMPLETE:'warning',GATE_REQUIRED:'info',GATE_FAILED:'error',HUMAN_CONFIRMATION_REQUIRED:'warning',READY_TO_CREATE:'success',CREATING:'info',CREATE_FAILED:'error',CREATED:'success'}[createState.value]))
const businessStatusLabel=computed(()=>({ORDER_INCOMPLETE:'待准入检查',GATE_REQUIRED:'待准入检查',GATE_FAILED:'准入阻断',HUMAN_CONFIRMATION_REQUIRED:'待人工确认',READY_TO_CREATE:'可以创建采购订单',CREATING:'正在创建采购订单',CREATE_FAILED:'采购订单创建失败',CREATED:'采购订单已创建'}[createState.value]))
function selectedPrice(row){return priceCatalog.value.find(price=>String(price.sourceId)===String(row.priceId))||null}
function selectedMaterial(row){return materials.value.find(material=>String(material.id)===String(row.materialId))||null}
function materialText(row){const material=selectedMaterial(row);return material?`${material.code} / ${material.name}`:'-'}
function specificationText(row){const material=selectedMaterial(row);return material?`${material.specification||'-'} / ${material.unit||'-'}`:'-'}
function priceCandidates(row){return currentPrices.value.filter(price=>String(price.materialId)===String(row.materialId))}
function selectedMaterialByOtherLine(materialId,row){return lines.value.some(item=>item!==row&&String(item.materialId)===String(materialId))}
function selectedByOtherLine(priceId,row){return lines.value.some(item=>item!==row&&String(item.priceId)===String(priceId))}
function scaled(value,scale=4){const[a='0',b='']=String(value||0).split('.');return BigInt(a||0)*10n**BigInt(scale)+BigInt((b+'0'.repeat(scale)).slice(0,scale)||0)}
function cents(row){const price=selectedPrice(row);return price&&Number(row.quantity)>0?(scaled(row.quantity)*scaled(price.unitPrice)+500000n)/1000000n:0n}
function money(value){return`${value/100n}.${String(value%100n).padStart(2,'0')}`}
function lineAmount(row){return money(cents(row))}
const totalAmount=computed(()=>money(lines.value.reduce((sum,row)=>sum+cents(row),0n)))
const totalQuantity=computed(()=>lines.value.reduce((sum,row)=>sum+Number(row.quantity||0),0))
const currencyText=computed(()=>[...new Set(lines.value.map(row=>selectedPrice(row)?.currency).filter(Boolean))].join('/')||'-')
const previewLines=computed(()=>lines.value.map((row,index)=>({lineNo:index+1,material:materialText(row),quantity:row.quantity,
  priceNo:selectedPrice(row)?.priceNo||'-',taxRate:selectedPrice(row)?`${selectedPrice(row).taxRate}%`:'-',arrival:row.expectedDate,amount:lineAmount(row)})))
function newKey(){return`PO-DIRECT-R2-${Date.now()}-${globalThis.crypto?.randomUUID?.()||Math.random().toString(36).slice(2)}`}
function invalidateGate(){const wasChecked=gateStatus.value==='PASS'||gateStatus.value==='BLOCKED'||Boolean(admissionToken.value);gateStatus.value='WAITING';gateChecks.value=[];gateError.value=wasChecked?'订单信息已变更，请重新执行 Gate 准入检查。':'';createError.value='';admissionToken.value='';humanConfirmed.value=false}
function humanConfirmationChanged(value){createError.value='';humanConfirmed.value=value===true}
function addLine(){lines.value.push({rowKey:++sequence.value,materialId:null,priceId:null,quantity:1,expectedDate:future(),remark:''});invalidateGate()}
function removeLine(row){lines.value=lines.value.filter(value=>value.rowKey!==row.rowKey);invalidateGate()}
function priceChanged(){invalidateGate()}
function materialChanged(row){row.priceId=null;invalidateGate()}
async function supplierChanged(){form.deliveryAddress=selectedSupplier.value?.delivery_address||'';lines.value=[];priceCatalog.value=[];priceLoaded.value=false;invalidateGate()
  if(!selectedSupplier.value)return;try{const runtime=await loadSupplierMaterialPrices({supplierCode:selectedSupplier.value.code});priceCatalog.value=[...runtime.rows];priceLoaded.value=true;addLine()}
  catch(error){priceLoaded.value=true;gateError.value=error.message||String(error)}}
function payload(){return{creationMode:'DIRECT_SELECTION',purchaseMode:'DIRECT',idempotencyKey:idempotencyKey.value,supplierId:form.supplierId,
  orderDate:form.orderDate,buyerEmployeeId:form.buyerEmployeeId,deliveryAddress:form.deliveryAddress,remark:form.remark,
  items:lines.value.map((row,index)=>{const price=selectedPrice(row);return{lineNo:index+1,materialId:row.materialId||'',quantity:String(row.quantity||''),
    supplierMaterialPriceId:price?.sourceId||'',supplierMaterialPriceNo:price?.priceNo||'',expectedDate:row.expectedDate,remark:row.remark}})}}
async function inspectGate(){if(!canInspect.value)return;inspecting.value=true;invalidateGate();try{const response=await inspectPurchaseOrderGateCreation(payload(),csrfToken.value)
  if(!response?.success||response.data?.gateStatus!=='PASS')throw new Error(response?.error?.message||'准入检查未通过');gateChecks.value=response.data.checks||[];admissionToken.value=response.data.admissionToken||'';gateStatus.value=admissionToken.value?'PASS':'BLOCKED';ElMessage.success('全部正式价格对象和订单明细准入通过。')}
  catch(error){gateStatus.value='BLOCKED';gateError.value=error.message||String(error)}finally{inspecting.value=false}}
async function createOrder(){if(!canCreate.value){ElMessage.warning(stateMessage.value);return}creating.value=true;createError.value='';try{const response=await createPurchaseOrderFromGateRequest({...payload(),admissionToken:admissionToken.value,humanConfirmed:humanConfirmed.value},csrfToken.value)
  if(!response?.success)throw new Error(response?.error?.message||'采购订单未创建');createdOrder.value=response.data;ElMessage.success(`采购订单 ${response.data.objectNo} 已正式创建`);await router.push(`/scm/purchase-order/${response.data.objectId}`)}
  catch(error){createError.value=error.message||String(error);ElMessage.error(createError.value)}finally{creating.value=false}}
const blockingReason=computed(()=>stateMessage.value)
onMounted(async()=>{idempotencyKey.value=newKey()
  try{const prep=await preparePurchaseOrderGateCreation();authorization.value=prep?.data?.authorization||{allowed:false,reason:'授权事实缺失'};csrfToken.value=prep?.data?.csrfToken||'';if(!authorization.value.allowed)return
    const [supplierResponse,buyerResponse,materialResponse]=await Promise.all([getActivePurchaseOrderSuppliers(),getActivePurchaseOrderBuyers(),getActivePurchaseOrderMaterials()]);const data=supplierResponse?.data||{};suppliers.value=(data.results||data||[]).filter(row=>row.is_active!==false);const buyerData=buyerResponse?.data||{};buyers.value=(buyerData.results||buyerData||[]).filter(row=>row.status==='active'&&String(row.position||'').includes('采购'));const materialData=materialResponse?.data||{};materials.value=(materialData.results||materialData||[]).filter(row=>row.is_active!==false&&row.is_purchased!==false)}
  catch(error){authorization.value={allowed:false,reason:error.message||String(error)}}})
</script>

<style scoped>
.direct-workbench{display:grid;gap:18px;padding:20px;min-width:0}.page-heading,.section-title{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:4px 0}.page-heading p,.section-title p,.section-title span,.reason,small{color:#64748b}.panel{display:grid;gap:16px;padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff;min-width:0}.grid{display:grid;gap:14px}.grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.grid :deep(.el-select),.grid :deep(.el-date-editor){width:100%}.status-pair{display:flex;gap:10px}.gate-action-bar{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,600px) minmax(0,1fr);gap:12px;align-items:end}.action-cell{display:flex;align-items:flex-end}.action-right{justify-content:flex-end}.action-cell :deep(.el-button){width:100%;min-height:40px;white-space:normal}.reason{text-align:right;margin:0}@media(max-width:900px){.page-heading,.section-title{align-items:flex-start;flex-direction:column}.grid.three,.gate-action-bar{grid-template-columns:1fr}.action-right{justify-content:flex-start}}
.missing-price{margin-top:6px;color:#dc2626;font-size:13px}
</style>
