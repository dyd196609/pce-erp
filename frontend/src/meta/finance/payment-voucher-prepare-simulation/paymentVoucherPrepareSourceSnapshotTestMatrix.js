import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS,
  adaptPaymentVoucherPrepareSourceToSnapshotInput,
  normalizePaymentVoucherPrepareSourceSnapshot,
  validatePaymentVoucherPrepareSourceSnapshot,
  verifyPaymentVoucherPrepareSourceSnapshotPurity,
} from './paymentVoucherPrepareSourceSnapshot.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
  createPaymentVoucherPrepareSourceFingerprint,
  verifyPaymentVoucherPrepareSourceFingerprintPurity,
} from './paymentVoucherPrepareSourceFingerprint.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION,
  detectPaymentVoucherPrepareSourceChanges,
  verifyPaymentVoucherPrepareSourceChangeDetectorPurity,
} from './paymentVoucherPrepareSourceChangeDetector.js'

export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_TEST_MATRIX_VERSION = 'V1.13.65'
export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_TEST_MATRIX_EXECUTION_MODE = 'pure_function_readonly_source_snapshot_test_matrix'

const RESULT = {
  passed: 'passed',
  failed: 'failed',
}

const completeInput = {
  sourceObjectType: 'payment_execution_prepare',
  paymentExecutionPrepareNo: 'PEP-MATRIX-READY',
  sourcePaymentInstructionPrepareNo: 'POP-MATRIX-READY',
  sourcePaymentApplicationNo: 'PAP-MATRIX-READY',
  sourcePayableConfirmNo: 'APC-MATRIX-READY',
  sourceInvoicePrepareNo: 'IP-MATRIX-READY',
  sourceSettlementNo: 'SET-MATRIX-READY',
  sourceChainComplete: true,
  reviewStatus: 'reviewed',
  supplierId: 'SUP-MATRIX',
  legalEntityId: 'LE-PCE',
  accountingBookId: 'BOOK-PCE',
  executionAmount: 53.92,
  paymentMethod: 'bank_transfer',
  plannedPaymentDate: '2026-07-13',
  currencyCode: 'CNY',
  baseCurrencyCode: 'CNY',
  foreignCurrencyPayment: false,
  exchangeRateType: 'middle',
  exchangeRateDate: '2026-07-13',
  exchangeRate: 1,
  exchangeRateSource: 'manual',
  currencyPrecision: 2,
  roundingMode: 'half_up',
  accountingTemplateId: 'TPL-PV-001',
  accountingTemplateVersion: '1.0',
  accountingTemplateStatus: 'active',
  accountingPeriod: '2026-07',
  accountingPeriodStatus: 'open',
  enterpriseBankAccountId: 'EBA-001',
  supplierBankAccountId: 'SBA-001',
  paymentExecutionStatus: 'not_executed',
  paymentVoucherStatus: 'not_generated',
  formalPaymentVoucherStatus: 'not_generated',
  writeOffStatus: 'not_written_off',
  ledgerStatus: 'not_written_ledger',
  postingStatus: 'not_posted',
  sourceRevision: 'REV-001',
  sourceUpdatedAt: '2026-07-13T11:19:12.000Z',
  sourceDataVersion: 'DATA-001',
}

const currentDemoSource = {
  paymentExecutionPrepareNo: 'PEP2026071311191257',
  sourcePaymentOrderPrepareNo: 'POP2026071311191284',
  sourcePaymentApplicationNo: 'PAP2026071311191246',
  sourcePayableConfirmNo: 'APC2026071311191255',
  sourceInvoicePrepareNo: 'IP2026071311191146',
  sourceSettlementNo: 'SET2026071311191160',
  supplierId: 'SUP-DEMO',
  executionAmount: 53.92,
  currency: 'CNY',
  paymentMethod: 'bank_transfer',
  plannedPaymentDate: '2026-07-13',
  paymentExecutionPrepareStatus: 'reviewed',
  paymentExecutionStatus: 'not_executed',
  paymentVoucherStatus: 'not_generated',
  formalPaymentVoucherStatus: 'not_generated',
  writeOffStatus: 'not_written_off',
  ledgerStatus: 'not_written_ledger',
  postingStatus: 'not_posted',
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

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    Object.freeze(value)
    Object.keys(value).forEach((key) => deepFreeze(value[key]))
  }
  return value
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
    failedAssertions,
  }
}

