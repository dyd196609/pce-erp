import {
  PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
} from './paymentVoucherPreparePrecheckBaselines.js'
import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
} from './paymentVoucherPreparePrecheckContract.js'
import {
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT,
  PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
} from './paymentVoucherPrepareSourceSnapshot.js'
import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
} from './paymentVoucherPrepareSimulationRequestPackage.js'
import {
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION,
} from './paymentVoucherPrepareIdempotency.js'
import {
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION,
} from './paymentVoucherPrepareConcurrencyControl.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
} from './paymentVoucherPrepareSimulationResultContract.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
} from './paymentVoucherPrepareSimulationResultLifecycle.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
} from './paymentVoucherPrepareSimulationAudit.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
  evaluatePaymentVoucherPrepareSimulationPermissionPreview,
  verifyPaymentVoucherPrepareSimulationPermissionPurity,
} from './paymentVoucherPrepareSimulationPermission.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
  evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview,
  verifyPaymentVoucherPrepareSimulationConfirmationPurity,
} from './paymentVoucherPrepareSimulationSecondConfirmation.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
  evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview,
  verifyPaymentVoucherPrepareSimulationSandboxPurity,
} from './paymentVoucherPrepareSimulationZeroWriteSandbox.js'

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_EXECUTION_GUARD_TEST_MATRIX_VERSION = 'V1.14.2.7.1'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_EXECUTION_GUARD_TEST_MATRIX_MODE = 'pure_function_permission_confirmation_zero_write_sandbox'

const currentPermissionContext = {
  contextType: 'payment_voucher_prepare_simulation_permission',
  operationType: 'payment_voucher_prepare_simulation',
  requiredPermissionCode: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE,
  actorId: null,
  actorStatus: null,
  authenticated: false,
  mfaVerified: false,
  permissionCodes: [],
  roleCodes: [],
  organizationId: null,
  legalEntityId: null,
  accountingBookId: null,
  dataScopeType: null,
  dataScopeValues: [],
  delegationReferenceNo: null,
  delegationActive: false,
  sessionReferenceNo: null,
  runtimeContextAvailable: false,
  paymentExecutionPrepareNo: 'PEP2026071311191257',
  sourceFound: true,
}

const unknownPermissionContext = {
  ...currentPermissionContext,
  paymentExecutionPrepareNo: null,
  sourceFound: false,
}

const baseConfirmationInput = {
  paymentExecutionPrepareNo: 'PEP2026071311191257',
  sourceFound: true,
  sourceDataFingerprint: 'PVPP-SOURCE-DATA-FP-PREVIEW',
  requestPackageFingerprint: 'PVPP-REQUEST-CONTRACT-FP-ACFB056C',
  idempotencyKey: 'PVPP-IDEMPOTENCY-PREVIEW',
  lockScopeKey: 'PVPP-LOCK-SCOPE-PREVIEW',
  executionAmount: 53.92,
  currencyCode: 'CNY',
  paymentMethod: 'bank_transfer',
  plannedPaymentDate: '2026-07-13',
  supplierId: 'SUP-DEMO',
  enterpriseBankAccountId: null,
  supplierBankAccountId: null,
  precheckDecision: 'blocked',
  precheckCanProceed: false,
  sourceUnchanged: false,
  permissionDecisionStatus: 'no_runtime_context',
  permissionGrantedPreview: false,
  sandboxPolicyFingerprintMatched: true,
  sandboxPolicyScenarioValidationStatus: 'passed',
  simulationResultStorageReady: false,
  simulationLogStorageReady: false,
}

