<template>
  <section
    class="release-preflight"
    data-acceptance-id="pde-bom-version-release-preflight"
    data-fact-source="server"
    :data-write-action-count="canSubmitReview || canSubmitRelease ? '1' : '0'"
    :data-release-allowed="String(Boolean(preflight.releaseAllowed))"
  >
    <header class="preflight-header">
      <div>
        <p class="eyebrow">正式服务 · Workflow控制 · 人工确认</p>
        <h3>{{ detail.bomVersionNo }} 正式评审/发布控制链核验</h3>
        <p>核验当前持久事实与正式配置；评审与发布均只向服务端确认的独立合法人员开放一次，已完成动作不得重复。</p>
      </div>
      <div class="decision" :class="preflight.releaseAllowed || formalReleaseCompleted ? 'ready' : 'blocked'">
        <small>最终裁决</small>
        <strong>{{ preflight.decisionCode || '未取得' }}</strong>
        <span>{{ preflight.decisionLabel || '-' }}</span>
      </div>
    </header>

    <el-alert
      v-if="formalReleaseCompleted"
      :title="`${detail.bomVersionNo} 已完成正式发布`"
      description="服务端已回读发布人、发布时间、Workflow、状态迁移、审计与幂等请求事实；相同版本禁止重复发布。"
      type="success"
      :closable="false"
      show-icon
      data-acceptance-id="pde-bom-version-release-completed"
    />
    <el-alert
      v-else-if="!preflight.releaseAllowed"
      title="当前不允许正式发布"
      :description="preflight.firstBlockerLabel || '发布前置事实未完整取得。'"
      type="error"
      :closable="false"
      show-icon
      data-acceptance-id="pde-bom-version-release-first-blocker"
    />
    <el-alert
      v-else
      title="所有门禁已满足，等待用户明确发布授权"
      type="success"
      :closable="false"
      show-icon
    />

    <div class="fact-grid" data-acceptance-id="pde-bom-version-release-core-facts">
      <article><small>BOM版本</small><strong>{{ detail.bomVersionNo }}</strong><span>ID {{ detail.bomVersionId }} · Rev {{ detail.revision }}</span></article>
      <article><small>当前状态</small><strong>{{ detail.statusLabel }}</strong><span>合法下一状态：{{ state.nextLegalStateCode || '-' }}</span></article>
      <article><small>BOM内容</small><strong>{{ detail.materialCount }} 项</strong><span>{{ detail.sourceRequirementCount }} 条正式来源</span></article>
      <article><small>工程基线</small><strong>{{ baseline.baselineNo || '-' }}</strong><span>{{ baseline.statusLabel || '-' }} · 当前={{ yesNo(baseline.isCurrent) }}</span></article>
      <article><small>工程核算</small><strong>{{ calculation.calculationNo || '-' }}</strong><span>Rev {{ calculation.revision ?? '-' }} · {{ calculation.statusLabel || '-' }}</span></article>
      <article><small>发布权限</small><strong>{{ permission.code || '-' }}</strong><span>合法业务执行身份 {{ permission.eligibleActorCount ?? 0 }} 个</span></article>
    </div>

    <section class="readiness" data-acceptance-id="pde-bom-version-control-chain-readiness">
      <div class="section-heading">
        <h4>正式控制链整改状态</h4>
        <strong>{{ readiness.controlChainStatusLabel || '未接入' }}</strong>
      </div>
      <div class="readiness-grid">
        <article><small>控制链状态</small><PceBusinessStatus :status-label="readiness.controlChainStatusLabel || '未接入'" source="server" /></article>
        <article><small>Workflow Runtime</small><PceBusinessStatus :status-label="runtime.statusCode || 'BLOCKED'" source="server" /></article>
        <article><small>BusinessStateTransition</small><PceBusinessStatus :status-label="businessTransition.statusCode || 'BLOCKED'" source="server" /></article>
        <article><small>Request Idempotency</small><PceBusinessStatus :status-label="requestIdempotency.statusCode || 'BLOCKED'" source="server" /></article>
        <article><small>职责分离</small><PceBusinessStatus :status-label="segregation.statusCode || 'BLOCKED'" source="server" /></article>
        <article><small>当前{{ detail.bomVersionNo }}</small><strong>{{ state.currentStateCode || '-' }} / {{ approval.projectionState || '-' }}</strong></article>
      </div>
      <p class="current-action"><strong>当前业务动作：</strong>{{ readiness.currentBusinessAction || '等待正式评审授权' }}</p>
      <p v-if="runtime.blocker?.message" class="configuration-blocker">
        <strong>现有配置阻点：</strong>{{ runtime.blocker.message }}
      </p>
    </section>

    <section
      v-if="formalReviewDecision"
      class="formal-review-readback"
      data-acceptance-id="pde-bom-version-formal-review-readback"
    >
      <div class="section-heading">
        <div>
          <h4>正式评审结果</h4>
          <p>以下内容直接来自服务端 Workflow、决定与审计事实。</p>
        </div>
        <PceBusinessStatus status-label="已完成" source="server" />
      </div>
      <div class="fact-grid review-fact-grid">
        <article><small>评审人</small><strong>{{ formalReviewActor }}</strong><span>User {{ formalReviewDecision.actor_id }}</span></article>
        <article><small>评审决定</small><strong>{{ formalReviewDecision.decision === 'approved' ? '通过' : formalReviewDecision.decision }}</strong><span>{{ formalReviewDecision.action_id }}</span></article>
        <article><small>评审意见</small><strong>{{ formalReviewDecision.comment || '-' }}</strong><span>Decision {{ formalReviewDecision.id }}</span></article>
        <article><small>完成时间</small><strong>{{ formatTimestamp(formalReviewDecision.completed_at || formalReviewDecision.created_at) }}</strong><span>Workflow {{ formalReviewWorkflow?.instance_no || '-' }}</span></article>
      </div>
    </section>

    <section
      v-if="formalReleaseCompleted"
      class="formal-review-readback"
      data-acceptance-id="pde-bom-version-formal-release-readback"
    >
      <div class="section-heading">
        <div>
          <h4>正式发布结果</h4>
          <p>以下内容直接来自服务端状态迁移、审计、Workflow引用与幂等账本。</p>
        </div>
        <PceBusinessStatus status-label="已发布" source="server" />
      </div>
      <div class="fact-grid review-fact-grid">
        <article><small>发布人</small><strong>{{ formalReleaseActor }}</strong><span>User {{ formalReleaseReadback.actorId }}</span></article>
        <article><small>正式发布决定</small><strong>已发布</strong><span>{{ formalReleaseReadback.actionCode }}</span></article>
        <article><small>发布时间</small><strong>{{ formatTimestamp(formalReleaseReadback.occurredAt) }}</strong><span>BST {{ formalReleaseReadback.businessStateTransitionId }}</span></article>
        <article><small>对应Workflow</small><strong>{{ formalReleaseReadback.workflowInstanceNo || formalReviewWorkflow?.instance_no || '-' }}</strong><span>{{ formalReleaseReadback.auditReference || '-' }}</span></article>
        <article><small>幂等请求</small><strong>{{ formalReleaseReadback.requestIdentity || '-' }}</strong><span>同一请求安全回读，不重复写入</span></article>
        <article><small>当前合法下一动作</small><strong>{{ readiness.currentBusinessAction || '正式发布已完成' }}</strong><span>下一合法状态：{{ state.nextLegalStateCode || '无' }}</span></article>
      </div>
    </section>

    <section class="state-machine" data-acceptance-id="pde-bom-version-state-machine">
      <h4>现行生命周期</h4>
      <div class="state-flow">
        <span v-for="(transition, index) in state.legalTransitions || []" :key="transition">
          {{ transition }}<i v-if="index < (state.legalTransitions || []).length - 1">·</i>
        </span>
      </div>
      <p>状态机规则：draft 不能直接进入 released；当前持久状态为 {{ state.currentStateLabel || state.currentStateCode || '-' }}，合法下一状态为 {{ state.nextLegalStateCode || '无' }}。effective 不是独立生命周期状态。</p>
    </section>

    <section data-acceptance-id="pde-bom-version-release-gates">
      <div class="section-heading">
        <h4>发布 Gate</h4>
        <span>{{ preflight.gatePassCount ?? 0 }} 已满足 / {{ preflight.gateFailCount ?? 0 }} 未满足 / {{ preflight.gateNotRequiredCount ?? 0 }} 不要求</span>
      </div>
      <div class="gate-table-scroll">
        <table class="gate-table">
          <thead><tr><th>Gate</th><th>状态</th><th>服务端证据</th></tr></thead>
          <tbody>
            <tr v-for="gate in preflight.gates || []" :key="gate.code" :data-gate-code="gate.code">
              <td><strong>{{ gate.label }}</strong><small>{{ gate.code }}</small></td>
              <td><PceBusinessStatus :status-label="gate.statusLabel" source="server" /></td>
              <td>{{ gate.evidence }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="review-action" data-acceptance-id="pde-bom-version-formal-review-action">
      <div class="section-heading">
        <div>
          <h4>正式评审决定</h4>
          <p>当前登录：{{ currentActorLabel }}。动作固定为 <code>pde.bom_version.review</code>，目标状态固定为“已评审”。</p>
        </div>
        <PceBusinessStatus :status-label="canSubmitReview ? '允许执行' : (formalReviewCompleted ? '已完成' : '不可执行')" source="server" />
      </div>
      <template v-if="canSubmitReview">
        <el-alert
          title="本动作将形成唯一 WorkflowInstance、ApprovalTask、ApprovalDecision、状态迁移、审计与幂等账本；不会发布BOM版本。"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-form label-position="top" class="review-form">
          <el-form-item label="正式评审意见（必填）">
            <el-input
              v-model="reviewReason"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="请由评审人填写基于当前BOM版本、物料及来源事实的正式评审意见"
              data-acceptance-id="pde-bom-version-review-reason"
            />
          </el-form-item>
          <el-button
            type="primary"
            :loading="submitting"
            :disabled="!reviewReason.trim()"
            data-acceptance-id="pde-bom-version-submit-review"
            @click="submitFormalReview"
          >提交正式评审通过决定</el-button>
        </el-form>
      </template>
      <el-alert
        v-else
        :title="reviewBlockedMessage"
        type="info"
        :closable="false"
        show-icon
      />
    </section>

    <section class="review-action" data-acceptance-id="pde-bom-version-formal-release-action">
      <div class="section-heading">
        <div>
          <h4>正式发布决定</h4>
          <p>当前登录：{{ currentActorLabel }}。动作固定为 <code>pde.bom_version.release</code>，目标状态固定为“已发布”。</p>
        </div>
        <PceBusinessStatus :status-label="canSubmitRelease ? '允许执行' : (formalReleaseCompleted ? '已完成' : '不可执行')" source="server" />
      </div>
      <template v-if="canSubmitRelease">
        <el-alert
          :title="`本动作只写${detail.bomVersionNo}的正式发布状态迁移、审计和幂等账本，并引用已完成Workflow；不会修改ProductBOM或创建制造、MRP、采购、生产、ECN及工艺路线对象。`"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-form label-position="top" class="review-form">
          <el-form-item label="正式发布说明（必填）">
            <el-input
              v-model="releaseReason"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="请由发布人填写基于已完成正式评审与当前发布Gate的正式发布说明"
              data-acceptance-id="pde-bom-version-release-reason"
            />
          </el-form-item>
          <el-button
            type="primary"
            :loading="releasing"
            :disabled="!releaseReason.trim()"
            data-acceptance-id="pde-bom-version-submit-release"
            @click="submitFormalRelease"
          >提交正式发布决定</el-button>
        </el-form>
      </template>
      <el-alert
        v-else
        :title="releaseBlockedMessage"
        type="info"
        :closable="false"
        show-icon
      />
    </section>

    <section class="control-grid" data-acceptance-id="pde-bom-version-release-controls">
      <article>
        <h4>合法执行身份</h4>
        <p v-if="!(permission.eligibleActors || []).length">无非 superuser 合法执行身份。</p>
        <p v-for="actor in permission.eligibleActors || []" :key="actor.userId">
          <strong>{{ actor.username }}</strong> · {{ actor.employeeNo }} · {{ actor.positionCode }}<br>
          <small>{{ (actor.roleCodes || []).join('、') }} / {{ (actor.scopeCodes || []).join('、') }}</small>
        </p>
      </article>
      <article>
        <h4>现行自动副作用</h4>
        <p>正式动作只写 Workflow、BOMVersion 状态投影、统一状态迁移、审计与请求账本。</p>
        <p>不会自动修改 ProductBOM、工程资料、制造输出、MRP、采购/生产需求、ECN 或工艺路线。</p>
      </article>
      <article v-if="(preflight.configurationGaps || []).length" class="software-gap">
        <h4>最小正式配置缺口</h4>
        <ul><li v-for="gap in preflight.configurationGaps || []" :key="gap.code || gap.message">{{ gap.message || gap.code }}</li></ul>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accessControlApi } from '@/api/accessControl.js'
