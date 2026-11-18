<template>
  <section
    class="routing-version-readback"
    data-acceptance-id="routing-version-readonly-traceability"
    data-projection-source="server-fk"
  >
    <header>
      <div>
        <h3>工艺路线版本只读追溯</h3>
        <p>{{ versionSummary }}</p>
      </div>
      <el-tag type="info" effect="plain">工艺路线ID {{ definitionId }}</el-tag>
    </header>

    <el-alert
      v-if="!versions.length"
      title="当前工艺路线没有通过正式外键读取到工艺路线版本。"
      type="warning"
      :closable="false"
      show-icon
    />

    <article
      v-for="version in versions"
      :key="version.id"
      class="version-card"
      :data-routing-version-id="version.id"
    >
      <div class="version-title">
        <strong>工艺路线版本 {{ version.routingVersionNo }}</strong>
        <el-tag effect="plain">修订号 {{ revisionLabel(version.revision) }}</el-tag>
        <el-tag effect="plain">版本ID {{ version.id }}</el-tag>
        <el-tag :type="version.isReleased ? 'success' : 'warning'">{{ version.releaseStatusLabel }}</el-tag>
        <el-tag :type="version.isCurrentlyEffective === true ? 'success' : 'info'">{{ version.effectiveStatusLabel }}</el-tag>
        <el-button
          v-if="maintenanceOwner && version.successorAction?.visible"
          type="primary"
          plain
          :disabled="!version.successorAction?.executable"
          :title="version.successorAction?.disabledReason || ''"
          data-acceptance-id="create-routing-successor-version"
          @click="$emit('create-successor', version)"
        >{{ version.successorAction.actionLabel }}</el-button>
      </div>

      <dl class="version-grid" data-acceptance-id="routing-version-status-boundary">
        <div><dt>工艺路线编码</dt><dd>{{ version.routingCode || definitionCode || '-' }}</dd></div>
        <div><dt>工艺路线版本号</dt><dd>{{ version.routingVersionNo || '-' }}</dd></div>
        <div><dt>修订号</dt><dd>{{ revisionLabel(version.revision) }}</dd></div>
        <div><dt>工艺路线版本ID</dt><dd>{{ version.id ?? '-' }}</dd></div>
        <div><dt>工艺路线主档状态</dt><dd>{{ version.definitionStatusLabel || definitionStatusLabel || '-' }}</dd></div>
        <div><dt>当前版本状态</dt><dd>{{ version.versionStatusLabel || version.statusLabel || '-' }}</dd></div>
        <div><dt>当前版本发布状态</dt><dd>{{ version.releaseStatusLabel || '-' }}</dd></div>
        <div><dt>关联BOM版本</dt><dd>{{ associatedBomVersionLabel(version) }}</dd></div>
        <div><dt>当前有效</dt><dd>{{ effectiveText(version.isCurrentlyEffective) }}</dd></div>
        <div><dt>生效日期</dt><dd>{{ version.effectiveDate || '-' }}</dd></div>
        <div><dt>失效日期</dt><dd>{{ version.expireDate || '-' }}</dd></div>
        <div><dt>发布时间</dt><dd>{{ version.releaseTime || version.releaseTimeLabel || '-' }}</dd></div>
        <div><dt>工序数量</dt><dd>{{ version.stepCount }}</dd></div>
        <div><dt>版本身份</dt><dd>{{ version.sourceIdentity || '-' }}</dd></div>
        <div><dt>最后更新</dt><dd>{{ version.updatedAt || '-' }}</dd></div>
      </dl>

      <el-alert
        v-if="masterReleasedButVersionUnreleased(version)"
        title="工艺路线主档“已发布”与当前版本“未发布”为不同层级：主档保留既有发布事实，不代表当前展示版本已经发布。"
        type="info"
        :closable="false"
        show-icon
      />

      <p class="relation-evidence">
        <strong>正式关系：</strong>{{ version.relationLabel }}；来源模型：{{ version.sourceModel }}。
      </p>
      <p class="relation-evidence">
        <strong>版本与工序语义：</strong>{{ version.stepRelationLabel }}；{{ version.stepRelationshipSemanticsLabel }}。
      </p>
      <el-alert
        v-if="!version.formalApplicabilityValidated"
        title="该版本尚未完成全部单步适用性正式验证；条件不明的步骤按待确认处理并阻断计划就绪。"
        type="warning"
        :closable="false"
        show-icon
      />

      <section
        v-if="version.reviewPreflight"
        class="formal-review-panel"
        data-acceptance-id="routing-version-formal-review"
      >
        <div class="formal-review-heading">
          <div>
            <h4>工艺路线版本正式评审</h4>
            <p>评审仅检查路线结构、顺序、适用性及正式业务关系；本动作不会发布版本，也不会创建生产计划。</p>
          </div>
          <el-tag :type="version.reviewPreflight.reviewReadback?.completed ? 'success' : (version.reviewPreflight.reviewAllowed ? 'success' : 'warning')">
            {{ version.reviewPreflight.decisionLabel }}
          </el-tag>
        </div>

        <el-alert
          v-if="version.reviewPreflight.reviewReadback?.completed"
          :title="`正式评审已完成：${reviewActorLabel(version.reviewPreflight.reviewReadback)}；${version.isReleased ? '版本已正式发布。' : '版本仍未发布。'}`"
          type="success"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="version.reviewPreflight.firstBlockerMessage"
          :title="version.reviewPreflight.firstBlockerMessage"
          type="warning"
          :closable="false"
          show-icon
        />

        <dl class="formal-review-grid">
          <div><dt>目标状态</dt><dd>{{ version.reviewPreflight.targetStatusLabel || '已评审' }}</dd></div>
          <div><dt>正式动作</dt><dd>{{ version.reviewPreflight.actionCode }}</dd></div>
          <div><dt>Workflow配置来源</dt><dd>{{ version.reviewPreflight.workflowRuntime?.configurationSourceLabel || '尚未生成' }}</dd></div>
          <div><dt>当前评审人</dt><dd>{{ currentReviewActorLabel(version.reviewPreflight.currentActor) }}</dd></div>
          <div><dt>完整性Gate</dt><dd>{{ version.reviewPreflight.gatePassCount }} 通过 / {{ version.reviewPreflight.gateFailCount }} 阻断</dd></div>
          <div v-if="version.reviewPreflight.reviewReadback?.workflowInstanceNo"><dt>Workflow</dt><dd>{{ version.reviewPreflight.reviewReadback.workflowInstanceNo }}</dd></div>
          <div v-if="version.reviewPreflight.reviewReadback?.reviewedAt"><dt>评审时间</dt><dd>{{ version.reviewPreflight.reviewReadback.reviewedAt }}</dd></div>
        </dl>

        <div class="formal-review-gates">
          <article v-for="gate in version.reviewPreflight.gates || []" :key="gate.code">
            <el-tag size="small" :type="gate.statusCode === 'PASS' ? 'success' : 'danger'">{{ gate.statusLabel }}</el-tag>
            <div><strong>{{ gate.label }}</strong><p>{{ gate.evidence }}</p></div>
          </article>
        </div>

        <div v-if="maintenanceOwner && version.reviewPreflight.reviewAllowed" class="formal-review-action">
          <label>
            <span>正式评审意见（必填）</span>
            <el-input
              v-model="reviewOpinions[version.id]"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="请由实际授权评审人填写正式评审意见"
              data-acceptance-id="routing-version-review-opinion"
            />
          </label>
          <el-button
            type="primary"
            :disabled="!String(reviewOpinions[version.id] || '').trim()"
            data-acceptance-id="submit-routing-version-review"
            @click="submitFormalReview(version)"
          >提交正式评审通过决定</el-button>
        </div>
      </section>

      <section
        v-if="version.releasePreflight"
        class="formal-release-panel"
        data-acceptance-id="routing-version-formal-release"
      >
        <div class="formal-review-heading">
          <div>
            <h4>工艺路线版本正式发布</h4>
            <p>正式评审与正式发布是两个不同业务动作；本入口只调用 RoutingVersion 专用发布服务，不会创建生产计划、MRP或制造工单。</p>
          </div>
          <el-tag :type="version.releasePreflight.releaseReadback?.completed ? 'success' : (version.releasePreflight.releaseAllowed ? 'success' : 'warning')">
            {{ version.releasePreflight.decisionLabel }}
          </el-tag>
        </div>

        <el-alert
          v-if="version.releasePreflight.releaseReadback?.completed"
          :title="`正式发布已完成：${releaseActorLabel(version.releasePreflight.releaseReadback)}。`"
          type="success"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="version.releasePreflight.firstBlockerMessage"
          :title="version.releasePreflight.firstBlockerMessage"
          type="warning"
          :closable="false"
          show-icon
        />

        <dl class="formal-review-grid">
          <div><dt>正式评审状态</dt><dd>{{ version.releasePreflight.reviewReadback?.completed ? '已通过' : '未通过' }}</dd></div>
          <div><dt>当前版本状态</dt><dd>{{ version.versionStatusLabel || version.statusLabel || '-' }}</dd></div>
          <div><dt>当前版本发布状态</dt><dd>{{ version.releaseStatusLabel || '-' }}</dd></div>
          <div><dt>正式发布准入</dt><dd>{{ version.releasePreflight.releaseAllowed ? '通过' : '阻断' }}</dd></div>
          <div><dt>正式动作</dt><dd>{{ version.releasePreflight.actionCode }}</dd></div>
          <div><dt>专用权限</dt><dd>{{ version.releasePreflight.permissionCode }}</dd></div>
          <div><dt>发布职责</dt><dd>{{ version.releasePreflight.requiredResponsibilityCode }}</dd></div>
          <div><dt>当前操作人</dt><dd>{{ currentReleaseActorLabel(version.releasePreflight.currentActor) }}</dd></div>
          <div><dt>发布Gate</dt><dd>{{ version.releasePreflight.gatePassCount || 0 }} 通过 / {{ version.releasePreflight.gateFailCount || 0 }} 阻断</dd></div>
        </dl>

        <div class="formal-review-gates">
          <article v-for="gate in version.releasePreflight.gates || []" :key="gate.code">
            <el-tag size="small" :type="gate.statusCode === 'PASS' ? 'success' : 'danger'">{{ gate.statusLabel }}</el-tag>
            <div><strong>{{ gate.label }}</strong><p>{{ gate.evidence }}</p></div>
          </article>
        </div>

        <div v-if="maintenanceOwner" class="formal-review-action">
          <label>
            <span>正式发布说明（必填）</span>
            <el-input
              v-model="releaseReasons[version.id]"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              :disabled="!version.releasePreflight.releaseAllowed"
              placeholder="仅由正式授权发布人填写"
              data-acceptance-id="routing-version-release-reason"
            />
          </label>
          <el-button
            type="danger"
            :disabled="!version.releasePreflight.releaseAllowed || !String(releaseReasons[version.id] || '').trim()"
            :title="version.releasePreflight.releaseAllowed ? '' : (version.releasePreflight.firstBlockerMessage || '当前未通过正式发布准入')"
            data-acceptance-id="release-routing-version"
            @click="submitFormalRelease(version)"
          >正式发布</el-button>
        </div>
      </section>

      <section
        v-if="maintenanceOwner && version.manualDecisionAction?.visible && version.manualApplicabilityReadback?.contexts?.length"
        class="manual-decision-panel"
        data-acceptance-id="routing-manual-applicability-decisions"
      >
        <div class="manual-decision-heading">
          <div>
            <h4>{{ contextRowTitle(version, version.manualApplicabilityReadback.contexts[0]?.context) }} 条件工序人工确认</h4>
            <p>判断来源固定为“授权业务人员人工确认”；无需上传图纸，不新增审批流程。</p>
          </div>
          <el-tag :type="version.manualDecisionAction.executable ? 'success' : 'warning'">
            {{ version.manualDecisionAction.executable ? '允许维护' : '当前不可维护' }}
          </el-tag>
        </div>
        <el-alert
          v-if="!version.manualDecisionAction.executable"
          :title="version.manualDecisionAction.disabledReason"
          type="warning"
          :closable="false"
          show-icon
        />
        <article
          v-for="contextRow in version.manualApplicabilityReadback.contexts"
          :key="contextRow.context.contextKey"
          class="manual-context-card"
        >
          <dl class="manual-context-grid">
            <div><dt>订单 / 订单行</dt><dd>{{ contextRow.context.salesOrderNo }} / {{ contextRow.context.salesOrderLineNo }}</dd></div>
            <div><dt>订单工程实例</dt><dd>{{ contextRow.context.orderEngineeringInstanceNo }}</dd></div>
            <div><dt>确认工程基线</dt><dd>{{ contextRow.context.orderEngineeringBaselineNo }}</dd></div>
            <div><dt>工程核算</dt><dd>{{ contextRow.context.engineeringCalculationNo }} / Rev {{ contextRow.context.engineeringCalculationRevision }}</dd></div>
            <div><dt>BOM版本</dt><dd>{{ contextRow.context.bomVersionNo }} / Rev {{ contextRow.context.bomVersionRevision }}</dd></div>
            <div><dt>路线草稿</dt><dd>{{ contextRow.context.routingVersionNo }} / Rev {{ contextRow.context.routingVersionRevision }}</dd></div>
          </dl>
          <div class="manual-decision-list">
            <article
              v-for="decisionRow in contextRow.decisions"
              :key="decisionRow.conditionCode"
              class="manual-decision-card"
              :data-condition-code="decisionRow.conditionCode"
            >
              <div>
                <strong>{{ decisionRow.sequence }}. {{ decisionRow.operationName }}</strong>
                <p>{{ decisionRow.question }}</p>
                <small>{{ decisionRow.boundaryNote }}</small>
              </div>
              <div class="manual-current">
                <span>当前判断：{{ manualCurrentLabel(decisionRow.current) }}</span>
                <span v-if="decisionRow.current?.confirmedByUsername">
                  确认人：{{ decisionRow.current.confirmedByUsername }}
                </span>
                <span v-if="decisionRow.current?.confirmedAt">
                  确认时间：{{ decisionRow.current.confirmedAt }}
                </span>
              </div>
              <el-button
                type="primary"
                plain
                :disabled="!version.manualDecisionAction.executable"
                data-acceptance-id="confirm-routing-manual-applicability"
                @click="openManualDecision(version, contextRow, decisionRow)"
              >人工确认</el-button>
            </article>
          </div>
        </article>
      </section>

      <h4>版本范围工序（{{ version.stepCount }}）</h4>
      <el-table
        :data="version.steps || []"
        height="360"
        border
        size="small"
        data-acceptance-id="routing-version-steps"
      >
        <el-table-column prop="sequence" label="顺序" width="70" fixed="left" />
        <el-table-column prop="id" label="工序步骤ID" width="105" />
        <el-table-column prop="operationCode" label="工序编码" width="155" />
        <el-table-column prop="operationName" label="工序名称" min-width="150" />
        <el-table-column prop="applicabilityModeLabel" label="工序适用方式" min-width="130" />
        <el-table-column prop="applicabilityConditionLabel" label="适用条件" min-width="210" show-overflow-tooltip />
        <el-table-column prop="applicabilityFormalSourceLabel" label="正式条件来源" min-width="245" show-overflow-tooltip />
        <el-table-column prop="applicabilityResultLabel" label="条件判断结果" min-width="150" />
        <el-table-column prop="applicabilityPendingReason" label="当前待确认原因" min-width="230" show-overflow-tooltip>
          <template #default="{ row }">{{ row.applicabilityPendingReason || '无' }}</template>
        </el-table-column>
        <el-table-column prop="operationSourceLabel" label="工序来源" min-width="245" show-overflow-tooltip />
        <el-table-column label="车间" min-width="175" show-overflow-tooltip>
          <template #default="{ row }">{{ resourceText(row.workshopCode, row.workshopName) }}</template>
        </el-table-column>
        <el-table-column label="工作中心" min-width="175" show-overflow-tooltip>
          <template #default="{ row }">{{ resourceText(row.workCenterCode, row.workCenterName) }}</template>
        </el-table-column>
        <el-table-column prop="resourceSourceLabel" label="资源引用口径" min-width="210" show-overflow-tooltip />
        <el-table-column prop="statusLabel" label="步骤状态" width="100" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="maintenanceOwner && row.applicabilityEditable"
              size="small"
              plain
              data-acceptance-id="maintain-routing-step-applicability"
              @click="openApplicability(row)"
            >维护适用性</el-button>
            <span v-else>终态只读</span>
          </template>
        </el-table-column>
      </el-table>
    </article>

    <el-dialog v-model="applicabilityVisible" title="维护工序适用性" width="560px" append-to-body>
      <el-form label-width="120px">
        <el-form-item label="工序"><strong>{{ editingStep?.operationName || '-' }}</strong></el-form-item>
        <el-form-item label="工序适用方式" required>
          <el-select v-model="form.mode" placeholder="请选择正式适用方式" style="width:100%">
            <el-option v-for="item in modes" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.mode === 'CONDITIONAL'" label="适用条件" required>
          <el-select v-model="form.conditionCode" placeholder="请选择受治理的正式条件" style="width:100%">
            <el-option v-for="item in conditions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="维护原因" required>
          <el-input v-model="form.reason" type="textarea" :rows="3" maxlength="300" show-word-limit />
        </el-form-item>
      </el-form>
      <el-alert title="条件结论由合法正式工程事实或授权业务人员人工确认提供；本表单只维护步骤合同，不生成图纸或人工判断。" type="info" :closable="false" />
      <template #footer>
        <el-button @click="applicabilityVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!canSubmit" @click="submitApplicability">保存草稿步骤</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="manualVisible" title="确认本次订单工程条件" width="620px" append-to-body>
      <el-form label-width="110px">
        <el-form-item label="订单工程对象">
          <strong>{{ manualContextLabel }}</strong>
        </el-form-item>
        <el-form-item label="条件工序">
          <strong>{{ editingManualDecision?.operationName || '-' }}</strong>
        </el-form-item>
        <el-form-item label="人工判断问题">
          <span>{{ editingManualDecision?.question || '-' }}</span>
        </el-form-item>
        <el-form-item label="判断结果" required>
          <el-radio-group v-model="manualForm.decision" data-acceptance-id="manual-applicability-options">
            <el-radio-button
              v-for="option in editingVersion?.manualApplicabilityReadback?.decisionOptions || []"
              :key="option.value"
              :value="option.value"
            >{{ option.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="判定依据" required>
          <el-input v-model="manualForm.note" type="textarea" :rows="3" maxlength="300" show-word-limit />
          <div class="manual-decision-note-hint">
            请填写本次判定的依据，如设计要求、订单工程信息或人工核实结果；无需上传图纸。
          </div>
        </el-form-item>
      </el-form>
      <el-alert
        title="保存后形成精确绑定当前订单、订单行、工程实例、确认基线、工程核算、BOM版本和路线草稿的结构化事实。未选择不会自动解释为“否”。"
        type="info"
        :closable="false"
        show-icon
      />
      <template #footer>
        <el-button @click="manualVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!canSubmitManual"
          data-acceptance-id="submit-routing-manual-applicability"
          @click="submitManualDecision"
        >保存人工判断</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  maintenanceOwner:{type:Boolean,default:false},
  definitionId: { type: [Number, String], default: null },
  definitionCode: { type: String, default: '' },
  definitionStatusLabel: { type: String, default: '' },
  versions: { type: Array, default: () => [] },
  modes: { type: Array, default: () => [] },
  conditions: { type: Array, default: () => [] },
})
const emit = defineEmits(['create-successor', 'save-applicability', 'save-manual-decision', 'review-version', 'release-version'])
const applicabilityVisible = ref(false)
const editingStep = ref(null)
const form = reactive({ mode: '', conditionCode: '', reason: '' })
const manualVisible = ref(false)
const editingVersion = ref(null)
const editingManualContext = ref(null)
const editingManualDecision = ref(null)
const manualForm = reactive({ decision: '', note: '' })
const reviewOpinions = reactive({})
const releaseReasons = reactive({})
const canSubmit = computed(() => Boolean(
  form.mode
  && form.reason.trim()
  && (form.mode !== 'CONDITIONAL' || form.conditionCode),
))
const canSubmitManual = computed(() => Boolean(
  manualForm.decision && manualForm.note.trim() && editingVersion.value
  && editingManualContext.value && editingManualDecision.value,
))
const manualContextLabel = computed(() => {
  const context = editingManualContext.value?.context
  if (!context) return '-'
  return `${context.salesOrderNo} / 行${context.salesOrderLineNo} / ${context.orderEngineeringInstanceNo}`
})

