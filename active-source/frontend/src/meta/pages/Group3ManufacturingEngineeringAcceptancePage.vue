<template>
  <component :is="routingCompact ? 'div' : PceListPageShell" :module-id="pageCode" :governance="governance" :page-refresh-handler="load" :page-refresh-status="refreshStatus">
    <div class="g3-page" data-acceptance-id="group3-manufacturing-engineering-acceptance" data-read-only="true">
      <FoundationBreadcrumb v-if="!routingCompact" group="第3组 制造工程" :module="currentTab.label" show-return />
      <section v-if="!routingCompact" class="hero">
        <div><p>企业基础资料 · 第3组</p><h1>{{ currentTab.label }}人工验收</h1><small>真实来源 → 当前正式模型 → 精确映射 → 差异/模型缺口 → 人工裁决</small></div>
        <div class="boundary"><strong>只读预览</strong><span>正式制造主数据写入：0</span></div>
      </section>

      <nav v-if="!embedded" class="tabs" aria-label="第3组人工验收页面">
        <router-link v-for="tab in tabs" :key="tab.entity" :to="`/foundation/group3-acceptance/${tab.entity}`">{{ tab.label }}</router-link>
      </nav>

      <section v-if="loading" class="panel">正在读取来源快照与正式 PDE 事实……</section>
      <section v-else-if="error" class="panel error">{{ error }}</section>
      <template v-else>
        <section v-if="routingCompact" class="routing-first-screen" data-acceptance-id="group3b-user-visible-first-screen">
          <header class="routing-first-header">
            <div><p>产品工程 · 工艺路线 · 人工验收</p><h1>14种工艺类型与第一批代表路线</h1><small>已验收来源与正式 Routing 回读；本页只读</small></div>
            <div class="first-screen-counts">
              <span><b>{{ facts.sourceRecordCount }}</b> 条来源路线</span><span><b>{{ facts.sourceStepRecordCount }}</b> 个来源步骤</span>
              <span><b>{{ routeTypeGroups.length }}</b> 种工艺类型</span><span><b>{{ facts.representativeRouteCards?.length || 0 }}</b> 张代表路线</span>
            </div>
          </header>
          <div class="formal-zero">正式数据：Routing = {{ facts.formalRecordCount }}　RoutingVersion = {{ facts.formalVersionCount }}　RoutingStep = {{ facts.formalStepCount }}　｜　来源追溯保留　｜　本页写入 = 0</div>
          <div class="first-screen-quick" aria-label="首屏工艺类型与代表路线速览">
            <section><strong>14种工艺类型清单</strong><div><span v-for="(group, index) in routeTypeGroups" :key="`quick-${group.typeCode}`">{{ String(index + 1).padStart(2, '0') }} {{ group.typeName }}</span></div></section>
            <section><strong>第一批6张代表路线</strong><div><span v-for="card in facts.representativeRouteCards || []" :key="`quick-rep-${card.routeCode}`">{{ card.routeName }} · {{ card.stepCount }}步</span></div></section>
          </div>
          <div class="first-screen-grid">
            <section class="type-matrix" aria-label="14种工艺类型清单">
              <h2>工艺类型共：{{ routeTypeGroups.length }}</h2>
              <div class="type-grid">
                <article v-for="(group, index) in routeTypeGroups" :key="group.typeCode">
                  <strong>{{ String(index + 1).padStart(2, '0') }} · {{ group.typeName }}</strong>
                  <div><span v-for="routeItem in group.routes" :key="routeItem.routeCode"><b>{{ routeItem.applicableProductCategory }}</b> {{ routeItem.routeCode }} · {{ routeItem.stepCount }}步<small>{{ routeItem.sourceFile }} 第{{ routeItem.sourceRow }}行</small></span></div>
                </article>
              </div>
            </section>
            <section class="representative-index" aria-label="第一批6张代表路线">
              <h2>第一批代表路线：{{ facts.representativeRouteCards?.length || 0 }}张</h2>
              <p>{{ facts.representativeSelectionRule }}</p>
              <article v-for="card in facts.representativeRouteCards || []" :key="`first-${card.routeCode}`">
                <strong>{{ card.routeName }}</strong><span>{{ card.applicableProductCategory }} · {{ card.routeCode }} · {{ card.stepCount }}步</span><small>完整顺序见下方已准备路线卡</small>
              </article>
              <div class="mapping-lock">拉丝 → 拉丝/打磨：{{ facts.aliasMapping?.resolvedCount }}/{{ facts.aliasMapping?.sourceOccurrenceCount }} 已解析　｜　拼皮来源出现：{{ facts.pinpiProjection?.sourceRouteCount }}　｜　自动插入：0</div>
            </section>
          </div>
        </section>

        <section class="status-grid panel" data-acceptance-id="group3-three-statuses">
          <article><span>已开发</span><PceBusinessStatus status-code="DEVELOPED" status-label="是" /></article>
          <article><span>数据存在</span><PceBusinessStatus :status-code="facts.dataPresent" :status-label="businessStatus(facts.dataPresent)" /></article>
          <article><span>用户已验收</span><PceBusinessStatus :status-code="facts.userValidated ? 'READY' : 'NOT_VALIDATED'" :status-label="facts.userValidated ? '是' : '否，等待人工验收'" /></article>
          <article><span>人工准备</span><PceBusinessStatus :status-code="facts.ready" status-label="人工验收页面已准备" /></article>
        </section>

        <section class="summary">
          <article><span>来源记录</span><strong>{{ facts.sourceRecordCount }}</strong></article>
          <article v-if="entity === 'routings'"><span>来源路线步骤</span><strong>{{ facts.sourceStepRecordCount }}</strong></article>
          <article><span>正式记录</span><strong>{{ facts.formalRecordCount }}</strong></article>
          <article v-if="entity === 'operations'" class="good"><span>精确匹配</span><strong>{{ facts.matchedCount }}</strong></article>
          <article v-if="entity === 'operations'" class="danger"><span>冲突</span><strong>{{ facts.conflictCount }}</strong></article>
          <article v-if="entity !== 'operations'" class="blue"><span>拟映射/结构预览</span><strong>{{ facts.proposedCount }}</strong></article>
          <article v-if="entity !== 'operations'" class="warn"><span>{{ entity === 'routings' ? '未解决正式映射' : '未解决' }}</span><strong>{{ facts.unresolvedCount }}</strong></article>
          <article v-if="entity === 'routing-steps'" class="danger"><span>工序名未匹配</span><strong>{{ facts.unresolvedOperationMappingCount }}</strong></article>
          <article v-if="entity === 'routings'" class="good"><span>步骤已解析</span><strong>{{ facts.resolvedStepCount }}</strong></article>
          <article v-if="entity === 'routings'" class="danger"><span>步骤待解析 / 冲突</span><strong>{{ facts.unresolvedStepCount }} / {{ facts.conflictStepCount }}</strong></article>
        </section>

        <section class="panel model-gap">
          <h2>正式承载现实与最小缺口</h2>
          <p><strong>{{ facts.formalModel }}</strong></p>
          <p>{{ facts.modelGap }}</p>
          <p v-if="facts.linkageAudit"><strong>71 行工程关联：</strong>{{ facts.linkageAudit.reason }}</p>
        </section>

        <section v-if="entity === 'operations'" class="panel transition-help">
          <h2>一般工序 / 齐套工序正式回读</h2>
          <p>工序默认转序方式来自正式 Process 数据。未来具体 RoutingStep 可以覆盖；本页没有路线步骤写入。</p>
        </section>

        <template v-if="entity === 'routings'">
          <section class="panel interpretation" data-acceptance-id="group3b-routing-source-interpretation">
            <header><div><h2>42条来源路线解释</h2><p>{{ facts.routeInterpretation?.conclusion }}</p></div><PceBusinessStatus status-code="READY" status-label="已验收并正式化" /></header>
            <div class="interpretation-grid">
              <article><span>来源工艺类型</span><strong>{{ facts.routeInterpretation?.routeTypeCount }}</strong></article>
              <article><span>适用产品类别</span><strong>{{ facts.routeInterpretation?.applicabilityCategoryCount }}</strong></article>
              <article><span>拼皮来源路线</span><strong>{{ facts.pinpiProjection?.sourceRouteCount }}</strong><small>自动插入 0</small></article>
              <article><span>拉丝映射</span><strong>{{ facts.aliasMapping?.resolvedCount }}/{{ facts.aliasMapping?.sourceOccurrenceCount }}</strong><small>拉丝 → 拉丝/打磨</small></article>
              <article><span>结构异常路线</span><strong>{{ facts.anomalyRouteCount }}</strong><small>异常项 {{ facts.totalAnomalyCount }}</small></article>
            </div>
            <p class="version-note"><strong>路线版本：</strong>{{ facts.versionReadiness }}</p>
          </section>

          <section class="panel category-summary" data-acceptance-id="group3b-routing-category-summary">
            <header><div><h2>路线分类汇总</h2><p>类别依据来源路线编码后缀和来源名称，不使用推测分类。</p></div><span>无法确定类别：{{ facts.unknownCategoryCount }}</span></header>
            <div class="category-grid">
              <article v-for="item in categoryEntries" :key="item.name">
                <h3>{{ item.name }}相关路线：{{ item.routeCount }}</h3>
                <p>步骤数范围：{{ item.stepCountMin }}–{{ item.stepCountMax }}</p>
                <p>最短：{{ item.shortestRoute.routeName }}（{{ item.shortestRoute.stepCount }}步）</p>
                <p>最长：{{ item.longestRoute.routeName }}（{{ item.longestRoute.stepCount }}步）</p>
              </article>
            </div>
          </section>

          <section class="panel route-card-panel" data-acceptance-id="group3b-routing-cards">
            <header><div><h2>工艺路线卡</h2><p>{{ facts.representativeSelectionRule }}</p></div><span>全部 {{ facts.routeCards?.length || 0 }} 张已准备</span></header>
            <div class="route-controls">
              <button type="button" :class="{ active: routeCardScope === 'representative' }" @click="routeCardScope = 'representative'">第一批代表路线</button>
              <button type="button" :class="{ active: routeCardScope === 'all' }" @click="routeCardScope = 'all'">查看全部42张路线卡</button>
              <select v-model="routeCategory" aria-label="筛选适用产品类别"><option value="">全部产品类别</option><option value="房门">房门</option><option value="饰面">饰面</option><option value="柜体">柜体</option></select>
              <input v-model="routeSearch" aria-label="搜索路线" placeholder="搜索路线编号或名称" />
            </div>
            <p class="batch-count">当前显示 {{ displayedRouteCards.length }} 张路线卡；本轮只确认来源解析和展示方式。</p>
            <details v-for="(card, cardIndex) in displayedRouteCards" :key="card.routeCode" class="route-card" :open="cardIndex === 0">
              <summary>
                <span><strong>{{ card.routeName }}</strong><small>工艺路线：{{ card.routeCode }} · 适用产品/类别：{{ card.applicableProductCategory }}</small></span>
                <span><b>{{ card.stepCount }}步</b><small>{{ card.anomalyStatus }}</small></span>
              </summary>
              <div class="route-meta">
                <span>来源：{{ card.sourceFile }} / {{ card.sourceRowRange }}</span>
                <span>解释：{{ card.sourceInterpretation }}</span>
                <span>正式状态：{{ card.formalStatus }} · {{ card.formalVersionStatus }} · {{ card.formalStepCount }}个正式步骤</span>
              </div>
              <div class="step-flow" aria-label="完整工序顺序">
                <article v-for="step in card.steps" :key="`${card.routeCode}-${step.sequence}`" :class="{ kitting: step.transitionMode === 'KITTING', problem: step.operationMappingStatus !== 'RESOLVED' }">
                  <span>第{{ step.sequence }}步</span><strong>{{ step.formalOperationName || step.sourceOperation }}</strong>
                  <small v-if="step.formalOperationName !== step.sourceOperation">来源：{{ step.sourceOperation }}</small>
                  <small>前一道：{{ step.predecessor }}</small><small>下一道：{{ step.next }}</small>
                  <small>数据来源：{{ step.source }}</small>
                  <b>{{ step.transitionModeLabel }}</b><em>{{ step.operationMappingStatusLabel }}</em>
                </article>
              </div>
              <div class="route-review">
                <p><strong>异常/待确认：</strong>{{ card.anomalies.join('；') || '未发现重复步骤、未知工序、循环、缺号、重复编号或首末关系异常。' }}</p>
                <p><strong>齐套节点后续关系：</strong>{{ card.kittingRelationshipExplanation.join('；') || '本路线没有齐套节点。' }}</p>
                <p><strong>转序方式来源：</strong>当前展示 Operation 默认配置；未来 RoutingStep 可按具体路线覆盖，本轮不自动覆盖。</p>
              </div>
            </details>
          </section>
        </template>

        <template v-if="entity === 'boms'">
          <section class="panel interpretation" data-acceptance-id="group3c-bom-linkage-analysis">
            <header><div><h2>71条工程拆单稳定关联分析</h2><p>{{ facts.stableLinkageAnalysis?.conclusion }}</p></div><PceBusinessStatus status-code="UNRESOLVED" status-label="禁止模糊拼接" /></header>
            <div class="interpretation-grid">
              <article><span>来源结构行</span><strong>{{ facts.sourceRecordCount }}</strong></article>
              <article><span>稳定匹配</span><strong>{{ facts.stableLinkageAnalysis?.stableMatchCount }}</strong></article>
              <article><span>待关联</span><strong>{{ facts.stableLinkageAnalysis?.unresolvedCount }}</strong></article>
              <article><span>结构预览卡</span><strong>{{ facts.hierarchyCardCount }}</strong></article>
            </div>
            <p><strong>已检查稳定键：</strong>{{ facts.stableLinkageAnalysis?.checkedFields?.join('、') }}</p>
            <p><strong>来源实际字段：</strong>{{ facts.stableLinkageAnalysis?.sourceAvailableFields?.join('、') }}</p>
          </section>

          <section class="panel route-card-panel" data-acceptance-id="group3c-bom-hierarchy-preview">
            <header><div><h2>第一批代表结构</h2><p>{{ facts.representativeSelectionRule }}</p></div><span>BOM正式写入 0</span></header>
            <div class="category-grid bom-hierarchy-grid">
              <article v-for="card in facts.representativeHierarchyCards || []" :key="card.identity">
                <h3>{{ card.productCategory }} · {{ card.productName }}</h3>
                <p>订单/工程对象：未解析</p><p>空间：{{ card.space || '来源未提供' }}</p><p>工艺编码：{{ card.processCode || '来源未提供' }}</p>
                <p>组成行：{{ card.componentCount }}</p><small>{{ card.identityStatus }}</small>
                <ul><li v-for="child in card.children" :key="`${child.sourceSheet}-${child.sourceRow}`">第{{ child.sourceRow }}行 · {{ child.materialCode }} · {{ child.dimensionsText }} · {{ child.materialRole }}</li></ul>
              </article>
            </div>
          </section>
        </template>

        <section class="panel list-panel">
          <header><div><h2>{{ currentTab.tableTitle }}</h2><p>{{ sourceMeaning }}</p></div><span>{{ rows.length }} 条真实来源行</span></header>
          <PceEnterpriseListTable
            ref="tableRef" :contract="enterpriseListContract" :page-id="pageCode" :table-id="`${pageCode}-main-table`"
            :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
            :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
            :active-filter-count="activeFilterCount" :sort-text="sortText" :primary-field="primaryField"
            :primary-label="primaryLabel" :primary-width="260" min-width="2100px" :action-width="160"
            @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
            @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort"
            @export-current="exportCurrent" @clear-selection="clearSelection"
            @update-filter="(field, value) => filters[field] = value" @selection-change="selectedRows = $event" @sort-change="handleSort"
          >
            <template #primary="{ row }"><strong>{{ row[primaryField] }}</strong></template>
            <template #columns>
              <template v-if="entity === 'operations'">
                <el-table-column prop="sourceSequence" label="来源序号" width="100" />
                <el-table-column prop="sourceCode" label="来源编码" width="130"><template #default="{ row }">{{ row.sourceCode || '来源未提供' }}</template></el-table-column>
                <el-table-column prop="formalCode" label="正式编码" width="170" />
                <el-table-column prop="formalName" label="正式名称" width="180" />
                <el-table-column prop="sourceOperationCategoryLabel" label="来源工序类别" width="190" />
                <el-table-column prop="formalOperationCategory" label="正式工序类别" width="140" />
                <el-table-column prop="formalWorkshop" label="车间" width="120" />
                <el-table-column prop="quantityDriver" label="投产量来源" width="160" />
                <el-table-column prop="sourceCalculationExpression" label="来源核算表达" width="130" />
                <el-table-column prop="formalCalculationBasis" label="核算方式" width="140" />
                <el-table-column prop="formalCalculationUom" label="计量单位" width="240" />
                <el-table-column prop="enabled" label="启用" width="90"><template #default="{ row }">{{ row.enabled ? '是' : '否' }}</template></el-table-column>
                <el-table-column prop="matchStatus" label="匹配状态" width="130"><template #default="{ row }"><PceBusinessStatus :status-code="row.matchStatus" :status-label="businessStatus(row.matchStatus)" /></template></el-table-column>
                <el-table-column prop="defaultTransitionModeLabel" label="转序方式" width="150" />
                <el-table-column prop="dataProvenance" label="数据来源" width="300" />
              </template>
              <template v-else-if="entity === 'routings'">
                <el-table-column prop="routeName" label="来源路线名称" width="260" />
                <el-table-column prop="applicableProductCategory" label="适用产品分类" width="150" />
                <el-table-column prop="stepCount" label="步骤数" width="100" />
                <el-table-column prop="matchedOperationCount" label="已匹配工序数" width="130" />
                <el-table-column prop="unresolvedOperationNames" label="未匹配工序" width="180"><template #default="{ row }">{{ row.unresolvedOperationNames.join('、') || '无' }}</template></el-table-column>
                <el-table-column prop="predecessorRule" label="顺序/前置语义" width="320" />
                <el-table-column prop="proposedFormalObject" label="拟正式承载" width="340" />
                <el-table-column prop="formalStatus" label="正式当前状态" width="140"><template #default="{ row }"><PceBusinessStatus :status-code="row.formalStatus" :status-label="businessStatus(row.formalStatus)" /></template></el-table-column>
                <el-table-column prop="status" label="关联状态" width="160"><template #default="{ row }"><PceBusinessStatus :status-code="row.status" :status-label="businessStatus(row.status)" /></template></el-table-column>
              </template>
              <template v-else-if="entity === 'routing-steps'">
                <el-table-column prop="routeName" label="路线名称" width="260" />
                <el-table-column prop="applicableProductCategory" label="适用分类" width="120" />
                <el-table-column prop="sequence" label="步骤顺序" width="110" />
                <el-table-column prop="predecessorName" label="前置工序" width="190" />
                <el-table-column prop="nextName" label="下一工序" width="190" />
                <el-table-column prop="mandatory" label="必经" width="90"><template #default="{ row }">{{ row.mandatory ? '是' : '否' }}</template></el-table-column>
                <el-table-column prop="formalOperationCode" label="正式工序编码" width="170" />
                <el-table-column prop="operationMatchStatus" label="工序匹配" width="160"><template #default="{ row }"><PceBusinessStatus :status-code="row.operationMatchStatus" :status-label="businessStatus(row.operationMatchStatus)" /></template></el-table-column>
                <el-table-column prop="transitionMode" label="流转方式" width="170"><template #default>待人工裁决</template></el-table-column>
                <el-table-column prop="formalStepStatus" label="正式步骤状态" width="150"><template #default="{ row }"><PceBusinessStatus :status-code="row.formalStepStatus" :status-label="businessStatus(row.formalStepStatus)" /></template></el-table-column>
                <el-table-column prop="dataProvenance" label="来源" width="300" />
              </template>
              <template v-else>
                <el-table-column prop="sourceSheet" label="来源工作表" width="180" />
                <el-table-column prop="sourceRow" label="来源行" width="100" />
                <el-table-column prop="productCategory" label="客户成品分类" width="140" />
                <el-table-column prop="space" label="安装空间" width="180" />
                <el-table-column prop="productName" label="工程部件/组成项" width="190" />
                <el-table-column prop="model" label="型号/形态" width="130" />
                <el-table-column prop="dimensionsText" label="高 × 宽 × 厚" width="180" />
                <el-table-column prop="materialCode" label="半成品物料编码" width="180" />
                <el-table-column prop="processCode" label="来源工艺编码" width="150" />
                <el-table-column prop="componentRole" label="结构语义" width="220" />
                <el-table-column prop="materialRole" label="物料角色" width="160" />
                <el-table-column prop="formalMaterialName" label="正式物料匹配" width="220" />
                <el-table-column prop="proposedFormalObject" label="拟正式承载" width="300" />
                <el-table-column prop="status" label="关联状态" width="160"><template #default="{ row }"><PceBusinessStatus :status-code="row.status" :status-label="businessStatus(row.status)" /></template></el-table-column>
                <el-table-column prop="unresolvedReason" label="未解决原因" width="420" />
              </template>
            </template>
            <template #actions><span class="read-only-action">仅查看</span></template>
          </PceEnterpriseListTable>
        </section>

        <section class="panel provenance"><h2>数据来源</h2><ul><li v-for="item in facts.dataProvenance" :key="item.fileName"><strong>{{ item.fileName }}</strong><code>{{ item.sha256 }}</code><span>{{ item.sheets.length }} 个工作表已核对</span></li></ul></section>
        <section class="panel final-boundary"><strong>{{ entity === 'routings' ? '第3组B：已完成 / 已冻结' : entity === 'boms' ? '第3组C：BOM人工验收准备完成' : '第3组整体：人工验收页面已准备' }}</strong><span>第4组未进入 · 计划生产未部署 · BOM正式写入 0</span></section>
      </template>
    </div>
  </component>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import FoundationBreadcrumb from '@/meta/components/FoundationBreadcrumb.vue'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'

