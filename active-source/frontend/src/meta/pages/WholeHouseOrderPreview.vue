<template>
  <section class="preview" data-preview-code="WHOLE_HOUSE_ORDER_20231112_6_READ_ONLY" :aria-busy="busy">
    <header class="card"><h2>订单来源核对与办理</h2><p>来源资格、映射与数量确认、草稿建档分别办理；不包含订单审批、需求生成或排程授权。</p>
      <el-button @click="back">返回销售订单</el-button><el-button type="primary" :disabled="!developmentEntry?.target" @click="openDevelopmentContract">开发合同与报价</el-button><el-button @click="navigate('/system-login', {redirect: route.fullPath})">正常登录入口</el-button><el-button :loading="busy" @click="load">重新读取服务端事实</el-button>
      <p v-if="developmentEntry" class="development-entry-context">开发样本：{{ developmentEntry.customerName }} · {{ developmentEntry.projectName }} · {{ developmentEntry.sourceOrderNo }} · {{ developmentEntry.sourceRowCount }}条工程来源</p>
      <p v-else-if="developmentEntryError" class="development-entry-error">开发合同入口暂不可用：{{ developmentEntryError }}</p>
    </header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/>
    <el-alert v-if="notice" :title="notice" type="success" show-icon :closable="false"/>
    <template v-if="preview">
      <section class="card"><h3>{{ preview.order.externalOrderNo }} · {{ preview.order.customerOrDealer }}</h3>
        <p>{{ preview.order.project }}；来源交期 {{ preview.order.deliveryDate }}（保留原日期）</p>
        <p>{{ preview.source.evidenceType }}。37 条工程／排产来源记录，销售行数由商业凭据和逐行映射决定。</p>
        <el-tag type="warning">{{ preview.review.sourceStatusLabel }}</el-tag> <el-tag>{{ preview.review.mappingStatusLabel }}</el-tag>
      </section>
      <section class="card"><h3>分类汇总，不等于已确认销售明细</h3>
        <el-table :data="preview.productGroups" border><el-table-column prop="productName" label="类别"/><el-table-column prop="sourceQuantityField" label="原字段"/><el-table-column prop="quantity" label="精确工程合计"/><el-table-column prop="statusLabel" label="业务含义" min-width="240"/></el-table>
        <p>{{ preview.quantityPrecision.meaning }}</p><p>{{ preview.quantityPrecision.rounding }}；销售数量独立核实，不截断 3.951972。</p>
      </section>
      <section class="card"><h3>主数据解析 · 组织 #{{ preview.databaseResolution.organizationId }}</h3>
        <p>{{ preview.databaseResolution.customerBasis }} 同名候选 {{ preview.databaseResolution.customerExactMatches.length }} 条；交叉映射 {{ preview.databaseResolution.customerExternalMappings.length }} 条。</p>
        <p>{{ preview.databaseResolution.departmentDifference }}</p><p>{{ preview.databaseResolution.productDifference }}</p><p>{{ preview.databaseResolution.unitBasis }}</p>
        <p>已解析类别（只用于分类）：{{ preview.databaseResolution.categories.map(optionLabel).join('；') || '当前组织未命中' }}。</p>
        <el-collapse><el-collapse-item title="查看正式工程引用与产品候选差异" name="masters">
          <p>以下工程编码精确命中仅证明工程对象存在，不自动成为客户购买产品。</p>
          <p v-for="x in preview.databaseResolution.engineeringMaterials" :key="x.sourceCode">{{ x.sourceCode }} → {{ x.matches.map(materialLabel).join('；') || '当前组织未命中' }}；{{ x.unique ? '唯一有效对象' : '尚不唯一' }}；外部映射 #{{ x.externalIdentityIds.join('、') }}。{{ x.basis }}</p>
          <p v-for="x in preview.databaseResolution.routingReferences" :key="x.sourceCode">工艺引用 {{ x.sourceCode }} → {{ x.matches.map(optionLabel).join('；') || '当前组织未命中' }}；{{ x.basis }}</p>
          <p v-for="x in preview.databaseResolution.engineeringProcesses" :key="x.id">工序 #{{ x.id }} {{ x.code }} / {{ x.name }}：驱动字段 {{ x.quantity_driver }}；正式计算单位 #{{ x.calculation_uom_id || '尚未提供' }}（仅工程用途）。</p>
          <p>当前组织产品定义候选 {{ preview.databaseResolution.products.length }} 条；不会因名称相似自动匹配。</p>
        </el-collapse-item></el-collapse>
        <el-form label-position="top"><div class="grid">
          <el-form-item label="正式客户"><el-select v-model="draft.customerId" filterable clearable><el-option v-for="x in preview.databaseResolution.customers" :key="x.id" :value="x.id" :label="optionLabel(x)"/></el-select></el-form-item>
          <el-form-item label="客户匹配凭据／差异说明"><el-input v-model="draft.customerEvidence" placeholder="正式映射编号或商业凭据定位"/></el-form-item>
          <el-form-item label="历史订单销售部门"><el-select v-model="draft.departmentId" clearable filterable><el-option v-for="x in preview.databaseResolution.departments" :key="x.id" :value="x.id" :label="optionLabel(x)"/></el-select></el-form-item>
          <el-form-item label="销售部门归属凭据"><el-input v-model="draft.departmentEvidence" placeholder="不得默认当前用户部门"/></el-form-item>
        </div></el-form>
        <el-button v-for="link in preview.maintenanceLinks" :key="link.path" link type="primary" @click="navigate(link.path)">{{ link.label }}</el-button>
      </section>
      <section class="card"><h3>拟建销售明细（{{ draft.lines.length }} 行草稿，不是已确认事实）</h3>
        <p>每个独立商业凭据行只计数一次。多个工程行仅可引用同产品、配置、空间、单位和交付职责的商业行，并填写合并依据。本版不支持来源行一对多拆分，不以工序数量计算销售数量。</p>
        <el-button @click="addLine">添加有凭据的销售行</el-button>
        <article v-for="(line,i) in draft.lines" :key="line.localKey" class="line-card">
          <h4>销售行 {{ i+1 }} <el-button link type="danger" @click="draft.lines.splice(i,1)">移除此拟建行</el-button></h4>
          <el-form label-position="top"><div class="grid">
            <el-form-item v-for="field in lineFields" :key="field.key" :label="field.label"><el-input v-model="line[field.key]" :placeholder="field.placeholder"/></el-form-item>
            <el-form-item label="正式成品／半成品（候选，不自动选择）"><el-select v-model="line.materialId" filterable clearable><el-option v-for="x in preview.databaseResolution.materials" :key="x.id" :value="x.id" :label="materialLabel(x)"/></el-select></el-form-item>
            <el-form-item label="商业凭据原始数量（十进制文本）"><el-input v-model="line.quantity" placeholder="不得直接复制工程合计"/></el-form-item>
            <el-form-item label="商业凭据正式单位"><el-select v-model="line.quantityUomId" filterable clearable><el-option v-for="x in preview.databaseResolution.units" :key="x.id" :value="x.id" :label="unitLabel(x)"/></el-select></el-form-item>
          </div>
          <el-form-item label="关联来源行（禁止在多条销售行重复引用）"><el-select v-model="line.sourceLineIds" multiple filterable style="width:100%"><el-option v-for="row in preview.sourceLineIdentities" :key="row.salesOrderItemNo" :value="row.salesOrderItemNo" :label="rowLabel(row)"/></el-select></el-form-item>
          </el-form>
        </article>
      </section>
      <el-collapse class="card"><el-collapse-item title="37 条逐行原始证据与拟建行关联" name="rows">
        <el-table :data="preview.sourceLineIdentities" border>
          <el-table-column type="expand"><template #default="{row}"><pre>{{ JSON.stringify(row.rawFields, null, 2) }}</pre><p>正式工程引用：{{ row.engineeringMapping?.matches.map(materialLabel).join('；') || '当前组织未命中' }}</p><p>{{ row.mergeRule }}</p><p>未确定：{{ row.unknowns.join('、') }}</p></template></el-table-column>
          <el-table-column prop="sourceRow" label="源行" width="70"/><el-table-column prop="salesOrderItemNo" label="稳定来源身份" min-width="250"/><el-table-column prop="productType" label="类别" width="80"/>
          <el-table-column prop="quantityField" label="原字段"/><el-table-column prop="rawQuantity" label="原值（完整精度）"/>
          <el-table-column prop="quantityRoleLabel" label="数量职责" min-width="260"/>
          <el-table-column label="拟建销售行（本地草稿）" min-width="180"><template #default="{row}">{{ references(row.salesOrderItemNo) }}</template></el-table-column>
        </el-table>
      </el-collapse-item></el-collapse>
      <section class="card"><h3>服务端数量核对（仅针对已保存映射）</h3>
        <el-table :data="preview.review.checks" border><el-table-column prop="lineNo" label="销售行"/><el-table-column prop="rawCommercialQuantity" label="凭据原量"/><el-table-column prop="businessQuantity" label="精确业务量"/><el-table-column prop="businessUomId" label="正式单位 ID"/><el-table-column prop="conservationStatusLabel" label="守恒核对"/><el-table-column prop="quantityRoleLabel" label="口径" min-width="260"/></el-table>
        <p v-if="dirty">存在未保存修改；请先保存，再重新办理确认。</p>
      </section>
      <section class="card"><h3>待办与合法办理 · {{ preview.review.statusLabel }}</h3>
        <ul><li v-for="block in preview.review.blockers" :key="block.code">{{ block.message }}</li></ul>
        <el-input v-model="evidence" type="textarea" maxlength="300" show-word-limit placeholder="本次办理凭据定位、确认范围与依据（不填写密码或密钥）"/>
        <el-checkbox v-model="confirmed">我确认本次动作范围；来源确认不代替映射确认，建草稿不代替订单审批。</el-checkbox>
        <div v-for="action in preview.actions" :key="action.action" class="action-row"><el-button :disabled="busy || !action.allowed || (dirty && action.action !== 'save-mapping')" @click="act(action.action)">{{ action.label }}</el-button><span>{{ action.reason }}</span></div>
        <p>保存和确认会写入来源审计；只有建档动作调用原订单创建链。须取得对应业务授权后办理。</p>
      </section>
      <section class="card"><h3>分阶段就绪度</h3><p v-for="stage in preview.stageReadiness" :key="stage.label">{{ stage.label }}：{{ stage.statusLabel }} — {{ stage.reason }}</p></section>
      <section class="card"><h3>来源办理审计</h3><p v-if="!preview.review.audits.length">尚无办理记录；真实来源未被代确认。</p><p v-for="audit in preview.review.audits" :key="audit.id">#{{ audit.id }} · {{ audit.actionLabel }} · 用户 #{{ audit.actorId }} · {{ audit.createdAt }} · {{ audit.effective ? '当前有效' : '历史记录（非当前有效确认）' }} · {{ audit.evidence }}</p></section>
      <footer class="card"><p>{{ preview.source.fileName }} / {{ preview.source.sheet }} / {{ preview.source.range }}</p><p>原件历史指纹 {{ preview.source.sha256 }}</p><p>归档指纹 {{ preview.source.archiveSha256 }}</p><p>当前事实指纹 {{ preview.sourceFingerprint }}</p><el-button @click="copyFacts">复制同源服务端诊断</el-button></footer>
    </template>
    <el-skeleton v-else-if="busy" :rows="8" animated/>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { salesApi } from '@/api/sales'