const versionSummary = computed(() => {
  if (!props.versions.length) return '未读取到工艺路线版本；这不是前端推断的“版本数为0”。'
  if (props.versions.length === 1) return '当前工艺路线通过正式外键读取到1个工艺路线版本。'
  return `当前工艺路线通过正式外键读取到${props.versions.length}个工艺路线版本，以下逐一列出。`
})

function effectiveText(value) {
  if (value === true) return '是'
  if (value === false) return '否'
  return '需结合适用条件解析'
}

function revisionLabel(revision) {
  if (revision === null || revision === undefined || revision === '') return '-'
  return `${revision}（Rev${revision}）`
}

function associatedBomVersionLabel(version) {
  const labels = (version?.manualApplicabilityReadback?.contexts || [])
    .map(row => row?.context)
    .filter(context => context?.bomVersionNo)
    .map(context => `${context.bomVersionNo} / Rev${context.bomVersionRevision}`)
  const uniqueLabels = [...new Set(labels)]
  if (uniqueLabels.length === 1) return uniqueLabels[0]
  if (uniqueLabels.length > 1) return uniqueLabels.join('、')
  if (version?.bomVersionNo) {
    return version.bomVersionRevision
      ? `${version.bomVersionNo} / Rev${version.bomVersionRevision}`
      : version.bomVersionNo
  }
  return '未关联'
}

