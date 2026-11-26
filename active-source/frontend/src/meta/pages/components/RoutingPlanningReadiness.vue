<template>
  <section
    class="routing-planning-readiness"
    data-acceptance-id="routing-production-planning-readiness"
    data-fact-source="server"
    :data-planning-ready="readiness?.planningReady ? 'true' : 'false'"
  >
    <header>
      <div>
        <h3>生产计划承接就绪度</h3>
        <p>只读核验路线、作业量、日产能、准备与转运天数、候选资源、日历与依赖；本页不会创建生产计划或排程。</p>
      </div>
      <el-tag :type="readiness?.planningReady ? 'success' : 'warning'" size="large">
        {{ readiness?.statusLabel || '未取得就绪度事实' }}
      </el-tag>
    </header>

    <el-alert
      v-if="readiness && !readiness.planningReady"
      :title="readiness.blockingSummary"
      :description="`需业务人员提供：${readiness.requiredHumanInputLabel || '未取得'}。系统不会用0、默认资源或推断值补齐。`"
      type="warning"
      :closable="false"
      show-icon
    />

    <dl v-if="readiness" class="summary-grid">
      <div><dt>路线版本</dt><dd>#{{ readiness.routingVersionId }} · {{ readiness.routingVersionNo }}</dd></div>
      <div><dt>BOM版本</dt><dd>#{{ readiness.bomVersionId }} · {{ readiness.bomVersionNo }}</dd></div>
      <div><dt>工序就绪</dt><dd>{{ readiness.readyStepCount }} / {{ readiness.stepCount }}</dd></div>
      <div><dt>依赖完整</dt><dd>{{ readiness.dependencyTopology?.dependencyReferenceIntegrity ? '是' : '否' }}</dd></div>
      <div><dt>分支 / 汇合</dt><dd>{{ readiness.dependencyTopology?.branchStepCount ?? 0 }} / {{ readiness.dependencyTopology?.mergeStepCount ?? 0 }}</dd></div>
      <div><dt>计划／排程写入</dt><dd>{{ readiness.productionPlanCreatedCount }} / {{ readiness.productionScheduleCreatedCount }}</dd></div>
    </dl>

    <section v-if="foundation" class="foundation-assessment">
      <h4>通用工艺路线基础能力</h4>
      <div class="inventory-grid">
        <span>路线 {{ foundation.inventory?.routingCount ?? '-' }}</span>
        <span>版本 {{ foundation.inventory?.routingVersionCount ?? '-' }}</span>
        <span>步骤 {{ foundation.inventory?.routingStepCount ?? '-' }}</span>
        <span>工序 {{ foundation.inventory?.operationCount ?? '-' }}</span>
        <span>工作中心 {{ foundation.inventory?.workCenterCount ?? '-' }}</span>
        <span>设备 {{ foundation.inventory?.equipmentCount ?? '-' }}</span>
        <span>班组 {{ foundation.inventory?.teamCount ?? '-' }}</span>
        <span>标准产能 {{ foundation.inventory?.standardCapacityCount ?? '-' }}</span>
        <span>有效制造日历 {{ foundation.inventory?.workCenterCalendarCount ?? '-' }}</span>
      </div>
      <el-table :data="foundation.capabilities || []" border size="small">
        <el-table-column prop="name" label="能力" min-width="180" />
        <el-table-column prop="classificationLabel" label="分类" width="190" />
        <el-table-column prop="evidence" label="服务端依据" min-width="360" show-overflow-tooltip />
      </el-table>
    </section>

    <section class="maintenance-links">
      <h4>缺失事实的正式维护入口</h4>
      <router-link to="/foundation/master-data/operations">工序核算口径</router-link>
      <router-link to="/foundation/master-data/work-centers">工作中心与制造日历</router-link>
      <router-link to="/foundation/master-data/work-center-operation-capabilities">工序候选工作中心</router-link>
      <router-link to="/foundation/master-data/standard-capacities">标准产能</router-link>
      <router-link to="/foundation/master-data/teams">班组</router-link>
      <router-link to="/foundation/master-data/work-center-team-assignments">工作中心可用班组</router-link>
    </section>

    <section v-if="readiness" class="step-readiness">
      <h4>路线步骤计划输入（{{ readiness.stepCount }}）</h4>
      <el-table :data="readiness.steps || []" height="420" border size="small">
        <el-table-column prop="sequence" label="顺序" width="70" fixed="left" />
        <el-table-column prop="operationCode" label="工序编码" width="140" />
        <el-table-column prop="operationName" label="工序名称" min-width="150" />
        <el-table-column label="作业量口径" min-width="210">
          <template #default="{ row }">
            {{ row.calculationBasis || '未维护' }} / {{ row.calculationUom || '未维护单位' }} / {{ row.quantityDriver || '未维护来源' }}
          </template>
        </el-table-column>
        <el-table-column label="标准产能（数量 / 天）" min-width="300">
          <template #default="{ row }">
            <div v-if="row.dailyCapacity?.length" class="daily-capacity-facts">
              <p v-for="capacity in row.dailyCapacity" :key="capacity.id">
                {{ capacity.productTypeCode }} · {{ capacity.quantity ?? '未维护' }} {{ capacity.uomLabel }} / 天 · {{ capacity.statusLabel }}
              </p>
            </div>
            <span v-else>未维护</span>
          </template>
        </el-table-column>
        <el-table-column label="准备时间（天）" width="145">
          <template #default="{ row }">{{ row.preparationDays ?? '未维护' }}</template>
        </el-table-column>
        <el-table-column label="转运时间（天）" width="145">
          <template #default="{ row }">{{ row.transferDays ?? '未维护' }}</template>
        </el-table-column>
        <el-table-column label="候选工作中心" min-width="230">
          <template #default="{ row }">
            {{ row.candidateWorkCenters?.length ? row.candidateWorkCenters.map(item => `${item.code}(${item.role})`).join('、') : '未维护' }}
          </template>
        </el-table-column>
        <el-table-column label="产能 / 日历" width="150">
          <template #default="{ row }">
            {{ row.capacities?.length || 0 }} 条 / {{ row.candidateWorkCenters?.filter(item => item.calendar?.ready).length || 0 }} 个
          </template>
        </el-table-column>
        <el-table-column label="前置步骤" width="130">
          <template #default="{ row }">{{ row.predecessorSequences?.length ? row.predecessorSequences.join('、') : '起始步骤' }}</template>
        </el-table-column>
        <el-table-column label="阻断" min-width="280" fixed="right">
          <template #default="{ row }">{{ row.blockerLabels?.length ? row.blockerLabels.join('、') : '无' }}</template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>