import { pdeApi } from '@/api/pde.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'

const props = defineProps({ detail: { type: Object, required: true } })
const emit = defineEmits(['review-readback'])
const preflight = computed(() => props.detail?.releasePreflight || {})
const state = computed(() => preflight.value.stateMachine || {})
const baseline = computed(() => preflight.value.baseline || {})
const calculation = computed(() => preflight.value.calculation || {})
const permission = computed(() => preflight.value.permission || {})
const approval = computed(() => preflight.value.approval || {})
const readiness = computed(() => preflight.value.controlChainReadiness || {})
const runtime = computed(() => readiness.value.workflowRuntime || {})
const businessTransition = computed(() => readiness.value.businessStateTransition || {})
const requestIdempotency = computed(() => readiness.value.requestIdempotency || {})
const segregation = computed(() => readiness.value.segregationOfDuties || {})
const yesNo = value => value ? '是' : '否'
const formalReviewDecision = computed(() => (approval.value.approvalDecisions || [])[0] || null)
const formalReviewWorkflow = computed(() => (approval.value.workflowInstances || [])[0] || null)
const formalReleaseReadback = computed(() => preflight.value.releaseControl?.authoritativeReleaseReadback || {})
const formalReviewCompleted = computed(() => Boolean(
  ['reviewed', 'released', 'obsolete'].includes(state.value.currentStateCode)
  && approval.value.projectionState === 'workflow_approved'
  && approval.value.projectionConsistent
  && formalReviewDecision.value?.decision === 'approved'
))
const formalReleaseCompleted = computed(() => Boolean(
  state.value.currentStateCode === 'released'
  && formalReleaseReadback.value.released
))
const formalReviewActor = computed(() => {
  const decision = formalReviewDecision.value || {}
  return `${decision.actor__real_name || decision.actor__username || '未取得'}（${decision.actor__username || '-'}）`
})
const formalReleaseActor = computed(() => {
  const release = formalReleaseReadback.value || {}
  return `${release.actorRealName || release.actorUsername || '未取得'}（${release.actorUsername || '-'}）`
})
const formatTimestamp = value => value
  ? `${new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium', timeStyle: 'medium', hour12: false, timeZone: 'Asia/Shanghai',
  }).format(new Date(value))}（Asia/Shanghai）`
  : '-'