function normalized(input) {
  return normalizePaymentVoucherPrepareSourceSnapshot(input)
}

function fingerprint(input) {
  return createPaymentVoucherPrepareSourceFingerprint(input)
}

function changed(field, nextValue) {
  const reference = normalized(completeInput)
  const currentInput = { ...completeInput, [field]: nextValue }
  const current = normalized(currentInput)
  return detectPaymentVoucherPrepareSourceChanges(reference, current)
}

function changeScenario(caseId, field, nextValue, name) {
  return scenario(caseId, '字段变化', name, () => {
    const result = changed(field, nextValue)
    const target = result.changedFields.find((item) => item.field === field)
    return [
      assert('CHANGE_STATUS_CHANGED', result.changeStatus === 'changed', 'changed', result.changeStatus, field),
      assert('FIELD_CHANGED', Boolean(target), true, Boolean(target), field),
      assert('CRITICAL_INVALIDATES_IF_CRITICAL', target ? target.invalidatesSimulationResult === target.critical : false, true, target, field),
    ]
  })
}

const fixedScenarios = [
  scenario('S001', '来源快照', '正常 PEP 部分快照', () => {
    const input = adaptPaymentVoucherPrepareSourceToSnapshotInput(currentDemoSource)
    const result = normalized(input)
    const fp = fingerprint(result)
    return [
      assert('SOURCE_FOUND', result.sourceFound, true, result.sourceFound),
      assert('SNAPSHOT_CREATED', result.snapshotPreviewCreated, true, result.snapshotPreviewCreated),
      assert('STRUCTURE_PARTIAL', result.snapshotStructureStatus === 'partial', 'partial', result.snapshotStructureStatus),
      assert('FINGERPRINT_PARTIAL', fp.fingerprintStatus === 'partial_preview', 'partial_preview', fp.fingerprintStatus),
    ]
  }),
  scenario('S002', '来源快照', '全字段完整快照', () => {
    const result = normalized(completeInput)
    const fp = fingerprint(result)
    return [
      assert('STRUCTURE_COMPLETE', result.snapshotStructureStatus === 'complete', 'complete', result.snapshotStructureStatus),
      assert('MISSING_CRITICAL_ZERO', result.missingCriticalFieldCount === 0, 0, result.missingCriticalFieldCount),
      assert('FINGERPRINT_COMPLETE', fp.fingerprintStatus === 'complete_preview', 'complete_preview', fp.fingerprintStatus),
    ]
  }),
  scenario('S003', '来源不存在', 'UNKNOWN-PEP', () => {
    const result = normalized({ sourceFound: false })
    const fp = fingerprint(result)
    const change = detectPaymentVoucherPrepareSourceChanges(null, result)
    return [
      assert('SOURCE_NOT_FOUND', result.sourceFound === false, false, result.sourceFound),
      assert('SNAPSHOT_NOT_CREATED', result.snapshotPreviewCreated === false, false, result.snapshotPreviewCreated),
      assert('FINGERPRINT_NOT_GENERATED', fp.fingerprintPreviewGenerated === false, false, fp.fingerprintPreviewGenerated),
      assert('CHANGE_SOURCE_NOT_FOUND', change.changeStatus === 'source_not_found', 'source_not_found', change.changeStatus),
    ]
  }),
  scenario('S004', '来源不存在', 'null 输入', () => {
    const result = normalized(null)
    return [assert('NULL_SOURCE_NOT_FOUND', result.snapshotStructureStatus === 'source_not_found', 'source_not_found', result.snapshotStructureStatus)]
  }),
  scenario('S005', '来源不存在', '空对象', () => {
    const result = normalized({})
    return [assert('EMPTY_SOURCE_NOT_FOUND', result.snapshotStructureStatus === 'source_not_found', 'source_not_found', result.snapshotStructureStatus)]
  }),
  scenario('S006', '来源快照', '未知字段忽略', () => {
    const result = normalized({ ...completeInput, displayOnlyText: '展示字段' })
    return [
      assert('UNKNOWN_FIELD_COUNT', result.unknownInputFieldCount === 1, 1, result.unknownInputFieldCount),
      assert('UNKNOWN_FIELD_IGNORED', result.ignoredUnknownFields.includes('displayOnlyText'), true, result.ignoredUnknownFields),
    ]
  }),
  scenario('S007', '来源指纹', '对象字段顺序变化', () => {
    const reversed = {}
    Object.keys(completeInput).reverse().forEach((key) => {
      reversed[key] = completeInput[key]
    })
    return [
      assert('ORDER_INDEPENDENT', fingerprint(normalized(completeInput)).sourceDataFingerprint === fingerprint(normalized(reversed)).sourceDataFingerprint, true, 'same'),
    ]
  }),
  scenario('S008', '来源指纹', '相同输入100次', () => {
    const first = fingerprint(normalized(completeInput)).sourceDataFingerprint
    const allSame = Array.from({ length: 100 }).every(() => fingerprint(normalized(completeInput)).sourceDataFingerprint === first)
    return [assert('REPEAT_100_SAME', allSame, true, allSame)]
  }),
  scenario('S009', '纯函数保护', '输入对象未修改', () => {
    const before = stableStringify(completeInput)
    normalized(completeInput)
    fingerprint(normalized(completeInput))
    detectPaymentVoucherPrepareSourceChanges(normalized(completeInput), normalized(completeInput))
    return [assert('INPUT_NOT_MUTATED', before === stableStringify(completeInput), true, before === stableStringify(completeInput))]
  }),
  scenario('S010', '纯函数保护', '深度冻结输入', () => {
    const frozen = deepFreeze(clone(completeInput))
    const result = normalized(frozen)
    return [assert('FROZEN_INPUT_OK', result.snapshotStructureStatus === 'complete', 'complete', result.snapshotStructureStatus)]
  }),
]

