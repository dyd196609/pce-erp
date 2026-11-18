<template>
  <main
    class="foundation-import-preview"
    data-page-code="foundation-manufacturing-import-preview"
    data-page-type="VALIDATION_PAGE"
    data-action-type="VALIDATION_ACTION"
    data-fact-source="server"
    data-formal-master-data-write="0"
    :data-load-status="loadStatus"
  >
    <header class="hero">
      <div>
        <p class="eyebrow">Foundation Wave 1 · VALIDATION ACTION</p>
        <h1>制造基础数据导入预览</h1>
        <p>查看真实来源准备复用、新增或待裁决的内容。选择、上传、预览和刷新均不会写入正式主数据。</p>
      </div>
      <PceBusinessStatus status-code="READ_ONLY_VALIDATION" status-label="只读校验 · 正式写入为 0" source="server" />
    </header>

    <section class="source-panel" data-acceptance-id="FOUNDATION_IMPORT_SOURCE_SELECTION">
      <div>
        <h2>1. 选择当前批准的来源文件</h2>
        <p>本检查点仅接受：05半成品板材.xlsx、10采购物料.xlsx、01工序.xlsx。服务端会校验文件 SHA256。</p>
      </div>
      <div class="source-actions">
        <input ref="fileInput" type="file" accept=".xlsx" @change="selectFile">
        <el-button type="primary" :loading="loading" :disabled="!selectedFile" @click="preview">
          {{ loading ? '正在执行只读预览' : '执行只读预览' }}
        </el-button>
      </div>
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
    </section>

    <template v-if="result">
      <section class="source-identity" data-acceptance-id="FOUNDATION_SOURCE_IDENTITY">
        <article><span>来源文件</span><strong>{{ result.source.fileName }}</strong></article>
        <article><span>工作表</span><strong>{{ result.source.sheet }}</strong></article>
        <article><span>来源记录</span><strong>{{ result.statistics.total }}</strong></article>
        <article><span>Source Identity</span><strong>{{ result.statistics.sourceIdentityVerified }} 已确认</strong></article>
        <article class="hash"><span>SHA256</span><strong>{{ result.source.sha256 }}</strong></article>
      </section>

      <section class="boundary-banner">
        <div>
          <strong>PRODUCT FORMAL IMPORT = NOT IN CURRENT CHECKPOINT</strong>
          <span>{{ result.productBoundary.message }}</span>
        </div>
        <div>
          <strong>WORKCENTER = NOT_MAINTAINED</strong>
          <span>当前来源没有可靠工作中心事实，不创建、不用车间替代。</span>
        </div>
      </section>

      <section class="statistics" data-acceptance-id="FOUNDATION_PREVIEW_STATISTICS">
        <article v-for="card in statisticCards" :key="card.key" :class="card.tone">
          <span>{{ card.label }}</span><strong>{{ card.value }}</strong>
        </article>
      </section>

      <section class="protection" data-acceptance-id="FOUNDATION_EXISTING_DATA_PROTECTION">
        <header>
          <div><h2>已有正式数据实时保护</h2><p>数量来自当前 Server 正式事实；不是前端写死。</p></div>
          <strong>EXISTING RECORD UPDATE PLAN = {{ result.protection.existingRecordUpdatePlan }}</strong>
        </header>
        <div class="protection-grid">
          <article v-for="item in protectionCards" :key="item.key"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></article>
        </div>
      </section>

      <section class="candidate-list" data-acceptance-id="FOUNDATION_PREVIEW_CANDIDATE_TABLE">
        <header><div><h2>2. 候选与异常信息</h2><p>按来源文件、候选类型、校验状态、UOM状态和建议决定筛选；仅冲突、缺失和语义歧义需要逐行裁决。</p></div></header>
        <PceEnterpriseListTable
          ref="tableRef"
          :contract="enterpriseListContract"
          page-id="foundation-manufacturing-import-preview"
          table-id="foundation-wave1-preview-candidates"
          :rows="rows"
          :table-rows="filteredRows"
          :filter-schema="filterSchema"
          :filters="filters"
          :quick-search="quickSearch"
          :advanced-visible="advancedVisible"
          :selected-count="selectedRows.length"
          :active-filter-count="activeFilterCount"
          :sort-text="sortText"
          primary-field="sourceCode"
          primary-label="来源编码"
          :primary-width="180"
          min-width="2780px"
          :show-action-column="false"
          :show-refresh="false"
          :default-page-size="20"
          :page-sizes="[20, 50, 100, 200]"
          @update:quick-search="quickSearch=$event"
          @search="appliedSearch=quickSearch"
          @toggle-advanced="advancedVisible=!advancedVisible"
          @clear-filters="clearFilters"
          @clear-sort="clearSort"
          @export-current="exportCurrent"
          @clear-selection="clearSelection"
          @update-filter="updateFilter"
          @selection-change="selectedRows=$event"
        >
          <template #primary="{ row }"><span>{{ row.sourceCode || '来源未提供编码' }}</span></template>
          <template #columns>
            <el-table-column prop="sourceFile" label="来源文件" width="170" />
            <el-table-column prop="sourceSheet" label="工作表" width="120" />
            <el-table-column prop="sourceRow" label="来源行号" width="105" />
            <el-table-column label="来源对象类型" width="190"><template #default="{row}">{{ label(row.sourceObjectType) }}</template></el-table-column>
            <el-table-column prop="sourceName" label="来源名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="specification" label="规格 / 来源计算语义" min-width="190" show-overflow-tooltip />
            <el-table-column prop="sourceCategory" label="来源分类" width="180" show-overflow-tooltip />
            <el-table-column prop="rawUom" label="来源计量单位" width="110"><template #default="{row}">{{ row.rawUom || '未维护' }}</template></el-table-column>
            <el-table-column label="来源身份状态" width="185"><template #default="{row}">{{ label(row.sourceIdentityStatus) }}</template></el-table-column>
            <el-table-column label="现有正式数据匹配" min-width="210"><template #default="{row}">{{ canonicalMatch(row) }}</template></el-table-column>
            <el-table-column label="候选对象" width="150"><template #default="{row}">{{ label(row.candidateObject) }}</template></el-table-column>
            <el-table-column label="正式编码策略" min-width="230"><template #default="{row}">{{ label(row.canonicalCodePolicy) }}</template></el-table-column>
            <el-table-column label="计量单位处理" min-width="180"><template #default="{row}">{{ uomDecision(row) }}</template></el-table-column>
            <el-table-column label="校验状态" width="165"><template #default="{row}">{{ label(row.validationStatus) }}</template></el-table-column>
            <el-table-column label="建议处理" width="190"><template #default="{row}">{{ label(row.recommendedDecision) }}</template></el-table-column>
            <el-table-column label="车间 / 工作中心" min-width="210"><template #default="{row}">{{ resourceDecision(row) }}</template></el-table-column>
            <el-table-column prop="reason" label="原因" min-width="320" show-overflow-tooltip />
          </template>
        </PceEnterpriseListTable>
      </section>

      <section class="commit-readiness" data-acceptance-id="FOUNDATION_COMMIT_READINESS">
        <header>
          <div>
            <p class="eyebrow readiness-eyebrow">Foundation Wave 1 · DECOUPLED GATE REVIEW</p>
            <h2>3. 三 Gate 独立裁决与正式写入准备</h2>
            <p>工程代码、生产迁移和正式主数据写入分别裁决；任何 Gate 的就绪均不等于已获执行授权。</p>
          </div>
          <PceBusinessStatus
            :status-code="result.commitReadiness.status"
            :status-label="`正式写入准备：${readinessLabel(result.commitReadiness.status)}`"
            source="server"
          />
        </header>

        <div class="gate-grid" data-acceptance-id="FOUNDATION_DECOUPLED_GATES">
          <article v-for="gate in gateCards" :key="gate.key" :class="gate.tone">
            <span>{{ gate.label }}</span><strong>{{ gate.decision }}</strong><small>{{ gate.authorization }}</small>
          </article>
        </div>

        <div class="policy-decision">
          <span>当前来源级编码裁决</span>
          <strong>{{ result.commitReadiness.sourcePolicyDecision }}</strong>
          <small>{{ label(result.commitReadiness.sourcePolicy) }}</small>
        </div>

        <div class="readiness-grid">
          <article v-for="card in readinessCards" :key="card.key" :class="card.tone">
            <span>{{ card.label }}</span><strong>{{ card.value }}</strong>
          </article>
        </div>

        <div class="readiness-details">
          <article>
            <h3>正式写入链能力</h3>
            <ul>
              <li v-for="item in formalChainItems" :key="item.key">
                <span>{{ item.label }}</span><strong :class="item.status === 'READY' ? 'ready' : 'blocked'">{{ readinessLabel(item.status) }}</strong>
              </li>
            </ul>
          </article>
          <article>
            <h3>真实数据阻塞项</h3>
            <ol><li v-for="blocker in result.commitReadiness.blockers" :key="blocker">{{ blocker }}</li></ol>
            <p v-if="!result.commitReadiness.blockers.length">当前来源没有记录级阻塞。</p>
          </article>
          <article>
            <h3>业务复核项</h3>
            <ol><li v-for="item in result.commitReadiness.reviewItems" :key="item">{{ item }}</li></ol>
            <p v-if="!result.commitReadiness.reviewItems.length">无待复核项。</p>
          </article>
        </div>

        <div v-if="result.commitReadiness.rowExceptions.length" class="row-exceptions">
          <h3>仅需逐行处理的异常来源</h3>
          <div class="exception-table-wrap">
            <table>
              <thead><tr><th>来源行号</th><th>来源编码</th><th>来源名称</th><th>异常内容</th><th>正式写入候选</th></tr></thead>
              <tbody><tr v-for="item in result.commitReadiness.rowExceptions" :key="`${item.sourceRow}:${item.sourceCode}`">
                <td>{{ item.sourceRow }}</td><td>{{ item.sourceCode }}</td><td>{{ item.sourceName }}</td><td>{{ item.issue }}</td><td>否 · 需修正来源</td>
              </tr></tbody>
            </table>
          </div>
        </div>

        <div class="authorization-bar">
          <span>AUTHORIZATION：Git Commit / Production Migration / Formal Write 均为 NOT_GRANTED · 授权后可写入 {{ result.commitReadiness.readyForAuthorizedWrite }}</span>
          <el-button type="primary" disabled data-acceptance-id="FOUNDATION_FORMAL_WRITE_DISABLED">
            正式写入 · 未授权
          </el-button>
        </div>
      </section>

      <details class="diagnostics">
        <summary>查看技术诊断与零写入证据</summary>
        <pre>{{ diagnostics }}</pre>
      </details>
    </template>
    <section v-else class="empty-state" data-acceptance-id="FOUNDATION_PREVIEW_EMPTY_STATE">
      <h2>尚未生成预览</h2><p>请选择一份批准来源文件，然后点击“执行只读预览”。</p>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { pdeApi } from '@/api/pde.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'

