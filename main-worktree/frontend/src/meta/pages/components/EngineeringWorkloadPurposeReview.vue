<template>
  <section class="purpose-review" data-section="engineering-workload-purpose-review" data-fact-source="server">
    <h3>按用途分组与计划数量双列评审</h3>
    <p class="boundary">工程投产候选量、已确认计划投产量分别保留原单位和来源范围，均不等于已执行投产。工序负荷不累加为产品量；本页不分配、不排产。</p>
    <div v-if="!review" class="unknown" data-state="purpose-review-unknown"><p>用途评审尚未完整读取，候选量、计划量和负荷未知，未补为零。</p><div v-if="readFailure" data-cell="purpose-read-failure"><strong>{{ readFailure.statusLabel }}</strong><ul v-if="readFailure.missingReasons?.length"><li v-for="(reason, index) in readFailure.missingReasons" :key="index">{{ reasonLabel(reason) }}</li></ul></div></div>
    <template v-else>
      <PceBusinessStatus :status-label="review.statusLabel" source="server" />
      <p data-state="purpose-review-plan-access"><PceBusinessStatus :status-label="review.planningAccess?.statusLabel" source="server" /></p>
      <p class="boundary">记录数仅用于完整性核对：有效需求 {{ value(review.counts?.effectiveRequirementCount) }}；历史需求 {{ value(review.counts?.historicalRequirementCount) }}。历史需求仅供追溯。</p>
      <ul v-if="review.missingReasons?.length"><li v-for="(reason, index) in review.missingReasons" :key="index">{{ reasonLabel(reason) }}</li></ul>
      <section v-for="list in lists" :key="list.id" :data-section="list.id">
        <h4>{{ list.title }}</h4>
        <p>{{ list.description }}</p>
        <div v-if="list.kind === 'operationLoads'" class="load-explanation" data-cell="plan-load-explanation">
          <p v-for="group in planSourceGroups" :key="group.key">计划源数量：<span v-if="review.planningAccess?.allowed === true">{{ value(group.confirmedPlan?.quantity) }} {{ value(group.confirmedPlan?.uomLabel, '单位未知') }}</span><span v-else>{{ value(review.planningAccess?.statusLabel, '计划查看资格未知') }}</span>。{{ value(group.confirmedPlan?.scopeLabel, '计划范围未知') }}</p>
          <p>计划源数量与各步骤已分配的加工负荷分开表达，保留各自单位，不直接换算；各步骤负荷不累加为产品投产量。</p>
          <p v-if="paintPlanAreaUnknown">油漆计划对应面积未知：该计划面积指标尚无正式映射，不表示已保存的工序分配失败；请分别查看下表的有效需求量与已分配负荷。</p>
          <p>每行右侧直接显示工序、有效需求量、已分配计划负荷和分配状态；展开下方“查看对象贡献与来源依据”可追溯各对象。</p>
        </div>
        <PceEnterpriseListTable
          :ref="component => list.runtime.tableRef = component" :contract="list.contract"
          :page-id="list.id" :table-id="`${list.id}-table`"
          :rows="list.rows" :table-rows="list.runtime.filteredRows" :filter-schema="list.filterSchema"
          :filters="list.runtime.filters" :quick-search="list.runtime.quickSearch"
          :advanced-visible="list.runtime.advancedVisible" :selected-count="list.runtime.selectedRows.length"
          :active-filter-count="list.runtime.activeFilterCount" :sort-text="list.runtime.sortText"
          row-key="key" primary-field="purposeLabel" primary-label="业务用途" :primary-width="180"
          min-width="1900px" :action-label="list.kind === 'operationLoads' ? '工序负荷与分配状态' : '来源与准入依据'" :action-width="list.kind === 'operationLoads' ? 160 : 260"
          :class="{ 'operation-load-list': list.kind === 'operationLoads' }"
          :refreshing="refreshing" :default-page-size="20" :page-sizes="[20, 50, 100]"
          @update:quick-search="list.runtime.quickSearch = $event" @search="list.runtime.applySearch"
          @toggle-advanced="list.runtime.advancedVisible = !list.runtime.advancedVisible"
          @clear-filters="list.runtime.clearFilters" @clear-sort="list.runtime.clearSort"
          @export-current="list.runtime.exportCurrent" @clear-selection="list.runtime.clearSelection"
          @update-filter="list.runtime.updateFilter" @selection-change="list.runtime.handleSelectionChange"
          @sort-change="list.runtime.handleSort" @refresh="$emit('refresh')"
        >
          <template #primary="{ row }">{{ value(row.purposeLabel, '用途未知') }}</template>
          <template #columns>
            <el-table-column label="正式工艺与适用版本" min-width="190"><template #default="{ row }"><span>{{ value(row.dimensions?.routingCode, '工艺未知') }}</span><small>{{ value(row.dimensions?.routingVersionLabel, '适用版本未知') }}</small></template></el-table-column>
            <el-table-column label="制造模式／生产组" min-width="185"><template #default="{ row }">{{ value(row.dimensions?.manufacturingModeLabel, '制造模式未知') }}<small>模式版本：{{ value(row.dimensions?.manufacturingModeVersion) }}</small><small>生产组：{{ value(row.dimensions?.productionGroupLabel) }}</small></template></el-table-column>
            <el-table-column label="评审范围" min-width="190"><template #default="{ row }">{{ value(row.dimensions?.sourceScopeLabel, '对象范围未知') }}<small v-if="row.dimensions?.lineNo != null">第{{ row.dimensions.lineNo }}行 · 数据库行ID {{ value(row.dimensions.salesOrderItemId) }}</small></template></el-table-column>
            <template v-if="list.kind === 'groups'">
              <el-table-column label="工程投产候选量" min-width="195"><template #default="{ row }"><div data-cell="engineering-candidate">{{ value(row.engineeringCandidate?.quantity) }} {{ value(row.engineeringCandidate?.uomLabel, '单位未知') }}<small v-if="row.engineeringCandidate?.quantity == null && row.engineeringCandidate?.sourceQuantity != null">{{ value(row.engineeringCandidate.sourceQuantityLabel, '正式来源量') }} {{ row.engineeringCandidate.sourceQuantity }} {{ value(row.engineeringCandidate.uomLabel, '单位未知') }}</small><small>{{ value(row.engineeringCandidate?.statusLabel, '候选量状态未知') }}</small></div></template></el-table-column>
              <el-table-column label="已确认计划投产量" min-width="210"><template #default="{ row }"><div data-cell="confirmed-plan"><span v-if="review.planningAccess?.allowed === true">{{ value(row.confirmedPlan?.quantity) }} {{ value(row.confirmedPlan?.uomLabel, '单位未知') }}</span><span v-else>{{ value(review.planningAccess?.statusLabel, '计划查看资格未知') }}</span><small>{{ value(row.confirmedPlan?.statusLabel, '计划量状态未知') }}</small><small>{{ value(row.confirmedPlan?.scopeLabel, '计划范围未知') }}</small><small>{{ value(row.confirmedPlan?.sourceLabel, '计划来源未知') }}</small></div></template></el-table-column>
              <el-table-column label="同口径比较" min-width="185"><template #default="{ row }"><div data-cell="quantity-comparison"><span v-if="review.planningAccess?.allowed === true && row.comparison?.allowed === true">差额 {{ value(row.comparison.difference) }} {{ value(row.dimensions?.uomLabel, '单位未知') }}</span><small>{{ value(row.comparison?.statusLabel, '对应数量未知，未作比较') }}</small></div></template></el-table-column>
            </template>
            <template v-else-if="list.kind === 'operationLoads'">
              <el-table-column label="步骤／工序" min-width="180"><template #default="{ row }">步骤 {{ value(row.stepSequence) }}<small>{{ value(row.operationName, '工序未知') }}</small></template></el-table-column>
              <el-table-column label="工作中心" min-width="170"><template #default="{ row }">{{ value(row.workCenterLabel) }}</template></el-table-column>
              <el-table-column label="有效工序需求量" min-width="160"><template #default="{ row }">{{ value(row.effectiveQuantity) }} {{ value(row.uomLabel, '单位未知') }}</template></el-table-column>
              <el-table-column label="已分配计划负荷" min-width="195"><template #default="{ row }"><div data-cell="allocated-load"><span v-if="review.planningAccess?.allowed === true">{{ value(row.allocatedQuantity) }} {{ value(row.uomLabel, '单位未知') }}</span><span v-else>{{ value(review.planningAccess?.statusLabel, '计划查看资格未知') }}</span><small>{{ value(row.allocationStatusLabel, '分配状态未知') }}</small></div></template></el-table-column>
              <el-table-column label="匹配标准日产能" min-width="205"><template #default="{ row }"><div data-cell="matched-capacity">{{ value(row.capacity?.quantity) }} {{ value(row.capacity?.uomLabel, '单位未知') }} / {{ value(row.capacity?.timeBasisLabel, '时间基数未知') }}<small>{{ value(row.capacity?.statusLabel, '产能匹配未知') }}</small><small>{{ value(row.capacity?.capacityScopeLabel, '产能用途未证明') }}</small><small>{{ value(row.capacity?.applicabilityPeriodLabel, '适用期间未证明') }}</small></div></template></el-table-column>
              <el-table-column label="理论生产资源天" min-width="180"><template #default="{ row }"><div data-cell="theoretical-days">{{ value(row.capacity?.theoreticalResourceDaysLabel, '未知') }}<small>{{ value(row.capacity?.admissionStatusLabel, '不代表排产资格') }}</small></div></template></el-table-column>
            </template>
            <template v-else>
              <el-table-column label="历史工序需求" min-width="150"><template #default="{ row }">{{ value(row.operationRequirementId ?? row.id) }}<small>{{ value(row.operationName, '工序未知') }}</small></template></el-table-column>
              <el-table-column label="历史数量（仅追溯）" min-width="170"><template #default="{ row }">{{ value(row.workloadQuantity ?? row.quantity) }} {{ value(row.uomLabel, '单位未知') }}</template></el-table-column>
              <el-table-column label="正式替代关系" min-width="200"><template #default="{ row }">{{ value(row.replacementStatusLabel, '替代关系详见来源依据') }}<small>替代需求：{{ value(row.supersededById) }}</small></template></el-table-column>
            </template>
            <el-table-column prop="statusLabel" label="当前状态与边界" min-width="220"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel || row.allocationStatusLabel" source="server" /></template></el-table-column>
          </template>
          <template #actions="{ row }">
            <div v-if="list.kind === 'operationLoads'" class="operation-load-overview" data-cell="operation-load-overview">
              <strong>步骤 {{ value(row.stepSequence) }} · {{ value(row.operationName, '工序未知') }}</strong>
              <p><b>有效工序需求量</b><span>{{ value(row.effectiveQuantity) }} {{ value(row.uomLabel, '单位未知') }}</span></p>
              <p><b>已分配计划负荷</b><span v-if="review.planningAccess?.allowed === true">{{ value(row.allocatedQuantity) }} {{ value(row.uomLabel, '单位未知') }}</span><span v-else>{{ value(review.planningAccess?.statusLabel, '计划查看资格未知') }}</span></p>
              <p><b>分配状态</b><PceBusinessStatus :status-label="row.allocationStatusLabel" source="server" /></p>
            </div>
            <details class="trace"><summary>{{ value(row.purposeLabel, '用途未知') }}<small v-if="list.kind === 'operationLoads'">步骤 {{ value(row.stepSequence) }}</small><small v-else-if="list.kind === 'historyRequirements'">历史需求 {{ value(row.operationRequirementId ?? row.id) }}</small><small>{{ list.kind === 'operationLoads' ? '查看对象贡献与来源依据' : '查看来源与准入依据' }}</small></summary>
              <div data-cell="compact-review">
                <p><b>正式工艺：</b>{{ value(row.dimensions?.routingCode) }}；{{ value(row.dimensions?.routingVersionLabel, '适用版本未知') }}</p>
                <p><b>制造模式：</b>{{ value(row.dimensions?.manufacturingModeLabel) }}；模式版本 {{ value(row.dimensions?.manufacturingModeVersion) }}</p>
                <p><b>生产组：</b>{{ value(row.dimensions?.productionGroupLabel) }}；<b>评审范围：</b>{{ value(row.dimensions?.sourceScopeLabel) }}</p>
                <template v-if="list.kind === 'groups'">
                  <p><b>工程投产候选量：</b>{{ value(row.engineeringCandidate?.quantity) }} {{ value(row.engineeringCandidate?.uomLabel, '单位未知') }}<small>{{ value(row.engineeringCandidate?.statusLabel, '候选量状态未知') }}</small></p>
                  <p v-if="row.engineeringCandidate?.quantity == null && row.engineeringCandidate?.sourceQuantity != null">{{ value(row.engineeringCandidate.sourceQuantityLabel, '正式来源量') }}：{{ row.engineeringCandidate.sourceQuantity }} {{ value(row.engineeringCandidate.uomLabel, '单位未知') }}</p>
                  <p><b>已确认计划投产量：</b><span v-if="review.planningAccess?.allowed === true">{{ value(row.confirmedPlan?.quantity) }} {{ value(row.confirmedPlan?.uomLabel, '单位未知') }}</span><span v-else>{{ value(review.planningAccess?.statusLabel, '计划查看资格未知') }}</span><small>{{ value(row.confirmedPlan?.statusLabel, '计划量状态未知') }}</small><small>{{ value(row.confirmedPlan?.scopeLabel, '计划范围未知') }}；{{ value(row.confirmedPlan?.sourceLabel, '计划来源未知') }}</small></p>
                </template>
                <template v-else-if="list.kind === 'operationLoads'">
                  <p><b>步骤 {{ value(row.stepSequence) }}：</b>{{ value(row.operationName, '工序未知') }}；工作中心 {{ value(row.workCenterLabel) }}</p>
                  <p><b>有效工序需求量：</b>{{ value(row.effectiveQuantity) }} {{ value(row.uomLabel, '单位未知') }}</p>
                  <p><b>已分配计划负荷：</b><span v-if="review.planningAccess?.allowed === true">{{ value(row.allocatedQuantity) }} {{ value(row.uomLabel, '单位未知') }}</span><span v-else>{{ value(review.planningAccess?.statusLabel, '计划查看资格未知') }}</span><small>{{ value(row.allocationStatusLabel, '分配状态未知') }}</small></p>
                  <p><b>标准日产能：</b>{{ value(row.capacity?.quantity) }} {{ value(row.capacity?.uomLabel, '单位未知') }} / {{ value(row.capacity?.timeBasisLabel, '时间基数未知') }}<small>{{ value(row.capacity?.statusLabel, '产能匹配未知') }}</small><small>{{ value(row.capacity?.capacityScopeLabel, '产能用途未证明') }}；{{ value(row.capacity?.applicabilityPeriodLabel, '适用期间未证明') }}</small></p>
                  <p><b>理论生产资源天：</b>{{ value(row.capacity?.theoreticalResourceDaysLabel) }}<small>{{ value(row.capacity?.admissionStatusLabel, '不代表排产资格') }}</small></p>
                </template>
                <template v-else>
                  <p><b>历史需求 {{ value(row.operationRequirementId ?? row.id) }}：</b>{{ value(row.operationName, '工序未知') }}；{{ value(row.workloadQuantity ?? row.quantity) }} {{ value(row.uomLabel, '单位未知') }}</p>
                  <p><b>替代需求：</b>{{ value(row.supersededById) }}；{{ value(row.statusLabel, '历史状态未知') }}</p>
                </template>
              </div>
              <p>{{ value(row.admissionStatusLabel, '本行仅供只读评审，不代表分配或排产资格') }}</p>
              <p>公司：{{ value(row.dimensions?.companyLabel) }}（ID {{ value(row.dimensions?.companyId) }}）；产能产品类型：{{ value(row.dimensions?.productTypeLabel) }}（ID {{ value(row.dimensions?.productTypeId) }}）</p>
              <p>数量口径：{{ value(row.dimensions?.quantityBasisLabel) }}；正式单位：{{ value(row.dimensions?.uomLabel) }}（ID {{ value(row.dimensions?.uomId) }}）</p>
              <p>正式路线ID {{ value(row.dimensions?.routingId) }}；适用版本ID {{ value(row.dimensions?.routingVersionId) }}；制造模式ID {{ value(row.dimensions?.manufacturingModeId) }}</p>
              <p v-if="list.kind === 'operationLoads'">步骤ID {{ value(row.dimensions?.routingStepId) }}；工序ID {{ value(row.dimensions?.operationId) }}；工作中心ID {{ value(row.dimensions?.workCenterId) }}；标准产能ID {{ value(row.dimensions?.standardCapacityId) }}</p>
              <ul v-if="row.missingReasons?.length"><li v-for="(reason, index) in row.missingReasons" :key="index">{{ reasonLabel(reason) }}</li></ul>
              <p v-if="row.requirementIds?.length">有效需求：{{ row.requirementIds.join('、') }}</p>
              <p v-if="row.sourceCalculationId != null">来源核算 {{ row.sourceCalculationId }}；主核算 {{ value(row.originCalculationId) }}；事实 {{ value(row.sourceFactId) }}</p>
              <article v-for="(source, index) in row.contributions || []" :key="source.key || index">
                <div data-cell="contribution-trace">
                <b>{{ sourceObjectName(source) }}</b>
                <p class="contribution-quantity">贡献量：{{ value(source.quantity) }} {{ value(source.uomLabel, '单位未知') }}</p>
                <small>当前正式设计名称；{{ value(source.orderNo, '订单未提供') }} · 第{{ value(source.lineNo) }}行</small>
                <p>辅助追溯：对象 {{ value(source.designItemId) }}；基线对象 {{ value(source.baselineItemId) }}</p>
                <p>主核算 {{ value(source.originCalculationId) }}；来源核算 {{ value(source.sourceCalculationId) }}；事实 {{ value(source.sourceFactId) }}</p>
                <p>规则 {{ value(source.ruleCode) }} · 版本 {{ value(source.ruleVersion) }}</p>
                <p v-if="source.operationRequirementId != null">工序需求 {{ source.operationRequirementId }}；工序规则 {{ value(source.operationRuleCode) }} · 版本 {{ value(source.operationRuleVersion) }}</p>
                <p>{{ value(source.quantity) }} {{ value(source.uomLabel, '单位未知') }}；{{ value(source.statusLabel, '来源状态未知') }}</p>
                </div>
              </article>
              <div data-cell="plan-trace"><template v-if="review.planningAccess?.allowed === true"><article v-for="plan in row.confirmedPlan?.plans || []" :key="plan.id || plan.planId"><p>计划 {{ value(plan.planNo || plan.planCode) }}；{{ value(plan.quantity) }} {{ value(plan.uomLabel, '单位未知') }}</p><p>{{ value(plan.statusLabel, '计划状态未知') }}</p></article></template></div>
            </details>
          </template>
        </PceEnterpriseListTable>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, reactive } from 'vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'

