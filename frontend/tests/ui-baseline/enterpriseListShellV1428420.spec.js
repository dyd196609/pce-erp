import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const canaryDatabase = path.resolve(frontendRoot, '../backend/canary-data/purchase-flow-demo.sqlite3')

function digest(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
}

test('采购申请一页一验收：固定表头、内部滚动、分页与刷新保留', async ({ page }) => {
  const authentication = await page.request.post('/api/auth/login/', {
    data: { username: 'admin', password: 'admin123' },
  })
  expect(authentication.ok()).toBeTruthy()
  const authenticationPayload = await authentication.json()
  await page.addInitScript(token => localStorage.setItem('token', token), authenticationPayload.token)

  const businessWrites = []
  page.on('request', request => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())
      && !request.url().endsWith('/api/auth/login/')) {
      businessWrites.push(`${request.method()} ${request.url()}`)
    }
  })

  const canaryHashBefore = digest(canaryDatabase)
  await page.goto('/#/scm/purchase-request', { waitUntil: 'domcontentloaded' })

  const list = page.locator('[data-acceptance-id="purchase-request-enterprise-list-runtime"]')
  const table = page.locator('[data-acceptance-id="purchase-request-table"]')
  const pagination = page.locator('[data-acceptance-id="purchase-request-pagination"]')
  await expect(list).toBeVisible()
  await expect(table).toBeVisible()
  await expect(pagination).toBeVisible()

  const headerStyle = await list.locator('.el-table__header-wrapper').evaluate(element => {
    const style = getComputedStyle(element)
    return { position: style.position, top: style.top }
  })
  expect(headerStyle.position).toBe('sticky')
  expect(headerStyle.top).toBe('0px')

  const verticalScroller = list.locator('.el-table__body-wrapper .el-scrollbar__wrap').first()
  const scrollState = await verticalScroller.evaluate(element => {
    const style = getComputedStyle(element)
    return {
      overflowY: style.overflowY,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }
  })
  expect(scrollState.overflowY).toBe('auto')
  expect(scrollState.clientHeight).toBeLessThanOrEqual(440)

  await expect(pagination.locator('[data-acceptance-id="pagination-total"]')).toContainText('总记录数')
  await expect(pagination.locator('[data-acceptance-id="pagination-current"]')).toContainText('当前页')
  await expect(pagination.locator('[data-acceptance-id="pagination-page-size"]')).toHaveValue('20')
  await expect(pagination.locator('[data-acceptance-id="pagination-previous"]')).toBeVisible()
  await expect(pagination.locator('[data-acceptance-id="pagination-next"]')).toBeVisible()

  const rowsBefore = await table.locator('.el-table__body tbody tr').allTextContents()
  expect(rowsBefore.length).toBeGreaterThan(0)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="purchase-request-pagination"]')).toBeVisible()
  await expect.poll(async () => (
    page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').count()
  )).toBe(rowsBefore.length)
  const rowsAfter = await page.locator('[data-acceptance-id="purchase-request-table"] .el-table__body tbody tr').allTextContents()
  expect(rowsAfter).toEqual(rowsBefore)
  expect(digest(canaryDatabase)).toBe(canaryHashBefore)
  expect(businessWrites).toEqual([])
})
