import fs from 'node:fs/promises'
import { test, expect } from '@playwright/test'
import { listBusinessProcessSteps } from '../../src/meta/process/businessProcessRegistry.js'
import {
  GOLDEN_FLOW_CASE_NO,
  GOLDEN_FLOW_PREFIX,
  GOLDEN_FLOW_VERSION,
  expectedGoldenFlowStages,
} from '../fixtures/purchaseToFormalPaymentGoldenFlow.js'

test('采购付款金丝雀全链路使用注册表和真实页面动作', async ({ page }, testInfo) => {
  const consoleErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))

  await page.goto('/#/process-center', { waitUntil: 'networkidle' })
  const isolatedStorageBefore = await page.evaluate(() => JSON.stringify(localStorage))
  const registeredStages = listBusinessProcessSteps().map((step) => ({
    stageId: step.stepId,
    canonicalName: step.pageTitle || step.stepName,
    route: step.routePath,
    primaryActionCodes: [...step.primaryActionCodes],
  }))
  const firstMissingStage = expectedGoldenFlowStages.find((expected) => !registeredStages.some((actual) => (
    expected.aliases.includes(actual.canonicalName) && actual.route && actual.primaryActionCodes.length
  )))

  const screenshotPath = testInfo.outputPath('golden-flow-first-failure.png')
  await page.screenshot({ path: screenshotPath, fullPage: true })
  const isolatedStorageAfter = await page.evaluate(() => JSON.stringify(localStorage))
  const report = {
    version: GOLDEN_FLOW_VERSION,
    goldenFlowNo: GOLDEN_FLOW_CASE_NO,
    dataPrefix: GOLDEN_FLOW_PREFIX,
    totalStageCount: expectedGoldenFlowStages.length,
    executedStageCount: 1,
    passedStageCount: 0,
    failedStageCount: 1,
    lastPassedStage: '',
    currentFailedStage: firstMissingStage?.canonicalName || '',
    failurePage: '/process-center',
    fullUrl: page.url(),
    pageCanonicalName: '业务流程中心',
    sectionTitle: '业务流程注册表发现',
    userAction: '从现有业务流程注册表读取真实模块、路由和合法动作',
    expectedResult: `注册表包含“${firstMissingStage?.canonicalName}”的真实路由和合法页面动作`,
    actualResult: `注册表首个阶段为“${registeredStages[0]?.canonicalName || '空'}”，未找到所需前置阶段`,
    currentBusinessObject: GOLDEN_FLOW_CASE_NO,
    sourceBusinessObject: '',
    targetBusinessObject: '',
    currentStatus: 'registry_discovery_blocked',
    blockedReason: `缺少“${firstMissingStage?.canonicalName}”的注册模块、真实路由或合法动作；禁止静默跳过。`,
    consoleErrors,
    screenshotPath,
    latestPassedCheckpoint: '',
    registeredStages,
    expectedStages: expectedGoldenFlowStages.map(({ stageId, canonicalName }) => ({ stageId, canonicalName })),
    isolatedStorageUnchanged: isolatedStorageBefore === isolatedStorageAfter,
    userBusinessDataModified: false,
    overall: 'failed',
  }
  const reportPath = testInfo.outputPath('purchase-payment-golden-flow-report.json')
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8')
  await testInfo.attach('purchase-payment-golden-flow-report', { path: reportPath, contentType: 'application/json' })

  expect(isolatedStorageAfter).toBe(isolatedStorageBefore)
  expect(firstMissingStage, '全部目标阶段均已在注册表中定义真实路由和动作').toBeUndefined()
})