const props = defineProps({ facts: { type: Object, default: null }, refreshing: { type: Boolean, default: false },
  sourceObjects: { type: Array, default: () => [] }, sourceSalesOrderItemId: { type: [String, Number], default: null } })
defineEmits(['refresh'])
const review = computed(() => {
  const facts = props.facts
  return facts?.contractVersion === 'PCE-ENGINEERING-WORKLOAD-PURPOSE-REVIEW-V1'
    && facts.factSource === 'server' && facts.readStatus === 'loaded'
    && Array.isArray(facts.groups) && Array.isArray(facts.operationLoads) && Array.isArray(facts.historyRequirements)
    ? facts : null
})
const readFailure = computed(() => {
  const facts = props.facts
  return facts?.contractVersion === 'PCE-ENGINEERING-WORKLOAD-PURPOSE-REVIEW-V1'
    && facts.factSource === 'server' && facts.readStatus === 'read_failed' ? facts : null
})
const groupRows = computed(() => review.value?.groups || [])
const loadRows = computed(() => review.value?.operationLoads || [])
const historyRows = computed(() => review.value?.historyRequirements || [])
const planSourceGroups = computed(() => groupRows.value.filter(row => row.purposeCode === 'PHYSICAL_SOURCE'))
const paintPlanAreaUnknown = computed(() => review.value?.planningAccess?.allowed === true && groupRows.value.some(row => row.purposeCode === 'PAINTING'
  && row.confirmedPlan?.quantity == null && row.missingReasons?.some(reason => reason.code === 'PLAN_PURPOSE_QUANTITY_UNKNOWN')))
