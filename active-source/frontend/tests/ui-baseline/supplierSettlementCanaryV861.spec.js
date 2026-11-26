import { expect, test } from '@playwright/test'

const expectedNodes = [
  ['purchase-request', '采购申请'],
  ['request-for-quotation', '询价'],
  ['price-verification', '核价'],
  ['purchase-order', '采购订单'],
  ['goods-receipt', '收货'],
  ['quality-inspection', '质量检验'],
  ['warehouse-receipt', '入库'],
  ['supplier-reconciliation', '供应商对账'],
  ['reconciliation-difference', '差异分析'],
  ['supplier-confirmation', '供应商确认'],
  ['supplier-payable-confirmation', '应付确认'],
  ['supplier-payment-request', '付款申请'],
  ['payment-status-record', '付款状态记录'],
  ['supplier-settlement-completion', '供应商结算完成'],
  ['supplier-performance', '供应商绩效'],
  ['buyer-performance', '采购员绩效'],
]

test('V861业务流程中心展示完整SCM供应商结算16节点', async ({ page }) => {
  await page.goto('/#/process-center')

  const process = page.locator('[data-acceptance-id="scm-purchase-settlement-process"]')
  await expect(process.getByText('SCM采购与供应商结算流程', { exact: true })).toBeVisible()

  const nodes = process.locator('[data-process-node]')
  await expect(nodes).toHaveCount(16)
  const actualNodes = await nodes.evaluateAll(elements => elements.map(element => ({
    nodeCode: element.getAttribute('data-process-node'),
    nodeName: element.querySelector('strong')?.textContent?.trim(),
    pageUrl: element.getAttribute('data-page-url'),
  })))

  expect(actualNodes.map(node => [node.nodeCode, node.nodeName])).toEqual(expectedNodes)
  expect(actualNodes.every(node => Boolean(node.pageUrl))).toBe(true)
})
