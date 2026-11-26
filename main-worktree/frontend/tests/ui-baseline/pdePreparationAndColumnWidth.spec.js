import { expect, test } from '@playwright/test'
import path from 'node:path'


const TEST_PASSWORD = 'Pce-Isolated-Column-2026!'
const EVIDENCE_DIR = path.resolve(process.cwd(), '../docs/evidence/pde-formal-preparation-column-width-20260917')
const RUNTIME_CHAIN_EVIDENCE_DIR = path.resolve(process.cwd(), '../docs/evidence/pde-real-runtime-chain-fix-20260917')
const AUTO_RESPONSIBILITY_EVIDENCE_DIR = path.resolve(process.cwd(), '../docs/evidence/pde-auto-responsibility-20260917')

async function login(page, username) {
  await page.goto('/#/system-login?redirect=%2Fprocess-center%3Fmodule%3DPDE')
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(TEST_PASSWORD)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/process-center\?module=PDE/)
}

async function logoutByClearingBrowserSession(page) {
  await page.context().clearCookies()
  await page.evaluate(() => localStorage.clear())
}

async function openPdeFromProcessCenter(page) {
  await page.goto('/#/process-center?module=PDE')
  const node = page.getByText('生产可行性评审', { exact: true }).last()
  await expect(node).toBeVisible()
  await node.click()
  await expect(page).toHaveURL(/#\/pde\/product-requirement-reviews/)
  await expect(page.getByRole('main').getByRole('heading', { name: '生产可行性评审' })).toBeVisible()
}

async function dragHeader(page, table, label, delta, useLast = false) {
  if (!useLast) {
    await table.locator('.el-scrollbar__wrap').evaluateAll(nodes => {
      const owner = nodes.find(node => node.scrollWidth > node.clientWidth)
      if (owner) {
        owner.scrollLeft = 320
        owner.dispatchEvent(new Event('scroll', { bubbles: true }))
      }
    })
    await page.waitForTimeout(120)
  }
  const headers = table.locator('th').filter({ hasText: label })
  const header = useLast ? headers.last() : headers.first()
  await header.scrollIntoViewIfNeeded()
  if (!useLast) {
    await table.evaluate((root, targetLabel) => {
      const header = [...root.querySelectorAll('th')].find(node => node.innerText.includes(targetLabel) && !node.classList.contains('el-table-fixed-column--right'))
      const overlay = root.querySelector('th.el-table-fixed-column--right')
      const owner = [...root.querySelectorAll('.el-scrollbar__wrap')].find(node => node.scrollWidth > node.clientWidth)
      if (!header || !overlay || !owner) return
      const overlap = header.getBoundingClientRect().right - overlay.getBoundingClientRect().left
      if (overlap > -20) {
        owner.scrollLeft += overlap + 40
        owner.dispatchEvent(new Event('scroll', { bubbles: true }))
      }
    }, label)
    await page.waitForTimeout(120)
  }
  const initialWidth = await header.evaluate(node => node.getBoundingClientRect().width)
  const box = await header.boundingBox()
  const pointProbe = await page.evaluate(({ x, y }) => {
    const node = document.elementFromPoint(x, y)
    const th = node?.closest?.('th')
    return { tag: node?.tagName, text: th?.innerText, className: th?.className, rect: th ? { x: th.getBoundingClientRect().x, width: th.getBoundingClientRect().width } : null }
  }, { x: box.x + box.width - 3, y: box.y + box.height / 2 })
  let cursor = ''
  for (const offset of [2, 3, 4, 5, 6, 7]) {
    await page.mouse.move(box.x + box.width - offset, box.y + box.height / 2)
    cursor = await page.evaluate(() => document.body.style.cursor)
    if (cursor === 'col-resize') break
  }
  console.log('drag-header-probe', { label, initialWidth, box, cursor, pointProbe })
  expect(cursor).toBe('col-resize')
  await page.mouse.down()
  await page.mouse.move(box.x + box.width + delta, box.y + box.height / 2, { steps: 8 })
  await page.mouse.up()
  const finalWidth = await header.evaluate(node => node.getBoundingClientRect().width)
  return { header, initialWidth, finalWidth }
}

test('pce_emp104 normal process entry shows preparation state before a formal PDE review exists', async ({ page }) => {
  test.setTimeout(45_000)
  await login(page, 'pce_emp104')
  await openPdeFromProcessCenter(page)

  await expect(page.getByText('尚未建立正式评审／待准备人员保存', { exact: false })).toBeVisible()
  await expect(page.getByText('当前身份没有查看资格', { exact: true })).toHaveCount(0)
  await expect(page.getByText('VIEW_PERMISSION_DENIED', { exact: true })).toHaveCount(0)
  await expect(page.locator('[data-pce-column-width-table="order-review-fixed-items"] .el-table__body-wrapper tbody tr')).toHaveCount(9)
  await expect(page.getByRole('button', { name: '保存草稿', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '签认本人已完成项目', exact: true })).toBeDisabled()
  await page.screenshot({ path: path.join(RUNTIME_CHAIN_EVIDENCE_DIR, 'ISOLATED_EMP104_NO_REVIEW_PREPARATION_STATE.png'), fullPage: false })
})

test('normal-page PDE preparation, participant handling, and column-width persistence', async ({ page }) => {
  test.setTimeout(90_000)
  await login(page, 'pce_plan_r12')
  await openPdeFromProcessCenter(page)

  await expect(page.getByText('1-4-正', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('尚未建立正式评审／待准备人员保存', { exact: false })).toBeVisible()

  const fixedTable = page.locator('[data-pce-column-width-table="order-review-fixed-items"]')
  const scrollProbe = await fixedTable.locator('.el-scrollbar__wrap').evaluateAll(nodes => nodes.map((node, index) => ({
    index, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, scrollLeft: node.scrollLeft,
  })))
  const scrollOwner = scrollProbe.find(row => row.scrollWidth > row.clientWidth)
  expect(scrollOwner).toBeTruthy()
  await fixedTable.locator('.el-scrollbar__wrap').nth(scrollOwner.index).evaluate(node => {
    node.scrollLeft = 520
    node.dispatchEvent(new Event('scroll', { bubbles: true }))
  })
  await page.waitForTimeout(150)
  const responsibleHeader = fixedTable.locator('th').filter({ hasText: '责任人' }).first()
  await responsibleHeader.scrollIntoViewIfNeeded()
  const initialWidth = await responsibleHeader.evaluate(node => node.getBoundingClientRect().width)
  const box = await responsibleHeader.boundingBox()
  let dragOffset = 2
  for (const offset of [2, 3, 4, 5, 6, 7]) {
    await page.mouse.move(box.x + box.width - offset, box.y + box.height / 2)
    if (await page.evaluate(() => document.body.style.cursor === 'col-resize')) {
      dragOffset = offset
      break
    }
  }
  console.log('column-drag-probe', {
    initialWidth,
    box,
    dragOffset,
    cursor: await page.evaluate(() => document.body.style.cursor),
  })
  expect(await page.evaluate(() => document.body.style.cursor)).toBe('col-resize')
  await page.mouse.down()
  await page.mouse.move(box.x + box.width + 120, box.y + box.height / 2, { steps: 8 })
  await page.mouse.up()
  console.log('column-width-storage', await page.evaluate(() => Object.fromEntries(
    Object.keys(localStorage).filter(key => key.startsWith('pce:column-width:')).map(key => [key, localStorage.getItem(key)]),
  )))
  const expandedWidth = await responsibleHeader.evaluate(node => node.getBoundingClientRect().width)
  expect(expandedWidth).toBeGreaterThan(initialWidth + 60)

  await expect(page.getByText('系统责任安排', { exact: true })).toBeVisible()
  await expect(page.getByText('已按正式分工自动匹配', { exact: true })).toHaveCount(9)
  await expect(page.getByText('EMP104', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('EMP-COMP001-0001', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('EMP107', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('EMP109', { exact: false }).first()).toBeVisible()
  await page.screenshot({ path: path.join(AUTO_RESPONSIBILITY_EVIDENCE_DIR, 'ISOLATED_AUTO_RESPONSIBILITY_PREVIEW.png'), fullPage: true })
  await page.getByRole('button', { name: '保存草稿' }).click()
  await expect(page.getByText('草稿、责任安排及精确对象授权已保存并完成服务端回读', { exact: false })).toBeVisible()
  await expect(page.getByText('EMP104', { exact: false }).first()).toBeVisible()

  await page.reload()
  await expect(page.getByRole('main').getByRole('heading', { name: '生产可行性评审' })).toBeVisible()
  const refreshedHeader = page.locator('[data-pce-column-width-table="order-review-fixed-items"] th').filter({ hasText: '责任人' }).first()
  const refreshedWidth = await refreshedHeader.evaluate(node => node.getBoundingClientRect().width)
  expect(refreshedWidth).toBeGreaterThan(initialWidth + 60)
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'PDE_COLUMN_WIDTH_REFRESH_PERSISTED.png'), fullPage: false })

  await page.getByRole('button', { name: '恢复默认列宽' }).first().click()
  const resetWidth = await refreshedHeader.evaluate(node => node.getBoundingClientRect().width)
  expect(resetWidth).toBeLessThan(refreshedWidth - 40)

  await logoutByClearingBrowserSession(page)
  await login(page, 'pce_emp104')
  await openPdeFromProcessCenter(page)

  const rows = page.locator('[data-pce-column-width-table="order-review-fixed-items"] .el-table__body-wrapper tbody tr')
  const ownRow = rows.nth(0)
  await expect(ownRow.locator('.el-select__wrapper').first()).not.toHaveClass(/is-disabled/)
  await expect(rows.nth(1).locator('.el-select__wrapper').first()).not.toHaveClass(/is-disabled/)
  await expect(rows.nth(2).locator('.el-select__wrapper').first()).not.toHaveClass(/is-disabled/)
  await expect(rows.nth(3).locator('.el-select__wrapper').first()).toHaveClass(/is-disabled/)
  await ownRow.locator('.el-select').first().click()
  await page.getByRole('option', { name: '同意', exact: true }).click()
  await page.getByRole('button', { name: '保存草稿' }).click()
  await expect(page.getByText('草稿、责任安排及精确对象授权已保存并完成服务端回读', { exact: false })).toBeVisible()
  await ownRow.getByText('本人签认', { exact: true }).click()
  await page.getByRole('button', { name: '签认本人已完成项目' }).click()
  await expect(page.getByText('本人所选项目已按服务端时间签认', { exact: true })).toBeVisible()

  await page.reload()
  await expect(page.getByText('已签认', { exact: true }).first()).toBeVisible()
  await expect(rows.nth(3).locator('.el-select__wrapper').first()).toHaveClass(/is-disabled/)
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'ISOLATED_EMP104_SIGNED.png'), fullPage: false })
})

