import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
  PCE_PAGE_ACCEPTANCE_RULES,
  createPageAcceptanceReport,
  runPageAcceptanceRules,
} from '../../src/meta/acceptance/pageAcceptanceContract.js'

const passingEvidence = {
  page: {
    opened: true,
    url: 'http://localhost:5173/#/finance/example',
    title: '示例页面',
    expectedTitle: '示例页面',
    version: 'V1',
    moduleCode: 'FIN_EXAMPLE',
    expectedModuleCode: 'FIN_EXAMPLE',
    consoleErrors: [],
    resourceFailures: [],
  },
  list: {
    search: true,
    advancedFilter: true,
    filterFieldCount: 7,
    sort: true,
    export: true,
    selection: true,
    fixedLeft: ['selection', 'index', 'primaryNo'],
    fixedRight: ['operation'],
    horizontalScroll: true,
    fixedPositionsStable: true,
    fixedPositionMaxDelta: 0,
  },
  status: {
    visibleText: '发送前待分发',
    expectedLabel: '发送前待分发',
    technicalStatuses: ['ready_to_dispatch'],
    source: 'server',
  },
  facts: {
    apiCount: 8,
    pageCount: 8,
    diagnosticCount: 8,
    strictCount: 8,
    statusValues: ['发送前待分发', '发送前待分发', '发送前待分发', '发送前待分发'],
    source: 'server',
    readFailureTested: true,
    readFailureStatus: 'read_failed',
    readFailureCount: null,
  },
  actions: {
    registrySource: true,
    buttonTexts: ['查看详情', '查看来源对象'],
    viewActionCount: 2,
  },
  security: {
    businessProgressWriteCount: 0,
    bankSendExecutionWriteCount: 0,
    paymentExecutionCount: 0,
    fundDeductionCount: 0,
    bankTransactionCount: 0,
  },
  acceptanceFacts: {
    pageCode: 'FIN_EXAMPLE',
    factSource: 'server',
    recordCount: 8,
    selectedCount: 0,
    actionCount: 2,
    dangerActionCount: 0,
    businessProgressWriteCount: 0,
    downstreamObjectCount: 0,
  },
  filter: {
    fields: [
      { field: 'supplierName', filterType: 'select', actualControl: 'select', optionsProvider: 'server', optionCount: 2 },
      { field: 'period', filterType: 'daterange', actualControl: 'daterange', optionCount: 0 },
    ],
    apiParamsCorrect: true,
    apiParams: { supplierName: '供应商甲', periodFrom: '2026-01-01', periodTo: '2026-01-31' },
  },
}

test('验收契约版本固定为V2.0', () => {
  assert.equal(PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION, 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0')
})

for (const rule of PCE_PAGE_ACCEPTANCE_RULES) {
  test(`${rule.id} ${rule.name}`, () => {
    const result = rule.evaluate(passingEvidence)
    assert.equal(result.result, 'PASS')
  })
}

test('统一报告准确汇总PASS/FAIL/UNKNOWN', () => {
  const checks = runPageAcceptanceRules(passingEvidence)
  const report = createPageAcceptanceReport('/finance/example', checks)
  assert.equal(report.totalChecks, 42)
  assert.equal(report.pass, 42)
  assert.equal(report.fail, 0)
  assert.equal(report.unknown, 0)
})
