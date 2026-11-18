import { expect, test } from '@playwright/test'
import { loadProcessCenterRuntimeModel } from '../src/meta/runtime/processCenterRuntime.js'

const model = loadProcessCenterRuntimeModel()

test('真实目录中的每个模块只显示自己的唯一正式流程或明确空态', async ({ page }) => {
  const writes = []
  page.on('request', request => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) writes.push(`${request.method()} ${request.url()}`)
  })
  await page.goto('/#/process-center?module=SCM')
  const navigation = page.locator('[data-acceptance-id="business-module-navigation"]')
  await expect(navigation.locator('[data-process-module]')).toHaveCount(model.modules.length)
  for (const module of model.modules) {
    await navigation.locator(`[data-process-module="${module.moduleCode}"]`).click()
    await expect(navigation.locator(`[data-process-module="${module.moduleCode}"]`)).toHaveClass(/active/)
    const process = model.processes.find(item => item.moduleCode === module.moduleCode)
    if (process) {
      const rendered = page.locator('[data-acceptance-id="selected-module-formal-process"]')
      await expect(rendered).toHaveCount(1)
      await expect(rendered).toHaveAttribute('data-process-module', module.moduleCode)
      await expect(rendered).toHaveAttribute('data-process-code', process.processCode)
      await expect(rendered).toHaveAttribute('data-formal-root-count', '1')
      await expect(rendered.locator('[data-process-node]')).toHaveCount(process.nodes.length)
    } else {
      const empty = page.locator('[data-acceptance-id="module-formal-process-empty"]')
      await expect(empty).toHaveCount(1)
      await expect(empty).toContainText('本模块尚未配置正式运作流程')
    }
  }
  expect(writes).toEqual([])
})

test('PDE直接显示正式流程并保留工作台能力与物料核算入口', async ({ page }) => {
  await page.goto('/#/process-center?module=PDE')
  const process = page.locator('[data-acceptance-id="selected-module-formal-process"]')
  const pde = model.processes.find(item => item.processCode === 'PDE_PRODUCT_ENGINEERING')
  await expect(process).toHaveAttribute('data-process-code', 'PDE_PRODUCT_ENGINEERING')
  await expect(process.locator('[data-process-node]')).toHaveCount(pde.nodes.length)
  await expect(page.locator('[data-acceptance-id="pde-workbench-primary-entry"]')).toHaveCount(0)
  await expect(page.locator('[data-acceptance-id="process-center-page-navigation"]')).toHaveCount(0)
  for (const nodeCode of ['engineering-readiness-control', 'bom-management', 'routing-management', 'engineering-material-calculation']) {
    await expect(process.locator(`[data-process-node="${nodeCode}"]`)).toBeVisible()
  }
  const calculation = process.locator('[data-process-node="engineering-material-calculation"]')
  const renderedNodeCodes = await process.locator('[data-process-node]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-process-node')))
  const calculationIndex = renderedNodeCodes.indexOf('engineering-material-calculation')
  expect(renderedNodeCodes.filter(nodeCode => nodeCode === 'engineering-material-calculation')).toHaveLength(1)
  expect(renderedNodeCodes[calculationIndex - 1]).toBe('product-version-management')
  expect(renderedNodeCodes[calculationIndex + 1]).toBe('bom-management')
  await page.evaluate(() => {
    window.__singleFormalFlowOpenedUrl = ''
    window.open = (url) => {
      window.__singleFormalFlowOpenedUrl = String(url)
      return { opener: null }
    }
  })
  await calculation.locator('[data-process-node-action="new-tab"]').click()
  await expect.poll(() => page.evaluate(() => window.__singleFormalFlowOpenedUrl)).toContain('#/pde/engineering-calculations')
  await calculation.locator('.process-node-summary').click()
  await expect(page).toHaveURL(/#\/pde\/engineering-calculations$/)
})

test('切换、刷新、前进后退和旧链接都保持模块与正式流程一致', async ({ page }) => {
  await page.goto('/#/process-center?module=SCM')
  const moduleButton = code => page.locator(`[data-acceptance-id="business-module-navigation"] [data-process-module="${code}"]`)
  await moduleButton('PDE').click()
  await expect(page).toHaveURL(/module=PDE/)
  await expect(page.locator('[data-process-code="PDE_PRODUCT_ENGINEERING"]')).toBeVisible()
  await page.reload()
  await expect(moduleButton('PDE')).toHaveClass(/active/)
  await moduleButton('WMS').click()
  await expect(page.locator('[data-process-code="WMS_WAREHOUSE_OPERATION"]')).toBeVisible()
  await page.goBack()
  await expect(moduleButton('PDE')).toHaveClass(/active/)
  await page.goForward()
  await expect(moduleButton('WMS')).toHaveClass(/active/)
  await page.goto('/#/pde/workbench?orderId=ORDER-001')
  await expect(page).toHaveURL(/#\/process-center\?(?=.*module=PDE)(?=.*orderId=ORDER-001)/)
  await expect(page.locator('[data-process-code="PDE_PRODUCT_ENGINEERING"]')).toBeVisible()
})
