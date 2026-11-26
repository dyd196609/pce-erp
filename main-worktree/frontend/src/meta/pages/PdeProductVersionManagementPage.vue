<template>
  <div class="version-page" data-acceptance-id="pde-product-version-management-page" data-fact-source="server">
    <section class="card intro">
      <div><small>订单工程基线 / 正式产品版本 / BOM版本边界</small><h2>产品版本管理</h2></div>
      <p><b>订单工程基线：</b>为整份订单保存一版工程资料，记录保存人与确认人，并保留当时的内容。</p>
      <div class="boundary">
        <span><b>设计修订号（R）</b>单个设计项的修订次序，例如 R3 是本项第 3 次修订，不是整单第 3 版。</span>
        <span><b>订单工程基线</b>整单工程内容与来源的不可变快照，001、002 是整单版本。</span>
        <span><b>来源版本</b>原始工程资料的版本，用于追溯，不等同于设计修订号。</span>
        <span><b>BOM版本</b>独立制造结构版本，不由本页自动生成。</span>
      </div>
    </section>

    <section v-if="selectedBaseline?.approvalScope === 'TEST_BUSINESS'" class="card" aria-label="测试核算预览">
      <h3>测试核算预览</h3>
      <p>仅查看所选冻结基线；服务端复核测试用途及精确来源。不会保存正式核算或取得生产资格。需既有核算查看权限。</p>
      <button type="button" :disabled="previewBusy" @click="loadTestPreview">读取所选基线测试核算预览</button>
      <p v-if="previewError" class="error">{{ previewError }}</p>
      <template v-if="testPreview">
        <p><b>{{ testPreview.statusLabel }}</b> · {{ testPreview.baselineNo }} · R{{ testPreview.designRevision }} · 测试业务用途</p>
        <p>来源身份：{{ testPreview.sourceIdentityValid ? '有效' : '未通过' }}；批准用途：{{ testPreview.approvalPurposeValid ? '有效' : '未通过' }}；输入完整：{{ testPreview.inputComplete ? '是' : '否' }}；计算成功：{{ testPreview.calculationSucceeded ? '是' : '否' }}</p>
        <p v-for="(item,index) in testPreview.blockers" :key="index">{{ item.reason }}</p>
        <ul><li v-for="item in testPreview.mapping" :key="item.field">{{ item.meaning }}；单位：{{ item.unit }}；适用条件：{{ item.requiredWhen }}；当前缺失（{{ item.field }}）</li></ul>
        <p>{{ testPreview.ruleEvidence.optional }}</p>
        <template v-if="testPreview.calculationSucceeded">
          <p>规则版本：{{ testPreview.ruleVersion }}；{{ testPreview.quantityBasis }}</p>
          <ul><li v-for="input in testPreview.inputs" :key="input.original.key">{{ input.name }}：{{ input.original.length }} × {{ input.original.width }} {{ input.dimensionUnit }} → {{ input.lengthMm }} × {{ input.widthMm }} mm；订单总数量 {{ input.quantityUsedOnce }} {{ input.quantityUnit }}</li></ul>
          <table><thead><tr><th>部件</th><th>结果</th><th>数值</th><th>单位</th><th>原规则表达式</th></tr></thead><tbody><tr v-for="row in testPreview.rows" :key="row.id"><td>{{ row.componentName }}</td><td>{{ row.project }}</td><td>{{ row.value }}</td><td>{{ row.unit }}</td><td>{{ row.expression }}</td></tr></tbody></table>
          <p>汇总：部件数量 {{ testPreview.summary.quantity }}；净面积 {{ testPreview.summary.S }} m²；见光面积 {{ testPreview.summary.Q }} m²；封边净长度 {{ testPreview.summary.R }} m</p>
        </template>
      </template>
      <SavedTestCalculationPanel :baseline-id="selectedBaseline.baselineId" />
    </section>
    <section class="card primary-flow">
      <div class="step-label">1　选择订单</div>
      <label>订单与工程范围
        <select v-model="selectedOrderNo" @change="changeOrder">
          <option value="">{{ orderOptions.length > 1 ? '请选择订单' : '正在识别订单范围' }}</option>
          <option v-for="order in orderOptions" :key="order.orderId" :value="order.orderNo">{{ order.orderNo }} · {{ order.customer }} · {{ order.designItemCount }}项设计</option>
        </select>
      </label>
      <div v-if="selectedOrder" class="facts">
        <article><small>订单</small><strong>{{ selectedOrder.orderNo }}</strong></article>
        <article><small>客户 / 项目</small><strong>{{ selectedOrder.customer }} / {{ selectedOrder.project || '未维护' }}</strong></article>
        <article><small>工程范围</small><strong>{{ selectedOrder.designItemCount }} 项</strong></article>
        <article><small>负责人</small><strong>{{ selectedOrder.salesOwner }}</strong></article>
      </div>

      <template v-if="!loading && !errorMessage">
        <div class="step-label">2　已保存工程基线</div>
        <div v-if="savedBaselines.length" class="history" aria-label="已保存工程基线">
          <button v-for="baseline in savedBaselines" :key="baseline.baselineId" :class="{active:selectedBaseline?.baselineId===baseline.baselineId}" type="button" @click="loadBaseline(baseline)">
            <span><b>{{ baseline.baselineNo }}</b><em>{{ baseline.statusLabel }}</em></span>
            <span>{{ baseline.scopeItemCount }}项 · 保存人 {{ baseline.createdByName || baseline.createdBy }} · {{ formatTime(baseline.createdAt) }}</span>
            <span v-if="baseline.confirmedBy">确认人 {{ baseline.confirmedByName || baseline.confirmedBy }} · {{ formatTime(baseline.confirmedAt) }}</span>
          </button>
        </div>
        <p v-else>尚未建立。页面不会用当前资料或静态版本号模拟历史。</p>

        <div class="step-label">3　所选基线详情</div>
        <section v-if="selectedBaseline" class="selected-panel" aria-live="polite">
          <div class="viewing-banner">正在查看：<b>{{ selectedBaseline.baselineNo }}</b><strong>{{ selectedBaseline.statusLabel }}</strong></div>
          <p class="source-warning"><b>用途：{{ selectedBaseline?.approvalScope === 'TEST_BUSINESS' ? '测试业务，不用于生产' : (selectedBaseline?.approvalScope === 'PRODUCTION_USE' ? '生产业务' : '存量用途，须核验历史依据') }}。以下是本版保存时的资料。</b>上方历史切换不会改写后面的“当前工程资料”；旧版缺失值也不会用当前值补齐。</p>
          <div class="detail-grid">
            <article><small>保存范围</small><strong>{{ selectedBaseline.scopeItemCount }} 项</strong></article>
            <article><small>保存时确认条件</small><strong>{{ selectedBaseline.confirmableItemCount }} 项满足 / {{ selectedBaseline.blockerCount }} 项阻断</strong></article>
            <article><small>保存人 / 时间</small><strong>{{ selectedBaseline.createdByName || selectedBaseline.createdBy }}</strong><span>{{ formatTime(selectedBaseline.createdAt) }}</span></article>
            <article><small>确认人 / 时间</small><strong>{{ selectedBaseline.confirmedByName || '尚未确认' }}</strong><span>{{ formatTime(selectedBaseline.confirmedAt) }}</span></article>
            <article><small>保存原因</small><strong>{{ selectedBaseline.reason || '该版未记录' }}</strong></article>
            <article><small>确认记录</small><strong>{{ selectedBaseline.statusTransitionCount }} 次状态流转</strong><span>{{ selectedBaseline.blockerSummary || (selectedBaseline.blockerCount ? '存在阻断' : '无阻断') }}</span></article>
          </div>
          <p v-if="selectedBaseline.statusCode==='confirmed'" class="confirmed-note">本版已确认，可查看保存内容和确认记录；确认动作不可重复执行。</p>

          <section class="comparison" data-acceptance-id="baseline-comparison">
            <header><div><small>只读差异</small><h3>{{ historyComparison.statusLabel }}</h3></div><span v-if="historyComparison.available">新增 {{ historyComparison.summary.added }} · 移除 {{ historyComparison.summary.removed }} · 变化 {{ historyComparison.summary.changed }} · 相同 {{ historyComparison.summary.same }}</span></header>
            <template v-if="historyComparison.available">
              <p>比较方向：<b>{{ historyComparison.olderBaseline.baselineNo }}</b> → <b>{{ historyComparison.newerBaseline.baselineNo }}</b>。内容差异与状态、人员变化分开显示。</p>
              <div v-if="historyComparison.baselineChanges.length" class="baseline-changes">
                <span v-for="change in historyComparison.baselineChanges" :key="change.fieldCode"><b>{{ change.fieldLabel }}</b>：{{ change.beforeDisplay }} → {{ change.afterDisplay }}</span>
              </div>
              <div v-if="comparisonItems.length" class="difference-list">
                <article v-for="item in comparisonItems" :key="item.designItemId" :id="`history-diff-${item.designItemId}`">
                  <header><div><b>{{ item.itemName || '该版未记录名称' }}</b><small>{{ item.itemNo }}</small></div><span>{{ item.changeCategoryLabel }} · {{ item.changedFieldCount }}个字段</span></header>
                  <table v-if="item.changedFields.length"><thead><tr><th>变化字段</th><th>{{ historyComparison.olderBaseline.baselineNo }}</th><th>{{ historyComparison.newerBaseline.baselineNo }}</th></tr></thead><tbody>
                    <tr v-for="field in item.changedFields" :key="field.fieldCode"><td>{{ field.fieldLabel }}</td><td>{{ differenceDisplay(field, field.beforeDisplay) }}</td><td>{{ differenceDisplay(field, field.afterDisplay) }}</td></tr>
                  </tbody></table>
                </article>
              </div>
              <p v-else>两版保存的业务内容相同；上方仅列整版状态或办理人员变化。</p>
            </template>
          </section>

          <details class="snapshot-items" open>
            <summary>查看本版保存内容（{{ selectedBaseline.items.length }}项）</summary>
            <div class="list-scope-note">筛选结果 {{ historyFilteredRows.length }} 项 / 本版共 {{ historyRows.length }} 项；筛选、排序和分页仅改变显示，不改变本版快照范围。</div>
            <PceEnterpriseListTable
              ref="historyTableRef"
              :contract="historyListContract"
              page-id="pde-product-version-history"
              table-id="pde-product-version-history-table"
              :rows="historyRows"
              :table-rows="historyFilteredRows"
              :filter-schema="historyFilterSchema"
              :filters="historyFilters"
              :quick-search="historyQuickSearch"
              :advanced-visible="historyAdvancedVisible"
              :selected-count="historySelectedRows.length"
              :active-filter-count="historyActiveFilterCount"
              :sort-text="historySortText"
              primary-field="itemNo"
              primary-label="工程对象"
              :primary-width="250"
              min-width="1460px"
              :show-action-column="false"
              row-density="comfortable"
              :default-page-size="20"
              :page-sizes="[20, 50, 100]"
              @update:quick-search="historyQuickSearch = $event"
              @search="historyApplySearch"
              @toggle-advanced="historyAdvancedVisible = !historyAdvancedVisible"
              @clear-filters="historyClearFilters"
              @clear-sort="historyClearSort"
              @export-current="exportHistoryCurrent"
              @update-filter="historyUpdateFilter"
              @selection-change="historyHandleSelectionChange"
              @sort-change="historyHandleSort"
            >
              <template #primary="{ row }"><strong>{{ row.itemName || '该版未记录名称' }}</strong><small>{{ row.itemNo }}</small></template>
              <template #columns>
                <el-table-column prop="sourceTypeLabel" label="保存来源" min-width="170" sortable="custom" show-overflow-tooltip />
                <el-table-column prop="designRevisionSortKey" label="设计修订" min-width="160" sortable="custom"><template #default="{ row }">{{ row.designRevisionLabel }}<small>{{ row.approvalScope === 'TEST_BUSINESS' ? '获准修订（测试业务；原测试来源保留）' : designNatureLabel(row.designNature) }}</small></template></el-table-column>
                <el-table-column prop="sourceVersionSortKey" label="来源版本" min-width="150" sortable="custom"><template #default="{ row }">{{ row.sourceVersion || '该版未记录' }}</template></el-table-column>
                <el-table-column prop="savedQualificationCode" label="保存时确认条件" min-width="230" sortable="custom"><template #default="{ row }"><PceBusinessStatus :status-label="row.savedQualificationLabel" source="server" /></template></el-table-column>
                <el-table-column prop="currentQualificationCode" label="当前确认条件" min-width="230" sortable="custom"><template #default="{ row }"><PceBusinessStatus :status-label="row.currentQualificationLabel" source="server" /></template></el-table-column>
                <el-table-column label="保存内容" min-width="520"><template #default="{ row }"><details class="field-details"><summary>查看字段</summary><dl><template v-for="field in row.snapshotDisplayFields" :key="field.fieldCode"><dt>{{ field.fieldLabel }}</dt><dd>{{ field.displayValue }}</dd></template></dl></details></template></el-table-column>
              </template>
            </PceEnterpriseListTable>
          </details>
        </section>
        <p v-else>请选择一条已保存基线查看该版快照。</p>
      </template>
    </section>

    <section v-if="loading" class="card state">正在读取服务端事实…</section>
    <section v-else-if="errorMessage" class="card state error"><strong>读取失败，当前数据数量未知。</strong><span>{{ errorMessage }}</span><button @click="load(selectedOrderNo)">重新读取</button></section>
    <template v-else>
      <section class="card guide"><header><div><small>操作说明</small><h3>查看与办理的区别</h3></div></header><ol>
        <li>先在上方选择历史基线，查看该版保存内容及与相邻版本的真实差异。</li>
        <li>“当前工程资料”是当前最新设计和来源，不随历史版本切换。</li>
        <li>“保存新草稿”固定当前整单资料；“确认所选草稿”只办理当前选中的未确认基线。</li>
        <li>设计修订号 R、整单工程基线编号和来源版本是三类不同标识。</li>
      </ol></section>

      <section class="card status-grid">
        <article><small>当前工程范围</small><strong>{{ candidateBaseline?.designItemCount ?? 0 }} 项</strong><span>草稿可快照 {{ candidateBaseline?.draftSnapshotItemCount ?? 0 }} 项</span></article>
        <article><small>当前确认条件</small><strong>{{ candidateBaseline?.confirmableItemCount ?? 0 }} 项满足</strong><span>{{ candidateBaseline?.gapCount ?? 0 }} 项阻断</span></article>
        <article><small>已保存基线</small><strong>{{ savedBaselineStatus }}</strong><span>历史 {{ savedBaselines.length }} 版</span></article>
        <article><small>当前与最近基线</small><strong>{{ diffFacts.statusLabel || '尚不可比较' }}</strong><span>读取、切换和比较均为零业务写入</span></article>
      </section>

      <section class="card gap-panel"><header><div><small>当前资料的来源与确认条件</small><h3>按原因定位工程对象</h3></div><span>{{ gapFacts.length }} 项需说明</span></header><p v-if="!gapSummary.length">当前范围没有确认阻断项。</p><details v-for="group in gapSummary" :key="group.code"><summary><b>{{ group.count }} 项</b> · {{ group.label }}</summary><div class="gap-items"><button v-for="itemNo in group.itemNos" :key="itemNo" type="button" @click="focusItem(itemNo)">{{ itemNo }}</button></div><p>草稿保存：{{ gapFacts.find(row => row.code === group.code)?.saveImpactLabel }}；基线确认：{{ gapFacts.find(row => row.code === group.code)?.confirmImpactLabel }}。</p></details><div class="nav-actions"><button type="button" @click="goDesign">返回产品设计资料</button><button type="button" @click="goCalculation">进入工程核算 / 物料核算</button></div></section>

      <section class="card current-facts"><header><div><small>当前工程资料（不随历史切换）</small><h3>当前最新设计、来源与候选状态</h3></div><span>筛选结果 {{ currentFilteredRows.length }} 项 / 当前整版共 {{ currentRows.length }} 项</span></header><p class="list-scope-note">显示筛选不会缩小保存草稿或整单确认的业务范围；候选哈希、阻断项和完整范围差异仍由服务端整版事实决定。</p>
        <PceEnterpriseListTable
          ref="currentTableRef"
          :contract="currentListContract"
          page-id="pde-product-version-current"
          table-id="pde-product-version-current-table"
          :rows="currentRows"
          :table-rows="currentFilteredRows"
          :filter-schema="currentFilterSchema"
          :filters="currentFilters"
          :quick-search="currentQuickSearch"
          :advanced-visible="currentAdvancedVisible"
          :selected-count="currentSelectedRows.length"
          :active-filter-count="currentActiveFilterCount"
          :sort-text="currentSortText"
          primary-field="itemNo"
          primary-label="产品设计项"
          :primary-width="250"
          min-width="1960px"
          :show-action-column="false"
          :default-page-size="20"
          :page-sizes="[20, 50, 100]"
          @update:quick-search="currentQuickSearch = $event"
          @search="currentApplySearch"
          @toggle-advanced="currentAdvancedVisible = !currentAdvancedVisible"
          @clear-filters="currentClearFilters"
          @clear-sort="currentClearSort"
          @export-current="exportCurrentRows"
          @update-filter="currentUpdateFilter"
          @selection-change="currentHandleSelectionChange"
          @sort-change="currentHandleSort"
        >
          <template #primary="{ row }"><strong :id="`item-${row.itemNo}`">{{ row.itemNo }}</strong><small>{{ row.itemName }}</small></template>
          <template #columns>
            <el-table-column prop="designGroup" label="分组" min-width="120" sortable="custom" />
            <el-table-column prop="identityLabel" label="工程身份" min-width="210" sortable="custom" show-overflow-tooltip />
            <el-table-column prop="designRevisionSortKey" label="设计修订" min-width="165" sortable="custom"><template #default="{ row }">{{ row.designRevisionLabel }}<small>{{ row.approvalScope === 'TEST_BUSINESS' ? '获准修订（测试业务；原测试来源保留）' : designNatureLabel(row.designNature) }}</small></template></el-table-column>
            <el-table-column prop="snapshotSourceTypeLabel" label="工程内容来源" min-width="210" sortable="custom"><template #default="{ row }">{{ row.snapshotSourceTypeLabel }}<small>{{ row.snapshotSourceType === 'DESIGN_REVISION' ? '已保存设计修订' : (row.hasPersistedEngineeringContent ? '已有持久工程内容' : '尚无持久工程内容') }}</small></template></el-table-column>
            <el-table-column prop="sourceVersionSortKey" label="来源版本" min-width="210" sortable="custom"><template #default="{ row }">{{ row.sourceNo }} / {{ row.sourceVersion || '未记录' }}</template></el-table-column>
            <el-table-column prop="formalProductVersionNo" label="正式产品版本" min-width="165" sortable="custom"><template #default="{ row }">{{ row.formalProductVersionNo || row.formalProductApplicabilityLabel }}</template></el-table-column>
            <el-table-column prop="responsibleEmployee" label="负责人" min-width="150" sortable="custom" />
            <el-table-column prop="confirmImpactLabel" label="草稿 / 确认" min-width="260" sortable="custom"><template #default="{ row }"><PceBusinessStatus :status-label="`${row.saveImpactLabel}；${row.confirmImpactLabel}`" source="server" /><small v-if="row.confirmBlockerLabel">{{ row.confirmBlockerLabel }}</small></template></el-table-column>
          </template>
        </PceEnterpriseListTable>
      </section>

      <section class="card actions"><div><small>保存与确认能力</small><h3>{{ persistenceCapability.statusLabel || '尚未核验' }}</h3><p>{{ persistenceCapability.reason }}</p></div><label>办理原因<input v-model.trim="actionReason" maxlength="500" placeholder="说明本次保存或确认依据" /></label><div class="action-buttons"><button :disabled="!canSaveDraft || writing" @click="saveDraft">{{ writing ? '办理中…' : '保存工程基线草稿' }}</button><button :disabled="!canConfirm || writing" @click="confirmBaseline">确认所选工程基线</button></div><p class="stop">{{ actionBlocker }}</p></section>

      <details class="card technical"><summary>技术信息与诊断依据</summary><p>页面身份：PDE / pde-product-versions；当前候选哈希：{{ candidateBaseline?.candidateId || '无' }}；所选快照哈希：{{ selectedBaseline?.snapshotHash || '未选择' }}。</p></details>
      <section class="card"><h3>职责与下一步</h3><p>{{ nextAction }}</p></section>
    </template>
  </div>