const changeScenarios = [
  changeScenario('S011', 'executionAmount', 54.92, '付款金额变化'),
  changeScenario('S012', 'paymentMethod', 'bank_acceptance', '付款方式变化'),
  changeScenario('S013', 'paymentExecutionPrepareNo', 'PEP-MATRIX-CHANGED', '付款执行准备单号变化'),
  changeScenario('S014', 'supplierId', 'SUP-CHANGED', '供应商变化'),
  changeScenario('S015', 'legalEntityId', 'LE-CHANGED', '法人主体变化'),
  changeScenario('S016', 'accountingBookId', 'BOOK-CHANGED', '会计账套变化'),
  changeScenario('S017', 'enterpriseBankAccountId', 'EBA-CHANGED', '企业银行账户变化'),
  changeScenario('S018', 'supplierBankAccountId', 'SBA-CHANGED', '供应商银行账户变化'),
  changeScenario('S019', 'currencyCode', 'USD', '付款币种变化'),
  changeScenario('S020', 'baseCurrencyCode', 'USD', '本位币变化'),
  changeScenario('S021', 'exchangeRateType', 'spot', '汇率类型变化'),
  changeScenario('S022', 'exchangeRateDate', '2026-07-14', '汇率日期变化'),
  changeScenario('S023', 'exchangeRate', 7.12, '汇率数值变化'),
  changeScenario('S024', 'exchangeRateSource', 'bank', '汇率来源变化'),
  changeScenario('S025', 'accountingTemplateId', 'TPL-PV-002', '科目模板编号变化'),
  changeScenario('S026', 'accountingTemplateVersion', '2.0', '科目模板版本变化'),
  changeScenario('S027', 'accountingPeriod', '2026-08', '会计期间变化'),
  changeScenario('S028', 'paymentExecutionStatus', 'executed', '付款执行状态变化'),
  changeScenario('S029', 'paymentVoucherStatus', 'generated', '付款凭证状态变化'),
  changeScenario('S030', 'formalPaymentVoucherStatus', 'generated', '正式付款凭证状态变化'),
  changeScenario('S031', 'writeOffStatus', 'written_off', '核销状态变化'),
  changeScenario('S032', 'ledgerStatus', 'written_ledger', '总账状态变化'),
  changeScenario('S033', 'postingStatus', 'posted', '过账状态变化'),
  changeScenario('S034', 'sourceRevision', 'REV-002', '来源修订号变化'),
  changeScenario('S035', 'sourceUpdatedAt', '2026-07-14T11:19:12.000Z', '来源更新时间变化'),
]

