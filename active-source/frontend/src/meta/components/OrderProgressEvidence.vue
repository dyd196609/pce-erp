<template>
  <section class="order-progress" :data-task-read-timing="JSON.stringify(taskReadTiming)" aria-label="本单生产进度" :data-progress-order="progress.orderNo">
    <h4>订单 {{ progress.orderNo }} · 生产进度</h4>
    <p>整单完成条件：{{ eligibilityLabel }}。现场实际完工时间：{{ physicalTime(completion) }}。</p>
    <dl v-if="progress.deliveryTiming" class="progress-fields" aria-label="订单承诺交期核对">
      <div><dt>客户需求交期</dt><dd>{{ field(progress.deliveryTiming.customerRequiredDate) }}</dd></div>
      <div><dt>订单承诺交期</dt><dd>{{ field(progress.deliveryTiming.promisedDate) }}</dd></div>
      <div><dt>实际交付日期</dt><dd>{{ field(progress.deliveryTiming.actualDeliveryDate) }}</dd></div>
      <div><dt>延期天数</dt><dd>{{ progress.deliveryTiming.delayDays == null ? '待核' : progress.deliveryTiming.delayDays + ' 天' }}</dd></div>
    </dl>
    <p v-if="progress.deliveryTiming">{{ progress.deliveryTiming.statusLabel }}。{{ progress.deliveryTiming.reason }}
      日期依据：{{ progress.deliveryTiming.planSourceLabel }}、{{ progress.deliveryTiming.actualSourceLabel }}。</p>
    <p v-if="!progress.lines.length">原服务本次未返回订单行进度。</p>

    <SalesDeliveryEvidence v-if="progress.deliveryTiming?.lines?.length" :facts="progress.deliveryTiming" />

    <article v-for="line in progress.lines" :key="line.salesOrderItemId" class="progress-card" :data-progress-line="line.salesOrderItemId">
      <h5>订单第 {{ line.lineNo }} 行 · {{ field(line.materialName) }}</h5>
      <dl class="progress-fields">
        <div><dt>订单行需求</dt><dd>{{ quantity(line.quantity, line.uomLabel) }}</dd></div>
        <div><dt>制造闭合量</dt><dd>{{ quantity(line.supplyCoverage?.manufacturingCompletedQuantity, line.supplyCoverage?.uomLabel) }}</dd></div>
        <div><dt>本行完成条件</dt><dd>{{ condition(line.completionReady) }}</dd></div>
      </dl>
      <ul v-if="line.blockingReasons?.length" aria-label="本行完成条件原因">
        <li v-for="(reason, index) in line.blockingReasons" :key="index">{{ field(reason.message) }}</li>
      </ul>
      <p v-if="!line.workOrders.length">当前未取得本行可核实的工单及工序。</p>

      <div v-for="work in line.workOrders" :key="work.workOrderId" class="progress-card">
        <h6>工单 {{ field(work.workOrderNo) }} · {{ field(work.statusLabel) }}</h6>
        <p v-if="work.factStatus === 'SOURCE_UNKNOWN' || work.factStatus === 'READ_FAILED'" role="status">
          {{ work.factStatus === 'READ_FAILED' ? '工单记录读取失败。' : '工单来源待核。' }}
        </p>
        <ul v-if="newReasons(work.blockingReasons, line.blockingReasons).length">
          <li v-for="(reason, index) in newReasons(work.blockingReasons, line.blockingReasons)" :key="index">{{ field(reason.message) }}</li>
        </ul>
        <template v-if="work.workOrderNo">
          <dl class="progress-fields">
            <div><dt>生产计划</dt><dd>{{ field(work.productionPlanNo) }}</dd></div>
            <div><dt>工单数量</dt><dd>{{ quantity(work.quantity, work.uomLabel) }}</dd></div>
            <div><dt>执行完工</dt><dd>{{ condition(work.executionCompleted) }}</dd></div>
            <div><dt>物理闭合</dt><dd>{{ condition(work.mesClosed) }}</dd></div>
          </dl>
          <template v-for="batch in batches(line, work)" :key="batch.demandId">
            <p data-progress-batch>制造批次 {{ field(batch.batchKey) }} · 计划范围 {{ field(batch.rangeStart) }} 至 {{ field(batch.rangeEnd) }} · 数量 {{ quantity(batch.quantity, line.supplyCoverage?.uomLabel) }}</p>
          </template>
          <p v-if="!batches(line, work).length">原服务未提供该工单对应的制造批次范围。</p>
        </template>

        <details v-for="receipt in work.verifiedWarehouseReceipts || []" :key="receipt.transferId">
          <summary>原成品入库 {{ field(receipt.inboundNo) }} · {{ quantity(receipt.quantity, receipt.uomLabel) }}</summary>
          <p>成品交接单 {{ field(receipt.transferNo) }} · {{ field(receipt.statusLabel) }} · 入库日期 {{ field(receipt.inboundDate) }}</p>
          <p>仓库 {{ field(receipt.warehouseName) }} · 库位 {{ field(receipt.locationName) }} · 实收 {{ field(receipt.receivedAt) }}</p>
          <p>原库存流水 {{ field(receipt.stockTransactionNo) }} · 原保管记录 {{ field(receipt.custodyEventId) }}</p>
          <p>工单执行完工与整单完成条件见本页各自的核验结果。</p>
        </details>
        <ol v-if="work.tasks?.length" class="progress-tasks" aria-label="本工单工序">
          <li v-for="task in work.tasks" :key="task.taskId" class="progress-card" :data-progress-task="task.taskNo">
            <p class="task-title">{{ field(task.operationName) }} · {{ field(task.taskNo) }}</p>
            <p>{{ field(task.workshopName) }}／{{ field(task.workCenterName) }} · {{ field(task.statusLabel) }}</p>
            <p>完工审核：{{ field(task.completionStatusLabel) }}。<template v-if="task.executionConfirmation">{{ field(task.executionConfirmation.statusLabel) }}。</template><template v-if="task.quantityFacts?.quantityApplicable === false">数量不适用。</template></p>
            <p v-if="task.completion?.statusCode === 'pending_review'">待独立审核 · 申请时间 {{ field(task.completion.requestedAtLabel) }}</p>
            <dl v-if="task.quantityFacts?.quantityApplicable !== false" class="progress-fields">
              <div><dt>已核实有效产出</dt><dd>{{ quantity(task.quantityFacts?.account?.E, task.quantityFacts?.account?.uom?.name) }}</dd></div>
              <div><dt>剩余计划量</dt><dd>{{ quantity(task.quantityFacts?.account?.planDeficit, task.quantityFacts?.account?.uom?.name) }}</dd></div>
              <div><dt>已报待核量</dt><dd>{{ quantity(task.quantityFacts?.account?.unconfirmedReportedQuantity, task.quantityFacts?.account?.uom?.name) }}</dd></div>
            </dl>
            <p v-if="task.scheduleTiming">{{ task.scheduleTiming.start.statusLabel }} · {{ task.scheduleTiming.completion.statusLabel }}</p>
            <p v-for="handover in task.handovers || []" :key="handover.id">
              <button type="button" @click="openTask(line, task, handover.id)">回查交接 {{ field(handover.businessNo || handover.no) }}</button>
              · 待实收（在途）{{ quantity(handover.inTransitQuantity, handover.uomLabel) }}
              · 去向 {{ field(handover.targetOperationName) }}／{{ field(handover.targetWorkCenterName) }}
            </p>
            <template v-if="task.factStatus === 'SOURCE_UNKNOWN'">
              <p role="status">部分原始记录来源待核。</p>
              <ul v-if="task.blockingReasons?.length"><li v-for="(reason, index) in task.blockingReasons" :key="index">{{ field(reason.message) }}</li></ul>
            </template>
            <button type="button" :aria-expanded="isSelected(line, task)" @click="openTask(line, task)">查看本工序原始记录</button>
            <section v-if="isSelected(line, task)" class="task-evidence" aria-label="本工序原始记录" :data-evidence-line="line.salesOrderItemId">
              <h6>{{ progress.orderNo }} · 第 {{ line.lineNo }} 行 · {{ task.taskNo }}</h6>
              <button type="button" @click="closeTask">返回本行工序</button>
              <p v-if="loading" role="status">正在读取本工序原始记录。</p>
              <p v-if="error" role="alert">{{ error }}</p>
              <template v-if="evidence">
                <dl class="progress-fields">
                  <div><dt>冻结计划开始</dt><dd>{{ field(evidence.dates?.plannedStartAt) }}</dd></div>
                  <div><dt>冻结计划完成</dt><dd>{{ field(evidence.dates?.plannedCompletionAt) }}</dd></div>
                  <div><dt>实际开工</dt><dd>{{ field(evidence.dates?.actualStartAtLabel || evidence.dates?.actualStartAt) }}</dd></div>
                  <div><dt>开工登记</dt><dd>{{ field(evidence.dates?.startRecordedAtLabel || evidence.dates?.startRecordedAt) }}</dd></div>
                  <div><dt>独审生效</dt><dd>{{ field(evidence.dates?.completionReviewEffectiveAtLabel) }}</dd></div>
                  <div><dt>现场实际完工</dt><dd>{{ physicalTime(evidence) }}</dd></div>
                  <div><dt>工序记录最近登记更新</dt><dd>{{ field(evidence.progressUpdatedAt) }}</dd></div>
                  <div><dt>本次读取时间</dt><dd>{{ field(evidenceReadAt) }}</dd></div>
                </dl>
                <p v-for="timing in visibleTiming(evidence)" :key="timing.actualSourceLabel">
                  {{ timing.statusLabel }}。{{ timing.reason }} 依据：{{ timing.planSourceLabel }}、{{ timing.actualSourceLabel }}。
                </p>
                <p>当前生产事实：{{ field(evidence.currentProduction?.statusLabel) }}。</p>
                <p v-if="evidence.quantityFacts?.quantityApplicable === false">工序数量：不适用。</p>
                <dl v-else-if="evidence.quantityFacts?.account" class="progress-fields">
                  <div v-for="[key, label] in taskQuantities" :key="key"><dt>{{ label }}</dt><dd>{{ quantity(evidence.quantityFacts.account[key], evidence.quantityFacts.account.uom?.name) }}</dd></div>
                </dl>

                <details v-if="evidence.executionConfirmation"><summary>实际经过 · {{ field(evidence.executionConfirmation.statusLabel) }}</summary>
                  <p>{{ field(evidence.executionConfirmation.confirmedByLabel) }} · {{ field(evidence.executionConfirmation.confirmedAtLabel) }}</p>
                  <p>{{ field(evidence.executionConfirmation.reason) }}</p><p>原审计 {{ field(evidence.executionConfirmation.auditReference) }}</p>
                </details>
                <details v-if="evidence.completion"><summary>完工申请与独审 · {{ field(evidence.completion.statusLabel) }}</summary>
                  <p>申请人 {{ field(evidence.completion.applicantLabel) }} · {{ field(evidence.completion.requestedAtLabel) }}</p>
                  <p>审核人 {{ field(evidence.completion.reviewerLabel) }} · 生效 {{ field(evidence.completion.completedAtLabel) }}</p>
                  <p v-for="entry in evidence.completion.statusTransitionHistory" :key="entry.id">{{ field(entry.actionLabel) }} · {{ field(entry.targetStateLabel) }} · {{ field(entry.timestampLabel) }} · {{ field(entry.auditReference) }}</p>
                </details>

                <p v-if="evidence.reports == null">原报工记录未提供。</p>
                <details v-for="report in evidence.reports || []" :key="report.id"><summary>原报工 {{ report.id }} · {{ quantity(report.quantity, report.uomLabel) }}</summary>
                  <p>{{ field(report.statusLabel) }} · {{ field(report.reportedByLabel) }} · 实际发生 {{ field(report.reportedAtLabel || report.reportedAt) }}</p>
                  <p>{{ field(report.reason) }}</p><p>原审计 {{ field(report.auditReference) }}</p>
                </details>
                <p v-if="evidence.handovers == null">原交接记录未提供。</p>
                <details v-for="handover in evidence.handovers || []" :key="handover.id" :open="route.query.officeProgressHandover === String(handover.id)"><summary>原交接 {{ field(handover.businessNo || handover.no) }} · {{ handover.factStatus === 'SOURCE_UNKNOWN' ? '来源待核' : field(handover.statusLabel) }}</summary>
                  <p v-if="handover.factStatus === 'SOURCE_UNKNOWN'">{{ field(handover.blockingReason?.message) }}</p>
                  <template v-else>
                    <p>{{ field(handover.senderEmployeeName) }} → {{ field(handover.receiverEmployeeName) }} · {{ field(handover.receiptStateLabel) }}</p>
                    <dl class="progress-fields">
                      <div v-for="[key, label] in handoverQuantities" :key="key"><dt>{{ label }}</dt><dd>{{ quantity(handover[key], handover.uomLabel) }}</dd></div>
                    </dl>
                    <p v-for="event in handover.historicalDispatches" :key="event.eventId">交出 · {{ field(event.employeeName) }} · {{ quantity(event.quantity, event.uomLabel) }} · {{ field(event.occurredAt) }}</p>
                    <p v-for="event in handover.historicalReceipts" :key="event.eventId">接收 · {{ field(event.employeeName) }} · {{ quantity(event.matchedQuantity, event.uomLabel) }} · {{ field(event.occurredAt) }}</p>
                  </template>
                </details>
              </template>
            </section>
          </li>
        </ol>
      </div>
    </article>
  </section>
