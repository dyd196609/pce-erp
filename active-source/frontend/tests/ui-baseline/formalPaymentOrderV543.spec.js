import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

import { assertStatusTransitionCountMatchesHistory } from '../../src/meta/runtime/pceStateMachineFactContract.js'

const VERSION = 'V1.14.2.8.4.7.54.3'
const FULL_URL = 'http://localhost:5173/#/finance/formal-payment-orders'
const API_URL = 'http://localhost:8000/api/finance/formal-payment-orders/'
const resultRoot = path.resolve('test-results', 'formal-payment-order-v543')
const screenshotRoot = path.join(resultRoot, 'screenshots')
const database = path.resolve(
  '..',
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}

test('V54.3 transition count is identical across API, page, diagnostic and strictFacts', async ({ page, context }) => {
  fs.mkdirSync(screenshotRoot, { recursive: true })
  await context.grantPermissions(
    ['clipboard-read', 'clipboard-write'],
    { origin: 'http://127.0.0.1:5173' },
  )
  expect(() => assertStatusTransitionCountMatchesHistory({
    statusTransitionHistory: [{}, {}, {}],
    statusTransitionCount: 0,
  }, 'playwright-mismatch-probe')).toThrow()

  const databaseHashBefore = sha256(database)
  const response = await page.request.get(API_URL)
  expect(response.ok(), 'E-FPO543-API-001').toBeTruthy()
  const envelope = await response.json()
  expect(envelope.version).toBe(VERSION)
  expect(envelope.currentStateSource).toBe('server')
  expect(envelope.data.results).toHaveLength(8)
  for (const row of envelope.data.results) {
    expect(row.status).toBe('frozen_for_execution')
    expect(row.statusTransitionHistory).toHaveLength(3)
    expect(row.statusTransitionCount).toBe(
      row.statusTransitionHistory.length,
    )
    expect(row.statusTransitionCount).toBe(3)
    expect(row.stateMachineConsistent).toBe(true)
    expect(row.executionGateFacts.statusTransitionCount).toBe(
      row.executionGateFacts.statusTransitionHistory.length,
    )
    expect(row.executionGateFacts.statusTransitionHistory).toEqual(
      row.statusTransitionHistory,
    )
    expect(
      Object.values(row.downstreamCounts).every(value => value === 0),
    ).toBe(true)
  }

  const writes = []
  page.on('request', request => {
    if (request.url().includes('/api/finance/') && request.method() !== 'GET') {
      writes.push(`${request.method()} ${request.url()}`)
    }
  })
  await page.goto('/#/finance/formal-payment-orders')
  await expect(
    page.locator('[data-version-classification="runtimeBusinessVersion"]'),
  ).toContainText(VERSION)
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')
  await expect(
    page.locator(
      '[data-acceptance-id="formal-payment-order-approval-status"]',
    ),
  ).toContainText('3')

  const copyButton = page.locator(
    '[data-acceptance-id="page-observability-action-bar"] '
    + '[data-acceptance-id="copy-diagnostic-data-button"]',
  )
  await expect(copyButton).toHaveCount(1)
  await copyButton.click()
  const diagnostic = JSON.parse(
    await page.evaluate(() => navigator.clipboard.readText()),
  )
  const apiFacts = envelope.data.results[0]
  const surfaces = [
    {
      name: 'api',
      history: apiFacts.statusTransitionHistory,
      count: apiFacts.statusTransitionCount,
    },
    {
      name: 'page',
      history: diagnostic.statusTransitionHistory,
      count: diagnostic.statusTransitionCount,
    },
    {
      name: 'diagnostic-current-object',
      history: diagnostic.currentObject.statusTransitionHistory,
      count: diagnostic.currentObject.statusTransitionCount,
    },
    {
      name: 'strictFacts',
      history: diagnostic.strictServerFacts.statusTransitionHistory,
      count: diagnostic.strictServerFacts.statusTransitionCount,
    },
  ]
  for (const surface of surfaces) {
    expect(surface.history, surface.name).toEqual(
      apiFacts.statusTransitionHistory,
    )
    expect(surface.count, surface.name).toBe(surface.history.length)
    expect(surface.count, surface.name).toBe(3)
  }
  expect(diagnostic.stateMachineConsistent).toBe(true)
  expect(diagnostic.strictServerFacts.stateMachineConsistent).toBe(true)
  expect(writes).toHaveLength(0)

  await page.screenshot({
    path: path.join(screenshotRoot, 'transition-count-consistent.png'),
    fullPage: true,
  })
  await page.reload()
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await expect(
    page.locator('[data-acceptance-id="strict-server-row-count"]'),
  ).toHaveText('8')

  const databaseHashAfter = sha256(database)
  expect(databaseHashAfter).toBe(databaseHashBefore)
  const common = {
    result: 'passed',
    version: VERSION,
    fullUrl: FULL_URL,
    canonicalName: '正式付款单',
    currentStateSource: 'server',
    databaseHashBefore,
    databaseHashAfter,
    databaseUnchanged: true,
    businessWriteRequestCount: 0,
  }
  const assertions = [
    {
      evidenceId: 'E-FPO543-PAGE-001',
      fullUrl: FULL_URL,
      regionTitle: '审批状态',
      relativePosition: '正式付款单对象之后',
      fieldName: '状态转换记录',
      expected: 3,
      actual: diagnostic.statusTransitionCount,
      ctrlF: '状态转换记录',
      passed: diagnostic.statusTransitionCount === 3,
    },
    {
      evidenceId: 'E-FPO543-PAGE-002',
      fullUrl: FULL_URL,
      regionTitle: '复制诊断数据',
      relativePosition: '页面顶部公共动作栏',
      fieldName: 'statusTransitionCount',
      expected: '等于 statusTransitionHistory.length',
      actual: `${diagnostic.statusTransitionCount}/${diagnostic.statusTransitionHistory.length}`,
      ctrlF: '复制诊断数据',
      passed: diagnostic.statusTransitionCount
        === diagnostic.statusTransitionHistory.length,
    },
    {
      evidenceId: 'E-FPO543-PAGE-003',
      fullUrl: FULL_URL,
      regionTitle: 'strictFacts',
      relativePosition: '标准列表服务端事实区域',
      fieldName: 'statusTransitionCount',
      expected: 3,
      actual: diagnostic.strictServerFacts.statusTransitionCount,
      ctrlF: '服务端持久事实',
      passed: diagnostic.strictServerFacts.statusTransitionCount === 3,
    },
    {
      evidenceId: 'E-FPO543-PAGE-004',
      fullUrl: FULL_URL,
      regionTitle: '审批状态',
      relativePosition: '状态转换记录之后',
      fieldName: 'stateMachineConsistent',
      expected: true,
      actual: diagnostic.stateMachineConsistent,
      ctrlF: '状态机一致',
      passed: diagnostic.stateMachineConsistent === true,
    },
    {
      evidenceId: 'E-FPO543-PAGE-005',
      fullUrl: FULL_URL,
      regionTitle: '下游零对象保护',
      relativePosition: '页面最底部',
      fieldName: '银行任务及付款执行',
      expected: 0,
      actual: Math.max(...Object.values(envelope.data.downstreamCounts)),
      ctrlF: '下游零对象保护',
      passed: Object.values(envelope.data.downstreamCounts)
        .every(value => value === 0),
    },
  ]
  expect(assertions.every(row => row.passed)).toBe(true)
  writeJson('page-assertions.json', { ...common, assertions })
  writeJson('fact-consistency-report.json', {
    ...common,
    surfaces: Object.fromEntries(
      surfaces.map(surface => [surface.name, {
        statusTransitionHistory: surface.history,
        statusTransitionCount: surface.count,
        historyLength: surface.history.length,
        countMatchesHistory: surface.count === surface.history.length,
      }]),
    ),
    stateMachineConsistent: true,
    statusTransitionCountMatchesHistory: true,
  })
})