</template>

<script setup>
import { designOrderQuery } from '@/meta/runtime/productDesignNavigation.js'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pdeApi } from '@/api/pde.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import SavedTestCalculationPanel from '@/meta/components/SavedTestCalculationPanel.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createLatestRequestGate } from './productVersionHistoryState.js'

const route=useRoute(),router=useRouter(),loading=ref(false),writing=ref(false),errorMessage=ref(''),orderOptions=ref([]),selectedOrderNo=ref(String(route.query.orderNo||'')),selectedOrder=ref(null),candidateRows=ref([]),candidateBaseline=ref(null),savedBaselineStatus=ref('尚未建立'),savedBaselines=ref([]),selectedBaseline=ref(null),historyComparison=ref({available:false,statusLabel:'暂无其他已保存版本可比较',summary:{}}),persistenceCapability=ref({}),diffFacts=ref({}),gapFacts=ref([]),gapSummary=ref([]),nextAction=ref(''),actionReason=ref('')
const loadGate=createLatestRequestGate()
const previewBusy=ref(false),previewError=ref(''),testPreview=ref(null)
watch([selectedOrderNo,()=>selectedBaseline.value?.baselineId],()=>{testPreview.value=null;previewError.value=''})
async function loadTestPreview(){
  const baselineId=selectedBaseline.value?.baselineId
  previewBusy.value=true;previewError.value='';testPreview.value=null
  try{
    const unpack=r=>r?.data??r
    const context=unpack(await pdeApi.testCalculationPreview({mode:'context',baselineId})).context
    const result=unpack(await pdeApi.testCalculationPreview(context))
    if(selectedBaseline.value?.baselineId===baselineId)testPreview.value=result
  }catch(e){if(selectedBaseline.value?.baselineId===baselineId)previewError.value=e?.response?.data?.message||e.message||'测试预览读取失败。'}
  finally{previewBusy.value=false}
}
const distinctOptions=(rows,field,labelField=field)=>[...new Map((rows||[]).filter(row=>row?.[field]!==''&&row?.[field]!=null).map(row=>[String(row[field]),{value:row[field],label:String(row[labelField]||row[field])}])).values()]
const governedOptions=(field,labelField=field)=>({rows})=>distinctOptions(rows,field,labelField)
const historySortDirection=ref(''),currentSortDirection=ref('')
const missingSortKey=direction=>direction==='descending'?'':'ZZZZZZ未记录'
const historyRows=computed(()=>(selectedBaseline.value?.items||[]).map(item=>({
  ...item,
  designRevisionLabel:item.designRevision?`R${item.designRevision}`:'无独立修订号',
  designRevisionSortKey:item.designRevision==null?missingSortKey(historySortDirection.value):`R${item.designRevision}`,
  sourceVersionSortKey:item.sourceVersion||missingSortKey(historySortDirection.value),
  designNatureLabel:designNatureLabel(item.designNature),
  savedQualificationCode:item.confirmable?'SAVED_CONFIRMABLE':'SAVED_BLOCKED',
  savedQualificationLabel:item.confirmable?'保存时满足':`保存时阻断：${item.blockerLabel}`,
  currentQualificationCode:item.currentConfirmable?'CURRENT_CONFIRMABLE':'CURRENT_BLOCKED',
  currentQualificationLabel:item.currentConfirmable?'当前仍满足':`当前不满足：${item.currentConfirmBlockerLabel}`,
})))
const currentRows=computed(()=>candidateRows.value.map(row=>({
  ...row,
  designRevisionSortKey:row.designRevision==null?missingSortKey(currentSortDirection.value):`R${row.designRevision}`,
  sourceVersionSortKey:row.sourceVersion||missingSortKey(currentSortDirection.value),
  designNatureLabel:designNatureLabel(row.designNature),
  confirmationCode:row.confirmable?'CONFIRMABLE':row.confirmBlockerCode,
  confirmationLabel:row.confirmable?'可确认':row.confirmBlockerLabel,
})))
const historyFilterSchema=[
  {field:'sourceTypeLabel',label:'保存来源',filterType:'select',optionsProvider:governedOptions('sourceTypeLabel')},
  {field:'designNature',label:'设计修订性质',filterType:'select',optionsProvider:governedOptions('designNature','designNatureLabel')},
  {field:'savedQualificationCode',label:'保存时确认条件',filterType:'select',options:[{value:'SAVED_CONFIRMABLE',label:'保存时满足'},{value:'SAVED_BLOCKED',label:'保存时阻断'}]},
  {field:'currentQualificationCode',label:'当前确认条件',filterType:'select',options:[{value:'CURRENT_CONFIRMABLE',label:'当前仍满足'},{value:'CURRENT_BLOCKED',label:'当前不满足'}]},
]
const currentFilterSchema=[
  {field:'designGroup',label:'分组',filterType:'select',optionsProvider:governedOptions('designGroup')},
  {field:'identityCode',label:'工程身份',filterType:'select',optionsProvider:governedOptions('identityCode','identityLabel')},
  {field:'snapshotSourceType',label:'工程内容来源',filterType:'select',optionsProvider:governedOptions('snapshotSourceType','snapshotSourceTypeLabel')},
  {field:'responsibleEmployee',label:'负责人',filterType:'select',optionsProvider:governedOptions('responsibleEmployee')},
  {field:'designNature',label:'设计修订性质',filterType:'select',optionsProvider:governedOptions('designNature','designNatureLabel')},
  {field:'confirmationCode',label:'确认条件',filterType:'select',optionsProvider:governedOptions('confirmationCode','confirmationLabel')},
]
const historyListContract=createPceEnterpriseListContract({pageCode:'pde-product-version-history',pageType:'list',title:'订单工程基线历史快照',moduleCode:'PDE'})
const currentListContract=createPceEnterpriseListContract({pageCode:'pde-product-version-current',pageType:'list',title:'当前最新设计、来源与候选状态',moduleCode:'PDE'})
const historyRuntime=usePceEnterpriseListRuntime({rows:historyRows,filterSchema:historyFilterSchema,pageCode:'pde-product-version-history',searchFields:['itemNo','itemName','sourceTypeLabel','sourceVersion'],exportColumns:[{field:'itemNo',label:'工程对象编号'},{field:'itemName',label:'工程对象名称'},{field:'sourceTypeLabel',label:'保存来源'},{field:'designRevisionLabel',label:'设计修订'},{field:'sourceVersion',label:'来源版本'},{field:'savedQualificationLabel',label:'保存时确认条件'},{field:'currentQualificationLabel',label:'当前确认条件'}],exportFileName:'订单工程基线历史快照.csv'})
const currentRuntime=usePceEnterpriseListRuntime({rows:currentRows,filterSchema:currentFilterSchema,pageCode:'pde-product-version-current',searchFields:['itemNo','itemName','designGroup','identityLabel','snapshotSourceTypeLabel','sourceNo','sourceVersion','responsibleEmployee'],exportColumns:[{field:'itemNo',label:'产品设计项编号'},{field:'itemName',label:'产品设计项名称'},{field:'designGroup',label:'分组'},{field:'identityLabel',label:'工程身份'},{field:'designRevisionLabel',label:'设计修订'},{field:'snapshotSourceTypeLabel',label:'工程内容来源'},{field:'sourceNo',label:'来源编号'},{field:'sourceVersion',label:'来源版本'},{field:'formalProductVersionNo',label:'正式产品版本'},{field:'responsibleEmployee',label:'负责人'},{field:'saveImpactLabel',label:'草稿条件'},{field:'confirmImpactLabel',label:'确认条件'}],exportFileName:'当前工程资料候选状态.csv'})
const {quickSearch:historyQuickSearch,advancedVisible:historyAdvancedVisible,selectedRows:historySelectedRows,filters:historyFilters,tableRef:historyTableRef,activeFilterCount:historyActiveFilterCount,sortState:historySortState,filteredRows:historyFilteredRows,applySearch:historyApplySearch,updateFilter:historyUpdateFilter,clearFilters:historyClearFilters,handleSort:applyHistorySort,clearSort:clearHistoryRuntimeSort,handleSelectionChange:historyHandleSelectionChange,clearSelection:historyClearSelection}=historyRuntime
const {quickSearch:currentQuickSearch,advancedVisible:currentAdvancedVisible,selectedRows:currentSelectedRows,filters:currentFilters,tableRef:currentTableRef,activeFilterCount:currentActiveFilterCount,sortState:currentSortState,filteredRows:currentFilteredRows,applySearch:currentApplySearch,updateFilter:currentUpdateFilter,clearFilters:currentClearFilters,handleSort:applyCurrentSort,clearSort:clearCurrentRuntimeSort,handleSelectionChange:currentHandleSelectionChange,clearSelection:currentClearSelection}=currentRuntime
function historyHandleSort(event={}){historySortDirection.value=event.order||'';applyHistorySort(event)}
function currentHandleSort(event={}){currentSortDirection.value=event.order||'';applyCurrentSort(event)}
function historyClearSort(){historySortDirection.value='';clearHistoryRuntimeSort()}
function currentClearSort(){currentSortDirection.value='';clearCurrentRuntimeSort()}
const sortDirectionLabel=state=>state.order==='descending'?'降序':'升序'
const historySortLabels={itemNo:'工程对象',sourceTypeLabel:'保存来源',designRevisionSortKey:'设计修订',sourceVersionSortKey:'来源版本',savedQualificationCode:'保存时确认条件',currentQualificationCode:'当前确认条件'}
const currentSortLabels={itemNo:'产品设计项',designGroup:'分组',identityLabel:'工程身份',designRevisionSortKey:'设计修订',snapshotSourceTypeLabel:'工程内容来源',sourceVersionSortKey:'来源版本',formalProductVersionNo:'正式产品版本',responsibleEmployee:'负责人',confirmImpactLabel:'草稿 / 确认'}
const historySortText=computed(()=>historySortState.prop?`${historySortLabels[historySortState.prop]||historySortState.prop} ${sortDirectionLabel(historySortState)}`:'默认业务顺序')
const currentSortText=computed(()=>currentSortState.prop?`${currentSortLabels[currentSortState.prop]||currentSortState.prop} ${sortDirectionLabel(currentSortState)}`:'默认业务顺序')
const comparisonItems=computed(()=>(historyComparison.value.items||[]).filter(item=>item.changeCategory!=='same'))
const canSaveDraft=computed(()=>Boolean(persistenceCapability.value.saveDraftAllowed&&candidateBaseline.value?.candidateId&&candidateBaseline.value?.draftSnapshotItemCount===candidateBaseline.value?.designItemCount&&actionReason.value))
const selectedDraft=computed(()=>selectedBaseline.value?.statusCode==='draft'?selectedBaseline.value:null)
const canConfirm=computed(()=>Boolean(persistenceCapability.value.confirmAllowed&&selectedDraft.value&&selectedDraft.value.blockerCount===0&&actionReason.value))
const actionBlocker=computed(()=>{if(selectedBaseline.value?.statusCode==='confirmed')return '本版已确认，可查看保存内容和确认记录；不可重复确认。保存新草稿仍按当前工程资料和保存权限独立判断。';if(!selectedBaseline.value)return '尚未选择待确认的历史草稿。';if(!persistenceCapability.value.confirmAllowed)return persistenceCapability.value.confirmPermission?.reason||'当前账号缺少确认所选草稿的权限。';if(selectedDraft.value?.blockerCount)return `所选草稿保存时有 ${selectedDraft.value.blockerCount} 项阻断，不能确认。`;if(!actionReason.value)return '确认所选草稿前需填写办理原因；只读查看不需要填写。';return '当前所选草稿满足页面前置条件，提交时仍由服务端重新校验来源、权限、并发和幂等。'})