const selectedFile=ref(null),fileInput=ref(null),loading=ref(false),loadStatus=ref('empty_valid'),errorMessage=ref(''),result=ref(null)
const rows=computed(()=>result.value?.rows||[])
const labelMap={
  SEMI_FINISHED_MATERIAL_SOURCE:'半成品物料来源',PURCHASE_MATERIAL_SOURCE:'采购物料来源',MANUFACTURING_OPERATION_SOURCE:'制造工序来源',
  SOURCE_IDENTITY_VERIFIED:'来源身份已确认',MATERIAL:'物料',OPERATION:'制造工序',
  REUSE_EXISTING_CODE:'复用现有正式编码',GENERATE_FORMAL_MATERIAL_CODE:'由统一物料编码规则生成',GENERATE_CANONICAL_CODE_PENDING_APPROVAL:'提交时由正式编码规则生成',
  EXACT_MATCH:'精确匹配',NORMALIZED_MATCH:'规范化匹配',SEMANTIC_REVIEW:'语义复核',INVALID:'无效',UNIT_NOT_CONFIRMED:'来源未提供单位',EXISTING_UOM_REUSE:'正式单位已存在',STANDARD_INITIALIZATION_READY:'标准单位初始化已就绪',BASIS_ONLY_READY:'核算维度已就绪（具体单位可选）',
  READY_FOR_DECISION:'来源完整，可进入后续决策',INCOMPLETE_SOURCE:'来源不完整',UOM_INVALID:'单位无效',CONFLICT:'冲突',
  EXISTING_REUSE:'复用现有正式对象',NEW_MATERIAL_CANDIDATE:'新增物料候选',NEW_OPERATION_CANDIDATE:'新增工序候选',UNRESOLVED:'待人工裁决',
  FORMAL_OPERATION_AND_WORKSHOP_CODE_RULE_READY:'工序与车间正式编码规则已具备',
}
const label=value=>labelMap[value]||value||'未维护'
const readinessLabel=value=>({READY:'已具备',REVIEW:'待业务复核',BLOCKED:'被阻塞',PARTIAL:'部分具备',APPLIED:'已应用',READY_NOT_APPLIED:'迁移已就绪、未执行',AWAITING_USER_REVIEW:'等待人工验收'}[value]||value)
const filterSchema=[
  {field:'sourceFile',label:'来源文件',filterType:'select',options:[{label:'05半成品板材.xlsx',value:'05半成品板材.xlsx'},{label:'10采购物料.xlsx',value:'10采购物料.xlsx'},{label:'01工序.xlsx',value:'01工序.xlsx'}]},
  {field:'candidateObject',label:'候选类型',filterType:'select',options:[{label:'物料',value:'MATERIAL'},{label:'制造工序',value:'OPERATION'}]},
  {field:'validationStatus',label:'校验状态',filterType:'select',options:[{label:'可进入后续决策',value:'READY_FOR_DECISION'},{label:'来源不完整',value:'INCOMPLETE_SOURCE'},{label:'语义复核',value:'SEMANTIC_REVIEW'},{label:'单位无效',value:'UOM_INVALID'},{label:'冲突',value:'CONFLICT'}]},
  {field:'uomStatus',label:'UOM状态',filterType:'select',options:[{label:'正式单位已存在',value:'EXISTING_UOM_REUSE'},{label:'标准单位初始化已就绪',value:'STANDARD_INITIALIZATION_READY'},{label:'核算维度已就绪',value:'BASIS_ONLY_READY'},{label:'来源未提供单位',value:'UNIT_NOT_CONFIRMED'},{label:'语义复核',value:'SEMANTIC_REVIEW'}]},
  {field:'recommendedDecision',label:'建议决定',filterType:'select',options:[{label:'复用现有',value:'EXISTING_REUSE'},{label:'新增物料候选',value:'NEW_MATERIAL_CANDIDATE'},{label:'新增工序候选',value:'NEW_OPERATION_CANDIDATE'},{label:'待人工裁决',value:'UNRESOLVED'}]},
]
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'foundation-manufacturing-import-preview',pageType:'preview',title:'制造基础数据导入预览',moduleCode:'PDE'})
const runtime=usePceEnterpriseListRuntime({rows,filterSchema,pageCode:'foundation-manufacturing-import-preview',searchFields:['sourceCode','sourceName','sourceCategory','rawUom','reason'],exportFileName:'foundation-wave1-preview.csv',exportColumns:[{field:'sourceFile',label:'来源文件'},{field:'sourceRow',label:'来源行号'},{field:'sourceCode',label:'来源编码'},{field:'sourceName',label:'来源名称'},{field:'candidateObject',label:'候选对象'},{field:'validationStatus',label:'校验状态'},{field:'recommendedDecision',label:'建议决定'}]})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,clearSort,clearSelection,exportCurrent}=runtime
function updateFilter(field,value){filters[field]=value}
function selectFile(event){selectedFile.value=event.target.files?.[0]||null;errorMessage.value='';result.value=null;loadStatus.value='empty_valid'}
async function preview(){
  if(!selectedFile.value)return
  loading.value=true;loadStatus.value='loading';errorMessage.value=''
  try{
    const response=await pdeApi.previewFoundationImport(selectedFile.value)
    if(!response.success)throw new Error(response.error?.message||'制造基础数据预览失败。')
    if(!response.data?.commitReadiness)throw new Error('后端运行进程尚未加载正式写入准备版本，请刷新页面后重试。')
    result.value=response.data;loadStatus.value=response.data?.factLoadStatus||'loaded';clearFilters()
    ElMessage.success(`已生成 ${response.data?.statistics?.total||0} 条只读候选；正式主数据写入为0。`)
  }catch(error){result.value=null;loadStatus.value='read_failed';errorMessage.value=error?.message||String(error)}finally{loading.value=false}
}
const statisticCards=computed(()=>result.value?[
  {key:'verified',label:'SOURCE IDENTITY VERIFIED',value:result.value.statistics.sourceIdentityVerified,tone:'ok'},
  {key:'reuse',label:'EXISTING REUSE',value:result.value.statistics.existingReuse,tone:'ok'},
  {key:'material',label:'NEW MATERIAL CANDIDATE',value:result.value.statistics.newMaterialCandidate,tone:'info'},
  {key:'operation',label:'SOURCE OPERATION CANDIDATES',value:result.value.statistics.sourceOperationCandidates,tone:'info'},
  {key:'incomplete',label:'INCOMPLETE SOURCE',value:result.value.statistics.incompleteSource,tone:'warn'},
  {key:'code',label:'CANONICAL CODE PENDING',value:result.value.statistics.canonicalCodePending,tone:'warn'},
  {key:'uom',label:'UOM PENDING',value:result.value.statistics.uomPending,tone:'warn'},
  {key:'conflict',label:'CONFLICT',value:result.value.statistics.conflict,tone:'danger'},
]:[])
const protectionCards=computed(()=>result.value?[['existingMaterial','Material'],['existingUom','UOM'],['existingProduct','Product'],['existingOperation','Operation'],['existingWorkshop','Workshop'],['existingWorkCenter','WorkCenter'],['existingSupplier','Supplier'],['existingCustomer','Customer']].map(([key,label])=>({key,label,value:result.value.protection[key]})):[])
const readinessCards=computed(()=>result.value?[
  {key:'candidates',label:'正式写入候选',value:result.value.commitReadiness.formalCommitCandidates,tone:'info'},
  {key:'ready',label:'READY',value:result.value.commitReadiness.ready,tone:'ok'},
  {key:'review',label:'REVIEW',value:result.value.commitReadiness.review,tone:'warn'},
  {key:'blocked',label:'BLOCKED',value:result.value.commitReadiness.blocked,tone:'danger'},
  {key:'incomplete',label:'排除：来源不完整',value:result.value.commitReadiness.excludedIncomplete,tone:'warn'},
  {key:'reuse',label:'现有正式对象复用',value:result.value.commitReadiness.existingReuse,tone:'ok'},
  {key:'codeReady',label:'正式编码已具备',value:result.value.commitReadiness.canonicalCodeReady,tone:'ok'},
  {key:'codePending',label:'正式编码待处理',value:result.value.commitReadiness.canonicalCodePending,tone:'warn'},
  {key:'uomReady',label:'计量单位已具备',value:result.value.commitReadiness.uomReady,tone:'ok'},
  {key:'uomPending',label:'计量单位待处理',value:result.value.commitReadiness.uomPending,tone:'warn'},
  {key:'identityReady',label:'来源身份持久化已具备',value:result.value.commitReadiness.sourceIdentityPersistenceReady,tone:'ok'},
  {key:'identityBlocked',label:'来源身份持久化被阻塞',value:result.value.commitReadiness.sourceIdentityPersistenceBlocked,tone:'danger'},
  ...(result.value.source.candidateType==='OPERATION'?[
    {key:'workshop',label:'车间候选',value:result.value.commitReadiness.workshopCandidateCount,tone:'info'},
    {key:'workcenter',label:'工作中心候选',value:result.value.commitReadiness.workCenterCandidateCount,tone:'ok'},
  ]:[]),
  {key:'service',label:'正式写入服务',value:readinessLabel(result.value.commitReadiness.formalWriteServiceReady?'READY':'BLOCKED'),tone:result.value.commitReadiness.formalWriteServiceReady?'ok':'danger'},
  {key:'auth',label:'权限与审计链',value:readinessLabel(result.value.commitReadiness.authorizationAuditReady?'READY':'BLOCKED'),tone:result.value.commitReadiness.authorizationAuditReady?'ok':'danger'},
  {key:'final',label:'授权后可正式写入',value:result.value.commitReadiness.readyForAuthorizedWrite,tone:'info'},
]:[])
const gateCards=computed(()=>{
  const gates=result.value?.commitReadiness?.gateDecisions
  if(!gates)return []
  return [
    {key:'A',label:'Gate A · 工程代码提交就绪',decision:gates.engineeringCodeCommitReadiness,authorization:`Git Commit：${gates.gitCommitAuthorization}`,tone:gates.engineeringCodeCommitReadiness==='GO'?'ok':'danger'},
    {key:'B',label:'Gate B · 生产迁移就绪',decision:gates.productionMigrationReadiness,authorization:`Production Migration：${gates.productionMigrationAuthorization}`,tone:gates.productionMigrationReadiness==='GO'?'ok':'danger'},
    {key:'C',label:'Gate C · 正式主数据写入就绪',decision:gates.formalMasterDataWriteReadiness,authorization:`Formal Write：${gates.formalMasterDataWriteAuthorization}`,tone:gates.formalMasterDataWriteReadiness==='GO'?'ok':'warn'},
  ]
})
const formalChainLabels={transaction:'事务边界',modelValidation:'模型校验',identityResolution:'来源身份解析',authorization:'组织权限',organizationAudit:'组织审计',serverReadback:'服务端回读',idempotency:'幂等与重复提交保护',migration:'迁移准备'}
const formalChainItems=computed(()=>Object.entries(result.value?.commitReadiness?.formalChain||{}).map(([key,status])=>({key,label:formalChainLabels[key]||key,status})))
const canonicalMatch=row=>row.existingCanonicalMatch?`${row.existingCanonicalMatch.code||'—'} / ${row.existingCanonicalMatch.name}`:'无精确匹配'
const uomDecision=row=>row.existingUomMatch?`${label(row.uomDecision)}：${row.existingUomMatch.code} / ${row.existingUomMatch.name}`:label(row.uomDecision)
const resourceDecision=row=>row.candidateObject==='OPERATION'?`${row.workshop?.sourceName||'车间待确认'} / WorkCenter未维护`:'不适用'
const diagnostics=computed(()=>JSON.stringify({source:result.value?.source,validationAction:result.value?.validationAction,authorization:result.value?.authorization,operationBoundary:result.value?.operationBoundary,commitReadiness:result.value?.commitReadiness,protection:result.value?.protection},null,2))
</script>

