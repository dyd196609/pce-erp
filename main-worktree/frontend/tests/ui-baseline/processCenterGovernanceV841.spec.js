import { expect, test } from '@playwright/test'

test('V841 业务流程中心只展示企业流程体系并可导航付款申请', async ({ page }) => {
  await page.goto('/#/process-center')
  const catalog = page.locator('[data-acceptance-id="business-process-center-v1"]')
  await expect(catalog).toBeVisible()
  await expect(catalog).toContainText('SCM供应链管理中心')
  await expect(catalog).toContainText('采购业务流程')

  const process = page.locator('[data-acceptance-id="scm-purchase-settlement-process"]')
  const expectedOrder = [
    '采购申请', '询价', '核价', '采购订单', '收货', '质量检验', '入库',
    '供应商对账', '差异分析', '供应商确认', '应付确认', '付款申请',
    '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效',
  ]
  const actualOrder = await process.locator('[data-process-node] strong').allTextContents()
  expect(actualOrder.map(value => value.trim())).toEqual(expectedOrder)
  await expect(process.locator('[data-process-node]')).toHaveCount(16)
  await expect(process.locator('[data-process-node][data-page-url]')).toHaveCount(16)

  const centerLabels = (await page.locator('button:visible').allTextContents()).map(value => value.trim())
  for (const forbidden of ['新建流程', '编辑流程', '执行流程', '停用']) {
    expect(centerLabels).not.toContain(forbidden)
  }

  await process.locator('[data-process-node="supplier-payment-request"]').click()
  await expect(page).toHaveURL(/#\/scm\/supplier-payment-requests$/)
})

test('V841 流程设计中心承接全部管理动作', async ({ page }) => {
  await page.goto('/#/process-designer')
  await expect(page.locator('main.process-designer-page h1')).toHaveText('流程设计中心')
  await expect(page.getByRole('button', { name: '新建流程' })).toBeVisible()
  const firstCard = page.locator('.process-card').first()
  await expect(firstCard.getByRole('button', { name: '查看' })).toBeVisible()
  await expect(firstCard.getByRole('button', { name: '编辑' })).toBeVisible()
  await expect(firstCard.getByRole('button', { name: '执行' })).toBeVisible()
  await expect(firstCard.getByRole('button', { name: /停用|启用/ })).toBeVisible()

  await firstCard.getByRole('button', { name: '查看' }).click()
  await expect(page.locator('[data-acceptance-id="pce-business-detail-card"]')).toBeVisible()
  await expect(page.locator('body')).not.toContainText('technicalState')
  await expect(page.locator('body')).not.toContainText('sourceObjectRefs')
})
