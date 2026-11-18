<template>
  <section ref="previewTop" class="handoff" data-acceptance-id="order-bom-handoff-preview">
    <h2>正式工程核算 → 订单BOM承接预览</h2>
    <el-alert :title="facts.modeLabel" type="warning" show-icon :closable="false" />
    <p>本区只读，不生成需求、不占用BOM编号、不保存或发布。工程结果位置数不等于BOM明细数。</p>
    <label>选择已完成核算的订单
      <select aria-label="承接订单" :value="facts.selectedOrderId || ''" @change="$emit('select-order', $event.target.value)">
        <option value="">请选择订单</option>
        <option v-for="order in facts.orders" :key="order.id" :value="order.id">{{ order.orderNo }}</option>
      </select>
    </label>
    <p class="muted">正常账号：{{ facts.account }} · 公司 {{ facts.companyId }} · 当前主数据核对时间：{{ facts.checkedAt }}</p>
    <div v-if="facts.selectedOrderId">
      <div class="local-toolbar">
        <h3>{{ facts.selectedOrderNo }} · {{ selectedRecord ? `第${selectedRecord.lineNo}行承接详情` : '整单承接汇总' }}</h3>
        <div v-if="selectedRecord" class="return-actions" aria-label="承接详情返回导航">
          <el-button type="primary" plain data-acceptance-id="return-object-list" @click="returnObjectList">返回对象清单</el-button>
          <el-button type="primary" plain data-acceptance-id="return-handoff-summary" @click="returnSummary">返回整单承接汇总</el-button>
        </div>
      </div>
      <p>{{ facts.records.length }}份正式核算 · {{ facts.objectCount }}个稳定对象 · {{ facts.factCount }}个已保存结果位置 · {{ facts.candidateCount }}项正式材料需求映射候选</p>
      <p>当前公司已发布的材料／工序需求产出规则候选：{{ facts.currentRequirementRuleCandidates.length }}套（存在也须另核适用性）。</p>
      <section class="gate-panel" data-acceptance-id="bom-handoff-gate">
        <div class="local-toolbar">
          <div>
            <h3>订单用途与BOM承接门禁</h3>
            <p><strong>Business Purpose：</strong>{{ facts.selectedOrder?.businessPurpose?.code }}（{{ facts.selectedOrder?.businessPurpose?.statusLabel }}）</p>
          </div>
          <PceBusinessStatus :status-label="facts.bomHandoffStatus?.statusLabel" source="server" />
        </div>
        <p class="purpose-boundary">{{ facts.selectedOrder?.businessPurpose?.boundary }}</p>
        <p><strong>门禁代码：</strong><code>{{ facts.bomHandoffStatus?.code }}</code></p>
        <p class="gate-message">{{ facts.bomHandoffStatus?.message }}</p>
        <div class="gate-facts">
          <article><small>稳定工程对象</small><strong>{{ facts.objectCount }}</strong></article>
          <article><small>缺Material业务组</small><strong>{{ confirmationPackage.missingMaterialBusinessGroupCount ?? 0 }}</strong></article>
          <article><small>Mapping确认卡</small><strong>{{ confirmationPackage.formalMaterialMappingCardCount ?? 0 }}</strong></article>
          <article><small>已确认Mapping</small><strong>{{ confirmationPackage.confirmedMappingCount ?? 0 }}</strong></article>
          <article><small>READY_FOR_REQUIREMENT</small><strong>{{ facts.materialRequirementPreview?.classificationCounts?.READY_FOR_REQUIREMENT ?? 0 }}</strong></article>
          <article><small>正式材料需求</small><strong>{{ facts.bomHandoffStatus?.formalEngineeringMaterialRequirementCount ?? 0 }}</strong></article>
          <article><small>整单待完成对象</small><strong>{{ facts.bomHandoffStatus?.remainingObjectCount ?? 0 }}</strong></article>
          <article><small>覆盖状态</small><strong>{{ facts.bomHandoffStatus?.coverageStatus }}</strong></article>
          <article><small>可预览Calculation</small><strong>{{ facts.bomHandoffStatus?.previewReadyCalculationCount ?? 0 }}</strong></article>
          <article><small>ProductBOM</small><strong>{{ facts.bomHandoffStatus?.productBomCount ?? 0 }}</strong></article>
          <article><small>BOMVersion</small><strong>{{ facts.bomHandoffStatus?.bomVersionCount ?? 0 }}</strong></article>
          <article><small>BOMItem</small><strong>{{ facts.bomHandoffStatus?.bomItemCount ?? 0 }}</strong></article>
          <article><small>正式制造资格</small><strong>{{ facts.bomHandoffStatus?.formalManufacturingEligible ? '允许继续门禁' : '禁止评审/发布' }}</strong></article>
        </div>
        <ul v-if="facts.bomHandoffStatus?.missingConditions?.length" class="missing-conditions">
          <li v-for="condition in facts.bomHandoffStatus.missingConditions" :key="condition.code"><strong>{{ condition.statusLabel }}：</strong>{{ condition.message }}</li>
        </ul>
        <div class="gate-actions">
          <el-button
            type="primary"
            data-acceptance-id="preview-bom-conditions"
            :loading="previewBusy"
            :disabled="!facts.bomHandoffStatus?.canPreview || previewBusy"
            @click="$emit('preview-bom', facts.records)"
          >{{ previewBusy ? '正在调用正式服务…' : '预览BOM条件' }}</el-button>
          <el-button
            data-acceptance-id="generate-bom-draft-disabled"
            :disabled="!facts.bomHandoffStatus?.canGenerate"
            :title="facts.bomHandoffStatus?.generationDisabledReason"
          >生成BOM草稿</el-button>
        </div>
        <p class="muted">只读Preview仅检查条件：不生成材料需求、不创建BOM草稿、不占用BOM编号、不发布BOM，也不进入Routing或Planning。</p>
        <p class="draft-boundary"><strong>开发验证草稿边界：</strong>{{ facts.bomHandoffStatus?.generationDisabledReason }}</p>
        <p class="draft-boundary"><strong>正式制造资格裁决：</strong><code>{{ facts.bomHandoffStatus?.formalManufacturingDecisionCode }}</code> · {{ facts.bomHandoffStatus?.formalManufacturingMessage }}</p>
        <details v-if="previewState" open data-acceptance-id="bom-preview-gate-detail">
          <summary>{{ previewState.statusLabel }} · 查看本次真实服务返回</summary>
          <p><strong>状态代码：</strong><code>{{ previewState.code }}</code></p>
          <p>{{ previewState.message }}</p>
          <p>已检查 {{ previewState.attemptCount }} 个Calculation；受阻 {{ previewState.blockedCount }}；形成预览 {{ previewState.previewCount }}；业务写入 {{ previewState.businessWriteSideEffectCount }}。</p>
          <p>调用：{{ facts.bomHandoffStatus?.previewService?.method }} {{ facts.bomHandoffStatus?.previewService?.api }} → {{ facts.bomHandoffStatus?.previewService?.service }}</p>
          <ul>
            <li v-for="result in previewState.results" :key="result.calculationId">{{ result.calculationNo }}：{{ result.code }} · {{ result.message }}</li>
          </ul>
        </details>
      </section>
      <section class="confirmed-requirements" data-acceptance-id="confirmed-representative-material-requirements">
        <div class="local-toolbar">
          <div>
            <h3>已确认代表性 Mapping / Material Requirement</h3>
            <p>{{ confirmationPackage.modeLabel }}</p>
          </div>
          <PceBusinessStatus status-label="仅代表对象已确认，整单未完成" source="server" />
        </div>
        <p>只展示正式持久化 Readback；页面本次读取业务写入 {{ confirmationPackage.databaseBusinessWriteCount ?? 0 }}。已确认 {{ confirmationPackage.confirmedMappingCount ?? 0 }} 个Mapping/Requirement关系，仍有 {{ confirmationPackage.pendingDecisionUnitCount ?? 0 }} 个业务确认单元待处理。</p>
        <div v-if="formalRequirements.length" class="requirement-grid">
          <article v-for="row in formalRequirements" :key="row.id" class="requirement-card">
            <h4>{{ row.mappingNo }} · {{ row.designItemNo }}</h4>
            <p><strong>Material{{ row.materialId }} · {{ row.materialCode }} {{ row.materialName }}</strong></p>
            <p>Saved Fact / Detail：#{{ row.sourceFactId }} / #{{ row.sourceDetailId }}；Calculation：{{ row.calculationNo }}</p>
            <p>净需求 {{ row.netQuantity }} {{ row.uom }}；grossQuantity {{ row.grossQuantity ?? 'NULL' }}；scrapRate {{ row.scrapRate ?? 'NULL' }}</p>
            <p>{{ row.scrapStatusLabel }}</p>
            <p>{{ row.quantityBasis }} / {{ row.salesItemMultiplier }}；ProductDesignItem 再乘：否；重算：{{ row.calculationReexecuted ? '是' : '否' }}</p>
            <p>Mapping：#{{ row.confirmedMappingId ?? row.mappingRuleId }} · {{ row.mappingRuleCode }} / {{ row.mappingVersion }}；EngineeringMaterialRequirement{{ row.id }}</p>
            <p>ExternalIdentity{{ row.sourceExternalIdentity?.id ?? '待确认' }} · {{ row.sourceExternalIdentity?.externalId || '未回读' }}</p>
            <PceBusinessStatus :status-label="row.acceptanceStatusLabel || '待确认'" source="server" />
          </article>
        </div>
        <p v-else>当前没有正式代表性材料需求。</p>
      </section>
      <div v-show="!selectedRecord" class="record-grid">
        <article v-for="record in facts.records" :key="record.calculationId" class="record">
          <h4>第{{ record.lineNo }}行 · {{ record.calculationNo }} / R{{ record.revision }}</h4>
          <p>实例：{{ record.instanceNo }}</p>
          <p>基线：{{ record.baseline.baselineNo }}</p>
          <p>来源 #{{ record.source.id }} · {{ record.source.sourceVersion }}</p>
          <p>{{ record.objectCount }}对象／{{ record.factCount }}结果位置；已引用物料 {{ record.materialReferencedCount }}对象</p>
          <p>正式材料需求 {{ record.materialRequirementCount }}／工序需求 {{ record.operationRequirementCount }}／关联BOM版本 {{ record.existingVersions.length }}</p>
          <PceBusinessStatus :status-label="record.statusLabel" source="server" />
          <el-button type="primary" plain @click="showLine(record)">查看第{{ record.lineNo }}行承接详情</el-button>
        </article>
      </div>
      <article v-if="selectedRecord" class="record">
        <p>{{ selectedRecord.calculationNo }} / R{{ selectedRecord.revision }} · {{ selectedRecord.instanceNo }} · {{ selectedRecord.baseline.baselineNo }}</p>
        <h4>分阶段资格（不代表本轮获准执行）</h4>
        <p v-for="stage in selectedRecord.stages" :key="stage.name"><strong>{{ stage.name }}：</strong>{{ stage.statusLabel }}</p>
        <h4>已有正式对象（与未保存预览分开）</h4>
        <p>材料需求 {{ selectedRecord.materialRequirementCount }}；工序需求 {{ selectedRecord.operationRequirementCount }}；制造定义 {{ selectedRecord.existingManufacturingOutputCount }}</p>
        <p v-if="!selectedRecord.existingVersions.length">本实例当前无关联正式BOM版本。</p>
        <p v-for="version in selectedRecord.existingVersions" :key="version.id">{{ version.bomCode }} / {{ version.version }} · {{ version.statusLabel }}</p>
        <p v-if="selectedRecord.formalRequirementPreviewError">原正式需求预览未通过：{{ selectedRecord.formalRequirementPreviewError.message }}</p>
      </article>
      <div v-show="!detailObject" ref="objectListTop" class="object-list" data-acceptance-id="handoff-object-list">
        <h3>稳定对象覆盖清单 · {{ selectedRecord ? `第${selectedRecord.lineNo}行` : '整单' }}</h3>
        <PceEnterpriseListTable
          ref="tableRef" :contract="contract" page-id="pde-product-boms-handoff" table-id="pde-bom-handoff-objects"
          :rows="objects" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
          :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
          :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="objectNo" primary-label="稳定工程对象编号"
          min-width="1550px" @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
          @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort"
          @export-current="exportCurrent" @clear-selection="clearSelection" @update-filter="(field, value) => filters[field] = value"
          @selection-change="selectedRows = $event" @sort-change="handleSort">
          <template #columns>
            <el-table-column prop="lineNo" label="订单行" width="90" sortable />
            <el-table-column prop="objectName" label="对象名称（基线）" width="180" show-overflow-tooltip />
            <el-table-column prop="sourceKey" label="稳定来源位置" width="190" />
            <el-table-column prop="materialLabel" label="物料引用（当前核对）" width="300" show-overflow-tooltip />
            <el-table-column prop="physicalQuantity" label="保存对象数量" width="140" />
            <el-table-column prop="physicalUnit" label="保存单位" width="100" />
            <el-table-column prop="factCount" label="结果位置数" width="110" sortable />
            <el-table-column prop="formalMaterialRequirementCount" label="正式材料需求" width="120" sortable />
            <el-table-column prop="gapCount" label="待补问题数" width="110" sortable />
            <el-table-column label="承接状态" width="170"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" source="server" /></template></el-table-column>
          </template>
          <template #actions="{ row }"><el-button plain @click="showObject(row)">查看依据与缺项</el-button></template>
        </PceEnterpriseListTable>
      </div>
      <article v-if="detailObject" ref="objectTop" class="record object-detail">
        <div class="local-toolbar"><h3>{{ detailObject.objectName }} · {{ detailObject.sourceKey }}</h3><el-button type="primary" plain @click="returnObjectList">返回对象清单</el-button></div>
        <p>第{{ detailObject.lineNo }}行 · {{ detailObject.objectNo }} · 基线对象 #{{ detailObject.baselineItemId }}</p>
        <h4>已保存依据，不重新计算</h4>
        <p>对象数量 {{ detailObject.physicalQuantity }} {{ detailObject.physicalUnit }}；尺寸 {{ detailObject.savedInput.designLength }} × {{ detailObject.savedInput.designWidth }} × {{ detailObject.savedInput.designThickness }}（单位按保存输入ID核对，不猜换算）</p>
        <p>本批正式BOM父子关联：未确认，不把分类树当BOM。历史已获批的来源配置和三层角色继续保留，不要求重新确认；仍需与本批R1稳定对象建立合法承接关系。候选材料用量：未确认（不是0）。</p>
        <p>{{ detailObject.scrapExplanation }}</p>
        <p>{{ detailObject.unitContractLabel }}</p>
        <section v-if="detailObject.formalMaterialRequirements?.length" class="formal-requirement-readback">
          <h4>已保存正式 Material Requirement</h4>
          <p v-for="row in detailObject.formalMaterialRequirements" :key="row.id">
            {{ row.mappingNo }} / Material{{ row.materialId }} / {{ row.materialCode }}：净需求 {{ row.netQuantity }} {{ row.uom }}；
            Mapping #{{ row.mappingRuleId }}；EngineeringMaterialRequirement{{ row.id }}；ExternalIdentity{{ row.sourceExternalIdentity?.id ?? '待确认' }}；
            {{ row.acceptanceStatusLabel || '待确认' }}；grossQuantity {{ row.grossQuantity ?? 'NULL' }}；{{ row.scrapStatusLabel }}；重算：{{ row.calculationReexecuted ? '是' : '否' }}。
          </p>
        </section>
        <h4>当前物料与路线（不是补写历史输入）</h4>
        <p>{{ detailObject.materialLabel }}；{{ detailObject.applicabilityLabel }}</p>
        <div v-if="detailObject.material">
          <p>规格：{{ detailObject.material.specification || '未维护' }}；{{ detailObject.material.materialType }}／{{ detailObject.material.supplyLabel }}；基础单位：{{ detailObject.material.baseUnit?.name || '未确认' }}；{{ detailObject.material.active ? '启用' : '停用' }}</p>
          <p>{{ detailObject.material.versionLabel }}；更新于 {{ detailObject.material.updatedAt }}</p>
        </div>
        <p>保存工艺编码：{{ detailObject.savedInput.routingProcessCode || '未维护' }}。无已批准映射时，不把工艺编码直接当工序需求。</p>
        <details v-for="routing in objectRoutings" :key="routing.id">
          <summary>{{ routing.code }} · {{ routing.name }} · {{ routing.statusLabel }} · 查看当前版本/工序</summary>
          <p>{{ routing.identityLabel }}</p>
          <div v-for="version in routing.versions" :key="version.id">
            <p>{{ version.version }} · {{ version.statusLabel }} · {{ version.stepCount }}步骤；生效 {{ version.effectiveFrom }} 至 {{ version.effectiveTo }}</p>
            <p>其中 {{ version.missingOperationUnitCount }}步骤未声明工序核算单位；由工艺负责人确认哪些步骤需要正式作业量，不默认全部适用。</p>
            <p v-for="step in version.steps" :key="step.id">{{ step.sequence }}. {{ step.operationCode }} {{ step.operationName }}；正式数量单位：{{ step.unit?.name || '未维护' }}；投入量须另有规则，不推算工时。</p>
          </div>
        </details>
        <h4>具体待补问题与原维护位置</h4>
        <p>R1未引用物料不等于主数据不存在。已有来源配置/角色先复用核对，不修改或补写本次R1。<router-link to="/pde/engineering-calculations?subview=semi-finished-structure">原半成品物料结构（历史只读参考，不是本批正式BOM）</router-link></p>
        <p>原入口名称对照：基础资料 → 物料与供应 →「物料档案」「计量单位」；制造资源 →「工序」；产品工程 →「工艺路线」「工艺路线版本」「工程规则定义」；PDE →「产品设计管理」「工程核算 / 物料核算」「BOM管理」「BOM版本管理」。由已有权限的责任岗位后续办理，本轮只查看。</p>
        <section v-for="gap in detailObject.gaps" :key="gap.code" class="gap">
          <strong>{{ gap.field }} · {{ gap.kind }}</strong><p>{{ gap.evidence }}</p>
          <p>影响：{{ gap.stage }}；责任：{{ gap.owner }}</p><p>原维护位置：{{ gap.location }}</p>
        </section>
        <h4>{{ detailObject.factCount }}项实际保存结果及数量依据</h4>
        <details v-for="fact in detailObject.facts" :key="fact.factId" class="saved-fact">
          <summary>{{ fact.displayName }}：{{ fact.valueText }} {{ fact.unit || '未声明单位' }} · 查看保存依据</summary>
          <p>正式派生事实 #{{ fact.factId }} / 明细 #{{ fact.detailId }} / {{ fact.ruleCode }} {{ fact.ruleVersion }}</p>
          <p>{{ fact.quantityBasis.label }}</p><p>表达式：{{ fact.quantityBasis.expression }}</p>
          <p>{{ fact.quantityBasis.quantityDependencyLabel }}。{{ fact.quantityBasis.batchBasisLabel }}</p>
          <p v-for="input in fact.quantityBasis.inputs" :key="input.key">{{ input.name }}（{{ input.key }}）= {{ input.value }} {{ input.unit }}</p>
          <p>{{ fact.downstreamUseLabel }}</p>
        </details>
      </article>
    </div>
    <details><summary>当前账号权限与正式办理边界</summary><p v-for="permission in facts.permissions" :key="permission.name">{{ permission.name }}：{{ permission.statusLabel }}。{{ permission.reason }}</p><p>本轮没有保存、生成、发布入口。后续正式办理必须独立批准；无权限时由相应责任岗位办理，不扩权。</p></details>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