const currentProfile = ref(null)
const identityChecked = ref(false)
const reviewReason = ref('')
const releaseReason = ref('')
const submitting = ref(false)
const releasing = ref(false)
const requestIdentity = ref('')
const releaseRequestIdentity = ref('')

function nextRequestIdentity() {
  requestIdentity.value = `bom-version-review-${props.detail.bomVersionId}-${crypto.randomUUID()}`
}

function nextReleaseRequestIdentity() {
  releaseRequestIdentity.value = `bom-version-release-${props.detail.bomVersionId}-${crypto.randomUUID()}`
}

const currentIdentity = computed(() => currentProfile.value?.identity || {})
const currentActorLabel = computed(() => {
  if (!identityChecked.value) return '正在核对服务端登录身份'
  const identity = currentIdentity.value
  if (!identity.username) return '未登录或身份读取失败'
  return `${identity.realName || identity.username}（${identity.username} / User ${identity.userId}）`
})
const configuredReviewer = computed(() => (
  segregation.value.reviewActors || []
).find(actor => Number(actor.userId) === Number(currentIdentity.value.userId)))
const configuredReleaser = computed(() => (
  segregation.value.releaseActors || []
).find(actor => Number(actor.userId) === Number(currentIdentity.value.userId)))
const approvalEmpty = computed(() => (
  (approval.value.workflowInstances || []).length === 0
  && (approval.value.approvalTasks || []).length === 0
  && (approval.value.approvalDecisions || []).length === 0
))
const canSubmitReview = computed(() => Boolean(
  identityChecked.value
  && configuredReviewer.value
  && readiness.value.formalExecutionReady
  && state.value.currentStateCode === 'draft'
  && approval.value.projectionState === 'not_submitted'
  && approval.value.projectionConsistent
  && approvalEmpty.value
))
const canSubmitRelease = computed(() => Boolean(
  identityChecked.value
  && configuredReleaser.value
  && preflight.value.releaseAllowed
  && preflight.value.explicitReleaseAuthorizationAcceptable
  && formalReviewCompleted.value
  && !formalReleaseCompleted.value
  && state.value.currentStateCode === 'reviewed'
))
const reviewBlockedMessage = computed(() => {
  if (!identityChecked.value) return '正在读取当前登录身份。'
  if (!currentIdentity.value.username) return '当前未登录；请由正式评审人通过正常账户机制登录。'
  if (formalReviewCompleted.value) return '正式评审已完成；页面已承接唯一Workflow实例、任务、决定、状态迁移与审计事实，禁止重复提交。'
  if (!configuredReviewer.value) return '当前登录账号不是服务端解析出的正式BOM版本评审执行人，不显示评审提交动作。'
  if (!approvalEmpty.value) return '服务端已存在Workflow实例、任务或决定；请先刷新并承接现有事实，禁止重复创建。'
  if (state.value.currentStateCode !== 'draft' || approval.value.projectionState !== 'not_submitted') return '当前BOM版本已不处于可发起正式评审的草稿状态。'
  return '服务端正式评审准入未就绪。'
})
const releaseBlockedMessage = computed(() => {
  if (!identityChecked.value) return '正在读取当前登录身份。'
  if (!currentIdentity.value.username) return '当前未登录；请由正式发布人通过正常账户机制登录。'
  if (formalReleaseCompleted.value) return '正式发布已完成；页面已回读唯一状态迁移、审计与幂等事实，禁止重复发布。'
  if (!formalReviewCompleted.value) return '正式评审尚未形成唯一、已批准且投影一致的Workflow事实。'
  if (!configuredReleaser.value) return '当前登录账号不是服务端解析出的正式BOM版本发布执行人，不显示发布提交动作。'
  if (!preflight.value.releaseAllowed) return preflight.value.firstBlockerLabel || '服务端正式发布Gate未就绪。'
  if (state.value.currentStateCode !== 'reviewed') return '当前BOM版本已不处于可执行正式发布的已评审状态。'
  return '服务端正式发布准入未就绪。'
})