<style scoped>
.foundation-import-preview{width:100%;max-width:100%;min-width:0;padding:24px;box-sizing:border-box;overflow-x:hidden;color:#18243a}.hero,.source-panel,.source-identity,.boundary-banner,.statistics,.protection,.candidate-list,.commit-readiness,.diagnostics,.empty-state{border:1px solid #dce4f0;border-radius:16px;background:#fff;padding:20px 22px;margin-bottom:18px;box-sizing:border-box}.hero{display:flex;justify-content:space-between;gap:24px;align-items:center;background:linear-gradient(135deg,#183d73,#315bcf);color:#fff}.hero h1,.hero p,.source-panel h2,.source-panel p,.protection h2,.protection p,.candidate-list h2,.candidate-list p,.commit-readiness h2,.commit-readiness p{margin:0}.hero h1{font-size:30px;margin:5px 0 8px}.eyebrow{font-size:12px;letter-spacing:.08em;opacity:.8}.source-panel{display:grid;gap:15px}.source-actions{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.source-identity,.statistics,.protection-grid,.readiness-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.source-identity article,.statistics article,.protection-grid article,.readiness-grid article{display:grid;gap:6px;padding:14px;border-radius:12px;background:#f6f8fc}.source-identity span,.statistics span,.protection-grid span,.readiness-grid span{font-size:12px;color:#627089}.source-identity .hash{grid-column:span 2}.source-identity .hash strong{font-size:11px;word-break:break-all}.boundary-banner{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;background:#fff8e7}.boundary-banner div{display:grid;gap:6px}.statistics article,.readiness-grid article{border-left:4px solid #315bcf}.statistics .warn,.readiness-grid .warn{border-left-color:#d98b00}.statistics .danger,.readiness-grid .danger{border-left-color:#d13b3b}.statistics strong,.readiness-grid strong{font-size:25px}.protection header,.candidate-list>header,.commit-readiness>header{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:14px}.readiness-eyebrow{color:#315bcf}.policy-decision{display:grid;gap:6px;padding:16px;margin-bottom:14px;border-radius:12px;background:#eef4ff;border:1px solid #cad9ff}.policy-decision span,.policy-decision small{color:#5d6b82}.readiness-details{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin-top:14px}.readiness-details article{padding:16px;border-radius:12px;background:#f7f9fc}.readiness-details h3,.row-exceptions h3{margin:0 0 10px}.readiness-details ul,.readiness-details ol{margin:0;padding-left:22px}.readiness-details li{margin:7px 0}.readiness-details ul li{display:flex;justify-content:space-between;gap:14px}.ready{color:#16794c}.blocked{color:#b42318}.row-exceptions{margin-top:14px;padding:16px;border-radius:12px;background:#fff8e7}.exception-table-wrap{overflow-x:auto}.row-exceptions table{width:100%;border-collapse:collapse;font-size:13px}.row-exceptions th,.row-exceptions td{padding:9px;text-align:left;border-bottom:1px solid #eadfbe;white-space:nowrap}.authorization-bar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:16px;padding-top:16px;border-top:1px solid #e1e7f0;font-weight:700}.diagnostics summary{cursor:pointer;font-weight:700}.diagnostics pre{white-space:pre-wrap;word-break:break-word;background:#101828;color:#d9e7ff;border-radius:10px;padding:14px;max-height:420px;overflow:auto}.empty-state{text-align:center;padding:54px}.empty-state h2{margin-top:0}@media(max-width:760px){.foundation-import-preview{padding:14px}.hero,.protection header,.commit-readiness>header,.authorization-bar{align-items:flex-start;flex-direction:column}.source-identity .hash{grid-column:span 1}}
.gate-grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:12px;margin-bottom:14px}.gate-grid article{display:grid;gap:7px;padding:16px;border:1px solid #dce4f0;border-left:5px solid #16794c;border-radius:12px;background:#f7fbf9}.gate-grid article.warn{border-left-color:#d98b00;background:#fffaf0}.gate-grid article.danger{border-left-color:#d13b3b;background:#fff6f5}.gate-grid span,.gate-grid small{color:#5d6b82}.gate-grid strong{font-size:24px}@media(max-width:760px){.gate-grid{grid-template-columns:1fr}}
</style>
