import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '@playwright/test'
import { listPceBatchCapabilityContracts } from '../../src/meta/runtime/pceBatchCapabilityRegistry.js'

const VERSION = 'V1.14.2.8.4.7.31'
const root = process.cwd()
const evidenceRoot = path.join(root, 'test-results/pce-semantic-batch-capability')
const checkpointStorage = path.join(root, 'test-results/purchase-payment-golden-flow/checkpoints/qualified_inbound_completed/storage-state.json')

test.use({ storageState: checkpointStorage })

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

async function visibleButtonTexts(page) {
  return page.locator('button:visible').allTextContents().then((items) => items.map((item) => item.trim()).filter(Boolean))
}

async function actionState(page, sectionId, actionId) {
  const locator = page.locator(`[data-pce-section="${sectionId}"] [data-pce-action-id="${actionId}"]`)
  const count = await locator.count()
  const visibleCount = await locator.filter({ visible: true }).count().catch(async () => {
    let total = 0
    for (let index = 0; index < count; index += 1) total += Number(await locator.nth(index).isVisible().catch(() => false))
    return total
  })
  const button = locator.first()
  return {
    actionId,
    count,
    visibleCount,
    text: count ? (await button.textContent() || '').trim() : '',
    disabled: count ? await button.isDisabled().catch(() => false) : null,
    disabledReason: count ? await button.getAttribute('title') || '' : '',
  }
}

async function selectRows(page, tableId, targetCount) {
  const rows = page.locator(`[data-pce-scroll-for="${tableId}"] tbody tr`)
  let selected = 0
  for (let index = 0; index < await rows.count() && selected < targetCount; index += 1) {
    const checkbox = rows.nth(index).locator('.el-checkbox').first()
    if (!await checkbox.isVisible().catch(() => false)) continue
    if (await checkbox.locator('input').isDisabled().catch(() => false)) continue
    await checkbox.click()
    selected += 1
  }
  return selected
}

for (const contract of listPceBatchCapabilityContracts({ includeInternal: false })) {
  test(`${contract.pageId} semantic batch capability`, async ({ page }) => {
    await page.goto(`/#${contract.route}`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})

    const section = page.locator(`[data-pce-section="${contract.sectionId}"]`)
    const sectionCount = await section.count()
    const actionStatesAtZero = []
    for (const actionId of contract.actionIds) actionStatesAtZero.push(await actionState(page, contract.sectionId, actionId))

    const allActionNodes = page.locator('[data-pce-action-id]')
    const discoveredBatchActionIds = sectionCount
      ? [...new Set((await section.locator('[data-pce-action-id]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-pce-action-id')))).filter(Boolean))]
      : []
    const missingActionIds = contract.actionIds.filter((actionId) => !discoveredBatchActionIds.includes(actionId))
    const extraActionIds = discoveredBatchActionIds.filter((actionId) => !contract.actionIds.includes(actionId))
    const duplicateActionIds = contract.actionIds.filter((actionId) => actionStatesAtZero.find((item) => item.actionId === actionId)?.count !== 1)
    const hiddenDuplicateActionIds = contract.actionIds.filter((actionId) => {
      const state = actionStatesAtZero.find((item) => item.actionId === actionId)
      return state && state.count > state.visibleCount
    })

    const selectionStates = [{ selectedCount: 0, actions: actionStatesAtZero }]
    if (contract.actionIds.length && await page.locator(`[data-pce-scroll-for="${contract.tableId}"]`).count()) {
      const selectedOne = await selectRows(page, contract.tableId, 1)
      if (selectedOne) {
        selectionStates.push({
          selectedCount: selectedOne,
          actions: await Promise.all(contract.actionIds.map((actionId) => actionState(page, contract.sectionId, actionId))),
        })
      }
      const clearSelection = section.getByRole('button', { name: '清空选择', exact: true })
      if (await clearSelection.count()) await clearSelection.click()
      const selectedMany = await selectRows(page, contract.tableId, 2)
      if (selectedMany > 1) {
        selectionStates.push({
          selectedCount: selectedMany,
          actions: await Promise.all(contract.actionIds.map((actionId) => actionState(page, contract.sectionId, actionId))),
        })
      }
      if (await clearSelection.count()) await clearSelection.click()
    }

    const nonBatchControlsExcluded = (await visibleButtonTexts(page)).filter((text) =>
      ['搜索', '展开高级筛选', '收起高级筛选', '清空筛选', '清除排序', '导出当前结果', '清空选择'].includes(text),
    )
    const disabledActionIds = actionStatesAtZero
      .filter((item) => item.disabled)
      .map((item) => ({ actionId: item.actionId, reason: item.disabledReason }))
    const pageActionIds = await allActionNodes.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-pce-action-id')).filter(Boolean))
    const expectedSectionCount = contract.actionIds.length ? 1 : 0
    const result = sectionCount === expectedSectionCount
      && missingActionIds.length === 0
      && extraActionIds.length === 0
      && duplicateActionIds.length === 0
      && hiddenDuplicateActionIds.length === 0

    const evidence = {
      version: VERSION,
      canonicalName: contract.canonicalName,
      fullUrl: `http://localhost:5173/#${contract.route}`,
      pageId: contract.pageId,
      component: contract.pageComponent,
      tableId: contract.tableId,
      sectionId: contract.sectionId,
      sectionCount,
      discoveredBatchActionIds,
      baselineBatchActionIds: contract.actionIds,
      missingActionIds,
      extraActionIds,
      duplicateActionIds,
      hiddenDuplicateActionIds,
      nonBatchControlsExcluded,
      disabledActionIds,
      semanticActionCount: discoveredBatchActionIds.length,
      selectionStates,
      pageActionIds,
      currentDomButtonTexts: await visibleButtonTexts(page),
      userBusinessDataModified: false,
      result: result ? 'passed' : 'failed',
    }
    writeJson(path.join(evidenceRoot, `${contract.pageId}.json`), evidence)
    expect(result, JSON.stringify(evidence, null, 2)).toBe(true)
  })
}