const props = defineProps({
  facts: { type: Object, required: true },
  previewState: { type: Object, default: null },
  previewBusy: { type: Boolean, default: false },
})
defineEmits(['select-order', 'preview-bom'])
const selectedRecord = ref(null)
const detailObject = ref(null)
const previewTop = ref(null)
const objectListTop = ref(null)
const objectTop = ref(null)
const confirmationPackage = computed(() => props.facts.materialRequirementPreview?.businessConfirmationPackage || {})
const formalRequirements = computed(() => props.facts.materialRequirementPreview?.formalRequirementRows || [])
const objects = computed(() => selectedRecord.value ? selectedRecord.value.objects : props.facts.records.flatMap(r => r.objects))
const objectRoutings = computed(() => props.facts.records.find(r => r.lineNo === detailObject.value?.lineNo)?.currentRoutings.filter(r => detailObject.value.routingCandidateIds.includes(r.id)) || [])
const filterSchema = [{ field: 'materialLabel', label: '物料引用', filterType: 'text' }, { field: 'sourceKey', label: '来源位置', filterType: 'text' }]
const contract = createPceEnterpriseListContract({ pageCode: 'pde-product-boms-handoff', pageType: 'list', title: '稳定对象承接清单', moduleCode: 'PDE' })
const runtime = usePceEnterpriseListRuntime({ rows: objects, filterSchema, pageCode: 'pde-product-boms-handoff', searchFields: ['objectNo', 'objectName', 'sourceKey', 'materialLabel'], exportFileName: 'BOM承接只读覆盖清单.csv', exportColumns: [{ field: 'objectNo', label: '对象编号' }, { field: 'materialLabel', label: '物料' }, { field: 'statusLabel', label: '承接状态' }] })
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef, activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection, handleSort, exportCurrent } = runtime
async function showLine(record) { selectedRecord.value = record; detailObject.value = null; await nextTick(); previewTop.value?.scrollIntoView({ block: 'start' }) }
async function returnObjectList() { detailObject.value = null; await nextTick(); objectListTop.value?.scrollIntoView({ block: 'start' }) }
async function returnSummary() { selectedRecord.value = null; detailObject.value = null; await nextTick(); previewTop.value?.scrollIntoView({ block: 'start' }) }
async function showObject(row) { detailObject.value = row; await nextTick(); objectTop.value?.scrollIntoView({ block: 'start' }) }
watch(() => props.facts, () => { selectedRecord.value = null; detailObject.value = null })
</script>

