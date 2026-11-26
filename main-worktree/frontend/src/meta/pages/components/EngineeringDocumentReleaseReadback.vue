<template>
  <section
    v-if="!detail"
    class="card engineering-document-handoff"
    data-acceptance-id="engineering-document-release-handoff"
    data-fact-source="server"
  >
    <header class="section-heading">
      <div>
        <small>第11节点 · 只读正式承接</small>
        <h2>工程资料发布状态</h2>
      </div>
      <strong class="handoff-badge">{{ facts.nodeHandoffStatusLabel || '承接状态未取得' }}</strong>
    </header>

    <el-alert
      v-if="Number(facts.engineeringDocumentCount) === 0"
      title="当前暂无可发布工程资料"
      description="上游工程数据已经承接，但上游数据不等于正式工程资料；本页没有创建资料，也没有执行发布。"
      type="warning"
      show-icon
      :closable="false"
      data-acceptance-id="engineering-document-empty-business-state"
    />

    <div class="metric-grid" data-acceptance-id="engineering-document-formal-counts">
      <article><small>工程资料</small><strong>{{ count(facts.engineeringDocumentCount) }}</strong></article>
      <article><small>资料版本</small><strong>{{ count(facts.engineeringDocumentVersionCount) }}</strong></article>
      <article><small>可发布资料</small><strong>{{ count(facts.publishableEngineeringDocumentCount) }}</strong></article>
      <article><small>已发布资料</small><strong>{{ count(facts.releasedEngineeringDocumentCount) }}</strong></article>
      <article><small>已发布至制造</small><strong>{{ count(facts.releasedManufacturingOutputCount) }}</strong></article>
      <article><small>本轮执行发布</small><strong>{{ facts.publicationExecutedThisRound ? '是' : '否' }}</strong></article>
    </div>

    <div class="explanation-grid">
      <article>
        <small>现有业务设计</small>
        <strong>{{ facts.engineeringDocumentBusinessDesign || '-' }}</strong>
      </article>
      <article>
        <small>物理文件能力</small>
        <strong>{{ facts.physicalFileCapabilityLabel || '-' }}</strong>
      </article>
      <article>
        <small>下一业务动作</small>
        <strong>{{ facts.nextBusinessActionLabel || '-' }}</strong>
      </article>
    </div>

    <section class="manual-input" data-acceptance-id="engineering-document-manual-input-requirements">
      <h3>如需形成真实工程资料，业务人员需一次性提供</h3>
      <dl>
        <div><dt>必填</dt><dd>{{ requiredInputs }}</dd></div>
        <div><dt>可选</dt><dd>{{ optionalInputs }}</dd></div>
        <div><dt>物理文件类型</dt><dd>{{ inputRequirements.physicalFileAcceptanceLabel || '未定义' }}</dd></div>
        <div><dt>业务对象关系</dt><dd>{{ inputRequirements.businessObjectRelationLabel || '未定义' }}</dd></div>
        <div><dt>版本号</dt><dd>{{ inputRequirements.versionRequired ? '必填' : '非必填' }}</dd></div>
        <div><dt>发布说明</dt><dd>{{ inputRequirements.releaseNoteLabel || '未定义' }}</dd></div>
        <div><dt>人工确认发布</dt><dd>{{ inputRequirements.humanReleaseConfirmationLabel || '未定义' }}</dd></div>
      </dl>
    </section>
  </section>

  <section
    v-else
    class="engineering-document-detail-readback"
    data-acceptance-id="engineering-document-release-detail-readback"
    data-fact-source="server"
  >
    <header>
      <small>订单行正式继承链</small>
      <h3>{{ detail.releaseCandidateIdentity }}</h3>
      <strong>{{ detail.nodeHandoffStatusLabel }}</strong>
    </header>

    <div class="chain-grid" data-acceptance-id="engineering-document-upstream-chain">
      <article><small>公司</small><strong>{{ detail.companyCode || '-' }}</strong></article>
      <article><small>销售订单 / 行</small><strong>{{ detail.orderNo }} / 行{{ detail.orderLineNo }}</strong></article>
      <article><small>订单工程实例</small><strong>{{ detail.orderEngineeringInstanceNo || '-' }}</strong></article>
      <article><small>ProductBOM</small><strong>ID {{ value(detail.productBomId) }} / {{ detail.bomCode || '-' }}</strong></article>
      <article><small>BOMVersion</small><strong>ID {{ value(detail.bomVersionId) }} / {{ detail.bomVersionNo || '-' }} / {{ detail.bomVersionStatusLabel || '-' }}</strong></article>
      <article><small>来源工程核算</small><strong>{{ detail.sourceCalculationNo || '-' }} / ID {{ value(detail.sourceCalculationId) }}</strong></article>
      <article><small>工艺路线</small><strong>ID {{ value(detail.routingId) }} / {{ detail.routingCode || '-' }} / {{ detail.routingName || '-' }} / {{ detail.routingStatusLabel || '-' }}</strong></article>
      <article><small>工艺路线版本</small><strong>ID {{ value(detail.routingVersionId) }} / {{ detail.routingVersionNo || '-' }} / Revision {{ value(detail.routingVersionRevision) }} / {{ detail.routingVersionStatusLabel || '-' }}</strong></article>
      <article><small>版本工序</small><strong>{{ count(detail.routingStepCount) }} 道</strong><span>{{ detail.routingStepRelationshipSemanticsLabel }}</span></article>
    </div>

    <div class="metric-grid" data-acceptance-id="engineering-document-line-counts">
      <article><small>工程资料</small><strong>{{ count(detail.engineeringDocumentCount) }}</strong></article>
      <article><small>资料版本</small><strong>{{ count(detail.engineeringDocumentVersionCount) }}</strong></article>
      <article><small>可发布资料</small><strong>{{ count(detail.publishableEngineeringDocumentCount) }}</strong></article>
      <article><small>已发布资料</small><strong>{{ count(detail.releasedEngineeringDocumentCount) }}</strong></article>
    </div>

    <el-alert
      :title="detail.documentAvailabilityStatusLabel || '资料状态未取得'"
      :description="detail.documentPublicationStatusLabel || ''"
      :type="Number(detail.publishableEngineeringDocumentCount) > 0 ? 'success' : 'warning'"
      show-icon
      :closable="false"
      data-acceptance-id="engineering-document-line-business-state"
    />

    <div class="status-grid">
      <article><small>当前资料状态</small><strong>{{ detail.currentDocumentStatusLabel || '-' }}</strong></article>
      <article><small>资料归属核验</small><strong>{{ detail.documentOwnershipStatusLabel || '-' }}</strong></article>
      <article><small>正式制造资格</small><strong>{{ detail.formalManufacturingEligibilityLabel || '-' }}</strong></article>
      <article><small>本轮发布</small><strong>{{ detail.publicationExecutedThisRound ? '已执行' : '未执行' }}</strong></article>
    </div>

    <section
      v-if="detail.engineeringDocumentVersionId"
      class="review-admission"
      data-acceptance-id="engineering-document-version-review-admission"
    >
      <header>
        <div>
          <small>工程资料版本正式评审</small>
          <h4>{{ reviewPreflight.decisionLabel || '评审准入未取得' }}</h4>
        </div>
        <strong>{{ reviewCompleted ? 'FORMAL REVIEW COMPLETED' : (reviewPreflight.readyForHumanReview ? 'READY_FOR_HUMAN_REVIEW' : '当前阻断') }}</strong>
      </header>
      <div class="status-grid">
        <article><small>工程资料版本</small><strong>ID {{ detail.engineeringDocumentVersionId }} / {{ detail.version }}</strong></article>
        <article><small>当前状态</small><strong>{{ detail.documentVersionStatusLabel || '-' }}</strong></article>
        <article><small>正式评审权限</small><strong>{{ reviewPreflight.permissionCode || '-' }}</strong></article>
        <article><small>当前操作人</small><strong>{{ currentActorLabel }}</strong></article>
        <article><small>合法评审人</small><strong>{{ eligibleActorsLabel }}</strong></article>
        <article><small>当前浏览器可操作</small><strong>{{ reviewPreflight.currentBrowserOperable ? '是' : '否' }}</strong></article>
      </div>
      <el-alert
        v-if="reviewCompleted"
        title="正式评审已完成"
        :description="`评审人：${reviewPreflight.reviewReadback?.actorRealName || reviewPreflight.reviewReadback?.actorUsername || '-'}；Workflow ${reviewPreflight.reviewReadback?.workflowInstanceId || '-'} / Decision ${reviewPreflight.reviewReadback?.decisionId || '-'}。不得重复评审。`"
        type="success"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="!reviewPreflight.readyForHumanReview"
        :title="reviewPreflight.firstBlockerLabel || '正式评审准入阻断'"
        :description="reviewPreflight.firstBlockerMessage || '服务端未返回可放行的正式责任链。'"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="!reviewPreflight.currentBrowserOperable"
        title="服务端准入已通过，但当前登录账号不是已授权评审人"
        description="请由页面列出的正式评审人员本人正常登录后执行；不得注入或替代会话。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else
        title="正式评审准入通过"
        description="评审与发布是两个业务动作；本按钮只保存当前工程资料版本的人工评审决定，不执行发布。"
        type="success"
        show-icon
        :closable="false"
      />
      <details v-if="!reviewCompleted">
        <summary>查看服务端准入门禁（{{ reviewPreflight.gatePassCount || 0 }}通过 / {{ reviewPreflight.gateFailCount || 0 }}阻断）</summary>
        <ul>
          <li v-for="gate in reviewGates" :key="gate.code">
            <strong>{{ gate.statusLabel }} · {{ gate.label }}</strong>：{{ gate.evidence }}
          </li>
        </ul>
      </details>
      <div v-if="!reviewCompleted && reviewPreflight.reviewAllowed" class="review-action">
        <el-input
          v-model="reviewReason"
          type="textarea"
          :rows="3"
          maxlength="300"
          show-word-limit
          :placeholder="`请填写本人对工程资料版本${detail.version || ''}的正式评审意见`"
        />
        <el-button
          type="primary"
          :loading="props.reviewSubmitting"
          :disabled="props.reviewSubmitting || !reviewReason.trim()"
          @click="submitReview"
        >正式评审通过</el-button>
      </div>
    </section>

    <section
      v-if="detail.engineeringDocumentVersionId"
      class="release-admission"
      data-acceptance-id="engineering-document-version-release-admission"
    >
      <header>
        <div>
          <small>工程资料版本正式发布</small>
          <h4>{{ documentReleasePreflight.decisionLabel || '发布准入未取得' }}</h4>
        </div>
        <strong>{{ documentReleaseCompleted ? 'FORMAL RELEASE COMPLETED' : (documentReleasePreflight.readyForHumanRelease ? 'READY_FOR_HUMAN_DOCUMENT_RELEASE' : '当前阻断') }}</strong>
      </header>
      <div class="status-grid">
        <article><small>正式评审</small><strong>{{ reviewCompleted ? '已完成' : '未完成' }}</strong></article>
        <article><small>当前版本</small><strong>{{ detail.documentVersionStatusLabel || '-' }}</strong></article>
        <article><small>当前版本发布状态</small><strong>{{ documentReleaseCompleted ? '已发布' : '未发布' }}</strong></article>
        <article><small>正式发布权限</small><strong>{{ documentReleasePreflight.permissionCode || '-' }}</strong></article>
        <article><small>合法发布人员</small><strong>{{ eligibleReleaseActorsLabel }}</strong></article>
        <article><small>当前操作人</small><strong>{{ currentReleaseActorLabel }}</strong></article>
        <article><small>当前浏览器可操作</small><strong>{{ documentReleasePreflight.currentBrowserOperable ? '是' : '否' }}</strong></article>
        <article><small>制造发布</small><strong>未执行（独立后续动作）</strong></article>
      </div>
      <el-alert
        v-if="documentReleaseCompleted"
        title="工程资料版本正式发布已完成"
        description="页面已回读到版本、状态转换、审计和写入请求；制造发布仍是独立后续动作。"
        type="success"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="!documentReleasePreflight.readyForHumanRelease"
        :title="documentReleasePreflight.firstBlockerLabel || '正式发布准入阻断'"
        :description="documentReleasePreflight.firstBlockerMessage || '服务端未返回可放行的工程资料版本发布控制链。'"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="!documentReleasePreflight.currentBrowserOperable"
        title="服务端正式发布准入已通过，但当前登录账号不是合法发布人员"
        description="请由页面列出的合法发布人员本人正常登录后操作。当前账号不能因此绕过发布责任链。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else
        title="工程资料版本正式发布准入通过"
        description="本动作仅将当前工程资料版本由已评审转换为已发布；不会创建或推进制造发布记录。"
        type="success"
        show-icon
        :closable="false"
      />
      <details>
        <summary>查看服务端发布门禁（{{ documentReleasePreflight.gatePassCount || 0 }}通过 / {{ documentReleasePreflight.gateFailCount || 0 }}阻断）</summary>
        <ul>
          <li v-for="gate in releaseGates" :key="gate.code">
            <strong>{{ gate.statusLabel }} · {{ gate.label }}</strong>：{{ gate.evidence }}
          </li>
        </ul>
      </details>
      <div v-if="documentReleasePreflight.releaseAllowed" class="review-action">
        <el-input
          v-model="releaseReason"
          type="textarea"
          :rows="3"
          maxlength="300"
          show-word-limit
          :placeholder="`请填写本人对工程资料版本${detail.version || ''}的正式发布说明`"
        />
        <el-button
          type="primary"
          :loading="props.releaseSubmitting"
          :disabled="props.releaseSubmitting || !releaseReason.trim()"
          @click="submitRelease"
        >正式发布工程资料版本</el-button>
      </div>
    </section>

    <section class="blockers" data-acceptance-id="engineering-document-release-blockers">
      <h4>后续制造发布尚缺条件（不阻断工程资料版本独立发布）</h4>
      <ul v-if="missingConditions.length">
        <li v-for="condition in missingConditions" :key="condition">{{ condition }}</li>
      </ul>
      <p v-else>当前没有服务端返回的阻断项。</p>
    </section>

    <section class="next-action" data-acceptance-id="engineering-document-next-business-action">
      <h4>下一业务动作</h4>
      <p>{{ detail.nextBusinessActionLabel || '-' }}</p>
      <small>{{ detail.physicalFileCapabilityLabel }}</small>
    </section>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  facts: { type: Object, default: () => ({}) },
  detail: { type: Object, default: null },
  reviewSubmitting: { type: Boolean, default: false },
  releaseSubmitting: { type: Boolean, default: false },
})
const emit = defineEmits(['review-version', 'release-version'])