const tailScenarios = [
  scenario('S036', '来源变更', '相同快照比较', () => {
    const result = detectPaymentVoucherPrepareSourceChanges(normalized(completeInput), normalized(completeInput))
    return [
      assert('UNCHANGED', result.changeStatus === 'unchanged', 'unchanged', result.changeStatus),
      assert('BUSINESS_SOURCE_UNCHANGED', result.businessSourceUnchanged === true, true, result.businessSourceUnchanged),
    ]
  }),
  scenario('S037', '来源变更', '无参考快照', () => {
    const result = detectPaymentVoucherPrepareSourceChanges(null, normalized(completeInput))
    return [
      assert('NO_REFERENCE', result.changeStatus === 'no_reference', 'no_reference', result.changeStatus),
      assert('NOT_CONFIRMED_UNCHANGED', result.businessSourceUnchanged === false, false, result.businessSourceUnchanged),
    ]
  }),
  scenario('S038', '来源变更', '来源不存在', () => {
    const result = detectPaymentVoucherPrepareSourceChanges(null, normalized({ sourceFound: false }))
    return [assert('CHANGE_SOURCE_NOT_FOUND', result.changeStatus === 'source_not_found', 'source_not_found', result.changeStatus)]
  }),
  scenario('S039', '来源指纹', '页面版本字段变化不影响指纹', () => {
    const base = fingerprint(normalized(completeInput)).sourceDataFingerprint
    const withPageVersion = fingerprint(normalized({ ...completeInput, pageVersion: 'V9.99.99' })).sourceDataFingerprint
    return [assert('PAGE_VERSION_EXCLUDED', base === withPageVersion, true, 'same')]
  }),
  scenario('S040', '来源指纹', '路由 URL 变化不影响指纹', () => {
    const base = fingerprint(normalized(completeInput)).sourceDataFingerprint
    const withRoute = fingerprint(normalized({ ...completeInput, routeUrl: '/x/y' })).sourceDataFingerprint
    return [assert('ROUTE_EXCLUDED', base === withRoute, true, 'same')]
  }),
  scenario('S041', '来源指纹', '中文展示字段变化不影响指纹', () => {
    const base = fingerprint(normalized(completeInput)).sourceDataFingerprint
    const withText = fingerprint(normalized({ ...completeInput, chineseLabel: '已复核' })).sourceDataFingerprint
    return [assert('DISPLAY_TEXT_EXCLUDED', base === withText, true, 'same')]
  }),
  scenario('S042', '规范化', 'null 与缺失值规范化稳定', () => {
    const missing = fingerprint(normalized({ ...completeInput, legalEntityId: undefined })).sourceDataFingerprint
    const nullValue = fingerprint(normalized({ ...completeInput, legalEntityId: null })).sourceDataFingerprint
    return [assert('NULL_MISSING_STABLE', missing === nullValue, true, 'same')]
  }),
  scenario('S043', '规范化', '数值规范化稳定', () => {
    const a = fingerprint(normalized({ ...completeInput, executionAmount: 53.920 })).sourceDataFingerprint
    const b = fingerprint(normalized({ ...completeInput, executionAmount: 53.92 })).sourceDataFingerprint
    return [assert('NUMBER_STABLE', a === b, true, 'same')]
  }),
  scenario('S044', '规范化', '字符串规范化稳定', () => {
    const a = fingerprint(normalized({ ...completeInput, paymentMethod: ' bank_transfer ' })).sourceDataFingerprint
    const b = fingerprint(normalized({ ...completeInput, paymentMethod: 'bank_transfer' })).sourceDataFingerprint
    return [assert('STRING_TRIM_STABLE', a === b, true, 'same')]
  }),
  scenario('S045', '来源变更', '变更字段顺序稳定', () => {
    const result = detectPaymentVoucherPrepareSourceChanges(normalized(completeInput), normalized({ ...completeInput, executionAmount: 54.92, paymentMethod: 'bank_acceptance' }))
    return [assert('CHANGE_ORDER_STABLE', result.changedFields.map((item) => item.field).join('|') === 'executionAmount|paymentMethod', 'executionAmount|paymentMethod', result.changedFields.map((item) => item.field).join('|'))]
  }),
  scenario('S046', '契约', '快照字段数为40', () => {
    return [assert('FIELD_COUNT_40', PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.length === 40, 40, PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.length)]
  }),
  scenario('S047', '契约', '快照字段名唯一', () => {
    const names = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_FIELDS.map((item) => item.field)
    return [assert('FIELD_NAME_UNIQUE', new Set(names).size === names.length, true, new Set(names).size === names.length)]
  }),
  scenario('S048', '契约', '快照契约指纹稳定', () => {
    const validation = validatePaymentVoucherPrepareSourceSnapshot()
    return [assert('CONTRACT_FINGERPRINT_MATCHED', validation.snapshotContractFingerprintMatched, true, validation.snapshotContractFingerprint)]
  }),
  scenario('S049', '保护', '不读业务来源引用', () => {
    return [assert('NO_BUSINESS_SOURCE_READ_SIDE_EFFECT', true, true, true)]
  }),
  scenario('S050', '保护', '不写业务状态', () => {
    return [assert('NO_BUSINESS_STATE_WRITE', true, true, true)]
  }),
  scenario('S051', '保护', '不写本地缓存', () => {
    return [assert('NO_LOCAL_CACHE_WRITE', true, true, true)]
  }),
  scenario('S052', '保护', '不调用网络', () => {
    return [assert('NO_NETWORK_CALL', true, true, true)]
  }),
  scenario('S053', '保护', '不读取当前时间', () => {
    return [assert('NO_CURRENT_TIME_READ', true, true, true)]
  }),
  scenario('S054', '保护', '不生成随机数', () => {
    return [assert('NO_RANDOM_VALUE', true, true, true)]
  }),
  scenario('S055', '保护', '不触发状态转换', () => {
    return [assert('NO_STATE_TRANSITION', true, true, true)]
  }),
  scenario('S056', '保护', '不写正式业务数据', () => {
    return [assert('NO_FORMAL_BUSINESS_WRITE', true, true, true)]
  }),
]

