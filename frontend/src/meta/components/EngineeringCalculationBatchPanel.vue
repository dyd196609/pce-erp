<template>
  <section class="batch-panel" data-section="calculation-batch-reuse"
    :data-export-stage="exportTrace.stage" :data-export-row-count="exportTrace.rowCount" :data-export-column-count="exportTrace.columnCount">
    <header><div><h2>来源范围与核算项目总览</h2><p>同一原核算模块内整体核对。已确认的业务方法保留；本次试算不生成材料需求、BOM或生产计划。</p></div><strong>{{ panelStatus }}</strong></header>
    <p v-if="!nonProduction" class="warning">尚未确认非生产环境，本区域不发起试算。已有订单记录仍在下方。</p>
    <p v-if="error" class="error" role="alert">{{ error }} <button @click="load" :disabled="busy">重新读取</button></p>
    <p v-if="message" role="status" class="feedback">{{ message }}</p>
    <template v-if="catalog">
      <p v-if="catalogStale" class="warning">下方来源目录为上次成功读取，尚未完成本次读取；暂不使用旧目录发起批量核对。</p>
      <p v-else-if="!catalog.sources.length" role="status">来源目录读取完成：当前没有可选来源。这是合法空集合，并非读取失败。</p>
      <div class="scope-controls">
        <label>选择来源范围<select v-model="scope" :disabled="busy" @change="sourceKey = ''"><option value="all">全部真实工程来源（{{ catalog.sources.length }} 行）</option><option value="order" :disabled="!order">当前订单/验收对象对应来源</option><option v-for="sheet in sheets" :key="sheet" :value="sheet">{{ sheet }}</option></select></label>
        <label>明细范围<select v-model="sourceKey" :disabled="busy"><option value="">范围内全部明细（{{ scopeRows.length }} 行）</option><option v-for="row in scopeRows" :key="row.key" :value="row.key">{{ row.sheet }} 第{{ row.row }}行 · {{ row.space }} · {{ row.component }}</option></select></label>
        <button :disabled="busy || catalogStale || !keys.length || !nonProduction" data-action="batch-trial-engineering-sources" @click="execute">{{ phase === 'running' ? '正在批量核对…' : actionLabel }}</button>
      </div>
      <p>当前验收对象：{{ order ? `${order.orderNo}/${order.lineNo}` : '未选择订单' }}。本区域选择 {{ keys.length }} 条来源，系统按结构确定适用项目；来源范围不冒充正式订单稳定关联。</p>
      <details class="source-details"><summary>查看所选范围原始工程数据、字段及来源（{{ keys.length }} 行）</summary>
        <article v-for="row in selectedSources" :key="row.key"><h4>{{ row.sheet }} 第{{ row.row }}行 · {{ row.space }} · {{ row.component }}</h4><p>配置 {{ row.configuration }} · 来源版本 {{ catalog.version }} · 正式订单稳定关联未建立</p>
          <dl class="source-grid"><div v-for="field in row.businessInputs" :key="field.cell"><dt>{{ field.name }}</dt><dd>{{ field.rawValue ?? '来源未填' }} {{ field.unit }}<small>{{ field.sourceFormula ? '来源派生值' : '来源原始输入（只读）' }} · {{ field.cell }}</small></dd></div></dl>
          <details><summary>全部来源单元格与原始公式（诊断）</summary><dl class="source-grid"><div v-for="(cell, address) in row.inputs" :key="address"><dt>{{ address }}</dt><dd>{{ cell.value ?? '来源未填' }}<small>{{ cell.formula }}</small></dd></div></dl></details>
        </article>
      </details>
      <details open><summary>全部业务能力与连接状态（{{ catalog.capabilities.length }} 类；不按技术输出重复计数）</summary>
        <div class="capability-grid"><article v-for="item in catalog.capabilities" :key="item.id"><h4>{{ item.name }}</h4><p>{{ item.meaning }}</p><b>{{ handlingLabels[item.handling] }}</b><p>{{ item.implementation }}</p><details><summary>实现依据</summary><code>{{ item.code }}</code></details></article></div>
      </details>
      <template v-if="result">
        <h3>{{ resultStale ? '上次成功批次结果（非本次成功）' : '本次结果汇总与下钻' }}</h3>
        <p>{{ result.sourceCount }} 行 · {{ result.rows.length }} 项明细 · {{ Object.entries(result.counts).map(([k,v]) => `${k} ${v}项`).join('；') }}。完成于 {{ result.completedAt }}。净量可查看，预留/损耗与毛量仍独立保持未定。</p>
        <p v-for="segment in result.segments" :key="segment.key"><b>{{ segment.label }}</b>：{{ segment.sourceCount }} 行来源，{{ segment.resultCount }} 项明细；{{ Object.entries(segment.counts).map(([k,v]) => `${k} ${v}项`).join('；') }}。缺项 {{ segment.missingCount }} 项，未按0计入。</p>
        <p v-if="!result.rows.length" role="status">本次服务返回合法空明细，未形成可汇总工程结果；不代表材料或BOM已完成。</p>
        <p v-if="missingRows.length" class="warning">本批次有 {{ missingRows.length }} 项来源条件缺失；汇总仅包含已知工程结果，缺项未按0计入，不能视为完整用量。</p>
        <div class="summary-grid"><button v-for="total in result.totals" :key="`${total.resultScope}-${total.sheet}-${total.project}-${total.unit}`" class="summary" @click="showGroup(total)"><b>{{ total.resultScopeLabel }} · {{ total.sheet }} · {{ total.project }}</b><span>{{ total.net ?? '查看明细，不作数量合计' }} {{ total.unit }}</span><small>{{ total.label }}；已知{{ total.known }}项，缺项{{ total.missing }}项 · 查看明细</small></button></div>
        <PceEnterpriseListTable ref="tableRef" :contract="contract" page-id="pde-calculation-batch" table-id="pde-calculation-batch-results"
          :rows="result.rows" :table-rows="filteredRows" :filters="filters" :filter-schema="filterSchema" :quick-search="quickSearch" :advanced-visible="advancedVisible"
          :selected-count="selectedRows.length" :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="project" primary-label="核算项目" :primary-width="190" min-width="1420px" data-source-mode="canary_acceptance"
          @update:quick-search="quickSearch = $event" @search="applySearch" @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort"
          @update-filter="updateFilter" @selection-change="handleSelectionChange" @clear-selection="clearSelection" @sort-change="handleSort" @export-current="handleExportCurrent">
          <template #columns><el-table-column v-for="c in columns" :key="c.field" :prop="c.field" :label="c.label" :width="c.width" sortable="custom" show-overflow-tooltip /></template>
          <template #actions="{ row }"><button class="detail-button" @click="detail = row">查看过程</button></template>
        </PceEnterpriseListTable>
        <article v-if="detail" class="detail"><h3>{{ detail.project }} · {{ detail.space }} · {{ detail.sheet }}第{{ detail.row }}行</h3><p>{{ detail.statusLabel }}：{{ detail.value ?? detail.reason }}<template v-if="detail.value != null"> {{ detail.unit }}</template></p><p>{{ detail.nature }}</p>
          <template v-if="detail.state === 'missing'">
            <p data-state="missing-calculation-trace">本项未形成可采用的计算结果；缺项未按0计入。以下为该来源行已有的原始条件，不是补算结果。</p>
            <dl class="source-grid"><div v-for="field in (catalog.sources.find(source => source.key === detail.sourceKey)?.businessInputs || [])" :key="field.cell"><dt>{{ field.name }} · {{ field.cell }}</dt><dd>{{ field.rawValue ?? '来源未填' }} {{ field.unit }}</dd></div></dl>
            <p v-if="detail.sourceFormula">来源公式（本项尚未算出）：<code>{{ detail.sourceFormula }}</code></p>
            <p v-else>本次缺项响应未提供可用公式；原始单元格及来源公式可在上方“查看所选范围原始工程数据、字段及来源”中追溯，不把缺项当成无公式的原始数量。</p>
          </template>
          <template v-else>
          <p>独立来源：{{ detail.expected ?? '无有效对照' }} {{ detail.unit }}；差异：{{ detail.difference ?? '不可比较' }}。来源公式单元格 {{ detail.sourceCell }}。</p>
          <div class="source-grid"><div v-for="input in detail.inputs || []" :key="input.key"><b>{{ input.name }}</b><p>{{ input.value }} {{ input.unit }}</p></div></div>
          <p>本次表达式：<code>{{ detail.expression }}</code></p><p>来源公式：<code>{{ detail.sourceFormula || '原始数量，无公式' }}</code></p><p>版本 {{ detail.ruleVersion }} · 中间精度{{ detail.precision }} · 输出{{ detail.scale }}位 · {{ detail.rounding }}</p>
          </template>
          <p>预留/损耗：未维护；毛量：未确定。以上结果不是正式材料耗用量。</p>
          <details v-if="detailEdges.length"><summary>历史逐边过程（只读，不冒充本次生成）</summary><RoomDoorEdgeRequirementPreview v-for="edge in detailEdges" :key="edge.requirementId" :requirement="edge" /></details>
        </article>
      </template>
      <details><summary>历史成果、部件与材料角色（已确认的原始证据，只读）</summary><p>{{ catalog.history.label }}；{{ catalog.history.businessConfirmation }}。</p>
        <p>部件 {{ catalog.history.components.length }} 行；房门边段 {{ catalog.history.roomDoorSummary.physicalEdgeCount }}；原板匹配与木皮净量详情保留原来源。</p>
        <div class="history-list"><details v-for="row in historicalComponents" :key="`${row.sheet}:${row.row}`"><summary>{{ row.sheet }} 第{{ row.row }}行 · {{ row.space }} · {{ row.role }}</summary>
          <p>历史见光面积：{{ historicalVisible(row)?.visibleAreaM2 ?? '缺见光条件' }} m²；不是采购毛量。</p>
          <p v-if="historicalBoard(row)">原板选择：尚未形成正式采购数量。{{ (historicalBoard(row).blockers || []).join('、') }}（详见集中缺口）。</p>
          <RoomDoorEdgeRequirementPreview v-for="edge in historicalEdges(row)" :key="edge.requirementId" :requirement="edge" />
          <p v-for="edge in historicalStructuralEdges(row)" :key="edge.requirementId">历史结构封边净量 {{ edge.netLengthM }} m；{{ edge.edgeMode }}；边长 {{ edge.edgeDimensionsMm?.join(' + ') }} mm；数量 {{ edge.componentQuantity }}；毛量未定。</p>
        </details></div>
      </details>
      <details><summary>原公式/参考实现完整登记（{{ catalog.families.length }} 个公式族，不等于业务项目数）</summary><p>完整保留参考、来源损坏及旧候选区别；本区域不执行旧选板候选，不代表全部参考方法已正式上线。</p><input v-model="familySearch" placeholder="按业务名称、工作表或公式族查找"><details v-for="family in visibleFamilies" :key="family.id"><summary>{{ family.sheet }} · {{ family.name }} · {{ family.status }}</summary><p>{{ family.id }} · {{ family.function || '无可执行参考函数' }}</p><code>{{ family.formula }}</code><p>{{ family.cells.join('、') }}</p></details></details>
      <section class="gaps"><h3>集中异常与BOM衔接</h3>
        <template v-if="missingRows.length"><h4>{{ resultStale ? '上次成功批次的来源缺项' : '本次批次的来源缺项' }}（{{ missingRows.length }} 项）</h4><article v-for="row in missingRows" :key="row.id"><b>{{ row.sheet }} 第{{ row.row }}行 · {{ row.project }}</b><p>{{ row.reason }}</p><button @click="detail = row">查看缺项明细</button></article></template>
        <article v-for="gap in catalog.gaps" :key="gap.key"><b>{{ gap.name }}</b><p>{{ gap.reason }}</p></article><p>原订单BOM预览、草案及版本入口保留在本页下方。净量通过不等于物料需求完整；当前案例不能生成BOM。工序工程量需后续结合工艺路线、速度/工时和日历，不在此占用产能。</p></section>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { pdeApi } from '@/api/pde.js'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