const inputRequirements = computed(() => props.facts.manualInputRequirements || {})
const requiredInputs = computed(() => (inputRequirements.value.required || []).join('、') || '未定义')
const optionalInputs = computed(() => (inputRequirements.value.optional || []).join('、') || '无')
const missingConditions = computed(() => Array.isArray(props.detail?.formalMissingConditions)
  ? props.detail.formalMissingConditions
  : [])
const reviewPreflight = computed(() => props.detail?.reviewPreflight || {})
const reviewGates = computed(() => Array.isArray(reviewPreflight.value.gates)
  ? reviewPreflight.value.gates
  : [])
const reviewCompleted = computed(() => reviewPreflight.value.reviewReadback?.completed === true)
const documentReleasePreflight = computed(() => props.detail?.documentReleasePreflight || {})
const documentReleaseCompleted = computed(() => (
  documentReleasePreflight.value.releaseReadback?.completed === true
))
const releaseGates = computed(() => Array.isArray(documentReleasePreflight.value.gates)
  ? documentReleasePreflight.value.gates
  : [])
const currentActorLabel = computed(() => {
  const actor = reviewPreflight.value.currentActor || {}
  const user = reviewPreflight.value.currentUser || {}
  if (actor.username) return `${actor.realName || actor.username} / ${actor.username}`
  return `${user.realName || user.username || '未取得'} / ${user.username || '未取得'}`
})
const eligibleActorsLabel = computed(() => {
  const actors = reviewPreflight.value.eligibleReviewActors || []
  if (!actors.length) return '未任命'
  return actors.map(actor => `${actor.realName || actor.username} / ${actor.positionName}`).join('；')
})
const currentReleaseActorLabel = computed(() => {
  const actor = documentReleasePreflight.value.currentActor || {}
  const user = documentReleasePreflight.value.currentUser || {}
  if (actor.username) return `${actor.realName || actor.username} / ${actor.username}`
  return `${user.realName || user.username || '未取得'} / ${user.username || '未取得'}`
})
const eligibleReleaseActorsLabel = computed(() => {
  const actors = documentReleasePreflight.value.eligibleReleaseActors || []
  if (!actors.length) return '未任命'
  return actors.map(actor => (
    `${actor.realName || actor.username} / ${actor.username} / ${actor.positionName}`
  )).join('；')
})
const reviewReason = ref('')
const releaseReason = ref('')