const props = defineProps({ entity: { type: String, required: true }, embedded: { type: Boolean, default: false } })
const entity = computed(() => props.entity)
const routingCompact = computed(() => props.embedded && entity.value === 'routings')
const tabs = [
  { entity: 'operations', label: '工序', tableTitle: 'A. 工序来源与正式事实逐条对照' },
  { entity: 'boms', label: 'BOM / 产品结构', tableTitle: 'B. BOM / 产品结构来源预览' },
  { entity: 'routings', label: '工艺路线', tableTitle: 'C. 工艺路线来源与正式承载预览' },
  { entity: 'routing-steps', label: '路线步骤', tableTitle: 'D. 路线步骤、前置与流转预览' },
]
const currentTab = computed(() => tabs.find(tab => tab.entity === entity.value) || tabs[0])
const pageCode = 'group3-manufacturing-engineering-acceptance'
const facts = ref({}); const rows = ref([]); const loading = ref(false); const error = ref(''); const refreshStatus = ref('idle')
const routeCardScope = ref('representative'); const routeCategory = ref(''); const routeSearch = ref('')
const categoryEntries = computed(() => ['房门', '饰面', '柜体']
  .filter(name => facts.value.categorySummary?.[name])
  .map(name => ({ name, ...facts.value.categorySummary[name] })))