const router = useRouter(), route = useRoute()
const preview = ref(null), draft = ref({lines: []}), error = ref(''), notice = ref(''), busy = ref(false)
const developmentEntry = ref(null), developmentEntryError = ref('')
const evidence = ref(''), confirmed = ref(false), saved = ref('')
const lineFields = [
  {key:'commercialPosition',label:'商业凭据唯一行号',placeholder:'合同编号 / 明细行号（不得重复）'},
  {key:'productIdentity',label:'客户购买产品身份',placeholder:'具体产品，不仅是房门/饰面类别'},
  {key:'configuration',label:'配置／规格',placeholder:'不适用也需说明及依据'},
  {key:'space',label:'空间／房间',placeholder:'不适用也需说明及依据'},
  {key:'deliveryResponsibility',label:'交付职责／范围'},
  {key:'quantityEvidence',label:'商业数量凭据定位'},
  {key:'mappingEvidence',label:'关联／合并凭据',placeholder:'证明同产品、配置、空间、单位及交付职责；工程量仅关联'},
]
const cleanDraft = () => ({...draft.value,lines:draft.value.lines.map(({localKey,...line})=>line)})
const dirty = computed(() => Boolean(preview.value) && JSON.stringify(cleanDraft()) !== saved.value)
const optionLabel = x => '#'+x.id+' · '+(x.code||x.routing_code)+' / '+x.name
const materialLabel = x => optionLabel(x)+' / '+(x.specification||'规格未提供')+' / 基本单位 #'+(x.base_uom_id||'未维护')
const unitLabel = x => optionLabel(x)+' / '+x.decimal_places+' 位'
const rowLabel = x => '源行 '+x.sourceRow+' · '+x.salesOrderItemNo+' · '+x.productType+' · '+x.engineeringSourceCode
function accept(value) {
  preview.value=value; draft.value=structuredClone(value.review.resolution); saved.value=JSON.stringify(draft.value)
  draft.value.lines.forEach(line=>{line.localKey=crypto.randomUUID()})
  if (!draft.value.customerId && value.databaseResolution.resolvedCustomerId) {
    draft.value.customerId=value.databaseResolution.resolvedCustomerId
    draft.value.customerEvidence='同组织唯一客户＋外部映射 '+value.databaseResolution.customerExternalMappings.map(x=>x.id).join(',')
  }
  confirmed.value=false
}
async function load() {
  if(dirty.value && preview.value){try{await ElMessageBox.confirm('重新读取将丢弃未保存映射，是否继续？','重新读取')}catch{return}}
  busy.value=true;error.value=''
  try{
    const [r, entryResponse]=await Promise.all([salesApi.wholeHouseOrderPreview(),salesApi.developmentContractEntry()])
    if(entryResponse.success){developmentEntry.value=entryResponse.data.entry;developmentEntryError.value=''}
    else{developmentEntry.value=null;developmentEntryError.value=entryResponse.error?.message||'服务端未解析到开发样本，不会回退到历史来源。'}
    if(!r.success)throw new Error(r.error?.message||'来源事实读取失败')
    accept(r.data.preview)
  }
  catch(e){error.value=e.message}finally{busy.value=false}
}
function addLine(){draft.value.lines.push({localKey:crypto.randomUUID(),commercialPosition:'',productIdentity:'',configuration:'',space:'',deliveryResponsibility:'',materialId:null,quantity:'',quantityUomId:null,quantityBasis:'COMMERCIAL_DOCUMENT',quantityEvidence:'',mappingEvidence:'',sourceLineIds:[]})}
function references(id){const values=draft.value.lines.flatMap((x,i)=>x.sourceLineIds.includes(id)?[i+1]:[]);return values.length?values.join('、'):'未关联'}
async function act(action){
  error.value='';notice.value='';busy.value=true
  try{
    const payload={binding:preview.value.review.binding,evidence:evidence.value,confirmed:confirmed.value}
    if(action==='save-mapping')payload.resolution=cleanDraft()
    if(action==='create-draft'){
      await ElMessageBox.confirm('将通过原订单服务创建草稿，不自动提交、审批或生成需求。是否继续？','创建销售草稿')
      const key='source-'+preview.value.review.binding.sourceFingerprint+'-'+preview.value.review.binding.revision
      const r=await salesApi.createSourceDraft({...payload,idempotencyKey:key,requestId:crypto.randomUUID()})
      if(!r.success)throw new Error(r.error?.message||'建档失败')
      notice.value='已建立草稿 '+r.data.order.orderNo+'；后续请返回原销售订单。'
      const refresh=await salesApi.wholeHouseOrderPreview();if(refresh.success)accept(refresh.data.preview)
    }else{
      const r=await salesApi.sourceAction(action,payload);if(!r.success)throw new Error(r.error?.message||'办理失败')
      accept(r.data.preview);notice.value='已保存审计并重新读取服务端就绪度。'
    }
  }catch(e){if(e instanceof Error)error.value=e.message}finally{busy.value=false}
}
async function navigate(path,query){if(dirty.value){try{await ElMessageBox.confirm('离开将丢弃未保存映射，是否继续？','离开来源办理')}catch{return}}router.push(query?{path,query}:path)}
function openDevelopmentContract(){const target=developmentEntry.value?.target;if(target)navigate(target.path,target.query)}
function back(){const {mode,...query}=route.query;navigate('/sales/orders',query)}
async function copyFacts(){try{await navigator.clipboard.writeText(JSON.stringify(preview.value.diagnosticFacts,null,2));notice.value='已复制同源服务端诊断。'}catch{error.value='浏览器未允许剪贴板访问。'}}
onMounted(load)
</script>
<style scoped>
.preview{display:grid;gap:16px}.card{padding:20px;border:1px solid #dce4ed;border-radius:12px;background:#fff;overflow:hidden}.card h2,.card h3{margin-top:0}.card p{color:#475569;overflow-wrap:anywhere}.card .development-entry-context{margin:12px 0 0;color:#166534}.card .development-entry-error{margin:12px 0 0;color:#b45309}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.grid .el-select{width:100%}.line-card{padding:16px;margin-top:14px;border:1px solid #cbd5e1;border-radius:8px}.action-row{display:flex;align-items:center;gap:12px;margin-top:12px}.action-row span{color:#64748b}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px}.el-checkbox{white-space:normal;height:auto;margin-top:12px}@media(max-width:800px){.grid{grid-template-columns:1fr}.action-row{display:grid}}
</style>
