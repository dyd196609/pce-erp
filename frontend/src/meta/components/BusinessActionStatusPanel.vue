<template>
  <section class="business-action-status-panel" data-acceptance-id="real-business-action-panel">
    <header>
      <p class="panel-eyebrow">V1.14.2.7.1 · 真实动作可观测</p>
      <h2>{{ model.actionPanelTitle || '真实业务动作与状态回写' }}</h2>
    </header>

    <div class="panel-grid">
      <article>
        <span>当前业务动作</span>
        <strong data-acceptance-id="current-action-name">{{ model.currentActionName }}</strong>
      </article>
      <article>
        <span>来源对象</span>
        <strong>{{ model.sourceObjectLabel }}</strong>
      </article>
      <article>
        <span>来源编号</span>
        <strong data-acceptance-id="current-action-source">{{ model.sourceObjectNoText }}</strong>
      </article>
      <article>
        <span>来源当前状态</span>
        <strong>{{ model.sourceStatusText }}</strong>
      </article>
      <article>
        <span>当前动作是否允许</span>
        <strong data-acceptance-id="current-action-allowed">{{ model.actionAllowedText }}</strong>
      </article>
      <article>
        <span>当前动作阻断原因</span>
        <strong data-acceptance-id="current-action-block-reasons">{{ model.actionBlockReasonText }}</strong>
      </article>
      <article>
        <span>当前动作是否已经完成</span>
        <strong>{{ model.actionCompletedText }}</strong>
      </article>
      <article>
        <span>已存在目标编号</span>
        <strong data-acceptance-id="current-action-existing-target">{{ model.existingTargetNoText }}</strong>
      </article>
    </div>

    <button
      type="button"
      class="execute-button"
      data-acceptance-id="current-action-button"
      :disabled="!canExecute"
      @click="$emit('execute')"
    >
      {{ executing ? '正在执行...' : model.actionButtonText }}
    </button>

    <section class="result-section" data-acceptance-id="business-action-result">
      <h3 data-acceptance-id="business-action-result-title">{{ model.resultPanelTitle || '本次动作结果' }}</h3>
      <div class="result-source" data-acceptance-id="business-action-result-source">
        <span>{{ fieldLabels.resultSource }}</span>
        <strong>{{ model.resultSourceText }}</strong>
      </div>

      <section
        id="target-evidence-summary-section"
        class="target-evidence-section"
        data-acceptance-id="target-evidence-status-section"
      >
        <h4>{{ sectionTitles.targetEvidenceSummary }}</h4>
        <div class="panel-grid">
          <article>
            <span>{{ fieldLabels.targetEvidenceStatus }}</span>
            <strong data-acceptance-id="action-target-evidence-status">{{ model.targetEvidenceStatusText }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.targetObjectNo }}</span>
            <strong data-acceptance-id="business-action-target-number">{{ model.targetObjectNoText }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.resultSource }}</span>
            <strong>{{ model.resultSourceText }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.executionStatus }}</span>
            <strong data-acceptance-id="action-execution-status">{{ model.executionStatusText }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.nextStepAllowed }}</span>
            <strong data-acceptance-id="business-action-next-step-release">{{ model.nextStepReleasedText }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.nextStepBlockReason }}</span>
            <strong data-acceptance-id="business-action-next-step-reason">{{ model.nextBusinessStepBlockReasonText }}</strong>
          </article>
        </div>
        <p class="evidence-reason" data-acceptance-id="action-target-evidence-reason">
          {{ model.targetEvidenceStatusReason || '当前无目标证据说明。' }}
        </p>
      </section>

      <section id="next-step-release-section" class="release-summary-card" data-acceptance-id="next-step-release-section">
        <h4>{{ sectionTitles.nextStepRelease }}</h4>
        <p>{{ model.nextBusinessStepBlockReasonText || '当前没有下一步阻断原因。' }}</p>
      </section>

      <section
        id="target-evidence-first-failure-section"
        class="target-evidence-first-failure"
        data-acceptance-id="target-evidence-first-failure-section"
      >
        <h4>{{ sectionTitles.firstFailure }}</h4>
        <div class="panel-grid">
          <article>
            <span>证据总数</span>
            <strong data-acceptance-id="target-evidence-trace-total-count">{{ model.targetEvidenceTraceItems?.length || 0 }}</strong>
          </article>
          <article>
            <span>通过数</span>
            <strong data-acceptance-id="target-evidence-trace-passed-count">{{ model.targetEvidenceTracePassedCount || 0 }}</strong>
          </article>
          <article>
            <span>异常数</span>
            <strong data-acceptance-id="target-evidence-trace-failed-count">{{ model.targetEvidenceTraceFailedCount || 0 }}</strong>
          </article>
          <article>
            <span>阻断数</span>
            <strong data-acceptance-id="target-evidence-trace-blocking-count">{{ model.targetEvidenceTraceBlockingCount || 0 }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.firstFailure }}</span>
            <strong data-acceptance-id="target-evidence-first-failure-label">{{ model.targetEvidenceFirstFailureLabel || emptyTexts.noFailure }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.responsibility }}</span>
            <strong data-acceptance-id="target-evidence-first-failure-responsibility">{{ model.targetEvidenceFirstFailureResponsibilityLabel || '暂无定位' }}</strong>
          </article>
          <article>
            <span>{{ fieldLabels.blocking }}</span>
            <strong>{{ model.targetEvidenceFirstFailureBlocking ? '是' : '否' }}</strong>
          </article>
        </div>
        <p class="evidence-reason" data-acceptance-id="target-evidence-first-failure-reason">
          {{ model.targetEvidenceFirstFailureReason || emptyTexts.noFailure }}
        </p>
      </section>

      <section
        id="target-evidence-trace-section"
        class="target-evidence-trace-section"
        data-acceptance-id="target-evidence-trace-section"
      >
        <h4>{{ sectionTitles.targetEvidenceTrace }}</h4>
        <p class="evidence-reason">
          本区域仅用于只读诊断，显示每项证据的来源、目标、期望关系、实际关系、检查结果和建议检查方向；不自动补写、不自动修复、不自动推进下一步。
        </p>
        <BusinessTableScrollContainer acceptance-id="target-evidence-trace-table-scroll" min-width="1900px">
          <table data-acceptance-id="target-evidence-trace-table" class="target-evidence-trace-table">
            <thead>
              <tr>
                <th>证据名称</th>
                <th>证据分类</th>
                <th>来源对象</th>
                <th>来源字段</th>
                <th>来源值</th>
                <th>目标对象</th>
                <th>目标字段</th>
                <th>目标值</th>
                <th>期望关系</th>
                <th>实际关系</th>
                <th>检查结果</th>
                <th>是否阻断</th>
                <th>建议检查方向</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!model.targetEvidenceTraceItems || !model.targetEvidenceTraceItems.length">
                <td colspan="13">{{ emptyTexts.noTraceItems }}</td>
              </tr>
              <tr
                v-for="item in model.targetEvidenceTraceItems"
                :key="item.deterministicTraceKey"
                :class="{ 'is-first-failure': item.firstFailure }"
              >
                <td>{{ item.evidenceLabel || item.evidenceCode }}</td>
                <td>{{ item.evidenceCategoryLabel || item.evidenceCategory }}</td>
                <td>{{ item.sourceObjectType || '不适用' }} {{ item.sourceObjectNo || '' }}</td>
                <td>{{ item.sourceField || '不适用' }}</td>
                <td>{{ formatCell(item.sourceValue) }}</td>
                <td>{{ item.targetObjectType || '不适用' }} {{ item.targetObjectNo || '' }}</td>
                <td>{{ item.targetField || '不适用' }}</td>
                <td>{{ formatCell(item.targetValue) }}</td>
                <td>{{ item.expectedRelation || '不适用' }}</td>
                <td>{{ item.actualRelation || '不适用' }}</td>
                <td>{{ item.evidenceStatusLabel || item.evidenceStatus }}</td>
                <td>{{ item.blocking ? '是' : '否' }}</td>
                <td>{{ item.responsibilityLabel || item.responsibilityCategory || '暂无定位' }}</td>
              </tr>
            </tbody>
          </table>
        </BusinessTableScrollContainer>
      </section>

      <div class="panel-grid">
        <article>
          <span>目标对象是否存在</span>
          <strong data-acceptance-id="action-target-exists">{{ model.targetObjectExistsText }}</strong>
        </article>
        <article>
          <span>是否创建目标</span>
          <strong data-acceptance-id="action-target-created">{{ model.targetCreatedText }}</strong>
        </article>
        <article>
          <span>是否复用原目标</span>
          <strong>{{ model.existingTargetReusedText }}</strong>
        </article>
        <article>
          <span>来源状态是否回写</span>
          <strong data-acceptance-id="action-source-writeback">{{ model.sourceWritebackText }}</strong>
        </article>
        <article>
          <span>双向关联是否完成</span>
          <strong data-acceptance-id="action-flow-link">{{ model.bidirectionalLinkText }}</strong>
        </article>
        <article>
          <span>事务是否提交</span>
          <strong data-acceptance-id="action-transaction-committed">{{ model.transactionCommittedText }}</strong>
        </article>
        <article>
          <span>是否执行回滚</span>
          <strong data-acceptance-id="action-rollback-status">{{ model.rollbackExecutedText }}</strong>
        </article>
        <article>
          <span>是否需要人工清理</span>
          <strong data-acceptance-id="action-cleanup-required">{{ model.cleanupRequiredText }}</strong>
        </article>
      </div>

      <section id="missing-evidence-section" class="evidence-detail missing-evidence" data-acceptance-id="action-missing-evidence-list">
        <h4>{{ sectionTitles.missingEvidence }}</h4>
        <ul v-if="model.targetEvidenceMissingItems && model.targetEvidenceMissingItems.length">
          <li v-for="item in model.targetEvidenceMissingItems" :key="item.code">
            {{ item.label || item.code }}（来源：{{ item.evidenceSource || 'runtime' }}）
          </li>
        </ul>
        <p v-else>{{ emptyTexts.noMissingEvidence }}</p>
      </section>

      <section id="conflict-evidence-section" class="evidence-detail conflict-evidence" data-acceptance-id="action-conflict-evidence-list">
        <h4>{{ sectionTitles.conflictEvidence }}</h4>
        <ul v-if="model.targetEvidenceConflictItems && model.targetEvidenceConflictItems.length">
          <li v-for="item in model.targetEvidenceConflictItems" :key="item.code + item.rawValue + item.compareValue">
            {{ item.conflictType || item.code }}：原始值 {{ item.rawValue }}，对比值 {{ item.compareValue }}，
            来源 {{ item.evidenceSource || 'runtime' }}；{{ item.description || '影响下一步放行。' }}
          </li>
        </ul>
        <p v-else>{{ emptyTexts.noConflictEvidence }}</p>
      </section>

      <section id="read-failure-section" class="evidence-detail read-failure" data-acceptance-id="action-read-failure-list">
        <h4>{{ sectionTitles.readFailure }}</h4>
        <ul v-if="model.targetEvidenceReadFailures && model.targetEvidenceReadFailures.length">
          <li v-for="item in model.targetEvidenceReadFailures" :key="item.code + item.readStage">
            {{ item.readStage }} / {{ item.dataSource }}：{{ item.safeErrorSummary }}；
            错误类型 {{ item.errorType }}；是否使用降级值 {{ item.fallbackUsed ? '是' : '否' }}；
            是否影响目标存在性判断 {{ item.affectsTargetExistence ? '是' : '否' }}。
          </li>
        </ul>
        <p v-else>{{ emptyTexts.noReadFailure }}</p>
      </section>

      <p class="result-message">{{ model.resultMessageText }}</p>
      <p v-if="model.nextBusinessStepBlockReasonText" class="block-message">
        阻断原因：{{ model.nextBusinessStepBlockReasonText }}
      </p>
    </section>

    <section class="release-section" data-acceptance-id="business-action-release-conditions">
      <h3>{{ sectionTitles.nextStepRelease }}</h3>
      <ul>
        <li v-for="condition in model.nextStepConditions" :key="condition.label">
          {{ condition.label }}：{{ condition.statusText || (condition.passed ? '满足' : '未满足') }}
        </li>
      </ul>
    </section>
  </section>