const value = (input, fallback = '未知') => input === 0 || (input != null && String(input).trim()) ? input : fallback
const reasonLabel = reason => typeof reason === 'string' ? reason : value(reason?.statusLabel, '原因未提供')
const sourceObjectName = source => {
  const scope = props.sourceSalesOrderItemId
  if (scope == null || source.salesOrderItemId == null || source.designItemId == null
    || String(source.salesOrderItemId) !== String(scope)) return '对象名称未提供'
  const matches = (props.sourceObjects || []).filter(object => object.salesOrderItemId != null
    && String(object.salesOrderItemId) === String(scope) && object.designItemId != null
    && String(object.designItemId) === String(source.designItemId))
  return matches.length === 1 ? value(matches[0].itemName, '对象名称未提供') : '对象名称未提供'
}
const filterSchema = Object.freeze([
  { field: 'purposeLabel', label: '业务用途', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'statusLabel', label: '当前状态与边界', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'routingCode', label: '正式工艺编码', filterType: 'text' },
  { field: 'routingVersionLabel', label: '适用版本', filterType: 'text' },
  { field: 'manufacturingModeLabel', label: '制造模式', filterType: 'text' },
  { field: 'productionGroupLabel', label: '生产组', filterType: 'text' },
  { field: 'uomLabel', label: '正式单位', filterType: 'select', optionsProvider: ({ rows }) => [...new Set(rows.map(row => row.dimensions?.uomLabel || row.uomLabel).filter(item => item != null))] },
])
const lists = reactive([
  { id: 'purpose-review-quantities', kind: 'groups', title: '按用途的候选量与确认计划量', rows: groupRows, description: '不同用途、版本、制造模式和单位分别保留；仅服务端证明可比时显示差额。' },
  { id: 'purpose-review-operation-loads', kind: 'operationLoads', title: '有效工序负荷与保存的计划分配', rows: loadRows, description: '逐步骤核对有效负荷、真实分配和匹配产能。未分配与对应数量未知分别表达，不输出排程日期。' },
  { id: 'purpose-review-history', kind: 'historyRequirements', title: '历史替代需求（仅供追溯）', rows: historyRows, description: '本区历史数量不进入当前候选量、有效工序负荷或待分配输入。' },
].map(list => ({ ...list, filterSchema,
  contract: createPceEnterpriseListContract({ pageCode: 'pde-order-engineering-calculation', title: list.title, moduleCode: 'PDE' }),
  runtime: reactive(usePceEnterpriseListRuntime({ rows: list.rows, filterSchema, pageCode: 'pde-order-engineering-calculation',
    filterValueResolver: (row, field) => row[field.field] ?? row.dimensions?.[field.field],
    searchFields: ['purposeLabel', 'statusLabel', 'operationName', row => Object.values(row.dimensions || {}).join(' ')],
    exportFileName: `${list.title}.csv`,
    exportColumns: [{ field: 'purposeLabel', label: '业务用途' },
      { label: '正式工艺', value: row => value(row.dimensions?.routingCode) },
      { label: '适用版本', value: row => value(row.dimensions?.routingVersionLabel) },
      { label: '制造模式', value: row => value(row.dimensions?.manufacturingModeLabel) },
      { label: '生产组', value: row => value(row.dimensions?.productionGroupLabel) },
      { label: '范围', value: row => value(row.dimensions?.sourceScopeLabel) },
      { label: '工程投产候选量', value: row => value(row.engineeringCandidate?.quantity) },
      { label: '候选量单位', value: row => value(row.engineeringCandidate?.uomLabel) },
      { label: '正式来源量（候选量未证明时）', value: row => row.engineeringCandidate?.quantity == null ? value(row.engineeringCandidate?.sourceQuantity) : '不适用' },
      { label: '已确认计划投产量', value: row => review.value?.planningAccess?.allowed === true ? value(row.confirmedPlan?.quantity) : value(review.value?.planningAccess?.statusLabel, '计划查看资格未知') },
      { label: '计划单位', value: row => review.value?.planningAccess?.allowed === true ? value(row.confirmedPlan?.uomLabel) : '未知' },
      { label: '有效工序需求量', value: row => value(row.effectiveQuantity) },
      { label: '已分配计划负荷', value: row => review.value?.planningAccess?.allowed === true ? value(row.allocatedQuantity) : value(review.value?.planningAccess?.statusLabel, '计划查看资格未知') },
      { label: '分配状态', value: row => value(row.allocationStatusLabel) },
      { field: 'statusLabel', label: '状态' },
      { label: '准入原因', value: row => (row.missingReasons || []).map(reasonLabel).join('；') }],
  })),
})))
</script>

