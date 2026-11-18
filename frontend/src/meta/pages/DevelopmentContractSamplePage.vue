<template>
  <section class="contract-page" data-page-code="sales-orders" data-page-subview="development-contract" :aria-busy="busy">
    <header class="card hero">
      <div><p class="eyebrow">销售订单工作台 / 开发联调样本</p><h2>开发合同与报价</h2><p>页面位置：销售订单工作台 / 开发合同与报价。仅限指定非生产B库，不是真实签约、收款、开票或发货。</p></div>
      <div class="actions"><el-button @click="back">返回销售订单</el-button><el-button @click="openSource">打开工程输入</el-button><el-button :loading="busy" @click="load">刷新</el-button></div>
    </header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="preview">
      <el-alert title="DEVELOPMENT_ONLY｜开发联调样本｜联系方式不可外联｜不触发收款、开票、物流或生产发布" type="warning" show-icon :closable="false" />
      <section v-if="preview.authorization.blockers.length" class="card blockers"><h3>当前保存门禁</h3><p v-for="row in preview.authorization.blockers" :key="row.code"><b>{{ row.code }}</b>：{{ row.message }}</p></section>
      <section class="card"><h3>合同主体与工程需求</h3>
        <div class="form-grid"><label>样本合同编号<el-input v-model="form.contractNo" disabled /></label><label>合同版本<el-input v-model="form.contractVersion" disabled /></label><label>供方<el-input v-model="form.supplierName" disabled /></label><label>需方<el-input v-model="form.customerName" disabled /></label><label>项目<el-input v-model="form.projectName" disabled /></label><label>原订单标识<el-input v-model="form.sourceOrderNo" disabled /></label><label>供方联系人<el-input v-model="form.supplierContact" /></label><label>需方联系人<el-input v-model="form.customerContact" /></label><label>收货点（测试占位）<el-input v-model="form.deliveryAddressPlaceholder" /></label><label>币种<el-input v-model="form.currency" disabled /></label></div>
        <p>供货范围：单开房门、单面门套、柜体配套部件包、L型木饰面；映射来源 {{ preview.source.id }} / {{ preview.source.version }} / {{ preview.source.rowCount }} 行。</p>
      </section>
      <section class="card"><div class="section-head"><h3>报价明细</h3><el-button :loading="calculating" @click="calculate">按服务端公式重新试算</el-button></div>
        <el-table :data="form.lines" border row-key="code">
          <el-table-column type="expand"><template #default="{ row }"><el-table :data="row.sourceRows" border size="small"><el-table-column prop="id" label="稳定来源身份" min-width="230"/><el-table-column prop="position" label="原表位置"/><el-table-column prop="space" label="空间/房间"/><el-table-column prop="product" label="工程产品"/><el-table-column prop="component" label="部件"/><el-table-column label="工程数量"><template #default="scope">{{ scope.row.quantity }} {{ scope.row.unit }}</template></el-table-column></el-table></template></el-table-column>
          <el-table-column prop="code" label="商业行号" width="105" fixed="left"/><el-table-column prop="name" label="销售产品/范围" min-width="220"/><el-table-column prop="quantity" label="商业数量" width="90"/><el-table-column prop="unit" label="单位" width="70"/><el-table-column label="含税单价" width="170"><template #default="{row}"><el-input-number v-model="row.unitPrice" :min="0" :precision="2" @change="calculate"/></template></el-table-column><el-table-column label="测试税率" width="105"><template #default="{row}">{{ percent(row.taxRate) }}</template></el-table-column><el-table-column prop="grossAmount" label="含税金额" width="120" align="right"/><el-table-column prop="netAmount" label="未税金额" width="120" align="right"/><el-table-column prop="taxAmount" label="税额" width="110" align="right"/><el-table-column prop="requiredDate" label="批次承诺" width="120"/><el-table-column prop="sourceRowCount" label="工程行数" width="90"/></el-table>
        <div class="totals"><span>含税总额 <b>{{ money(form.totals.gross) }}</b></span><span>未税金额 <b>{{ money(form.totals.net) }}</b></span><span>税额 <b>{{ money(form.totals.tax) }}</b></span></div>
        <p class="hint">金额由服务端按“数量×含税单价；未税=含税÷(1+税率)，逐行四舍五入到分”计算。13%仅为本样本测试参数，不写入价格主档。</p>
      </section>
      <section class="card"><h3>日期、交付批次与付款节点</h3><div class="form-grid"><label>订单日期<el-date-picker v-model="form.orderDate" value-format="YYYY-MM-DD" disabled/></label><label>报价有效至<el-date-picker v-model="form.quoteValidUntil" value-format="YYYY-MM-DD"/></label><label>客户要求交期<el-date-picker v-model="form.customerRequiredDate" value-format="YYYY-MM-DD"/></label><label>企业承诺交期<el-date-picker v-model="form.committedDeliveryDate" value-format="YYYY-MM-DD"/></label></div>
        <el-table :data="form.paymentNodes" border><el-table-column prop="name" label="付款节点"/><el-table-column label="比例"><template #default="{row}">{{ percent(row.ratio) }}</template></el-table-column><el-table-column label="开发金额"><template #default="{row}">{{ money(Number(form.totals.gross||0)*Number(row.ratio||0)) }}</template></el-table-column><el-table-column label="限制" value="只测试应收计划，不实际收款"><template #default>只测试应收计划，不实际收款</template></el-table-column></el-table>
      </section>
      <section class="card footer"><div><b>{{ preview.statusLabel }}</b><p>正式订单：{{ preview.order ? `${preview.order.orderNo}（ID ${preview.order.id}）` : '尚未创建' }}；样本合同编号与正式订单编号严格分开。</p></div><el-button type="primary" :disabled="!preview.authorization.canSave" :loading="saving" @click="save">保存并由服务端回读</el-button></section>
      <section class="card"><h3>同源诊断</h3><p>4条商业行，映射 {{ preview.strictFacts.mappedSourceRowCount }}/{{ preview.strictFacts.sourceRowCount }} 行；当前正式销售订单 {{ preview.strictFacts.salesOrderCount }} 条；计划写入 {{ preview.strictFacts.planningWriteCount }}。</p><el-button @click="copyFacts">复制诊断数据</el-button></section>
    </template>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { salesApi } from '@/api/sales'