</template>

<script setup>
import BusinessTableScrollContainer from './BusinessTableScrollContainer.vue'
import {
  businessAcceptanceEmptyTexts,
  businessAcceptanceFieldLabels,
  businessAcceptanceSectionTitles,
} from '../runtime/businessAcceptanceCopy.js'

defineProps({
  model: {
    type: Object,
    required: true,
  },
  canExecute: {
    type: Boolean,
    default: false,
  },
  executing: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['execute'])

const sectionTitles = businessAcceptanceSectionTitles
const fieldLabels = businessAcceptanceFieldLabels
const emptyTexts = businessAcceptanceEmptyTexts

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '空'
  if (Array.isArray(value)) return value.length ? value.join('；') : '空'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
</script>

<style scoped>
.business-action-status-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #ffffff;
}

.business-action-status-panel h2,
.business-action-status-panel h3,
.business-action-status-panel h4,
.business-action-status-panel p {
  margin: 0;
}

.panel-eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}

.panel-grid article,
.result-source {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.panel-grid span,
.result-source span {
  color: #64748b;
  font-size: 12px;
}

.panel-grid strong,
.result-source strong {
  color: #0f172a;
  word-break: break-word;
}

.execute-button {
  width: fit-content;
  min-height: 36px;
  padding: 0 16px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #2563eb;
  color: #ffffff;
  font-weight: 800;
}

.execute-button:disabled {
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #64748b;
  cursor: not-allowed;
}

.result-section,
.release-section,
.target-evidence-section,
.target-evidence-first-failure,
.target-evidence-trace-section,
.release-summary-card {
  display: grid;
  gap: 12px;
}

.target-evidence-section,
.target-evidence-first-failure,
.target-evidence-trace-section,
.release-summary-card {
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  scroll-margin-top: 16px;
}

.target-evidence-first-failure {
  border-color: #fde68a;
  background: #fffbeb;
}

.target-evidence-trace-section {
  border-color: #d8e0ea;
  background: #ffffff;
}

.target-evidence-trace-table {
  width: max-content;
  min-width: 1900px;
  border-collapse: collapse;
  background: #ffffff;
}

.target-evidence-trace-table th,
.target-evidence-trace-table td {
  max-width: 260px;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}

.target-evidence-trace-table th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
}