function unwrap(response){return response?.data?.data??response?.data??response}
function clearInvalidSelectFilters(schema,filters,rows){for(const field of schema){if(field.filterType!=='select'||!filters[field.field])continue;const valid=new Set((rows||[]).map(row=>String(row?.[field.field]??'')));if(!valid.has(String(filters[field.field])))filters[field.field]=''}}
function applyPayload(payload){orderOptions.value=payload.orderOptions||[];selectedOrder.value=payload.selectedOrder||null;selectedOrderNo.value=payload.selectedOrder?.orderNo||selectedOrderNo.value||'';candidateRows.value=payload.candidateRows||payload.rows||[];candidateBaseline.value=payload.candidateBaseline||null;savedBaselineStatus.value=payload.savedBaselineStatus||'尚未建立';savedBaselines.value=payload.savedBaselines||[];selectedBaseline.value=payload.selectedBaseline??null;historyComparison.value=payload.historyComparison||{available:false,statusLabel:'暂无其他已保存版本可比较',summary:{}};persistenceCapability.value=payload.persistenceCapability||{};diffFacts.value=payload.diffFacts||{};gapFacts.value=payload.gapFacts||[];gapSummary.value=payload.gapSummary||[];nextAction.value=payload.nextAction||'';clearInvalidSelectFilters(historyFilterSchema,historyFilters,historyRows.value);clearInvalidSelectFilters(currentFilterSchema,currentFilters,currentRows.value)}
async function load(orderNo='',baselineId='',clearSelection=false){const sequence=loadGate.begin();if(clearSelection){selectedBaseline.value=null;historyComparison.value={available:false,statusLabel:'正在读取所选订单历史',summary:{}}}loading.value=true;errorMessage.value='';try{const payload=unwrap(await pdeApi.facts('product-version-management',{...(orderNo?{orderNo}:{}),...(baselineId?{baselineId}:{})}));if(!loadGate.isCurrent(sequence))return;applyPayload(payload);if(clearSelection){historyClearSelection();currentClearSelection()}else if(baselineId){historyClearSelection()}if(selectedOrderNo.value&&route.query.orderNo!==selectedOrderNo.value)router.replace({query:{...route.query,orderNo:selectedOrderNo.value}})}catch(error){if(!loadGate.isCurrent(sequence))return;errorMessage.value=error?.response?.data?.error?.message||error?.response?.data?.message||error?.message||'服务端读取失败。';candidateRows.value=[]}finally{if(loadGate.isCurrent(sequence))loading.value=false}}
async function runAction(payload){writing.value=true;errorMessage.value='';try{applyPayload(unwrap(await pdeApi.productVersionManagementAction(payload,crypto.randomUUID())));actionReason.value=''}catch(error){errorMessage.value=error?.response?.data?.error?.message||error?.response?.data?.message||error?.message||'业务动作失败。'}finally{writing.value=false}}
function changeOrder(){load(selectedOrderNo.value,'',true)}
function loadBaseline(baseline){testPreview.value=null;previewError.value='';load(selectedOrderNo.value,baseline.baselineId)}
function saveDraft(){if(canSaveDraft.value)runAction({action:'saveDraft',orderNo:selectedOrderNo.value,candidateId:candidateBaseline.value.candidateId,reason:actionReason.value})}
function confirmBaseline(){if(canConfirm.value)runAction({action:'confirmBaseline',baselineId:selectedDraft.value.baselineId,expectedVersion:selectedDraft.value.version,reason:actionReason.value})}
function goDesign(){router.push({path:'/pde/product-definitions',query:designOrderQuery(route.query,selectedOrderNo.value)})}
function goCalculation(){router.push({path:'/pde/engineering-calculations',query:{orderNo:selectedOrderNo.value}})}
async function focusItem(itemNo){currentClearFilters();currentQuickSearch.value=itemNo;currentApplySearch();await nextTick();document.getElementById(`item-${itemNo}`)?.scrollIntoView({behavior:'smooth',block:'center'})}
function exportHistoryCurrent(){historyRuntime.exportCurrent()}
function exportCurrentRows(){currentRuntime.exportCurrent()}
function formatTime(value){return value?new Date(value).toLocaleString('zh-CN'):'尚未确认'}
function designNatureLabel(value){return({FORMAL:'正式设计',EXISTING_DESIGN_IMPORTED:'已有设计资料带入',SIMULATED_FOR_TEST:'开发演练模拟设计'})[value]||value||''}
function differenceDisplay(field,value){return field.fieldCode==='revision.designNature'?designNatureLabel(value):value}
onMounted(()=>load(selectedOrderNo.value))
</script>