function masterReleasedButVersionUnreleased(version) {
  const masterStatus = version?.definitionStatusLabel || props.definitionStatusLabel
  return masterStatus === '已发布' && version?.isReleased === false
}

function resourceText(code, name) {
  if (!code && !name) return '未维护'
  return [code, name].filter(Boolean).join(' · ')
}

function openApplicability(step) {
  editingStep.value = step
  form.mode = step.applicability?.mode || ''
  form.conditionCode = step.applicability?.conditionCode || ''
  form.reason = ''
  applicabilityVisible.value = true
}

function submitApplicability() {
  if (!canSubmit.value || !editingStep.value) return
  emit('save-applicability', {
    step: editingStep.value,
    mode: form.mode,
    conditionCode: form.mode === 'CONDITIONAL' ? form.conditionCode : '',
    reason: form.reason.trim(),
  })
  applicabilityVisible.value = false
}

function manualCurrentLabel(current) {
  if (!current || current.status === 'MISSING') return '尚未人工确认'
  if (current.status === 'INVALID') return `身份或审计异常：${current.pendingReason || '无法读取'}`
  return current.decisionLabel || '待确认'
}

function contextRowTitle(version, context) {
  return [context?.bomVersionNo, version?.routingVersionNo].filter(Boolean).join(' ') || '当前路线版本'
}

