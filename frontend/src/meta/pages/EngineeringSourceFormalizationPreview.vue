<template>
  <section class="formalization" data-page-code="engineering-source-sales-formalization" :data-source-record-id="sourceRecordId" :aria-busy="busy">
    <header class="card hero">
      <div><p class="eyebrow">SALES SOURCE INTAKE / ENGINEERING SOURCE</p><h2>工程来源转正式订单 · 人工确认准备</h2><p>复用销售订单受理边界；当前只读，不创建订单、工程实例、需求或计划。</p></div>
      <div class="actions"><el-button @click="back">返回销售订单</el-button><el-button type="primary" @click="openContract">打开开发合同</el-button><el-button @click="openEngineering">打开原工程页</el-button><el-button :loading="busy" @click="load">重新读取服务端事实</el-button></div>
    </header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="preview">
      <section class="card"><h3>{{ preview.businessOrderReference.sourceOrderNo || '来源订单号未提供' }} · {{ preview.businessOrderReference.customerName || '客户未提供' }}</h3>
        <div class="facts"><span>来源记录 <b>#{{ preview.source.id }}</b></span><span>版本 <b>{{ preview.source.sourceVersion }}</b></span><span>工程行 <b>{{ preview.source.rowCount }}</b></span><span>正式订单命中 <b>{{ preview.matchingSalesOrders.length }}</b></span></div>
        <p>项目：{{ preview.businessOrderReference.projectName || '来源未提供' }}；内容指纹：{{ preview.source.contentHash }}</p>
        <el-tag type="warning">{{ preview.statusLabel }}</el-tag>
      </section>
      <section class="card blockers"><h3>当前不能建档的明确原因</h3><ul><li v-for="row in preview.blockers" :key="row.code"><b>{{ row.code }}</b>：{{ row.message }}</li></ul></section>
      <section class="card"><h3>请人工确认的商业事实</h3><ol><li v-for="row in preview.questions" :key="row.code"><b>{{ row.code }}</b>：{{ row.question }}</li></ol><p>来源分组和工程数量只帮助定位，不能据此自动生成销售行。</p></section>
      <section class="card"><h3>来源分组（非销售明细）</h3>
        <el-table :data="preview.sourceGroups" border max-height="430"><el-table-column prop="product" label="工程产品"/><el-table-column prop="component" label="部件"/><el-table-column prop="sourceUom" label="来源单位"/><el-table-column prop="rowCount" label="来源行数"/><el-table-column prop="sourceQuantity" label="工程数量合计"/><el-table-column prop="businessMeaning" label="业务边界" min-width="280"/></el-table>
      </section>
      <section class="card"><h3>单位与工程编码解析</h3>
        <div class="two"><div><h4>单位</h4><p v-for="row in preview.unitResolution" :key="row.sourceUom">{{ row.sourceUom }} → {{ row.matches.map(optionLabel).join('；') || '没有正式单位匹配' }}（{{ row.resolved ? '唯一匹配' : '未解析' }}）</p></div>
        <div><h4>加工物料编码</h4><p v-for="row in preview.engineeringMaterialCandidates" :key="row.sourceCode">{{ row.sourceCode }} → {{ row.matches.map(materialLabel).join('；') || '未命中' }}；仅为工程候选，销售用途未确认</p></div></div>
      </section>
      <el-collapse class="card"><el-collapse-item :title="`查看 ${preview.sourceRows.length} 条来源事实`" name="rows">
        <el-table :data="preview.sourceRows" border max-height="620" row-key="sourceRowId">
          <el-table-column prop="sourceRowId" label="稳定身份" min-width="260" fixed="left"/><el-table-column prop="sourceCellRange" label="原表位置" min-width="170"/><el-table-column prop="space" label="空间/房间" min-width="150"><template #default="{row}">{{ row.space || '来源未提供' }}</template></el-table-column><el-table-column prop="product" label="工程产品"/><el-table-column prop="component" label="部件" min-width="130"/>
          <el-table-column label="尺寸" min-width="170"><template #default="{row}">{{ dimensions(row) }}</template></el-table-column><el-table-column label="数量/单位"><template #default="{row}">{{ row.quantity }} {{ row.sourceUom }}</template></el-table-column><el-table-column prop="materialProcessCode" label="加工物料编码" min-width="150"/><el-table-column prop="routingProcessCode" label="工艺编码" min-width="130"/><el-table-column prop="edgeMode" label="封边"/><el-table-column prop="visibleCondition" label="见光"/><el-table-column prop="salesMaterialStatus" label="销售物料" min-width="180" fixed="right"/>
        </el-table>
      </el-collapse-item></el-collapse>
      <section class="card"><h3>正式工程与计划边界</h3><div class="facts"><span>已发布规则 <b>{{ preview.formalEngineering.releasedRuleCount }}</b></span><span>订单工程实例 <b>{{ preview.formalEngineering.orderEngineeringInstanceCount }}</b></span><span>正式核算 <b>{{ preview.formalEngineering.calculationCount }}</b></span><span>材料需求 <b>{{ preview.formalEngineering.materialRequirementCount }}</b></span><span>工序需求 <b>{{ preview.formalEngineering.operationRequirementCount }}</b></span></div><p>{{ preview.planning.statusLabel }}</p></section>
      <section class="card"><h3>合法办理身份核对</h3><p>当前登录：{{ preview.currentUser.username }} / 公司 #{{ preview.currentUser.companyId }} / 员工 #{{ preview.currentUser.employeeId || '未关联' }}；正式办理人：{{ preview.currentUser.sourceActorReadiness.ready ? '就绪' : `${preview.currentUser.sourceActorReadiness.code}：${preview.currentUser.sourceActorReadiness.reason}` }}</p>
        <el-table :data="preview.knownOperatorChecks" border><el-table-column prop="username" label="既有用户名"/><el-table-column prop="companyId" label="公司ID"/><el-table-column prop="employeeId" label="员工ID"><template #default="{row}">{{ row.employeeId || '未关联' }}</template></el-table-column><el-table-column label="销售动作"><template #default="{row}">{{ actionText(row) }}</template></el-table-column><el-table-column label="工程核算"><template #default="{row}">查看 {{ yes(row.engineeringView.allowed) }}；执行 {{ yes(row.engineeringExecute.allowed) }}</template></el-table-column><el-table-column label="正式来源办理人" min-width="280"><template #default="{row}">{{ row.sourceActorReadiness.ready ? '就绪' : `${row.sourceActorReadiness.code}：${row.sourceActorReadiness.reason}` }}</template></el-table-column></el-table>
      </section>
      <footer class="card"><p>服务端事实来源：{{ preview.strictFacts.factSource }}。本页业务写入 {{ preview.strictFacts.businessWriteCount }}；计划写入 {{ preview.strictFacts.planningWriteCount }}。</p><el-button @click="copyFacts">复制同源服务端诊断</el-button></footer>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { salesApi } from '@/api/sales'