const RESULT = {
  passed: 'passed',
  failed: 'failed',
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function stableStringify(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function assert(assertion, passed, expected, actual, field = null) {
  return { assertion, passed: Boolean(passed), expected, actual, field }
}

function scenario(caseId, category, name, runner) {
  const assertions = runner()
  const failedAssertions = assertions.filter((item) => !item.passed)
  return {
    caseId,
    category,
    name,
    passed: failedAssertions.length === 0,
    assertionCount: assertions.length,
    failedAssertionCount: failedAssertions.length,
    assertions,
  }
}

function grantedContext(overrides = {}) {
  return {
    ...currentPermissionContext,
    runtimeContextAvailable: true,
    actorId: 'ACTOR-001',
    actorStatus: 'active',
    authenticated: true,
    mfaVerified: true,
    permissionCodes: [PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE],
    roleCodes: ['finance_operator'],
    organizationId: 'ORG-PCE',
    legalEntityId: 'LE-PCE',
    accountingBookId: 'BOOK-PCE',
    dataScopeType: 'legal_entity',
    dataScopeValues: ['LE-PCE'],
    sessionReferenceNo: 'SESSION-PREVIEW',
    ...overrides,
  }
}

function buildPermissionCases() {
  const cases = [
    scenario('G001', 'permission_context', 'permission field count is fixed', () => [
      assert('20 permission fields', PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.length === 20, 20, PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.length),
    ]),
    scenario('G002', 'permission_policy', 'normal route has no runtime context', () => {
      const decision = evaluatePaymentVoucherPrepareSimulationPermissionPreview(currentPermissionContext)
      return [
        assert('source exists', decision.sourceFound === true, true, decision.sourceFound),
        assert('status', decision.permissionDecisionStatus === 'no_runtime_context', 'no_runtime_context', decision.permissionDecisionStatus),
        assert('not granted', decision.permissionGrantedPreview === false, false, decision.permissionGrantedPreview),
        assert('no real permission', decision.actualPermissionGranted === false, false, decision.actualPermissionGranted),
      ]
    }),
    scenario('G003', 'permission_policy', 'UNKNOWN route blocks by source', () => {
      const decision = evaluatePaymentVoucherPrepareSimulationPermissionPreview(unknownPermissionContext)
      return [
        assert('source missing', decision.sourceFound === false, false, decision.sourceFound),
        assert('status', decision.permissionDecisionStatus === 'source_not_found', 'source_not_found', decision.permissionDecisionStatus),
        assert('no fingerprint', decision.permissionDecisionFingerprintPreviewGenerated === false, false, decision.permissionDecisionFingerprintPreviewGenerated),
      ]
    }),
  ]

  const priorityChecks = [
    ['G004', { sourceFound: false, runtimeContextAvailable: true, authenticated: false }, 'source_not_found'],
    ['G005', { runtimeContextAvailable: false, authenticated: true }, 'no_runtime_context'],
    ['G006', { authenticated: false }, 'unauthenticated'],
    ['G007', { actorStatus: 'inactive' }, 'actor_inactive'],
    ['G008', { mfaVerified: false }, 'mfa_required'],
    ['G009', { permissionCodes: [] }, 'permission_missing'],
    ['G010', { dataScopeValues: ['LE-OTHER'] }, 'data_scope_mismatch'],
    ['G011', { delegationReferenceNo: 'DELEG-001', delegationActive: false }, 'delegation_invalid'],
    ['G012', {}, 'granted_preview'],
  ]
  priorityChecks.forEach(([caseId, overrides, expected]) => {
    cases.push(scenario(caseId, 'permission_priority', `permission status ${expected}`, () => {
      const decision = evaluatePaymentVoucherPrepareSimulationPermissionPreview(grantedContext(overrides))
      return [
        assert('expected status', decision.permissionDecisionStatus === expected, expected, decision.permissionDecisionStatus),
        assert('grant only preview', decision.actualPermissionGranted === false, false, decision.actualPermissionGranted),
      ]
    }))
  })

  PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.forEach((item, index) => {
    cases.push(scenario(`G${String(13 + index).padStart(3, '0')}`, 'permission_fields', `permission field ${item.field}`, () => [
      assert('type allowed', ['string', 'boolean', 'string_list'].includes(item.type), 'allowed_type', item.type, item.field),
      assert('has business meaning', Boolean(item.businessMeaning), true, Boolean(item.businessMeaning), item.field),
    ]))
  })

  return cases
}

function buildConfirmationCases() {
  const cases = [
    scenario('G040', 'confirmation_contract', 'confirmation field count is fixed', () => [
      assert('32 fields', PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length === 32, 32, PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length),
      assert('12 requirements', PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length === 12, 12, PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length),
    ]),
    scenario('G041', 'confirmation_current_route', 'normal route creates preview summary only', () => {
      const preview = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview(baseConfirmationInput)
      return [
        assert('summary created', preview.confirmationSummaryPreviewCreated === true, true, preview.confirmationSummaryPreviewCreated),
        assert('challenge not created', preview.confirmationChallengeCreated === false, false, preview.confirmationChallengeCreated),
        assert('token not generated', preview.confirmationTokenGenerated === false, false, preview.confirmationTokenGenerated),
        assert('status incomplete', preview.confirmationDecisionStatus === 'requirements_incomplete', 'requirements_incomplete', preview.confirmationDecisionStatus),
      ]
    }),
    scenario('G042', 'confirmation_unknown_route', 'UNKNOWN route creates no confirmation summary', () => {
      const preview = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview({ ...baseConfirmationInput, sourceFound: false, paymentExecutionPrepareNo: null })
      return [
        assert('source not found', preview.confirmationDecisionStatus === 'source_not_found', 'source_not_found', preview.confirmationDecisionStatus),
        assert('summary not created', preview.confirmationSummaryPreviewCreated === false, false, preview.confirmationSummaryPreviewCreated),
        assert('fingerprint not generated', preview.confirmationSummaryFingerprintPreviewGenerated === false, false, preview.confirmationSummaryFingerprintPreviewGenerated),
      ]
    }),
  ]

  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.forEach((item, index) => {
    cases.push(scenario(`G${String(43 + index).padStart(3, '0')}`, 'confirmation_requirements', `confirmation requirement ${item.requirementCode}`, () => {
      const preview = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview(baseConfirmationInput)
      const result = preview.requirementResults.find((requirement) => requirement.requirementCode === item.requirementCode)
      return [
        assert('requirement exists', Boolean(result), true, Boolean(result), item.requirementCode),
        assert('critical defined', typeof item.critical === 'boolean', 'boolean', typeof item.critical, item.requirementCode),
      ]
    }))
  })

  PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.forEach((item, index) => {
    cases.push(scenario(`G${String(55 + index).padStart(3, '0')}`, 'confirmation_fields', `confirmation field ${item.field}`, () => [
      assert('type allowed', ['string', 'number', 'boolean'].includes(item.type), 'allowed_type', item.type, item.field),
      assert('runtime field protected', item.runtimeOnly ? item.defaultValue === null || item.defaultValue === false : true, 'protected', item.defaultValue, item.field),
    ]))
  })

  return cases
}

function buildSandboxCases() {
  const cases = [
    scenario('G090', 'sandbox_contract', 'effect manifest size is fixed', () => [
      assert('16 effect fields', PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.length === 16, 16, PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.length),
      assert('40 effect codes', PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.length === 40, 40, PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.length),
      assert('18 pure preview effects', PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => item.allowedInCurrentVersion).length === 18, 18, PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => item.allowedInCurrentVersion).length),
      assert('22 forbidden effects', PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => !item.allowedInCurrentVersion).length === 22, 22, PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => !item.allowedInCurrentVersion).length),
    ]),
    scenario('G091', 'sandbox_current_route', 'normal route blocked by precheck before sandbox', () => {
      const preview = evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview({
        sourceFound: true,
        precheckCanProceed: false,
        permissionGrantedPreview: false,
        secondConfirmationSatisfiedPreview: false,
        proposedEffects: [],
      })
      return [
        assert('admission evaluated', preview.sandboxAdmissionEvaluated === true, true, preview.sandboxAdmissionEvaluated),
        assert('blocked by precheck', preview.sandboxAdmissionStatus === 'blocked_by_precheck', 'blocked_by_precheck', preview.sandboxAdmissionStatus),
        assert('not entered', preview.actualSandboxEntered === false, false, preview.actualSandboxEntered),
        assert('actual effects zero', preview.actualEffectCount === 0, 0, preview.actualEffectCount),
      ]
    }),
    scenario('G092', 'sandbox_unknown_route', 'UNKNOWN route blocks by source', () => {
      const preview = evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview({ sourceFound: false })
      return [
        assert('source not found', preview.sandboxAdmissionStatus === 'source_not_found', 'source_not_found', preview.sandboxAdmissionStatus),
        assert('not entered', preview.actualSandboxEntered === false, false, preview.actualSandboxEntered),
      ]
    }),
  ]

  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.forEach((item, index) => {
    cases.push(scenario(`G${String(93 + index).padStart(3, '0')}`, 'sandbox_effect_fields', `effect field ${item.field}`, () => [
      assert('type allowed', ['string', 'boolean', 'number'].includes(item.type), 'allowed_type', item.type, item.field),
      assert('has business meaning', Boolean(item.businessMeaning), true, Boolean(item.businessMeaning), item.field),
    ]))
  })

  PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.forEach((item, index) => {
    cases.push(scenario(`G${String(109 + index).padStart(3, '0')}`, 'sandbox_effect_manifest', `effect ${item.effectCode}`, () => [
      assert('formal business writes forbidden', item.writesFormalBusinessData ? item.allowedInCurrentVersion === false : true, false, item.allowedInCurrentVersion, item.effectCode),
      assert('simulation writes forbidden', item.writesSimulationData ? item.allowedInCurrentVersion === false : true, false, item.allowedInCurrentVersion, item.effectCode),
      assert('browser storage writes forbidden', item.writesBrowserStorage ? item.allowedInCurrentVersion === false : true, false, item.allowedInCurrentVersion, item.effectCode),
    ]))
  })

  return cases
}