<style scoped>
.purpose-review{min-width:0;margin:16px 0;padding:16px;border:1px solid #b6cbdc;border-radius:8px;background:#f7fbfd}.purpose-review h3{margin-top:0}.purpose-review h4{font-size:16px;margin:20px 0 8px}.purpose-review p{line-height:1.6;overflow-wrap:anywhere}.boundary,.unknown{padding:10px 12px;background:#fff7e9;color:#684a22;border-left:3px solid #c19341}.purpose-review small{display:block;line-height:1.55;white-space:normal;overflow-wrap:anywhere;color:#53677d}.trace{max-width:240px;white-space:normal;overflow-wrap:anywhere}.trace summary{cursor:pointer;font-weight:600;color:#17676c}.trace article{margin-top:10px;padding-top:8px;border-top:1px solid #d5e0eb}.trace p{margin:6px 0}
.load-explanation{padding:10px 12px;margin:10px 0;border-left:3px solid #39767d;background:#edf6f6}.load-explanation p{margin:4px 0}.operation-load-overview{width:100%;white-space:normal;overflow-wrap:anywhere;color:#203e52}.operation-load-overview strong{display:block;color:#17676c;line-height:1.6}.operation-load-overview p{margin:8px 0}.operation-load-overview b,.operation-load-overview span{display:block;white-space:normal;overflow-wrap:anywhere}.operation-load-list :deep(.pce-enterprise-row-actions){display:block;min-width:0;white-space:normal}.operation-load-list .trace{max-width:100%;border-top:1px solid #d5e0eb;padding-top:8px}.operation-load-list :deep(.payment-fixed-action-column .cell){white-space:normal;overflow-wrap:anywhere;overflow:visible}.operation-load-overview :deep(.pce-business-status){white-space:normal;overflow-wrap:anywhere;max-width:100%}.contribution-quantity{font-weight:600;color:#17676c}
</style>