async function readCurrentIdentity() {
  identityChecked.value = false
  try {
    const response = await accessControlApi.profile()
    currentProfile.value = response.success ? response.data : null
  } finally {
    identityChecked.value = true
  }
}

async function submitFormalReview() {
  const reason = reviewReason.value.trim()
  if (!canSubmitReview.value || !reason || submitting.value) return
  try {
    await ElMessageBox.confirm(
      `确认由${currentActorLabel.value}对${props.detail.bomVersionNo}提交正式“评审通过”决定？本动作不会发布BOM版本。`,
      '确认正式评审决定',
      { type: 'warning', confirmButtonText: '确认评审通过', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    const response = await pdeApi.transitionEngineering(
      'bom-versions', props.detail.bomVersionId, 'reviewed', reason,
      requestIdentity.value, 'pde.bom_version.review',
    )
    if (!response.success) throw new Error(response.error?.message || '正式评审请求未完成。')
    ElMessage.success('正式评审决定已保存；正在回读Workflow、状态迁移与审计事实。')
    reviewReason.value = ''
    nextRequestIdentity()
    emit('review-readback', { outcome: 'committed', result: response.data })
  } catch (error) {
    emit('review-readback', { outcome: 'unknown-or-blocked' })
    ElMessage.error(error.message || String(error))
  } finally {
    submitting.value = false
  }
}

async function submitFormalRelease() {
  const reason = releaseReason.value.trim()
  if (!canSubmitRelease.value || !reason || releasing.value) return
  try {
    await ElMessageBox.confirm(
      `确认由${currentActorLabel.value}对${props.detail.bomVersionNo}提交正式“发布”决定？本动作将把BOMVersion从已评审转换为已发布。`,
      '确认正式发布决定',
      { type: 'warning', confirmButtonText: '确认正式发布', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  releasing.value = true
  try {
    const response = await pdeApi.transitionEngineering(
      'bom-versions', props.detail.bomVersionId, 'released', reason,
      releaseRequestIdentity.value, 'pde.bom_version.release',
    )
    if (!response.success) throw new Error(response.error?.message || '正式发布请求未完成。')
    ElMessage.success('正式发布决定已保存；正在回读发布人、Workflow、状态迁移、审计与幂等事实。')
    releaseReason.value = ''
    nextReleaseRequestIdentity()
    emit('review-readback', { outcome: 'release-committed', result: response.data })
  } catch (error) {
    emit('review-readback', { outcome: 'release-unknown-or-blocked' })
    ElMessage.error(error.message || String(error))
  } finally {
    releasing.value = false
  }
}

watch(() => props.detail.bomVersionId, () => {
  reviewReason.value = ''
  releaseReason.value = ''
  nextRequestIdentity()
  nextReleaseRequestIdentity()
})
onMounted(async () => {
  nextRequestIdentity()
  nextReleaseRequestIdentity()
  await readCurrentIdentity()
})
</script>

<style scoped>
.release-preflight { margin-top:18px; padding-top:16px; border-top:1px solid #dce4ed; color:#263b4b; }
.preflight-header,.section-heading { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:14px; }
.preflight-header h3,.release-preflight h4 { margin:0; color:#193a50; }
.preflight-header p { margin:6px 0 0; line-height:1.55; color:#60758a; }
.eyebrow { color:#9a3412!important; font-size:12px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.decision { min-width:330px; padding:12px 14px; border-radius:10px; border:1px solid #efb3b3; background:#fff3f3; }
.decision.ready { border-color:#9bd0b1; background:#effaf4; }
.decision small,.decision strong,.decision span { display:block; }
.decision small { color:#60758a; }
.decision strong { margin:4px 0; color:#a51d2d; font:600 13px ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; }
.decision.ready strong { color:#176b3a; }
.fact-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:14px 0; }
.fact-grid article,.control-grid article,.state-machine,.readiness { padding:12px 14px; border:1px solid #dce4ed; border-radius:9px; background:#f8fbfd; }
.fact-grid small,.fact-grid strong,.fact-grid span { display:block; }
.fact-grid small { color:#60758a; }
.fact-grid strong { margin:4px 0; color:#193a50; }
.fact-grid span { font-size:12px; color:#60758a; }
.state-flow { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-weight:600; }
.state-flow i { margin-left:8px; color:#93a4b3; font-style:normal; }
.state-machine p,.control-grid p { margin:6px 0 0; line-height:1.55; }
.readiness { margin:14px 0; background:#f7fafc; }
.readiness .section-heading { margin:0 0 10px; }
.readiness-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
.readiness-grid article { padding:10px; border:1px solid #dce4ed; border-radius:8px; background:#fff; }
.readiness-grid small,.readiness-grid strong { display:block; }
.readiness-grid small { margin-bottom:6px; color:#60758a; }
.current-action { margin:12px 0 0; color:#193a50; }
.configuration-blocker { margin:8px 0 0; color:#a51d2d; }
.section-heading { margin-top:18px; align-items:baseline; }
.section-heading span { color:#60758a; font-size:13px; }
.gate-table-scroll { width:100%; overflow-x:auto; }
.gate-table { width:100%; min-width:980px; border-collapse:collapse; }
.gate-table th,.gate-table td { padding:10px 11px; border:1px solid #dce4ed; text-align:left; vertical-align:top; }
.gate-table th { background:#f4f8fb; color:#3c5263; white-space:nowrap; }
.gate-table td { font-size:13px; }
.gate-table td:first-child { width:270px; }
.gate-table td:nth-child(2) { width:120px; }
.gate-table small { display:block; margin-top:3px; color:#718293; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
.review-action { margin-top:14px; padding:14px; border:1px solid #dce4ed; border-radius:9px; background:#f8fbfd; }
.review-action .section-heading { margin:0 0 12px; }
.review-action .section-heading p { margin:6px 0 0; color:#60758a; }
.review-form { margin-top:14px; }
.review-action code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
.control-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:14px; }
.control-grid .software-gap { grid-column:1 / -1; border-color:#efb3b3; background:#fff8f6; }
.control-grid ul { margin:8px 0 0; padding-left:20px; line-height:1.65; }
@media (max-width:900px) { .preflight-header { flex-direction:column; }.decision { min-width:0; width:100%; box-sizing:border-box; }.fact-grid,.control-grid,.readiness-grid { grid-template-columns:1fr; }.control-grid .software-gap { grid-column:auto; } }
</style>