<style scoped>
.version-page{display:grid;gap:16px;color:#17233b}.version-page,.version-page>*,.card,.primary-flow,.selected-panel,.selected-panel>*,.snapshot-items,.current-facts,.comparison{min-width:0;max-width:100%;box-sizing:border-box}.card{padding:18px;border:1px solid #d6e0ef;border-radius:12px;background:#fff}.intro h2,.card h3{margin:4px 0 8px}.intro p,.card p{color:#52647d}.boundary,.facts,.status-grid,.detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.boundary span,.facts article,.status-grid article,.detail-grid article{display:grid;gap:5px;padding:12px;border-radius:9px;background:#f4f7fb}.primary-flow{display:grid;gap:14px;border:2px solid #9db9df}.step-label{margin-top:6px;color:#174c8f;font-weight:800;letter-spacing:.04em}.card label{display:grid;gap:7px;font-weight:700}.card select,.card input{max-width:720px;padding:9px;border:1px solid #9fb1ca;border-radius:7px}.history{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.history button{display:grid;gap:5px;text-align:left;padding:13px;border:2px solid #c7d4e5;background:#fff;border-radius:10px}.history button span{display:flex;justify-content:space-between;gap:8px}.history button em{font-style:normal;color:#52647d}.history button.active{border-color:#175fc2;background:#eaf3ff;box-shadow:0 0 0 3px #bfdbfe}.selected-panel{display:grid;gap:14px}.viewing-banner{display:flex;align-items:center;gap:8px;padding:13px 16px;background:#123e73;color:#fff;border-radius:9px;font-size:17px}.viewing-banner strong{margin-left:auto;padding:4px 9px;border-radius:999px;background:#fff;color:#123e73}.source-warning,.confirmed-note{margin:0!important;padding:11px;border-radius:8px;background:#edf6ff;color:#244b76!important}.confirmed-note{background:#ecfdf5;color:#166534!important}.detail-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.detail-grid article:nth-child(5){grid-column:span 2}.comparison{padding:15px;border:1px solid #9db9df;border-radius:10px;background:#f8fbff}.card header,.comparison header,.difference-list article>header{display:flex;justify-content:space-between;align-items:center;gap:12px}.baseline-changes{display:flex;flex-wrap:wrap;gap:8px}.baseline-changes span{padding:7px 10px;border-radius:7px;background:#e8eef7}.difference-list{display:grid;gap:10px;margin-top:12px}.difference-list article{padding:12px;border:1px solid #cad7e8;border-radius:8px;background:#fff}.difference-list small{display:block;color:#61738c}.snapshot-items>summary,.technical>summary{cursor:pointer;font-weight:800}.filters{display:flex;gap:10px;margin:12px 0}.filters input{min-width:280px}.table-wrap{overflow-x:auto}table{width:100%;min-width:1050px;border-collapse:collapse}th,td{padding:9px;border:1px solid #dbe3ee;text-align:left;vertical-align:top}th{background:#eef4fb}td small{display:block;margin-top:4px;color:#6b7b90}dl{display:grid;grid-template-columns:minmax(120px,.5fr) 1fr;gap:4px 10px;min-width:480px}dt{font-weight:700}dd{margin:0;word-break:break-word}.guide ol{margin:8px 0;padding-left:22px;color:#40536d}.guide li+li{margin-top:7px}.gap-panel details{margin-top:10px;padding:10px;border:1px solid #dbe3ee;border-radius:8px}.gap-items{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.gap-items button{border:1px solid #b7c7dc;background:#f7faff;border-radius:6px;padding:5px 8px}.nav-actions,.action-buttons{display:flex;gap:10px;margin-top:12px}.actions{display:grid;gap:14px}.actions button,.nav-actions button{padding:9px 13px}.stop{padding:10px;background:#fff7ed;color:#9a3412!important}.current-facts{border-style:dashed}.state{display:flex;gap:12px;align-items:center}.error{color:#991b1b}.technical p{word-break:break-all}@media(max-width:900px){.boundary,.facts,.status-grid,.detail-grid{grid-template-columns:1fr 1fr}.history{grid-template-columns:1fr}.filters{flex-direction:column}}@media(max-width:560px){.boundary,.facts,.status-grid,.detail-grid{grid-template-columns:1fr}.detail-grid article:nth-child(5){grid-column:auto}.history button span,.viewing-banner{display:grid}.viewing-banner strong{margin-left:0}}
.list-scope-note{margin:12px 0!important;padding:9px 12px;border-radius:8px;background:#eef6ff;color:#31577d!important;font-weight:700}.field-details{white-space:normal}.field-details summary{cursor:pointer;color:#175fc2;font-weight:800}.field-details dl{min-width:0;margin:10px 0 0}.current-facts{min-width:0;overflow:hidden}.current-facts :deep(.el-table__cell small),.snapshot-items :deep(.el-table__cell small){display:block;margin-top:4px;color:#6b7b90}
</style>