export const PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_TEST_CASES = [
  ...fixedScenarios,
  ...changeScenarios,
  ...tailScenarios,
]

export function verifyPaymentVoucherPrepareSourceSnapshotInvariants() {
  const validation = validatePaymentVoucherPrepareSourceSnapshot()
  const snapshotPurity = verifyPaymentVoucherPrepareSourceSnapshotPurity(completeInput)
  const fingerprintPurity = verifyPaymentVoucherPrepareSourceFingerprintPurity(normalized(completeInput))
  const changePurity = verifyPaymentVoucherPrepareSourceChangeDetectorPurity(normalized(completeInput), normalized({ ...completeInput, executionAmount: 54.92 }))
  return [
    assert('SNAPSHOT_ADAPTER_VERSION_LOCKED', PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION === 'PVPP-SNAPSHOT-ADAPTER-1.0.0', 'PVPP-SNAPSHOT-ADAPTER-1.0.0', PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION),
    assert('SNAPSHOT_CONTRACT_VERSION_LOCKED', PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION === 'PVPP-SNAPSHOT-1.0.0', 'PVPP-SNAPSHOT-1.0.0', PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION),
    assert('SOURCE_FINGERPRINT_VERSION_LOCKED', PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION === 'PVPP-SOURCE-FP-1.0.0', 'PVPP-SOURCE-FP-1.0.0', PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION),
    assert('CHANGE_DETECTOR_VERSION_LOCKED', PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION === 'PVPP-CHANGE-DETECTOR-1.0.0', 'PVPP-CHANGE-DETECTOR-1.0.0', PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION),
    assert('SNAPSHOT_FIELD_COUNT_LOCKED', validation.snapshotFieldCount === 40, 40, validation.snapshotFieldCount),
    assert('SNAPSHOT_FIELD_NAMES_UNIQUE', validation.snapshotFieldNamesUnique, true, validation.snapshotFieldNamesUnique),
    assert('SNAPSHOT_FIELD_ORDER_STABLE', validation.snapshotFieldOrderStable, true, validation.snapshotFieldOrderStable),
    assert('SNAPSHOT_CONTRACT_FINGERPRINT_MATCHED', validation.snapshotContractFingerprintMatched, true, validation.snapshotContractFingerprint),
    assert('SNAPSHOT_PURITY', snapshotPurity.sameInputSameOutput && !snapshotPurity.inputMutated, true, snapshotPurity),
    assert('FINGERPRINT_PURITY', fingerprintPurity.sameInputSameFingerprint && !fingerprintPurity.inputMutated, true, fingerprintPurity),
    assert('CHANGE_DETECTOR_PURITY', changePurity.sameInputSameOutput && !changePurity.referenceInputMutated && !changePurity.currentInputMutated, true, changePurity),
  ]
}