import RoomDoorEdgeRequirementPreview from './RoomDoorEdgeRequirementPreview.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { pceBusinessActionLabel } from '@/meta/runtime/pceBusinessActionRegistry.js'
const props = defineProps({ order: { type: Object, default: null }, nonProduction: Boolean,workbookSourceRecordId:{ type:[String,Number],default:'' } })
let readSequence = 0
// null means not successfully read yet; publish only validated business objects.
const catalog=ref(null), result=ref(null), phase=ref('idle'), error=ref(''), message=ref(''), scope=ref('all'), sourceKey=ref(''), detail=ref(null), familySearch=ref('')
const catalogStale=ref(false), resultStale=ref(false)
const busy=computed(() => phase.value==='loading' || phase.value==='running')
const panelStatus=computed(() => !props.nonProduction ? '非生产环境未确认' : ({
  idle:'待读取来源', loading:'正在读取来源', ready:resultStale.value ? '范围已就绪 · 上次结果只读' : '来源已读取 · 待批量核对',
  running:'正在批量核对', completed:resultStale.value ? '范围已变化 · 上次结果只读' : '批量核对已完成',
  catalog_failed:'来源读取失败', batch_failed:'本次批量核对失败',
})[phase.value])
const actionLabel=pceBusinessActionLabel('batch-trial-engineering-sources')
const handlingLabels={ A:'已有服务和入口，保留', B:'已有方法，本页批量接入', C:'历史候选/模型只读续接，未正式部署', D:'机制已有，真实事实或参数缺口保留', E:'已证实尚缺实现', F:'已废弃/业务否定，仅留历史' }
const sheets=computed(() => [...new Set((catalog.value?.sources || []).map(r => r.sheet))])
const scopeRows=computed(() => (catalog.value?.sources || []).filter(r => scope.value==='all' || (scope.value==='order' ? r.sheet===props.order?.sourceSheet && r.row===props.order?.sourceRow : r.sheet===scope.value)))
const selectedSources=computed(() => scopeRows.value.filter(r => !sourceKey.value || r.key===sourceKey.value))
const keys=computed(() => selectedSources.value.map(r => r.key))
const historicalComponents=computed(() => (catalog.value?.history.components || []).filter(r => keys.value.includes(`${r.sheet}:${r.row}`)))
const historicalVisible=row => catalog.value.history.veneer.rows.find(r => r.sheet===row.sheet && r.row===row.row)
const historicalBoard=row => catalog.value.history.board.rows.find(r => r.sheet===row.sheet && r.row===row.row)
const historicalEdges=row => catalog.value.history.roomDoor.filter(r => r.sheet===row.sheet && r.row===row.row)
const historicalStructuralEdges=row => catalog.value.history.edges.filter(r => r.sheet===row.sheet && r.row===row.row)
const detailEdges=computed(() => detail.value && catalog.value ? historicalEdges(detail.value).filter(e => e.sourceCell===detail.value.sourceCell) : [])
const visibleFamilies=computed(() => (catalog.value?.families || []).filter(f => `${f.sheet} ${f.name} ${f.id}`.toLowerCase().includes(familySearch.value.toLowerCase())))
const columns=[{field:'resultScopeLabel',label:'结果范围',width:130},{field:'sheet',label:'来源工作表',width:140},{field:'row',label:'来源行',width:90},{field:'space',label:'空间',width:160},{field:'component',label:'产品/部件',width:130},{field:'configuration',label:'材料配置',width:150},{field:'value',label:'工程净量/尺寸',width:145},{field:'unit',label:'单位',width:80},{field:'statusLabel',label:'核对情况',width:145},{field:'difference',label:'实际差异',width:145}]
const filterSchema=columns.map(c => ({ field:c.field,label:c.label,filterType:'text' }))
const rows=computed(() => result.value?.rows || [])
const missingRows=computed(() => rows.value.filter(row => row.state==='missing'))
const contract=createPceEnterpriseListContract({pageCode:'pde-order-engineering-calculation',moduleCode:'PDE',title:'工程核算结果'})
const exportTrace=reactive({ stage:'idle', rowCount:0, columnCount:0 })
const {tableRef,quickSearch,advancedVisible,filters,selectedRows,activeFilterCount,sortText,filteredRows,applySearch,updateFilter,clearFilters,handleSort,clearSort,handleSelectionChange,clearSelection,exportCurrent}=usePceEnterpriseListRuntime({rows,filterSchema,searchFields:['project',...columns.map(c=>c.field)],exportColumns:[{field:'project',label:'核算项目'},...columns],exportFileName:'工程核算批量结果.csv',onExportStage(event){ Object.assign(exportTrace,event) }})
function handleExportCurrent() {
  exportTrace.stage='parent-received'
  exportCurrent()
}
function contractError(path, expected) {
  throw new Error(`BATCH_RESPONSE_CONTRACT_ERROR：${path} 应为${expected}；本次数据未作为成功结果接入。`)
}
function requireObject(value, path) {
  if (!value || typeof value!=='object' || Array.isArray(value)) contractError(path,'对象')
  return value
}
function requireList(value, path, check) {
  if (!Array.isArray(value)) contractError(path,'数组')
  value.forEach((item,index) => check ? check(item,`${path}[${index}]`) : requireObject(item,`${path}[${index}]`))
}
function requireText(value, path) {
  if (typeof value!=='string') contractError(path,'文本')
}
function requireCount(value, path) {
  if (!Number.isInteger(value) || value<0) contractError(path,'非负整数')
}
function requireSource(row, path) {
  requireObject(row,path); requireText(row.sheet,`${path}.sheet`); requireCount(row.row,`${path}.row`)
}
// request.js resolves both success and failure envelopes. Unwrap once here;
// pde.js and the shared transport contract deliberately remain unchanged.
function readBatchResponse(response, kind) {
  requireObject(response,'response')
  if (response.success===false) {
    const status=Number(response.factLoadFacts?.httpStatus || response.meta?.status || 0)
    const code=response.error?.code || response.factLoadFacts?.errorCode || `HTTP_${status || 'UNKNOWN'}`
    const reason=response.error?.message || response.factLoadFacts?.errorMessage || '服务端未提供失败说明'
    const category=status===401 || status===403 ? '身份或权限错误' : !status ? '网络读取失败' : status>=500 ? '服务读取失败' : '业务请求受阻'
    throw new Error(`${category}（${code}）：${reason}`)
  }
  if (response.success!==true) contractError('response.success','布尔成功标识')
  const data=requireObject(response.data,`${kind}.data`)
  if (kind==='catalog') validateCatalog(data)
  else validateResult(data)
  return data
}
function validateCatalog(data) {
  requireText(data.version,'catalog.version')
  requireList(data.sources,'catalog.sources',(row,path) => {
    requireSource(row,path); requireText(row.key,`${path}.key`)
    requireList(row.businessInputs,`${path}.businessInputs`)
    requireObject(row.inputs,`${path}.inputs`)
    Object.entries(row.inputs).forEach(([key,cell]) => requireObject(cell,`${path}.inputs.${key}`))
  })
  requireList(data.capabilities,'catalog.capabilities')
  requireList(data.families,'catalog.families',(family,path) => {
    requireObject(family,path); requireList(family.cells,`${path}.cells`,requireText)
  })
  requireList(data.gaps,'catalog.gaps')
  const history=requireObject(data.history,'catalog.history')
  requireList(history.components,'catalog.history.components',requireSource)
  for (const key of ['veneer','board']) {
    requireObject(history[key],`catalog.history.${key}`)
    requireList(history[key].rows,`catalog.history.${key}.rows`,(row,path) => {
      requireSource(row,path)
      if (key==='board' && row.blockers!=null) requireList(row.blockers,`${path}.blockers`,requireText)
    })
  }
  requireList(history.edges,'catalog.history.edges',(edge,path) => {
    requireSource(edge,path)
    if (edge.edgeDimensionsMm!=null) requireList(edge.edgeDimensionsMm,`${path}.edgeDimensionsMm`,(value,at) => {
      if (typeof value!=='number' && typeof value!=='string') contractError(at,'数值或数值文本')
    })
  })
  requireList(history.roomDoor,'catalog.history.roomDoor',(edge,path) => {
    requireSource(edge,path); requireList(edge.segments,`${path}.segments`)
  })
  requireObject(history.roomDoorSummary,'catalog.history.roomDoorSummary')
  requireCount(history.roomDoorSummary.physicalEdgeCount,'catalog.history.roomDoorSummary.physicalEdgeCount')
}
function validateResult(data) {
  requireCount(data.sourceCount,'result.sourceCount')
  requireText(data.completedAt,'result.completedAt')
  if (!data.completedAt || !Number.isFinite(Date.parse(data.completedAt))) contractError('result.completedAt','有效的服务端完成时间')
  requireList(data.rows,'result.rows',(row,path) => {
    requireSource(row,path)
    for (const key of ['id','sourceKey','project','state','statusLabel']) requireText(row[key],`${path}.${key}`)
    if (row.state==='missing') requireText(row.reason,`${path}.reason`)
    // Missing-condition rows legitimately have no inputs; calculated rows do.
    if (row.state==='calculated' || row.inputs!=null) requireList(row.inputs,`${path}.inputs`)
  })
  requireList(data.totals,'result.totals',(total,path) => {
    requireObject(total,path)
    for (const key of ['resultScope','resultScopeLabel','sheet','project','label']) requireText(total[key],`${path}.${key}`)
    requireCount(total.known,`${path}.known`); requireCount(total.missing,`${path}.missing`)
  })
  requireList(data.segments,'result.segments',(segment,path) => {
    requireObject(segment,path)
    for (const key of ['key','label']) requireText(segment[key],`${path}.${key}`)
    for (const key of ['sourceCount','resultCount','missingCount']) requireCount(segment[key],`${path}.${key}`)
    requireObject(segment.counts,`${path}.counts`)
    Object.entries(segment.counts).forEach(([key,count]) => requireCount(count,`${path}.counts.${key}`))
    if (Object.values(segment.counts).reduce((sum,count) => sum+count,0)!==segment.resultCount) contractError(`${path}.counts`,'与分段明细数一致的计数')
  })
  requireObject(data.counts,'result.counts')
  Object.entries(data.counts).forEach(([key,count]) => requireCount(count,`result.counts.${key}`))
  if (Object.values(data.counts).reduce((sum,count) => sum+count,0)!==data.rows.length) contractError('result.counts','与实际明细行数一致的计数')
}
async function load() {
  if (!props.nonProduction || busy.value) return
  const request = ++readSequence, workbookSourceId = props.workbookSourceRecordId
  phase.value='loading'; error.value=''; catalogStale.value=Boolean(catalog.value); resultStale.value=Boolean(result.value)
  message.value='正在读取来源目录与核算项目…'
  try {
    const next=readBatchResponse(await pdeApi.calculationBatchCatalog(workbookSourceId !== '' && workbookSourceId != null ? { workbookSourceRecordId:Number(workbookSourceId) } : {}),'catalog')
    if (request !== readSequence || workbookSourceId !== props.workbookSourceRecordId) return
    if (workbookSourceId !== '' && workbookSourceId != null && next.workbookSourceRecordId !== Number(workbookSourceId)) contractError('catalog.workbookSourceRecordId','本次明确选定的来源版本')
    catalog.value=next; catalogStale.value=false; phase.value='ready'
    message.value=`来源目录读取完成：${next.sources.length}行。${result.value ? '下方仍为上次成功批次，需重新核对所选范围。' : '请选择来源范围后执行批量核对。'}`
  } catch(e) {
    if (request !== readSequence || workbookSourceId !== props.workbookSourceRecordId) return
    phase.value='catalog_failed'; error.value=e.message || '来源读取失败，未用空数据代替'
    message.value='本次来源读取未完成，未作为空数据成功。'
  }
}
async function execute() {
  if (busy.value || catalogStale.value || !props.nonProduction || !keys.value.length) return
  const selected=[...keys.value]
  const request = ++readSequence, workbookSourceId = props.workbookSourceRecordId
  phase.value='running'; error.value=''; resultStale.value=Boolean(result.value)
  message.value='已接收，正在批量核对所选工程来源…'
  try {
    const next=readBatchResponse(await pdeApi.calculateSourceBatch(selected,workbookSourceId !== '' && workbookSourceId != null ? { workbookSourceRecordId:Number(workbookSourceId) } : {}),'result')
    if (request !== readSequence || workbookSourceId !== props.workbookSourceRecordId) return
    if (workbookSourceId !== '' && workbookSourceId != null && next.workbookSourceRecordId !== Number(workbookSourceId)) contractError('result.workbookSourceRecordId','本次明确选定的来源版本')
    // Validate first: a malformed response must never replace the last good batch.
    clearFilters(); result.value=next; detail.value=null
    resultStale.value=selected.join('\n')!==keys.value.join('\n')
    phase.value='completed'
    message.value=`本次批量核对已完成：${next.sourceCount}行，${next.rows.length}项明细。${Object.entries(next.counts).map(([k,v])=>`${k}${v}项`).join('；')}。未生成材料需求或BOM。${resultStale.value ? '选择范围已变化，下方为请求发起时范围的结果。' : ''}`
  } catch(e) {
    if (request !== readSequence || workbookSourceId !== props.workbookSourceRecordId) return
    phase.value='batch_failed'; error.value=e.message || '本次批量核对失败'
    message.value=result.value ? '本次未完成；上次成功结果保留其原完成时间，不作为本次成功。' : '本次未完成，尚无成功批次结果。'
  }
}
function showGroup(total) { clearFilters(); updateFilter('resultScopeLabel',total.resultScopeLabel); updateFilter('sheet',total.sheet); if (total.unit) updateFilter('unit',total.unit); quickSearch.value=total.project; applySearch(); detail.value=null }
watch(() => props.nonProduction, value => { if (value && !catalog.value) load() })
watch(() => props.workbookSourceRecordId, () => {
  readSequence += 1; catalogStale.value=Boolean(catalog.value); resultStale.value=Boolean(result.value)
  phase.value='idle'; error.value=''; detail.value=null
  message.value='来源版本已变化；旧目录与旧批次不作为当前版本结果。'
  load()
})
watch([scope,sourceKey,()=>props.order?.salesOrderItemId,()=>props.order?.sourceSheet,()=>props.order?.sourceRow], () => { if (result.value) { resultStale.value=true; message.value='选择范围已变化。下方仍为上次成功批次结果（见完成时间）；点击批量核对更新。' } })
onMounted(load)
onBeforeUnmount(() => { readSequence += 1 })
</script>