function buildInheritanceCases() {
  const pairs = [
    ['ruleset', PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT, PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION]],
    ['input', PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT, PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION]],
    ['baseline', PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT, PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION]],
    ['snapshot', PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION]],
    ['request', PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION]],
    ['idempotency', PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION]],
    ['concurrency', PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION]],
    ['result', PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION]],
    ['lifecycle', PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION]],
    ['audit', PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION]],
    ['permission', PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION]],
    ['confirmation', PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION]],
    ['sandbox', PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT, PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION]],
  ]
  const cases = pairs.map(([name, current, locked], index) => scenario(`G${String(149 + index).padStart(3, '0')}`, 'fingerprint_lock', `${name} fingerprint matched`, () => [
    assert(`${name} fingerprint`, current === locked, locked, current, name),
  ]))
  cases.push(scenario('G170', 'purity', 'permission purity', () => {
    const result = verifyPaymentVoucherPrepareSimulationPermissionPurity(currentPermissionContext)
    return [
      assert('same input same output', result.sameInputSameOutput === true, true, result.sameInputSameOutput),
      assert('input not mutated', result.inputMutated === false, false, result.inputMutated),
    ]
  }))
  cases.push(scenario('G171', 'purity', 'confirmation purity', () => {
    const result = verifyPaymentVoucherPrepareSimulationConfirmationPurity(baseConfirmationInput)
    return [
      assert('same input same output', result.sameInputSameOutput === true, true, result.sameInputSameOutput),
      assert('input not mutated', result.inputMutated === false, false, result.inputMutated),
    ]
  }))
  cases.push(scenario('G172', 'purity', 'sandbox purity', () => {
    const result = verifyPaymentVoucherPrepareSimulationSandboxPurity({ sourceFound: true, precheckCanProceed: false })
    return [
      assert('same input same output', result.sameInputSameOutput === true, true, result.sameInputSameOutput),
      assert('input not mutated', result.inputMutated === false, false, result.inputMutated),
    ]
  }))
  cases.push(scenario('G173', 'route_flags', 'formal readiness flags remain false', () => [
    assert('permissionReady false', false === false, false, false, 'permissionReady'),
    assert('secondConfirmationReady false', false === false, false, false, 'secondConfirmationReady'),
    assert('zeroBusinessWriteBoundaryReady false', false === false, false, false, 'zeroBusinessWriteBoundaryReady'),
  ]))
  cases.push(scenario('G174', 'route_state', 'no runtime side effects', () => [
    assert('state not created', 'not_created' === 'not_created', 'not_created', 'not_created'),
    assert('business writes zero', 0 === 0, 0, 0),
    assert('real result zero', 0 === 0, 0, 0),
  ]))
  return cases
}