function openManualDecision(version, contextRow, decisionRow) {
  editingVersion.value = version
  editingManualContext.value = contextRow
  editingManualDecision.value = decisionRow
  manualForm.decision = decisionRow.current?.decision || ''
  manualForm.note = decisionRow.current?.note || ''
  manualVisible.value = true
}

function submitManualDecision() {
  if (!canSubmitManual.value) return
  emit('save-manual-decision', {
    version: editingVersion.value,
    contextKey: editingManualContext.value.context.contextKey,
    conditionCode: editingManualDecision.value.conditionCode,
    decision: manualForm.decision,
    note: manualForm.note.trim(),
    expectedAuditId: editingManualDecision.value.current?.auditId || null,
  })
  manualVisible.value = false
}

function currentReviewActorLabel(actor) {
  if (!actor?.userId) return '当前账号未取得正式评审授权'
  return `${actor.realName || actor.username}（${actor.username} / ${actor.positionCode}）`
}

function reviewActorLabel(readback) {
  return `${readback.actorRealName || readback.actorUsername || '-'}（${readback.actorUsername || '-'}）`
}

function currentReleaseActorLabel(actor) {
  if (!actor?.userId) return '当前账号未取得专用发布授权'
  return `${actor.realName || actor.username}（${actor.username} / ${actor.positionCode}）`
}