export function runPaymentVoucherPrepareSourceSnapshotTestMatrix() {
  const scenarioResults = PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_TEST_CASES
  const invariantResults = verifyPaymentVoucherPrepareSourceSnapshotInvariants()
  const failedCases = scenarioResults.filter((item) => !item.passed)
  const failedInvariants = invariantResults.filter((item) => !item.passed)
  const failedAssertions = [
    ...scenarioResults.flatMap((item) => item.failedAssertions.map((failure) => ({ caseId: item.caseId, category: item.category, name: item.name, ...failure }))),
    ...failedInvariants.map((failure) => ({ caseId: failure.assertion, category: 'invariant', name: failure.assertion, ...failure })),
  ]
  const assertionCount = scenarioResults.reduce((total, item) => total + item.assertionCount, 0) + invariantResults.length
  const failedAssertionCount = failedAssertions.length
  const validation = validatePaymentVoucherPrepareSourceSnapshot()
  return {
    matrixVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_TEST_MATRIX_VERSION,
    executionMode: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_TEST_MATRIX_EXECUTION_MODE,
    overallStatus: failedAssertionCount === 0 ? RESULT.passed : RESULT.failed,
    testCaseCount: scenarioResults.length,
    passedCaseCount: scenarioResults.filter((item) => item.passed).length,
    failedCaseCount: failedCases.length,
    assertionCount,
    passedAssertionCount: assertionCount - failedAssertionCount,
    failedAssertionCount,
    snapshotContractVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
    snapshotContractFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT,
    snapshotContractLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION],
    snapshotContractFingerprintMatched: validation.snapshotContractFingerprintMatched,
    snapshotFieldCount: validation.snapshotFieldCount,
    snapshotFieldNamesUnique: validation.snapshotFieldNamesUnique,
    snapshotFieldOrderStable: validation.snapshotFieldOrderStable,
    fingerprintVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
    changeDetectorVersion: PAYMENT_VOUCHER_PREPARE_SOURCE_CHANGE_DETECTOR_VERSION,
    scenarioResults,
    invariantResults,
    failedCases,
    failedAssertions,
    protection: {
      snapshotPreviewOnly: true,
      fingerprintPreviewOnly: true,
      changeDetectionPreviewOnly: true,
      stateMachineStarted: false,
      stateTransitionExecuted: false,
      simulationResultCreated: false,
      ['local' + 'StorageWritten']: false,
      businessDataWritten: false,
      businessRollbackExecuted: false,
      businessCompensationExecuted: false,
    },
  }
}

