<template>
  <section v-if="candidate" class="card manufacturing-handoff" data-acceptance-id="manufacturing-output-handoff" data-fact-source="server">
    <h2>{{ candidate.orderNo }} / 行{{ candidate.lineNo }} — 制造输出承接</h2>
    <PceBusinessStatus :status-label="candidate.statusLabel" source="server" />
    <p>生成制造输出草稿与正式发布至制造是两个不同业务动作；发布不自动生成生产计划、MRP或工单。</p>
    <div v-if="candidate.selectionCandidates" class="source-grid" data-acceptance-id="manufacturing-output-version-selection">
      <label>订单行
        <el-select :model-value="candidate.selection?.salesOrderItemId" :disabled="submitting || selecting"
          placeholder="请选择订单行" @change="selectOrderItem">
          <el-option v-for="option in candidate.selectionCandidates.salesOrderItems || []" :key="option.id" :label="option.label" :value="option.id" />
        </el-select>
      </label>
      <label>工程资料版本
        <el-select :model-value="candidate.selection?.engineeringDocumentVersionId" :disabled="submitting || selecting"
          clearable placeholder="明确选择已发布工程资料版本" @change="selectDocument">
          <el-option v-for="option in candidate.selectionCandidates.engineeringDocumentVersions || []" :key="option.id" :label="option.label" :value="option.id" />
        </el-select>
      </label>
      <label>前驱制造输出
        <el-select :model-value="candidate.selection?.predecessorOutputId" :disabled="submitting || selecting"
          clearable placeholder="新修订须明确选择已发布前驱" @change="selectPredecessor">
          <el-option v-for="option in candidate.selectionCandidates.predecessorOutputs || []" :key="option.id" :label="option.label" :value="option.id" />
        </el-select>
      </label>
    </div>
    <p v-if="selecting" role="status">正在重新读取所选版本的正式事实…</p>
    <dl class="source-grid">
      <div><dt>工程实例</dt><dd>{{ candidate.orderEngineeringInstanceNo || '未取得' }}</dd></div>
      <div><dt>工程基线</dt><dd>{{ candidate.engineeringBaselineNo || '未取得' }}</dd></div>
      <div><dt>工程核算</dt><dd>{{ candidate.engineeringCalculationNo || '未取得' }}</dd></div>
      <div><dt>BOM版本</dt><dd>{{ candidate.bomVersionLabel }} · {{ candidate.bomStatusLabel }}</dd></div>
      <div><dt>工艺路线版本</dt><dd>{{ candidate.routingVersionLabel }} · {{ candidate.routingStatusLabel }}</dd></div>
      <div><dt>工程资料版本</dt><dd>{{ candidate.documentVersionLabel }} · {{ candidate.documentStatusLabel }}</dd></div>
      <div><dt>制造输出</dt><dd>{{ candidate.outputCount ?? '未取得' }} 条</dd></div>
      <div><dt>当前操作人</dt><dd>{{ candidate.currentUser?.realName }} / {{ candidate.currentUser?.username }}</dd></div>
      <div><dt>正式生成执行人</dt><dd>{{ candidate.eligibleExecutors?.map(actor => `${actor.realName} / ${actor.username} / ${actor.positionName}`).join('；') || '未解析' }}</dd></div>
    </dl>
    <el-alert v-if="candidate.firstBlockerMessage" type="warning" show-icon :closable="false"
      title="制造输出生成已阻断" :description="`${candidate.firstBlockerCode}：${candidate.firstBlockerMessage}`" />
    <section v-if="candidate.existingOutputs?.length" data-acceptance-id="manufacturing-output-version-history">
      <h3>已保存制造输出版本</h3>
      <p v-for="output in candidate.existingOutputs" :key="output.id">
        版本 {{ output.revision }} · ID {{ output.id }} · {{ output.statusLabel }}；
        工程资料 {{ output.engineeringDocumentVersionId }}；基线 {{ output.orderEngineeringBaselineId }}；路线 {{ output.routingVersionId }}
      </p>
    </section>
    <div v-if="candidate.output" data-acceptance-id="manufacturing-output-formal-readback">
      <strong>ProductManufacturingOutput ID {{ candidate.output.id }}</strong>
      <PceBusinessStatus :status-label="candidate.output.statusLabel" source="server" />
      <p>来源已按准确外键保存；制造发布结果以以下服务端原生回读为准。</p>
      <p>生成审计 {{ candidate.output.generationReadback?.auditId }}；写入请求 {{ candidate.output.generationReadback?.writeRequestId }}；初始化转换 {{ candidate.output.generationReadback?.initializationTransitionId }}</p>
      <section v-if="candidate.manufacturingRelease" data-acceptance-id="manufacturing-output-release-readiness">
        <h3>制造正式发布结果与准入</h3>
        <PceBusinessStatus :status-label="candidate.manufacturingRelease.statusLabelForReadiness" source="server" />
        <el-alert v-if="candidate.manufacturingRelease.releaseCompleted" type="success" show-icon :closable="false"
          :title="candidate.manufacturingRelease.statusLabelForReadiness" :description="candidate.manufacturingRelease.completionMessage"
          data-acceptance-id="manufacturing-output-release-completed" />
        <dl v-if="candidate.manufacturingRelease.releaseCompleted" class="source-grid" data-acceptance-id="manufacturing-output-release-native-proof">
          <div><dt>正式发布人</dt><dd>{{ candidate.manufacturingRelease.releaseReadback.actorUsername }}</dd></div>
          <div><dt>正式发布时间</dt><dd>{{ candidate.manufacturingRelease.releaseReadback.releasedAt }}</dd></div>
          <div><dt>发布审计</dt><dd>{{ candidate.manufacturingRelease.releaseReadback.auditId }}</dd></div>
          <div><dt>发布请求 / 状态转换</dt><dd>{{ candidate.manufacturingRelease.releaseReadback.writeRequestId }} / {{ candidate.manufacturingRelease.releaseReadback.businessStateTransitionId }}</dd></div>
        </dl>
        <p>合法发布人：{{ candidate.manufacturingRelease.eligiblePublishers?.map(actor => `${actor.realName} / ${actor.username} / ${actor.positionName}`).join('；') || '未解析' }}</p>
        <p>发布权限：{{ candidate.manufacturingRelease.actionContract.requiredPermission }}；公司级 Scope及生产发布职责由服务端校验。</p>
        <ul><li v-for="gate in candidate.manufacturingRelease.gates" :key="gate.code">{{ gate.label }}：{{ gate.statusLabel }} — {{ gate.evidence }}</li></ul>
        <el-alert v-if="candidate.manufacturingRelease.firstBlockerMessage" type="warning" show-icon :closable="false"
          title="制造发布已阻断" :description="`${candidate.manufacturingRelease.firstBlockerCode}：${candidate.manufacturingRelease.firstBlockerMessage}`" />
        <p>标准工时、工作中心和StandardCapacity为资源观察项，不是当前制造发布门禁。</p>
        <div v-if="candidate.manufacturingRelease.releaseAllowed" class="generation-input">
          <el-input v-model="releaseReason" type="textarea" :rows="2" maxlength="300" placeholder="请由合法发布人填写制造发布理由" />
          <el-button type="warning" :disabled="submitting || selecting || !releaseReason.trim()" :loading="submitting" @click="release">
            {{ candidate.manufacturingRelease.actionContract.displayName }}
          </el-button>
        </div>
      </section>
    </div>
    <div v-else class="generation-input">
      <el-input v-model="reason" type="textarea" :rows="2" maxlength="300" placeholder="请填写来源确认与生成说明" />
      <el-button type="primary" :disabled="!candidate.generationAllowed || submitting || selecting || !reason.trim()"
        :loading="submitting" @click="submit">{{ candidate.actionLabel }}</el-button>
    </div>
  </section>