</template>

<script setup>
import SalesDeliveryEvidence from './SalesDeliveryEvidence.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request.js'
import { officeOrderReadTiming } from '@/meta/runtime/enterpriseOfficeHome.js'
import { getTabAuthEpoch } from '@/meta/runtime/tabAuthenticationContext.js'

const props = defineProps({
  progress: { type: Object, required: true },
  completion: { type: Object, required: true },
  readFollowupTask: { type: Function, default: null },
})
const route = useRoute(), router = useRouter()
const taskReadTiming = ref(null)
const evidence = ref(null), evidenceReadAt = ref(null), loading = ref(false), error = ref('')
const activeLine = computed(() => props.progress.lines.find(line => String(line.salesOrderItemId) === route.query.officeOrderLine))
const activeTask = computed(() => activeLine.value?.workOrders.flatMap(work => work.tasks || []).find(task =>
  String(task.taskId) === route.query.officeProgressTask && task.recordLocator?.taskId === task.taskId && task.recordLocator.salesOrderId === props.progress.salesOrderId))
const eligibilityLabel = computed(() => ({ READY: '服务核验满足条件', BLOCKED: '受阻，服务核验条件未齐' })[props.progress.completionEligibility] || '尚未提供')
const taskQuantities = [['P', '原工序计划量'], ['R', '已报量'], ['E', '有效产出量'], ['planDeficit', '剩余计划量'], ['unconfirmedReportedQuantity', '已报待核量']]
const handoverQuantities = [['sentQuantity', '已交出'], ['receivedQuantity', '实收'], ['inTransitQuantity', '在途'], ['shortQuantity', '短收'], ['unmatchedQuantity', '待核差额'], ['currentTargetHeldQuantity', '目标当前在手']]
let readCycle = 0

