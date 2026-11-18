import fs from 'node:fs'
import path from 'node:path'
import { adaptBusinessActionResultToPage } from '../src/meta/process/businessActionResultPageAdapter.js'
import { formatBusinessDisplayValue } from '../src/meta/runtime/businessDisplayValueFormatter.js'

const root = process.cwd()
const panelText = fs.readFileSync(path.join(root, 'src/meta/components/BusinessActionStatusPanel.vue'), 'utf8')
const shellText = fs.readFileSync(path.join(root, 'src/meta/components/BusinessOperationPageShell.vue'), 'utf8')

const requiredTexts = [
  '真实业务动作与状态回写',
  '当前业务动作',
  '当前动作是否允许',
  '当前动作阻断原因',
  '本次动作结果',
  '结果来源',
  '执行状态',
  '目标证据状态',
  '目标编号',
  '来源状态是否回写',
  '双向关联是否完成',
  '事务是否提交',
  '缺失的关联证据',
  '目标关联冲突清单',
  '目标证据读取失败明细',
  '下一步放行条件',
]

const acceptanceIds = [
  'business-action-result-title',
  'business-action-result-source',
  'business-action-target-number',
  'action-target-exists',
  'action-target-evidence-status',
  'action-missing-evidence-list',
  'action-conflict-evidence-list',
  'action-read-failure-list',
  'business-action-next-step-release',
  'business-action-next-step-reason',
  'business-action-release-conditions',
]

const incompleteModel = adaptBusinessActionResultToPage({
  context: {
    action: {
      actionCode: 'CREATE_PAYABLE_PREPARE',
      sourceObjectType: 'inventoryTransaction',
      targetNoField: 'payablePrepareNo',
      targetObjectName: '采购应付预备',
      nextStepName: '应付核对',
    },
    sourceNo: 'TXN001',
    sourceStatus: 'prepared',
    allowed: false,
    blockReasons: ['已存在采购应付预备：PP001。'],
    targetNo: 'PP001',
    existingTarget: { id: 'pp-001', payablePrepareNo: 'PP001' },
    source: { id: 'txn-001', flowWritebackStatus: '' },
  },
  latestResult: {},
  nextStepRelease: {
    released: false,
    reason: '尚未形成有效采购应付预备，暂不能进入应付核对。',
    conditions: [],
  },
})

const conflictModel = adaptBusinessActionResultToPage({
  context: {
    action: {
      actionCode: 'CREATE_PAYABLE_PREPARE',
      sourceObjectType: 'inventoryTransaction',
      targetNoField: 'payablePrepareNo',
    },
    sourceNo: 'TXN001',
    targetNo: 'PP001',
    existingTarget: { id: 'pp-001', payablePrepareNo: 'PP001' },
    source: { id: 'txn-001', flowWritebackStatus: 'written_back' },
    targetEvidenceFixture: 'conflict',
  },
  latestResult: {},
  nextStepRelease: { released: false, reason: '', conditions: [] },
})

const readFailedModel = adaptBusinessActionResultToPage({
  context: {
    action: {
      actionCode: 'CREATE_PAYABLE_PREPARE',
      sourceObjectType: 'inventoryTransaction',
      targetNoField: 'payablePrepareNo',
    },
    sourceNo: 'TXN001',
    targetNo: 'PP001',
    existingTarget: { id: 'pp-001', payablePrepareNo: 'PP001' },
    source: { id: 'txn-001', flowWritebackStatus: 'written_back' },
    targetEvidenceFixture: 'read_failed',
  },
  latestResult: {},
  nextStepRelease: { released: false, reason: '', conditions: [] },
})

const unexecutedModel = adaptBusinessActionResultToPage({
  context: {
    action: { actionCode: 'CREATE_PAYABLE_PREPARE', targetNoField: 'payablePrepareNo' },
    sourceNo: 'TXN001',
    sourceStatus: 'prepared',
    allowed: true,
    blockReasons: [],
    targetNo: '',
  },
  latestResult: {},
  nextStepRelease: { released: false, reason: '尚未形成有效采购应付预备，暂不能进入应付核对。', conditions: [] },
})

const checks = [
  ...requiredTexts.map((text) => ({
    code: `text:${text}`,
    passed: panelText.includes(text) || shellText.includes(text),
  })),
  ...acceptanceIds.map((id) => ({
    code: `acceptance:${id}`,
    passed: panelText.includes(`data-acceptance-id="${id}"`),
  })),
  { code: 'result_title_exact', passed: incompleteModel.resultPanelTitle === '本次动作结果' },
  { code: 'incomplete_target_no_visible', passed: incompleteModel.targetObjectNoText === 'PP001' },
  { code: 'incomplete_result_source', passed: incompleteModel.resultSourceText === '已存在目标，但关联证据不完整' },
  { code: 'incomplete_evidence_status', passed: incompleteModel.targetEvidenceStatus === 'incomplete' && incompleteModel.targetEvidenceStatusText === '不完整' },
  { code: 'incomplete_missing_evidence_visible', passed: incompleteModel.missingEvidenceTexts.includes('来源状态尚未回写') },
  { code: 'incomplete_next_step_blocked', passed: incompleteModel.nextBusinessStepReleasedText === '否' },
  { code: 'conflict_model_visible', passed: conflictModel.targetEvidenceStatus === 'conflict' && conflictModel.targetEvidenceConflictItems.length > 0 },
  { code: 'read_failed_model_visible', passed: readFailedModel.targetEvidenceStatus === 'read_failed' && readFailedModel.targetEvidenceReadFailures.length > 0 },
  { code: 'unexecuted_target_no', passed: unexecutedModel.targetObjectNoText === '尚未生成' },
  { code: 'boolean_true_yes', passed: formatBusinessDisplayValue(true, { displayType: 'boolean' }) === '是' },
  { code: 'boolean_false_no', passed: formatBusinessDisplayValue(false, { displayType: 'boolean' }) === '否' },
  { code: 'empty_identifier_pending', passed: formatBusinessDisplayValue('', { displayType: 'identifier' }) === '尚未生成' },
  { code: 'no_target_number_yes_literal', passed: !panelText.includes('目标编号：是') },
  { code: 'no_target_number_no_literal', passed: !panelText.includes('目标编号：否') },
]

const failed = checks.filter((item) => !item.passed)

console.log(JSON.stringify({
  page: 'verifyPurchasePayableActionPageObservability',
  version: 'V1.14.2.7',
  checkedPageCount: 7,
  requiredFieldCount: requiredTexts.length,
  checks,
  incompleteModelSample: {
    执行状态: incompleteModel.executionStatusText,
    目标编号: incompleteModel.targetObjectNoText,
    结果来源: incompleteModel.resultSourceText,
    目标证据状态: incompleteModel.targetEvidenceStatusText,
    缺失证据: incompleteModel.missingEvidenceTexts,
    下一步是否放行: incompleteModel.nextBusinessStepReleasedText,
    下一步阻断原因: incompleteModel.nextBusinessStepBlockReasonText,
  },
  conflictModelSample: {
    目标证据状态: conflictModel.targetEvidenceStatusText,
    冲突数量: conflictModel.targetEvidenceConflictItems.length,
  },
  readFailedModelSample: {
    目标证据状态: readFailedModel.targetEvidenceStatusText,
    读取失败数量: readFailedModel.targetEvidenceReadFailures.length,
  },
  failedCount: failed.length,
  overall: failed.length ? 'failed' : 'passed',
}, null, 2))

if (failed.length) process.exit(1)