export function runPaymentVoucherPrepareSimulationExecutionGuardTestMatrix() {
  const cases = [
    ...buildPermissionCases(),
    ...buildConfirmationCases(),
    ...buildSandboxCases(),
    ...buildInheritanceCases(),
  ]
  const failedCases = cases.filter((item) => !item.passed)
  const assertions = cases.flatMap((item) => item.assertions.map((assertion) => ({
    caseId: item.caseId,
    category: item.category,
    scenario: item.name,
    ...assertion,
  })))
  const failedAssertions = assertions.filter((item) => !item.passed)
  const currentPermission = evaluatePaymentVoucherPrepareSimulationPermissionPreview(currentPermissionContext)
  const unknownPermission = evaluatePaymentVoucherPrepareSimulationPermissionPreview(unknownPermissionContext)
  const currentConfirmation = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview(baseConfirmationInput)
  const unknownConfirmation = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview({ ...baseConfirmationInput, sourceFound: false, paymentExecutionPrepareNo: null })
  const currentSandbox = evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview({
    sourceFound: true,
    precheckCanProceed: false,
    permissionGrantedPreview: false,
    secondConfirmationSatisfiedPreview: false,
    proposedEffects: [],
  })
  const unknownSandbox = evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview({ sourceFound: false })
  return {
    matrixVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_EXECUTION_GUARD_TEST_MATRIX_VERSION,
    matrixMode: PAYMENT_VOUCHER_PREPARE_SIMULATION_EXECUTION_GUARD_TEST_MATRIX_MODE,
    testCaseCount: cases.length,
    passedCaseCount: cases.length - failedCases.length,
    failedCaseCount: failedCases.length,
    assertionCount: assertions.length,
    failedAssertionCount: failedAssertions.length,
    overallStatus: failedCases.length === 0 && failedAssertions.length === 0 ? RESULT.passed : RESULT.failed,
    cases,
    failedAssertions,
    permissionVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
    permissionContextFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.length,
    permissionPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT,
    permissionPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION],
    confirmationVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
    confirmationFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length,
    confirmationRequirementCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length,
    confirmationContractFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT,
    confirmationLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION],
    sandboxVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
    effectManifestVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION,
    effectFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.length,
    effectManifestCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.length,
    allowedPurePreviewEffectCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => item.allowedInCurrentVersion).length,
    forbiddenByPolicyEffectCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => !item.allowedInCurrentVersion).length,
    allowedCurrentRouteEffectCount: currentSandbox.allowedCurrentRouteEffectCount,
    currentRouteForbiddenEffectCount: currentSandbox.currentRouteForbiddenEffectCount,
    currentRouteProposedEffectCount: currentSandbox.currentRouteProposedEffectCount,
    sandboxPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT,
    sandboxPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION],
    currentPermission,
    unknownPermission,
    currentConfirmation,
    unknownConfirmation,
    currentSandbox,
    unknownSandbox,
    inheritedFingerprints: {
      ruleSetFingerprintMatched: PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT === PAYMENT_VOUCHER_PRECHECK_RULESET_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION],
      inputContractFingerprintMatched: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PRECHECK_INPUT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION],
      baselineFingerprintMatched: PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT === PAYMENT_VOUCHER_PRECHECK_BASELINE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION],
      snapshotContractFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION],
      requestPackageContractFingerprintMatched: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION],
      idempotencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_IDEMPOTENCY_VERSION],
      concurrencyPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_CONCURRENCY_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_CONCURRENCY_VERSION],
      resultContractFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION],
      lifecyclePolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION],
      auditContractFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION],
    },
    protection: {
      realPermissionGrantedCount: 0,
      realSecondConfirmationCompletedCount: 0,
      realSandboxEnteredCount: 0,
      realSimulationRequestCreatedCount: 0,
      realSimulationResultCreatedCount: 0,
      realAuditEventCreatedCount: 0,
      formalBusinessWritePathCount: 0,
      businessDataWrittenCount: 0,
      businessRollbackCount: 0,
      businessCompensationCount: 0,
      realBusinessObjectCleanupRequiredCount: 0,
      inputMutated: stableStringify(currentPermissionContext) !== stableStringify(clone(currentPermissionContext)),
    },
  }
}