test('user account long columns and action column support persisted manual widths', async ({ page }) => {
  test.setTimeout(60_000)
  await login(page, 'admin')
  await page.getByText('组织结构', { exact: true }).first().click()
  await expect(page).toHaveURL(/#\/organization/)
  await page.getByRole('button', { name: '用户账户', exact: true }).click()
  const userTable = page.locator('[data-pce-table-id="erp-access-users-table"]')
  await expect(userTable).toBeVisible()
  const employeeWidth = await dragHeader(page, userTable, '关联员工', 110)
  expect(employeeWidth.finalWidth).toBeGreaterThan(employeeWidth.initialWidth + 60)
  const roleWidth = await dragHeader(page, userTable, '系统角色', 90)
  expect(roleWidth.finalWidth).toBeGreaterThan(roleWidth.initialWidth + 50)
  const actionWidth = await dragHeader(page, userTable, '操作', -50, true)
  expect(actionWidth.finalWidth).toBeLessThan(actionWidth.initialWidth - 20)
  await page.reload()
  await expect(page.locator('[data-pce-table-id="erp-access-users-table"]')).toBeVisible()
  const stored = await page.evaluate(() => Object.fromEntries(
    Object.keys(localStorage).filter(key => key.includes('erp-access-users-table')).map(key => [key, localStorage.getItem(key)]),
  ))
  expect(JSON.stringify(stored)).toContain('key:linked-employee')
  expect(JSON.stringify(stored)).toContain('key:system-roles')
  expect(JSON.stringify(stored)).toContain('key:__actions')
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'USER_ACCOUNT_COLUMN_WIDTHS_PERSISTED.png'), fullPage: false })
  await page.getByRole('button', { name: '恢复默认列宽', exact: true }).click()
})
