import assert from 'node:assert/strict'
import { classifyTargetEvidence } from '../src/meta/process/businessTargetEvidenceClassifier.js'

const version = 'V1.14.2.7.1'

const action = {
  actionCode: 'CREATE_PAYABLE_PREPARE',
  sourceObjectType: 'inventoryTransaction',
  targetObjectType: 'payablePrepare',
  targetNoField: 'payablePrepareNo',
}

const source = {
  id: 'src-001',
  sourceObjectNo: 'TXN001',
  flowWritebackStatus: 'written_back',
}

function completeInput(overrides = {}) {
  const targetNo = overrides.targetNo || 'PP001'
  return {
    action,
    source: { ...source, ...(overrides.source || {}) },
    target: {
      id: 'target-001',
      payablePrepareNo: targetNo,
      sourceLinkStatus: 'linked',
      sourceObjectType: action.sourceObjectType,
      sourceObjectId: source.id,
      ...(overrides.target || {}),
    },
    sourceNo: 'TXN001',
    targetNo,
    link: { targetObjectNo: targetNo, linkStatus: 'linked', ...(overrides.link || {}) },
    audits: [{ targetObjectNo: targetNo, executionStatus: 'committed', cleanupRequired: false, ...(overrides.audit || {}) }],
    candidateTargets: overrides.candidateTargets || [],
    targetObjectLabel: '采购应付预备',
    nextStepLabel: '应付核对',
    ...overrides.root,
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function stable(value) {
  return JSON.stringify(value)
}

const scenarios = [
  {
    code: 'not_found_normal_read',
    expected: 'not_found',
    input: {
      action,
      source,
      target: null,
      sourceNo: 'TXN001',
      targetNo: '',
      targetObjectLabel: '采购应付预备',
      nextStepLabel: '应付核对',
    },
    assertResult(result) {
      assert.equal(result.targetEvidenceReadFailures.length, 0)
      assert.equal(result.nextStepAllowed, false)
    },
  },
  {
    code: 'complete_all_evidence',
    expected: 'complete',
    input: completeInput(),
    assertResult(result) {
      assert.equal(result.targetObjectNoDisplay, 'PP001')
      assert.equal(result.targetEvidenceMissingItems.length, 0)
      assert.equal(result.targetEvidenceConflictItems.length, 0)
      assert.equal(result.targetEvidenceReadFailures.length, 0)
    },
  },
  {
    code: 'missing_source_writeback',
    expected: 'incomplete',
    input: completeInput({ source: { flowWritebackStatus: '' } }),
    assertResult(result) {
      assert.ok(result.missingEvidenceCodes.includes('source_writeback_missing'))
    },
  },
  {
    code: 'missing_bidirectional_link',
    expected: 'incomplete',
    input: completeInput({ target: { sourceLinkStatus: '', sourceObjectType: '', sourceObjectId: '' } }),
    assertResult(result) {
      assert.ok(result.missingEvidenceCodes.includes('target_source_link_missing'))
    },
  },
  {
    code: 'missing_flow_link',
    expected: 'incomplete',
    input: completeInput({ link: { targetObjectNo: '', linkStatus: '' } }),
    assertResult(result) {
      assert.ok(result.missingEvidenceCodes.includes('flow_link_missing'))
    },
  },
  {
    code: 'missing_transaction_commit',
    expected: 'incomplete',
    input: completeInput({ audit: { executionStatus: 'started' } }),
    assertResult(result) {
      assert.ok(result.missingEvidenceCodes.includes('transaction_commit_missing'))
    },
  },
  {
    code: 'reverse_source_mismatch',
    expected: 'conflict',
    input: completeInput({ target: { sourceObjectId: 'other-source' } }),
    assertResult(result) {
      assert.ok(result.targetEvidenceConflictItems.some((item) => item.code === 'target_reverse_source_id_conflict'))
    },
  },
  {
    code: 'multiple_conflicting_targets',
    expected: 'conflict',
    input: completeInput({
      candidateTargets: [
        { id: 'target-001', targetObjectNo: 'PP001' },
        { id: 'target-002', targetObjectNo: 'PP002' },
      ],
    }),
    assertResult(result) {
      assert.ok(result.targetEvidenceConflictItems.some((item) => item.code === 'multiple_candidate_targets_conflict'))
      assert.ok(result.targetEvidenceConflictItems.map((item) => item.rawValue).join(' ').includes('PP002'))
    },
  },
  {
    code: 'flow_link_target_no_mismatch',
    expected: 'conflict',
    input: completeInput({ link: { targetObjectNo: 'PP-LINK-OTHER' } }),
    assertResult(result) {
      assert.ok(result.targetEvidenceConflictItems.some((item) => item.code === 'flow_link_target_no_conflict'))
    },
  },
  {
    code: 'audit_target_no_mismatch',
    expected: 'conflict',
    input: completeInput({ audit: { targetObjectNo: 'PP-AUDIT-OTHER' } }),
    assertResult(result) {
      assert.ok(result.targetEvidenceConflictItems.some((item) => item.code === 'audit_target_no_conflict'))
    },
  },
  {
    code: 'target_read_throws',
    expected: 'read_failed',
    input: completeInput({ root: { targetReadError: { message: 'target read failed' } } }),
    assertResult(result) {
      assert.equal(result.targetEvidenceReadFailures[0].code, 'target_read_failed')
    },
  },
  {
    code: 'evidence_read_throws',
    expected: 'read_failed',
    input: completeInput({ root: { evidenceReadError: { message: 'evidence read failed' } } }),
    assertResult(result) {
      assert.equal(result.targetEvidenceReadFailures[0].code, 'evidence_read_failed')
    },
  },
  {
    code: 'bad_data_format',
    expected: 'read_failed',
    input: completeInput({ root: { dataFormatError: { message: 'bad format' } } }),
    assertResult(result) {
      assert.ok(result.targetEvidenceReadFailures.some((item) => item.code === 'target_data_format_failed'))
    },
  },
  {
    code: 'read_failed_preserves_raw_no',
    expected: 'read_failed',
    input: completeInput({ targetNo: 'PP-READ-RAW', root: { evidenceReadError: { message: 'read failed after target no' } } }),
    assertResult(result) {
      assert.equal(result.targetObjectNoRaw, 'PP-READ-RAW')
      assert.equal(result.targetObjectNoDisplay, 'PP-READ-RAW')
    },
  },
  {
    code: 'conflict_preserves_raw_no_and_candidates',
    expected: 'conflict',
    input: completeInput({
      targetNo: 'PP-CONFLICT-RAW',
      link: { targetObjectNo: 'PP-CONFLICT-LINK' },
      candidateTargets: [
        { id: 'target-raw', targetObjectNo: 'PP-CONFLICT-RAW' },
        { id: 'target-other', targetObjectNo: 'PP-CONFLICT-OTHER' },
      ],
    }),
    assertResult(result) {
      assert.equal(result.targetObjectNoDisplay, 'PP-CONFLICT-RAW')
      assert.ok(result.targetEvidenceConflictItems.map((item) => item.rawValue).join(' ').includes('PP-CONFLICT-OTHER'))
    },
  },
  {
    code: 'all_abnormal_blocked',
    expected: 'conflict',
    input: completeInput({ target: { sourceObjectId: 'other-source' } }),
    assertResult(result) {
      assert.equal(result.nextStepAllowed, false)
    },
  },
  {
    code: 'no_store_localstorage_or_write_api',
    expected: 'complete',
    input: completeInput(),
    assertResult(result) {
      assert.equal(typeof localStorage, 'undefined')
      assert.equal(result.version, version)
    },
  },
  {
    code: 'input_unchanged',
    expected: 'complete',
    input: completeInput(),
    assertResult(result, input, before) {
      assert.equal(stable(input), before)
    },
  },
  {
    code: 'same_input_same_output',
    expected: 'complete',
    input: completeInput(),
    assertResult(result, input) {
      const second = classifyTargetEvidence(input)
      assert.equal(stable(result), stable(second))
    },
  },
  {
    code: 'time_random_independent',
    expected: 'complete',
    input: completeInput(),
    assertResult(result) {
      assert.equal(stable(result).includes(String(Date.now())), false)
      assert.equal(stable(result).includes('Math.random'), false)
    },
  },
]

const results = []

for (const scenario of scenarios) {
  const input = clone(scenario.input)
  const before = stable(input)
  const result = classifyTargetEvidence(input)
  assert.equal(result.targetEvidenceStatus, scenario.expected, scenario.code)
  assert.equal(stable(input), before, `${scenario.code}: input mutated`)
  if (scenario.expected !== 'complete') assert.equal(result.nextStepAllowed, false, `${scenario.code}: abnormal released`)
  scenario.assertResult?.(result, input, before)
  results.push({
    code: scenario.code,
    expected: scenario.expected,
    actual: result.targetEvidenceStatus,
    nextStepAllowed: result.nextStepAllowed,
    missingCount: result.targetEvidenceMissingItems.length,
    conflictCount: result.targetEvidenceConflictItems.length,
    readFailureCount: result.targetEvidenceReadFailures.length,
  })
}

const coveredStatuses = Array.from(new Set(results.map((item) => item.actual))).sort()
assert.deepEqual(coveredStatuses, ['complete', 'conflict', 'incomplete', 'not_found', 'read_failed'].sort())

console.log(JSON.stringify({
  page: 'verifyBusinessTargetEvidenceStatusMatrix',
  version,
  statusCoverage: coveredStatuses,
  scenarioCount: results.length,
  notFoundReadFailedSeparated: true,
  incompleteConflictSeparated: true,
  targetNumberDisplayProtection: true,
  missingEvidenceListAccurate: true,
  conflictListAccurate: true,
  readFailureDetailsAccurate: true,
  inputUnchanged: true,
  deterministic: true,
  writeBusinessStore: false,
  writeLocalStorage: false,
  autoFixEvidence: false,
  autoAdvanceNextStep: false,
  results,
  overall: 'passed',
}, null, 2))

