<template>
  <main class="confirmation-page" data-page-code="agreed-price-purchase-confirmation" data-purchase-mode="AGREED_PRICE">
    <header class="page-heading">
      <div><h1>既定价格采购确认</h1><p>来源采购申请：<strong>{{ requestFact?.requestNo || '-' }}</strong>。本页只确认正式价格，不重新录入物料、数量或需求日期。</p></div>
      <PceBusinessStatus status-code="AGREED_PRICE" status-label="既定价格采购" source="server" />
    </header>
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <template v-if="requestFact">
      <section class="panel" data-acceptance-id="agreed-price-source-request">
        <div class="section-title"><strong>01 原采购申请（只读）</strong><PceBusinessStatus :status-code="requestFact.businessLifecycleStatus" :status-label="requestFact.businessLifecycleStatusLabel" source="server" /></div>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="采购申请编号">{{ requestFact.requestNo }}</el-descriptions-item>
          <el-descriptions-item label="申请日期">{{ requestFact.requestDate }}</el-descriptions-item>
          <el-descriptions-item label="申请人">{{ requestFact.requester }}</el-descriptions-item>
          <el-descriptions-item label="申请部门">{{ requestFact.department }}</el-descriptions-item>
          <el-descriptions-item label="采购部门">{{ requestFact.purchaseDepartment }}</el-descriptions-item>
          <el-descriptions-item label="使用部门">{{ requestFact.usageDepartment }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ requestFact.projectCode }} / {{ requestFact.projectName }}</el-descriptions-item>
          <el-descriptions-item label="需求日期">{{ requestFact.requiredDate }}</el-descriptions-item>
          <el-descriptions-item label="申请原因" :span="2">{{ requestFact.applicationReason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购用途" :span="2">{{ requestFact.purchasePurpose || '-' }}</el-descriptions-item>
          <el-descriptions-item label="交付要求" :span="2">{{ requestFact.deliveryRequirements || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ requestFact.noteDescription || '-' }}</el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="panel" data-acceptance-id="agreed-price-inherited-items">
        <div class="section-title"><div><strong>02 继承申请明细并确认 SupplierMaterialPrice（供应商物料价格）</strong><p>每行必须由用户明确选择一条 CURRENT（当前适用）正式价格。</p></div><span>{{ lines.length }} 条申请明细</span></div>
        <el-form-item label="采购员" required><el-select v-model="buyerEmployeeId" filterable placeholder="请选择正式人员档案中的采购员" @change="invalidateGate('采购员已变更，请重新执行 Gate 准入检查。')"><el-option v-for="row in buyers" :key="row.id" :value="row.id" :label="`${row.employee_no} / ${row.full_name} / ${row.position}`" /></el-select></el-form-item>
        <el-table :data="lines" border row-key="purchaseRequestItemId">
          <el-table-column prop="lineNo" label="序号" width="65" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" width="145" fixed="left" />
          <el-table-column prop="materialName" label="物料名称" min-width="180" />
          <el-table-column prop="specification" label="规格型号" min-width="150" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="quantity" label="申请数量（只读）" width="140" />
          <el-table-column prop="requiredDate" label="计划到货日期（继承）" width="170" />
          <el-table-column label="正式价格记录" min-width="480">
            <template #default="{ row }"><el-select v-model="row.priceId" filterable no-data-text="暂无有效正式价格"
              :data-acceptance-id="`agreed-price-select-${row.lineNo}`" @change="priceChanged">
              <el-option v-for="price in candidates(row)" :key="price.sourceId" :value="price.sourceId"
                :label="`${price.priceNo} | ${price.supplierCode} / ${price.supplierName} | ${price.unitPrice} ${price.currency} | 税率${price.taxRate}% | ${price.effectiveDate}~${price.expiryDate||'长期'} | ${price.versionStatusLabel}`" />
            </el-select></template>
          </el-table-column>
          <el-table-column label="供应商" min-width="210"><template #default="{row}">{{ selectedPrice(row)?.supplierCode || '-' }} / {{ selectedPrice(row)?.supplierName || '-' }}</template></el-table-column>
          <el-table-column label="执行单价" width="115"><template #default="{row}">{{ selectedPrice(row)?.unitPrice || '-' }}</template></el-table-column>
          <el-table-column label="币种" width="80"><template #default="{row}">{{ selectedPrice(row)?.currency || '-' }}</template></el-table-column>
          <el-table-column label="税率" width="85"><template #default="{row}">{{ selectedPrice(row)?.taxRate ?? '-' }}%</template></el-table-column>
          <el-table-column label="SupplierMaterialPrice ID" min-width="210"><template #default="{row}">{{ selectedPrice(row)?.sourceId || '-' }}</template></el-table-column>
          <el-table-column label="价格来源" width="130"><template #default="{row}">{{ selectedPrice(row)?.sourceTypeLabel || '-' }}</template></el-table-column>
        </el-table>
        <el-alert v-if="missingPriceLines.length" :title="missingPriceMessage" type="error" :closable="false" show-icon data-acceptance-id="agreed-price-missing-price-lines" />
      </section>

      <section class="panel" data-acceptance-id="agreed-price-gate">
        <div class="section-title"><strong>03 PurchaseOrderGate（采购订单准入门禁）</strong><PceBusinessStatus :status-code="effectiveGateStatus" :status-label="gateStatusLabel" source="runtime" /></div>
        <el-alert :title="stateMessage" :type="stateAlertType" :closable="false" show-icon data-acceptance-id="agreed-price-state" />
        <el-alert v-if="gateError" :title="gateError" type="error" :closable="false" show-icon />
        <el-table v-if="gateChecks.length" :data="gateChecks" border><el-table-column prop="checkName" label="检查项目" width="220" /><el-table-column prop="currentValue" label="当前值" min-width="240" /><el-table-column prop="result" label="结果" width="90" /><el-table-column prop="reason" label="中文说明" min-width="380" /></el-table>
        <div class="closure-actions">
          <el-button type="primary" :loading="inspecting" :disabled="!canInspect" data-process-action="INSPECT_AGREED_PRICE_GATE" @click="inspectGate">执行 Gate 准入检查</el-button>
          <PcePurchaseOrderHumanConfirmation v-model="humanConfirmed" :disabled="gateStatus!=='PASS'||creating" acceptance-id="agreed-price-human-confirmation-card" checkbox-acceptance-id="agreed-price-human-confirmation" confirmation-text="我已核对供应商、价格记录、采购数量和计划到货日期" />
          <el-button type="success" :loading="creating" :disabled="!canCreate" data-process-action="CREATE_AGREED_PRICE_PURCHASE_ORDERS" data-acceptance-id="agreed-price-create-button" @click="createOrders">创建既定价格采购订单</el-button>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed,onMounted,ref } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PcePurchaseOrderHumanConfirmation from '@/meta/components/PcePurchaseOrderHumanConfirmation.vue'
import { getActivePurchaseOrderBuyers } from '@/api/scmStandardPageFacts.js'
import { createAgreedPricePurchaseOrders,getScmStandardPageFacts,inspectAgreedPricePurchaseOrder,preparePurchaseOrderGateCreation } from '@/api/scmStandardPageFacts.js'
import { loadSupplierMaterialPriceRuntime } from '@/meta/providers/supplierMaterialPriceRuntimeProvider.js'

const route=useRoute(),router=useRouter(),requestFact=ref(null),priceCatalog=ref([]),lines=ref([]),buyers=ref([]),buyerEmployeeId=ref(null),loadError=ref(''),csrfToken=ref('')
const gateStatus=ref('WAITING'),gateChecks=ref([]),gateError=ref(''),admissionToken=ref(''),humanConfirmed=ref(false),inspecting=ref(false),creating=ref(false),createdOrders=ref([]),idempotencyKey=ref('')
const today=new Date().toISOString().slice(0,10)
const allSelected=computed(()=>lines.value.length>0&&lines.value.every(row=>selectedPrice(row)))
const missingPriceLines=computed(()=>lines.value.filter(row=>candidates(row).length===0))
const missingPriceMessage=computed(()=>`暂无有效正式价格：${missingPriceLines.value.map(row=>`第${row.lineNo}行 ${row.materialCode} / ${row.materialName}`).join('；')}。PurchaseOrderGate 已阻断，请先维护 SupplierMaterialPrice。`)
const effectiveGateStatus=computed(()=>missingPriceLines.value.length?'BLOCKED':gateStatus.value)
const canInspect=computed(()=>allSelected.value&&Boolean(buyerEmployeeId.value)&&!inspecting.value&&!creating.value&&!createdOrders.value.length)
const canCreate=computed(()=>canInspect.value&&gateStatus.value==='PASS'&&Boolean(admissionToken.value)&&humanConfirmed.value)
const gateStatusLabel=computed(()=>({WAITING:'待执行准入检查',PASS:'准入检查通过',BLOCKED:'准入检查未通过'}[effectiveGateStatus.value]))
const stateMessage=computed(()=>createdOrders.value.length?`已创建 ${createdOrders.value.length} 张正式采购订单。`:missingPriceLines.value.length?missingPriceMessage.value:!allSelected.value?'请为每条采购申请明细明确选择正式价格。':gateStatus.value==='BLOCKED'?(gateError.value||'准入检查未通过。'):gateStatus.value!=='PASS'?'请执行采购订单准入检查。':!humanConfirmed.value?'准入检查已经通过，请完成人工确认。':'可以创建既定价格采购订单。')
const stateAlertType=computed(()=>createdOrders.value.length?'success':effectiveGateStatus.value==='BLOCKED'?'error':gateStatus.value==='PASS'&&humanConfirmed.value?'success':'warning')
function candidates(row){return priceCatalog.value.filter(price=>String(price.materialId)===String(row.materialId)&&price.isCurrentApplicable===true&&price.materialSupplierRelationValid===true)}
function selectedPrice(row){return priceCatalog.value.find(price=>String(price.sourceId)===String(row.priceId))||null}
function invalidateGate(message='价格选择已变更，请重新执行 Gate 准入检查。'){const active=gateStatus.value!=='WAITING'||Boolean(admissionToken.value);gateStatus.value='WAITING';gateChecks.value=[];gateError.value=active?message:'';admissionToken.value='';humanConfirmed.value=false}
function priceChanged(){invalidateGate()}
function payload(){return{creationMode:'AGREED_PRICE_CONFIRMATION',purchaseMode:'AGREED_PRICE',purchaseRequestId:requestFact.value.objectId,idempotencyKey:idempotencyKey.value,orderDate:today,buyerEmployeeId:buyerEmployeeId.value,items:lines.value.map(row=>{const price=selectedPrice(row);return{purchaseRequestItemId:row.purchaseRequestItemId,supplierMaterialPriceId:price?.sourceId||'',supplierMaterialPriceNo:price?.priceNo||''}})}}
async function inspectGate(){if(!canInspect.value)return;inspecting.value=true;invalidateGate('');try{const response=await inspectAgreedPricePurchaseOrder(payload(),csrfToken.value);if(!response?.success||response.data?.gateStatus!=='PASS')throw new Error(response?.error?.message||'准入检查未通过');gateChecks.value=response.data.checks||[];admissionToken.value=response.data.admissionToken||'';gateStatus.value=admissionToken.value?'PASS':'BLOCKED';ElMessage.success('既定价格采购准入检查通过。')}catch(error){gateStatus.value='BLOCKED';gateError.value=error.message||String(error)}finally{inspecting.value=false}}
async function createOrders(){if(!canCreate.value)return;creating.value=true;gateError.value='';try{const response=await createAgreedPricePurchaseOrders({...payload(),admissionToken:admissionToken.value,humanConfirmed:true},csrfToken.value);if(!response?.success)throw new Error(response?.error?.message||'采购订单未创建');createdOrders.value=response.data.purchaseOrders||[];ElMessage.success(`已按供应商创建 ${createdOrders.value.length} 张正式采购订单`);if(createdOrders.value[0])await router.push(`/scm/purchase-order/${createdOrders.value[0].objectId}`)}catch(error){gateError.value=error.message||String(error);ElMessage.error(gateError.value)}finally{creating.value=false}}
onMounted(async()=>{idempotencyKey.value=`PO-AGREED-R5-${route.params.id}-${globalThis.crypto?.randomUUID?.()||Date.now()}`;try{const [facts,prices,prep,buyerResponse]=await Promise.all([getScmStandardPageFacts('purchase-request'),loadSupplierMaterialPriceRuntime({force:true}),preparePurchaseOrderGateCreation(),getActivePurchaseOrderBuyers()]);const buyerData=buyerResponse?.data||{};buyers.value=(buyerData.results||buyerData||[]).filter(row=>row.status==='active'&&String(row.position||'').includes('采购'));requestFact.value=(facts?.data?.objects||[]).find(row=>String(row.objectId)===String(route.params.id))||null;if(!requestFact.value)throw new Error('未找到来源采购申请。');if(requestFact.value.purchaseMode!=='AGREED_PRICE')throw new Error('来源采购申请不是既定价格采购。');if(requestFact.value.businessLifecycleStatus!=='waiting_agreed_price_confirmation')throw new Error(`当前申请状态为“${requestFact.value.businessLifecycleStatusLabel}”，不能再次确认价格。`);lines.value=(requestFact.value.items||[]).map(row=>({...row,priceId:null}));priceCatalog.value=[...prices.rows];csrfToken.value=prep?.data?.csrfToken||''}catch(error){loadError.value=error.message||String(error)}})
</script>

<style scoped>
.confirmation-page{display:grid;gap:18px;padding:20px;min-width:0}.page-heading,.section-title{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:4px 0}.page-heading p,.section-title p,.section-title span,small{color:#64748b}.panel{display:grid;gap:16px;padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff;min-width:0}.panel :deep(.el-select){width:100%}.closure-actions{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,600px) minmax(0,1fr);gap:12px;align-items:end}.closure-actions>button{width:100%;min-height:40px;white-space:normal}.closure-actions>button:last-child{justify-self:end}@media(max-width:900px){.page-heading,.section-title{align-items:flex-start;flex-direction:column}.closure-actions{grid-template-columns:1fr}.closure-actions>button:last-child{justify-self:start}}
</style>