<style scoped>
.batch-panel{background:white;border:1px solid #dce5ef;border-radius:12px;padding:22px;margin:18px 0;color:#273d52;min-width:0}.batch-panel header{display:flex;justify-content:space-between;gap:20px}.batch-panel h2{margin:0}.batch-panel p{line-height:1.65}.scope-controls{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.scope-controls label{display:flex;flex-direction:column;gap:6px}.batch-panel select,.batch-panel input{padding:9px;border:1px solid #c7d5df;border-radius:6px;max-width:100%}.batch-panel button{padding:10px 14px;border:1px solid #b4cbd0;border-radius:6px;background:#eef6f7;color:#22545c;cursor:pointer}.batch-panel button:disabled{opacity:.5;cursor:not-allowed}.batch-panel details{margin:14px 0}.batch-panel summary{cursor:pointer;font-weight:600}.capability-grid,.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:15px 0}.capability-grid article,.detail,.gaps{border:1px solid #e0e7ed;padding:14px;border-radius:8px}.capability-grid h4{margin:0}.capability-grid p{margin:8px 0}.summary{display:flex;flex-direction:column;text-align:left;gap:8px}.source-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.source-grid dd{margin:0}.source-grid small{display:block;overflow-wrap:anywhere}.source-details article{padding:12px;border-bottom:1px solid #eee}.history-list{max-height:600px;overflow:auto}.feedback{padding:12px;background:#eaf5f1}.warning{color:#805c18}.error{color:#aa2838}.batch-panel code{overflow-wrap:anywhere;white-space:pre-wrap}.detail{margin-top:15px}.gaps{background:#fff9e9;margin-top:16px}.detail-button{white-space:nowrap}
</style>