function field(value) { return value == null || value === '' ? '未提供' : String(value) }
function quantity(value, unit) { return value == null || value === '' ? '未提供' : `${value} ${unit || '（单位未提供）'}` }
function condition(value) { return value === true ? '已满足' : value === false ? '未满足' : '未提供' }
function visibleTiming(row) { return row.scheduleTiming ? [row.scheduleTiming.start, row.scheduleTiming.completion] : [] }
function physicalTime(row) { return row.physicalCompletedAtStatus === 'NOT_COLLECTED' ? '尚未采集' : field(row.physicalCompletedAt) }
function batches(line, work) {
  return (line.supplyCoverage?.batches || []).filter(batch => work.demandId != null && batch.demandId === work.demandId)
}
function newReasons(reasons = [], parent = []) {
  return reasons.filter(reason => !parent.some(item => item.scope === reason.scope && item.objectId === reason.objectId && item.code === reason.code && item.message === reason.message))
}
function isSelected(line, task) { return activeLine.value === line && activeTask.value === task }
function openTask(line, task, handoverId) {
  const officeProgressHandover = handoverId == null ? undefined : String(handoverId)
  if (isSelected(line, task) && route.query.officeProgressHandover === officeProgressHandover) return readTask()
  router.replace({ query: { ...route.query, officeOrderLine: String(line.salesOrderItemId),
    officeProgressTask: String(task.taskId), officeProgressHandover } })
}
function closeTask() {
  router.replace({ query: { ...route.query, officeProgressTask: undefined, officeProgressHandover: undefined } })
}