<style scoped>
.handoff { padding:20px; border:2px solid #91afd5; border-radius:12px; background:#fff; min-width:0; scroll-margin-top:80px; }
.handoff h2 { margin-top:0; }.handoff p { line-height:1.65; overflow-wrap:anywhere; }
.handoff select { margin:8px; padding:10px; border:1px solid #7189aa; border-radius:6px; max-width:100%; }
.local-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:14px; margin:14px 0; }
.return-actions { display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
.record-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr)); gap:12px; }
.record { padding:16px; border:1px solid #c4d3e4; border-radius:8px; margin:12px 0; background:#f8fbff; }
.record h4 { margin:8px 0; }.record .el-button { margin:12px 0; }.muted { color:#52647a; }
.gate-panel { margin:16px 0; padding:16px; border:1px solid #e3b35f; border-radius:10px; background:#fffaf0; }
.gate-panel h3 { margin:0; }.gate-panel code { font-weight:700; color:#7c3f00; }
.purpose-boundary,.gate-message { color:#5f4218; }
.draft-boundary { padding:10px 12px; border-left:4px solid #a85b1a; background:#fff3df; color:#6c3b12; }
.gate-facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:12px 0; }
.gate-facts article { display:grid; gap:4px; padding:10px; border-radius:8px; background:#fff; }
.gate-facts small { color:#687386; }.gate-facts strong { font-size:20px; }
.missing-conditions { margin:10px 0; padding-left:24px; }.missing-conditions li { margin:6px 0; line-height:1.6; }
.gate-actions { display:flex; flex-wrap:wrap; gap:10px; margin:14px 0; }
.gap { border-left:3px solid #c28128; padding:10px 14px; margin:10px 0; background:#fff8ec; }
.confirmed-requirements { margin:16px 0; padding:16px; border:1px solid #8bb99a; border-radius:10px; background:#f4fbf6; }
.confirmed-requirements h3 { margin:0; }.requirement-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr)); gap:12px; }
.requirement-card,.formal-requirement-readback { padding:14px; border:1px solid #b9d8c3; border-radius:8px; background:#fff; }
details { margin:10px 0; padding:10px; border:1px solid #d3deeb; border-radius:6px; background:#fff; }
summary { cursor:pointer; font-weight:600; line-height:1.6; }.object-list,.object-detail { scroll-margin-top:80px; }
</style>