const route=useRoute(),router=useRouter(),preview=ref(null),busy=ref(false),error=ref('')
const sourceRecordId=computed(()=>Number(route.query.sourceRecord||0))
const optionLabel=x=>`#${x.id} · ${x.code} / ${x.name}`
const materialLabel=x=>`${optionLabel(x)} / ${x.specification||'规格未提供'} / 基本单位 #${x.baseUomId||'未维护'}`
const yes=value=>value?'允许':'不允许'
const dimensions=row=>[row.dimensions.length,row.dimensions.width,row.dimensions.thickness].map(x=>x??'-').join(' × ')
const actionText=row=>row.actions.map(x=>`${x.actionCode.split('.').pop()} ${yes(x.allowed)}`).join('；')
async function load(){busy.value=true;error.value='';preview.value=null;try{if(!sourceRecordId.value)throw new Error('缺少工程来源稳定 ID');const r=await salesApi.engineeringSourceFormalization(sourceRecordId.value);if(!r.success)throw new Error(r.error?.message||'来源接入事实读取失败');preview.value=r.data.preview}catch(e){error.value=e.message}finally{busy.value=false}}
function back(){const {mode,sourceRecord,...query}=route.query;router.push({path:'/sales/orders',query})}
function openEngineering(){if(!preview.value)return;router.push(preview.value.navigation.engineeringSource)}
function openContract(){router.push({path:'/sales/orders',query:{mode:'development-contract',sourceRecord:sourceRecordId.value}})}
async function copyFacts(){try{await navigator.clipboard.writeText(JSON.stringify(preview.value.diagnosticFacts,null,2));ElMessage.success('已复制同源服务端诊断')}catch{ElMessage.error('浏览器未允许剪贴板访问')}}
onMounted(load)
</script>

<style scoped>
.formalization{display:grid;gap:16px}.card{padding:20px;border:1px solid #dce4ed;border-radius:12px;background:#fff;overflow:hidden}.hero{display:flex;justify-content:space-between;gap:20px}.hero h2,.card h3{margin-top:0}.eyebrow{font-size:12px;font-weight:700;color:#285ac7}.actions{display:flex;align-items:center;gap:8px}.facts{display:flex;flex-wrap:wrap;gap:12px}.facts span{padding:10px 12px;border-radius:8px;background:#f1f5f9}.blockers{border-color:#f2c58f;background:#fffaf0}.card li{margin:8px 0}.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card p{overflow-wrap:anywhere;color:#475569}@media(max-width:800px){.hero{display:block}.actions,.two{display:grid;grid-template-columns:1fr}}
</style>