import { applyPageDocumentTitle } from '@/meta/runtime/pageTitleManager'
const route=useRoute(),router=useRouter(),preview=ref(null),busy=ref(false),calculating=ref(false),saving=ref(false),error=ref('')
const form=reactive({lines:[],totals:{gross:'0',net:'0',tax:'0'},paymentNodes:[]})
const sourceId=()=>Number(route.query.sourceRecord||0)
const money=value=>Number(value||0).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const percent=value=>`${(Number(value||0)*100).toFixed(2)}%`
function apply(data){preview.value=data;Object.keys(form).forEach(key=>delete form[key]);Object.assign(form,JSON.parse(JSON.stringify(data.contract)))}
async function load(){busy.value=true;error.value='';const r=await salesApi.developmentContract(sourceId());busy.value=false;applyPageDocumentTitle(route);if(!r.success){error.value=r.error?.message||'开发合同读取失败';return}apply(r.data.preview)}
async function calculate(){if(!form.lines.length)return;calculating.value=true;const r=await salesApi.calculateDevelopmentContract(sourceId(),form.lines);calculating.value=false;if(!r.success)return ElMessage.error(r.error?.message||'价税试算失败');form.lines=r.data.lines;form.totals=r.data.totals}
async function save(){saving.value=true;const key=crypto.randomUUID();const r=await salesApi.saveDevelopmentContract(sourceId(),form,key);saving.value=false;if(!r.success)return ElMessage.error(r.error?.message||'开发合同保存失败');apply(r.data.preview);ElMessage.success(r.data.replayed?'重复请求已返回原结果，没有重复建单':'开发合同草稿已保存并回读')}
function back(){router.push('/sales/orders')}
function openSource(){router.push(preview.value.navigation.engineeringSource)}
async function copyFacts(){try{await navigator.clipboard.writeText(JSON.stringify(preview.value.strictFacts,null,2));ElMessage.success('已复制同源服务端诊断')}catch{ElMessage.error('浏览器未允许剪贴板访问')}}
load()
</script>

<style scoped>
.contract-page{display:grid;gap:16px;padding:18px;background:#f4f7fb}.card{padding:20px;border:1px solid #dce4ed;border-radius:12px;background:#fff;overflow:hidden}.hero,.section-head,.footer{display:flex;justify-content:space-between;gap:18px;align-items:center}.hero h2,.card h3{margin:0 0 10px}.hero p,.card p{color:#536176}.eyebrow{font-size:12px;font-weight:700;color:#285ac7!important}.actions{display:flex;gap:8px}.blockers{border-color:#f2c58f;background:#fffaf0}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.form-grid label{display:grid;gap:6px;font-weight:600;color:#334155}.form-grid :deep(.el-date-editor){width:100%}.totals{display:flex;justify-content:flex-end;gap:28px;padding:16px;background:#eaf7f4}.totals b{font-size:20px;color:#0f766e}.hint{margin-bottom:0}.footer p{margin-bottom:0}@media(max-width:900px){.hero,.section-head,.footer{display:block}.actions,.form-grid{display:grid;grid-template-columns:1fr}.actions{margin-top:12px}}
</style>