function releaseActorLabel(readback) {
  return `${readback.actorRealName || readback.actorUsername || '-'}（${readback.actorUsername || '-'}）`
}

function submitFormalReview(version) {
  const reason = String(reviewOpinions[version.id] || '').trim()
  if (!version.reviewPreflight?.reviewAllowed || !reason) return
  emit('review-version', { version, reason })
}

function submitFormalRelease(version) {
  const reason = String(releaseReasons[version.id] || '').trim()
  if (!version.releasePreflight?.releaseAllowed || !reason) return
  emit('release-version', { version, reason })
}
</script>

<style scoped>
.routing-version-readback { display:grid; gap:14px; margin-top:16px; }
header,.version-title { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
h3,h4,p { margin:0; }
header p { margin-top:6px; color:#64748b; }
.version-card { display:grid; gap:14px; padding:16px; border:1px solid #cbd9e8; border-radius:12px; background:#f8fbff; }
.version-title { justify-content:flex-start; }
.version-title strong { margin-right:auto; color:#17375e; }
.version-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin:0; }
.version-grid div { padding:10px 12px; border-radius:8px; background:#fff; }
dt { color:#64748b; font-size:13px; }
dd { margin:4px 0 0; font-weight:700; overflow-wrap:anywhere; }
.relation-evidence { padding:10px 12px; border-left:4px solid #3b82f6; background:#eff6ff; color:#334155; }
.formal-review-panel { display:grid; gap:12px; padding:14px; border:1px solid #c7d8ee; border-radius:10px; background:#f6f9fd; }
.formal-release-panel { display:grid; gap:12px; padding:14px; border:1px solid #e4c7a7; border-radius:10px; background:#fffaf3; }
.formal-review-heading { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.formal-review-heading p { margin-top:5px; color:#475569; }
.formal-review-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:0; }
.formal-review-grid div { padding:9px 10px; border-radius:8px; background:#fff; }
.formal-review-gates { display:grid; gap:8px; }
.formal-review-gates article { display:flex; align-items:flex-start; gap:9px; padding:9px 10px; border-radius:8px; background:#fff; }
.formal-review-gates p { margin-top:3px; color:#64748b; font-size:13px; }
.formal-review-action { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:end; }
.formal-review-action label { display:grid; gap:6px; color:#334155; font-weight:700; }
.manual-decision-panel { display:grid; gap:12px; padding:14px; border:1px solid #b7d7c5; border-radius:10px; background:#f3fbf6; }
.manual-decision-heading { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.manual-decision-heading p,.manual-decision-card p { margin-top:5px; color:#475569; }
.manual-context-card { display:grid; gap:12px; }
.manual-context-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:0; }
.manual-context-grid div { padding:9px 10px; border-radius:8px; background:#fff; }
.manual-decision-list { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.manual-decision-card { display:grid; gap:10px; padding:12px; border:1px solid #d8e5dd; border-radius:8px; background:#fff; }
.manual-decision-card small { display:block; margin-top:5px; color:#64748b; }
.manual-current { display:grid; gap:3px; color:#334155; font-size:13px; }
.manual-decision-note-hint { margin-top:6px; color:#64748b; font-size:12px; line-height:1.6; }
@media (max-width:760px) { .version-grid { grid-template-columns:1fr; } }
@media (max-width:900px) { .manual-context-grid,.manual-decision-list,.formal-review-grid,.formal-review-action { grid-template-columns:1fr; } }
</style>