</template>
<script setup>
import { ref, watch } from 'vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
const props = defineProps({ candidate: { type: Object, default: null }, submitting: Boolean })
const emit = defineEmits(['generate', 'release', 'select-version'])
const reason = ref('')
const releaseReason = ref('')
const selecting = ref(false)
watch(() => props.candidate, () => { selecting.value = false })
function selectVersion(selection) {
  if (props.submitting || selecting.value) return
  selecting.value = true
  emit('select-version', selection)
}
function selectOrderItem(salesOrderItemId) {
  selectVersion({ salesOrderItemId, engineeringDocumentVersionId: null, predecessorOutputId: null })
}
function selectDocument(engineeringDocumentVersionId) {
  selectVersion({ ...props.candidate.selection, engineeringDocumentVersionId: engineeringDocumentVersionId || null })
}
function selectPredecessor(predecessorOutputId) {
  selectVersion({ ...props.candidate.selection, predecessorOutputId: predecessorOutputId || null })
}
function submit() {
  if (props.submitting || selecting.value || !props.candidate?.generationAllowed || !reason.value.trim()) return
  emit('generate', { salesOrderItemId: props.candidate.salesOrderItemId,
    sourceFingerprint: props.candidate.sourceFingerprint, action: props.candidate.actionCode,
    ...(props.candidate.selection?.engineeringDocumentVersionId ? {
      engineeringDocumentVersionId: props.candidate.selection.engineeringDocumentVersionId,
      predecessorOutputId: props.candidate.selection.predecessorOutputId ?? null,
    } : {}),
    reason: reason.value.trim() })
}
function release() {
  const readiness = props.candidate?.manufacturingRelease
  if (props.submitting || selecting.value || !readiness?.releaseAllowed || !releaseReason.value.trim()) return
  emit('release', { outputId: props.candidate.output.id, action: readiness.actionContract.actionCode,
    sourceFingerprint: readiness.sourceFingerprint, reason: releaseReason.value.trim() })
}
</script>
<style scoped>
.manufacturing-handoff{display:grid;gap:14px}.source-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:0}.source-grid>div{background:#f5f8fb;border-radius:8px;padding:12px;display:grid;gap:6px}.source-grid dt{color:#64748b}.source-grid dd{margin:0;font-weight:600}.generation-input{display:grid;gap:10px}.generation-input .el-button{justify-self:start}
.source-grid>label{display:grid;gap:6px;min-width:0}.source-grid .el-select{width:100%}
</style>
