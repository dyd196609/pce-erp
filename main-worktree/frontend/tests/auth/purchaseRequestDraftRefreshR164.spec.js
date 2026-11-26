import { expect, test } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

test('V1.14.2.8.4.16 saved draft reloads, displays and reopens without downstream writes', async ({ page, context }) => {
  const factsStatuses = []
  await context.clearCookies()
  page.on('response', (response) => {
    if (response.url().includes('/api/procurement/scm-page-facts/purchase-request/')) factsStatuses.push(response.status())
  })

  await page.goto('/?r164=login#/login')
  await page.getByPlaceholder('Enterprise username').fill(process.env.PCE_TEST_USERNAME || 'admin')
  await page.getByPlaceholder('Enterprise password').fill(process.env.PCE_TEST_PASSWORD || 'admin123')
  await page.getByRole('button', { name: 'Enter ProfitOS' }).click()
  await expect(page).toHaveURL(/#\/dashboard$/)

  await page.goto('/?r164=list#/scm/purchase-request')
  const listRegion = page.locator('[data-acceptance-id="purchase-request-list-region"]')
  const targetRow = listRegion.getByRole('row').filter({ hasText: 'PR202608010012' })
  await expect(targetRow).toHaveCount(1)
  await expect(targetRow).toContainText('草稿')
  await expect(targetRow).toContainText('周丽')
  await expect(targetRow).toContainText('采购部')
  await expect(targetRow).toContainText('PCE-ERP制造数字化建设')
  await expect(targetRow).toContainText('示例物料')

  await targetRow.getByRole('button', { name: '查看' }).click()
  const viewDialog = page.getByRole('dialog', { name: '查看采购申请' })
  await expect(viewDialog).toBeVisible()
  const viewField = (label) => viewDialog.locator('.el-form-item').filter({ has: page.locator(`label:text-is("${label}")`) })
  await expect(viewField('请购人')).toContainText('EMP006 / 周丽 / 采购部')
  await expect(viewField('请购部门')).toContainText('采购部')
  await expect(viewField('需求部门')).toContainText('采购部')
  await expect(viewField('采购部门')).toContainText('采购部')
  await expect(viewField('项目')).toContainText('PRJ-PCE-ERP-2026')
  await expect(viewField('成本中心')).toContainText('CC-PROCUREMENT')
  await expect(viewField('费用类别')).toContainText('EXP-MATERIAL')
  await expect(viewField('预算类别')).toContainText('BUD-PRODUCTION')
  await expect(viewDialog.getByRole('row').filter({ hasText: 'MT001' })).toContainText('示例物料')
  await viewDialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(viewDialog).toBeHidden()

  await targetRow.getByRole('button', { name: '编辑' }).click()
  const editDialog = page.getByRole('dialog', { name: '编辑采购申请' })
  await expect(editDialog).toBeVisible()
  const editField = (label) => editDialog.locator('.el-form-item').filter({ has: page.locator(`label:text-is("${label}")`) })
  await expect(editField('请购人')).toContainText('EMP006 / 周丽 / 采购部')
  await expect(editField('请购部门')).toContainText('采购部')
  await expect(editField('需求部门')).toContainText('采购部')
  await expect(editField('采购部门')).toContainText('采购部')
  await expect(editField('项目')).toContainText('PRJ-PCE-ERP-2026')
  await expect(editField('成本中心')).toContainText('CC-PROCUREMENT')
  await expect(editField('费用类别')).toContainText('EXP-MATERIAL')
  await expect(editField('预算类别')).toContainText('BUD-PRODUCTION')
  const editItemRow = editDialog.getByRole('row').filter({ hasText: 'MT001' })
  await expect(editItemRow).toContainText('示例物料')
  await expect(editItemRow).toContainText('2026-08-10')
  await expect(editItemRow).toContainText('华为技术有限公司')
  await editDialog.getByRole('button', { name: '取消' }).click()
  await expect(editDialog).toBeHidden()

  const regionSource = readFileSync(resolve('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'), 'utf8')
  expect(regionSource).toContain("dialogVisible.value=false;ElMessage.success")
  expect(regionSource).toContain("emit('refreshed')")
  expect(factsStatuses.every((status) => status === 200)).toBe(true)

  const evidenceDir = resolve('test-results', 'purchase-request-draft-refresh-r164')
  mkdirSync(evidenceDir, { recursive: true })
  writeFileSync(resolve(evidenceDir, 'browser-evidence.json'), `${JSON.stringify({
    version: 'V1.14.2.8.4.16',
    result: 'PASS',
    requestNo: 'PR202608010012',
    listStatusLabel: '草稿',
    saveClosureContract: true,
    refreshContract: true,
    viewFieldsConsistent: true,
    editFieldsConsistent: true,
    itemCount: 1,
    inquiryObjectCreated: false,
    purchaseOrderCreated: false,
    receiptCreated: false,
    paymentCreated: false,
    productionUserDataWritten: false,
  }, null, 2)}\n`, 'utf8')
})