const routeTypeGroups = computed(() => {
  const categories = ['房门', '饰面', '柜体']
  const groups = new Map()
  for (const card of facts.value.routeCards || []) {
    const typeCode = String(card.routeCode || '').split('/')[0]
    if (!groups.has(typeCode)) groups.set(typeCode, { typeCode, typeName: String(card.routeName || '').replace(/(房门|饰面|柜体)$/, ''), routes: [] })
    groups.get(typeCode).routes.push(card)
  }
  return [...groups.values()].map(group => ({ ...group, routes: group.routes.sort((a, b) => categories.indexOf(a.applicableProductCategory) - categories.indexOf(b.applicableProductCategory)) }))
})
const displayedRouteCards = computed(() => {
  const sourceRows = routeCardScope.value === 'all' ? (facts.value.routeCards || []) : (facts.value.representativeRouteCards || [])
  const keyword = routeSearch.value.trim().toLocaleLowerCase()
  return sourceRows.filter(row => (!routeCategory.value || row.applicableProductCategory === routeCategory.value)
    && (!keyword || `${row.routeCode} ${row.routeName}`.toLocaleLowerCase().includes(keyword)))
})
const primaryField = computed(() => ({ operations: 'sourceName', routings: 'routeCode', 'routing-steps': 'operationName', boms: 'productName' }[entity.value]))
const primaryLabel = computed(() => ({ operations: '来源工序名称', routings: '来源路线编码', 'routing-steps': '工序名称', boms: '工程组成名称' }[entity.value]))
const sourceMeaning = computed(() => facts.value.sourceSemantics?.[({ operations: 'operation', routings: 'routing', 'routing-steps': 'routingStep', boms: 'bom' }[entity.value])] || '')
const governance = computed(() => ({
  pageCode, version: entity.value === 'routings' ? 'GROUP3B-ROUTING-ACCEPTANCE-V1' : 'GROUP3-ACCEPTANCE-V1', frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
  purpose: entity.value === 'routings' ? '以42张路线卡展示1,137个真实来源步骤及正式工序映射，供第一批代表路线人工验收；本页不写正式数据。' : '逐条展示制造工程来源与正式事实，供用户人工验收；本页不写正式数据。',
  allowed: ['读取真实来源', '查看正式事实', '筛选、排序与导出当前视图', '进行不落库的人工选择预览'],
  forbidden: ['写入工序/BOM/路线/步骤', '进入第4组', '部署计划生产'],
  flowSteps: ['工序', 'BOM / 产品结构', '工艺路线', '路线步骤'], currentFlowStep: currentTab.value.label,
  navigation: { current: { label: currentTab.value.label, pageCode, pageUrl: `/foundation/group3-acceptance/${entity.value}` }, previous: { label: '第2组已关闭' }, next: { label: '等待用户验收' } },
}))
const enterpriseListContract = computed(() => createPceEnterpriseListContract({ pageCode, pageType: 'list', title: currentTab.value.label, moduleCode: 'PDE_GROUP3_ACCEPTANCE' }))
const filterSchema = [
  { field: 'primaryBusinessName', label: '主要业务名称', filterType: 'text' },
  { field: 'businessStatusText', label: '业务状态', filterType: 'text' },
]
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'group3-manufacturing-engineering-acceptance',
  searchFields: ['sourceName', 'formalName', 'routeCode', 'routeName', 'operationName', 'productName', 'space', 'materialCode'],
  exportFileName: '第3组制造工程人工验收.csv',
  exportColumns: [{ field: primaryField.value, label: primaryLabel.value }, { field: 'status', label: '业务状态' }],
})
const businessStatus = code => ({ PRESENT: '已有正式数据', MISSING: '正式数据缺失', EXACT_MATCH: '精确匹配', RESOLVED: '已解析', CONFLICT: '冲突', UNRESOLVED_LINKAGE: '稳定关联未解决', UNRESOLVED_OPERATION: '来源工序未匹配', 'PREVIEW_ONLY / PENDING_USER_VALIDATION': '只读预览，等待人工确认', MANUAL_VALIDATION_READY: '人工验收页面已准备' }[code] || '待人工裁决')
async function load() {
  loading.value = true; error.value = ''; refreshStatus.value = 'refreshing'
  try {
    const response = await enterpriseMasterDataApi.group3Comparison(entity.value)
    facts.value = response?.data ?? response
    rows.value = (facts.value.rows || []).map(row => ({
      ...row,
      primaryBusinessName: row[primaryField.value],
      businessStatusText: businessStatus(row.matchStatus || row.status || row.formalizationStatus),
    }))
    refreshStatus.value = 'success'
  }
  catch (reason) { error.value = reason?.message || '第3组验收事实读取失败'; refreshStatus.value = 'error' }
  finally { loading.value = false }
}
watch(entity, load, { immediate: true })
</script>