.target-evidence-trace-table td {
  color: #0f172a;
  font-size: 13px;
}

.target-evidence-trace-table tr.is-first-failure td {
  background: #fff7ed;
  color: #7c2d12;
  font-weight: 800;
}

.evidence-reason {
  padding: 10px 12px;
  border-radius: 8px;
  background: #ffffff;
  color: #1e3a8a;
  line-height: 1.7;
}

.evidence-detail {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  scroll-margin-top: 16px;
}

.evidence-detail ul {
  margin: 0;
  padding-left: 22px;
  line-height: 1.8;
}

.evidence-detail p {
  color: #475569;
}

.missing-evidence {
  border: 1px solid #fed7aa;
  background: #fff7ed;
  color: #7c2d12;
}

.conflict-evidence {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #7f1d1d;
}

.read-failure {
  border: 1px solid #ddd6fe;
  background: #f5f3ff;
  color: #4c1d95;
}

.result-message,
.block-message {
  padding: 10px 12px;
  border-radius: 8px;
  line-height: 1.7;
}

.result-message {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1e3a8a;
}

.block-message {
  border: 1px solid #fde68a;
  background: #fffbeb;
  color: #92400e;
}

.release-section ul {
  margin: 0;
  padding-left: 22px;
  color: #334155;
  line-height: 1.8;
}
</style>
