import { test, expect } from '@playwright/test'
import { createHmac } from 'node:crypto'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { activateModule, getModuleAcceptanceProfile } from '../../src/meta/acceptance/registry/enterpriseAcceptanceFrameworkService.js'

const base64url = value => Buffer.from(JSON.stringify(value)).toString('base64url')
const createReadOnlyAdminToken = () => {
  const settings = readFileSync(path.resolve('../backend/pce_backend/settings.py'), 'utf8')
  const secret = settings.match(/^SECRET_KEY\s*=\s*["']([^"']+)["']/m)?.[1]
  if (!secret) throw new Error('TEST_JWT_SECRET_NOT_RESOLVED')
  const header = base64url({ alg: 'HS256', typ: 'JWT' })
  const payload = base64url({ user_id: 1, username: 'admin', exp: Math.floor(Date.now() / 1000) + 3600 })
  const signature = createHmac('sha256', secret).update(`${header}.${payload}`).digest('base64url')
  return `${header}.${payload}.${signature}`
}

test('SCM Profile 自动激活后以只读方式验收采购申请页面', async ({ page }) => {
  const activation = activateModule({ moduleCode: 'SCM' })
  const profile = getModuleAcceptanceProfile({ moduleCode: 'SCM' })
  expect(activation.success).toBe(true)
  expect(activation.activationStatus).toBe('READY')
  expect(profile).toMatchObject({ moduleCode: 'SCM', objects: 3, templates: 1, rules: 8, collectors: 10, readOnly: true, productionUserDataWritten: false })

  await page.addInitScript(token => localStorage.setItem('token', token), createReadOnlyAdminToken())

  const businessMutations = []
  page.on('request', request => {
    if (/\/api\/(procurement|pce)\//.test(request.url()) && request.method() !== 'GET') businessMutations.push({ method: request.method(), url: request.url() })
  })
  await page.goto('/#/scm/purchase-request', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('[data-acceptance-id="purchase-request-business-page"]')).toBeVisible()
  await expect(page.locator('[data-acceptance-id="purchase-request-business-page"]')).toHaveAttribute('data-business-object', 'PurchaseRequest')
  expect(businessMutations).toEqual([])
  expect(activation.productionUserDataWritten).toBe(false)
})