<style scoped>
.g3-page{padding:20px;color:#17223a}.hero,.panel{background:#fff;border:1px solid #dce4ef;border-radius:16px;padding:20px 22px;margin-bottom:18px}.hero{display:flex;justify-content:space-between;gap:18px;align-items:center;background:linear-gradient(135deg,#173c6a,#17676c);color:#fff}.hero p,.hero h1,.hero small,.panel h2,.panel p{margin:0}.hero h1{margin:5px 0 8px}.boundary{display:grid;gap:6px;border:1px solid #9fd5d4;border-radius:12px;padding:10px 14px}.tabs{display:flex;gap:10px;margin-bottom:18px}.tabs a{padding:10px 15px;border-radius:10px;background:#e9f3f4;color:#135961;text-decoration:none}.tabs a.router-link-active{background:#17676c;color:#fff}.status-grid,.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.status-grid article,.summary article{display:grid;gap:6px;padding:13px;border-radius:10px;background:#f5f8fc;border-left:4px solid #17676c}.status-grid span,.summary span{font-size:12px;color:#637189}.summary{margin-bottom:18px}.summary strong{font-size:22px}.summary .good{border-color:#168357}.summary .warn{border-color:#d48600}.summary .danger{border-color:#c5362d}.summary .blue{border-color:#315bcf}.model-gap{border-left:5px solid #d48600}.transition-help{border-left:5px solid #315bcf}.transition-help div{margin-top:12px;padding:12px;background:#f4f7ff;border-radius:9px}.list-panel header,.interpretation header,.category-summary header,.route-card-panel>header{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:14px}.interpretation{border-left:5px solid #315bcf}.interpretation-grid,.category-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.interpretation-grid article,.category-grid article{display:grid;gap:6px;padding:13px;background:#f5f8fc;border-radius:10px}.interpretation-grid span{font-size:12px;color:#637189}.interpretation-grid strong{font-size:22px}.version-note{margin-top:14px!important}.route-controls{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}.route-controls button,.route-controls select,.route-controls input{border:1px solid #b9c8db;border-radius:9px;padding:9px 12px;background:#fff;color:#23324a}.route-controls button{cursor:pointer;font-weight:700}.route-controls button.active{background:#17676c;color:#fff;border-color:#17676c}.route-controls input{min-width:220px}.batch-count{color:#637189;margin-bottom:12px!important}.route-card{border:1px solid #dbe4ef;border-radius:12px;margin:12px 0;overflow:hidden}.route-card summary{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:15px 17px;background:#f6f9fc;cursor:pointer}.route-card summary span{display:grid;gap:4px}.route-meta{display:grid;gap:5px;padding:12px 17px;background:#eef5ff;color:#40506a}.step-flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:9px;padding:16px}.step-flow article{display:grid;gap:4px;padding:11px;border:1px solid #dbe4ef;border-radius:9px;background:#fff}.step-flow article.kitting{border-color:#d48600;background:#fff8e7}.step-flow article.problem{border-color:#c5362d;background:#fff1f0}.step-flow article span,.step-flow article small{color:#637189}.step-flow article b{color:#a46300}.step-flow article em{font-style:normal;color:#168357}.route-review{display:grid;gap:7px;padding:13px 17px;border-top:1px solid #dbe4ef;background:#fbfcfe}.route-review p{line-height:1.6}.read-only-action{color:#617086}.provenance ul{padding:0;list-style:none}.provenance li{display:grid;grid-template-columns:minmax(220px,320px) 1fr auto;gap:12px;margin:8px 0}.provenance code{font-size:10px;word-break:break-all}.final-boundary{display:flex;justify-content:space-between;background:#fff8e6}.error{color:#a6241c}small{display:block}@media(max-width:800px){.g3-page{padding:10px}.hero,.final-boundary,.list-panel header,.interpretation header,.category-summary header,.route-card-panel>header,.route-card summary{align-items:flex-start;flex-direction:column}.provenance li{grid-template-columns:1fr}}
.routing-first-screen{background:#f7fafc;border:1px solid #b9cadb;border-radius:14px;padding:16px;margin-bottom:14px}.routing-first-header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.routing-first-header p,.routing-first-header h1{margin:0}.routing-first-header h1{font-size:22px;margin:3px 0}.first-screen-counts{display:grid;grid-template-columns:repeat(2,minmax(130px,1fr));gap:6px}.first-screen-counts span{background:#173c6a;color:#fff;border-radius:8px;padding:7px 10px}.first-screen-counts b{font-size:18px}.formal-zero{margin:10px 0;padding:8px 10px;border-radius:8px;background:#fff4d9;color:#704b00;font-weight:700}.first-screen-grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(300px,.85fr);gap:12px}.type-matrix,.representative-index{background:#fff;border:1px solid #dce4ef;border-radius:10px;padding:11px}.type-matrix h2,.representative-index h2{margin:0 0 8px;font-size:16px}.type-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.type-grid article{display:grid;grid-template-columns:minmax(120px,.7fr) minmax(0,1.3fr);gap:6px;padding:5px 7px;border-radius:7px;background:#f2f6fa;font-size:11px}.type-grid article>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:3px}.type-grid span{padding:3px 4px;border-left:2px solid #17676c;background:#fff}.type-grid small{color:#6b7889}.representative-index>p{font-size:11px;margin:0 0 6px}.representative-index>article{display:flex;justify-content:space-between;gap:6px;padding:5px 7px;margin:4px 0;border-radius:7px;background:#f2f6fa;font-size:11px}.representative-index>article small{color:#6b7889}.mapping-lock{margin-top:7px;padding:7px;border-radius:7px;background:#e7f5ee;color:#16633f;font-size:11px;font-weight:700}@media(max-width:1100px){.first-screen-grid{grid-template-columns:1fr}.routing-first-header{flex-direction:column}.type-grid{grid-template-columns:1fr}}@media(max-width:700px){.first-screen-counts{grid-template-columns:1fr 1fr}.type-grid article{grid-template-columns:1fr}.representative-index>article{display:grid}}
.first-screen-quick{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(260px,.8fr);gap:8px;margin-bottom:10px}.first-screen-quick section{padding:8px;border:1px solid #d5e0eb;border-radius:8px;background:#fff}.first-screen-quick section>strong{display:block;margin-bottom:5px;color:#173c6a}.first-screen-quick section>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:3px}.first-screen-quick span{padding:2px 4px;border-radius:4px;background:#edf3f8;font-size:10px;line-height:1.25}@media(max-width:700px){.routing-first-screen{padding:8px}.routing-first-header{gap:5px}.routing-first-header h1{font-size:16px}.routing-first-header p,.routing-first-header small{font-size:9px}.first-screen-counts{width:100%;grid-template-columns:repeat(4,minmax(0,1fr));gap:3px}.first-screen-counts span{padding:3px;font-size:8px}.first-screen-counts b{display:block;font-size:13px}.formal-zero{margin:4px 0;padding:4px;font-size:9px;line-height:1.25}.first-screen-quick{grid-template-columns:1fr 1fr;gap:4px}.first-screen-quick section{padding:4px}.first-screen-quick section>strong{font-size:9px;margin-bottom:2px}.first-screen-quick section>div{grid-template-columns:1fr;gap:1px}.first-screen-quick span{font-size:7px;padding:1px 2px;line-height:1.05}}
</style>