<script setup>
defineProps({
  readiness: { type: Object, default: null },
  foundation: { type: Object, default: null },
})
</script>

<style scoped>
.routing-planning-readiness{display:grid;gap:14px;margin-top:16px;padding:16px;border:1px solid #cbd9e8;border-radius:12px;background:#fff}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}h3,h4,p{margin:0}header p{margin-top:6px;color:#64748b}
.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0}.summary-grid div{padding:10px 12px;border-radius:8px;background:#f4f7fb}.summary-grid dt{font-size:13px;color:#64748b}.summary-grid dd{margin:4px 0 0;font-weight:700;overflow-wrap:anywhere}
.foundation-assessment,.step-readiness{display:grid;gap:10px}.inventory-grid{display:flex;gap:8px;flex-wrap:wrap}.inventory-grid span{padding:6px 9px;border-radius:999px;background:#eef5ff;color:#244b78}
.maintenance-links{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:12px;border:1px solid #d7b468;border-radius:9px;background:#fffaf0}.maintenance-links h4{flex-basis:100%}.maintenance-links a{padding:7px 10px;border:1px solid #9eb7d8;border-radius:7px;background:#fff;color:#2457a6;text-decoration:none;font-weight:700}
@media (max-width:760px){.summary-grid{grid-template-columns:1fr}}
</style>