async function readTask() {
  const cycle = ++readCycle, epoch = getTabAuthEpoch()
  evidence.value = null; evidenceReadAt.value = null; error.value = ''; loading.value = false
  const progress = props.progress, task = activeTask.value, line = activeLine.value
  if (!task || (!props.readFollowupTask && route.path !== '/home')) return
  loading.value = true
  taskReadTiming.value = null
  const started = performance.now()
  const read = props.readFollowupTask
    ? props.readFollowupTask(task.taskId)
    : request({ url: `/api/sales/orders/${encodeURIComponent(progress.salesOrderId)}/`,
      params: { includeProgressFacts: 1, progressTaskId: task.taskId, selectedTaskOnly: 1 },
      meta: { module: 'SALES', readOnly: true, factLoad: true }, timeout: 120000 })
  const response = await read.catch(() => null)
  if (cycle !== readCycle) return
  loading.value = false
  if (epoch !== getTabAuthEpoch()) return
  const order = response?.data?.order, result = order?.progressFacts, selected = result?.selectedTask
  if (!response?.success) {
    error.value = response?.error?.message || '原始记录读取失败，请重试本工序。'
    return
  }
  const returnedLine = Array.isArray(result?.lines) ? result.lines.find(item => item.salesOrderItemId === line.salesOrderItemId) : null
  const returnedTasks = Array.isArray(returnedLine?.workOrders) ? returnedLine.workOrders.flatMap(work => work.tasks || []) : []
  if (order?.id !== progress.salesOrderId || order?.orderNo !== progress.orderNo ||
      result?.contractVersion !== progress.contractVersion || result?.salesOrderId !== progress.salesOrderId || result?.orderNo !== progress.orderNo ||
      order.version !== progress.salesOrderVersion || result.salesOrderVersion !== progress.salesOrderVersion ||
      selected?.taskId !== task.taskId || selected?.taskNo !== task.taskNo || selected?.recordLocator?.salesOrderId !== progress.salesOrderId ||
      !returnedTasks.some(item => item.taskId === task.taskId && item.taskNo === task.taskNo)) {
    error.value = '原始记录与当前订单、订单行或版本不一致。请重新读取本单完成依据。'
    return
  }
  evidence.value = selected
  evidenceReadAt.value = result.loadedAt
  taskReadTiming.value = officeOrderReadTiming(progress.salesOrderId, started, String(task.taskId))
}
watch([activeTask, () => props.progress, () => route.path], readTask, { immediate: true })
onBeforeUnmount(() => { readCycle++ })
</script>

<style scoped>
.order-progress,.progress-card,.task-evidence { min-width:0; overflow-wrap:anywhere; }
.progress-card { padding:12px; margin-block:10px; border:1px solid #d6e0ee; border-radius:8px; }
.progress-card h5,.progress-card h6,.task-title { margin:0 0 6px; font-size:inherit; font-weight:650; }
.progress-fields { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
.progress-fields dt { color:#41546a; }
.progress-fields dd { margin:0; padding:0; font-weight:600; font-variant-numeric:tabular-nums; }
.progress-tasks,.order-progress ul { padding-inline-start:20px; }
.task-evidence details { margin-block:8px; }
.order-progress button,.order-progress summary { min-height:44px; cursor:pointer; }
@media(max-width:600px) {
 .order-progress .progress-fields { grid-template-columns:repeat(2,minmax(0,1fr)); }
 .progress-card { padding:8px; }
 .progress-tasks,.order-progress ul { padding-inline-start:16px; }
}
</style>