function submitReview() {
  const reason = reviewReason.value.trim()
  if (!reason || props.reviewSubmitting || !reviewPreflight.value.reviewAllowed) return
  emit('review-version', {
    versionId: props.detail.engineeringDocumentVersionId,
    versionNo: props.detail.version,
    reason,
  })
}

function submitRelease() {
  const reason = releaseReason.value.trim()
  if (!reason || props.releaseSubmitting || !documentReleasePreflight.value.releaseAllowed) return
  emit('release-version', {
    versionId: props.detail.engineeringDocumentVersionId,
    versionNo: props.detail.version,
    reason,
  })
}

const count = value => Number.isFinite(Number(value)) ? Number(value) : '未取得'
const value = raw => raw ?? '未形成'
</script>

<style scoped>
.engineering-document-handoff,.engineering-document-detail-readback{display:grid;gap:16px;min-width:0}.section-heading,.engineering-document-detail-readback>header,.review-admission>header,.release-admission>header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.section-heading h2,.engineering-document-detail-readback h3,.review-admission h4,.release-admission h4{margin:3px 0 0}.section-heading small,.engineering-document-detail-readback small,.metric-grid small,.chain-grid small,.status-grid small,.explanation-grid small{color:#64748b}.handoff-badge{max-width:420px;padding:8px 12px;border-radius:999px;background:#e8f5ec;color:#1d6840;text-align:center}.metric-grid,.chain-grid,.status-grid,.explanation-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.metric-grid article,.chain-grid article,.status-grid article,.explanation-grid article{display:grid;gap:5px;padding:12px;border-radius:9px;background:#f5f8fb}.metric-grid strong{font-size:24px;color:#173f68}.chain-grid article{background:#f7faf8}.chain-grid span{color:#64748b;font-size:12px}.manual-input,.blockers,.next-action,.review-admission,.release-admission{display:grid;gap:12px;padding:14px;border:1px solid #dce4ed;border-radius:10px;background:#fff}.manual-input h3,.blockers h4,.next-action h4{margin:0 0 10px}.manual-input dl{display:grid;gap:8px;margin:0}.manual-input dl>div{display:grid;grid-template-columns:120px 1fr;gap:12px}.manual-input dt{color:#64748b}.manual-input dd{margin:0;color:#1e293b}.blockers{border-color:#f2cf91;background:#fffaf0}.blockers ul,.review-admission ul,.release-admission ul{margin:8px 0 0;padding-left:20px}.blockers li,.review-admission li,.release-admission li{margin:5px 0}.next-action{border-color:#b7d9c4;background:#f5fbf7}.next-action p{margin:0 0 8px}.review-admission{border-color:#9fc5e8;background:#f5faff}.release-admission{border-color:#9fd7b4;background:#f4fbf6}.review-admission>header>strong,.release-admission>header>strong{padding:7px 10px;border-radius:999px;background:#e0effc;color:#1d4f7a}.release-admission>header>strong{background:#def4e5;color:#1d6840}.review-action{display:grid;gap:10px}.review-action .el-button{justify-self:start}.engineering-document-detail-readback>header{padding-bottom:12px;border-bottom:1px solid #e2e8f0}@media(max-width:760px){.section-heading,.engineering-document-detail-readback>header,.review-admission>header,.release-admission>header{display:grid}.manual-input dl>div{grid-template-columns:1fr;gap:3px}}
</style>
