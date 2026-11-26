import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const providerTypes = [
  'employees',
  'organization-tree',
  'projects',
  'cost-centers',
  'expense-categories',
  'budget-categories',
  'materials',
  'suppliers',
]

test('R17.1 Enter ProfitOS establishes JWT and Django session before Provider reads', async ({ page, context }) => {
  const providerStatuses = new Map()
  const providerAuthContext = new Map()
  let loginStatus = 0
  let jwtReturned = false
  let sessionCookieIssued = false

  await context.clearCookies()

  page.on('response', async (response) => {
    if (response.url().endsWith('/api/auth/login/')) {
      loginStatus = response.status()
      const payload = await response.json().catch(() => ({}))
      jwtReturned = Boolean(payload.token && payload.user)
      return
    }

    const match = response.url().match(/purchase-request-references\/([^/?]+)\//)
    if (!match) return
    const headers = await response.request().allHeaders()
    providerStatuses.set(match[1], response.status())
    providerAuthContext.set(match[1], {
      authorizationPresent: Boolean(headers.authorization),
      cookiePresent: /(?:^|;)\s*sessionid=/i.test(headers.cookie || ''),
    })
  })

  await page.goto('/?r171=login#/login')
  await expect(page.getByText('Demo Company').first()).toBeVisible()
  await expect(page.getByText('Role', { exact: true })).toBeVisible()
  await expect(page.getByText('Plan', { exact: true })).toBeVisible()

  await page.getByPlaceholder('Enterprise username').fill(process.env.PCE_TEST_USERNAME || 'admin')
  await page.getByPlaceholder('Enterprise password').fill(process.env.PCE_TEST_PASSWORD || 'admin123')
  await page.getByRole('button', { name: 'Enter ProfitOS' }).click()

  await expect(page).toHaveURL(/#\/dashboard$/)
  sessionCookieIssued = (await context.cookies()).some((cookie) => cookie.name === 'sessionid')
  expect(loginStatus).toBe(200)
  expect(jwtReturned).toBe(true)
  expect(sessionCookieIssued).toBe(true)

  await page.goto('/?r171=providers#/scm/purchase-request')
  await expect.poll(() => providerStatuses.size).toBe(providerTypes.length)
  for (const type of providerTypes) {
    expect(providerStatuses.get(type), `${type} HTTP status`).toBe(200)
    expect(providerAuthContext.get(type)?.authorizationPresent, `${type} JWT`).toBe(true)
    expect(providerAuthContext.get(type)?.cookiePresent, `${type} session`).toBe(true)
  }

  const outputDir = resolve('test-results', 'login-auth-context-unification-r17-1')
  mkdirSync(outputDir, { recursive: true })
  writeFileSync(resolve(outputDir, 'browser-evidence.json'), `${JSON.stringify({
    version: 'V1.14.2.8.4.15-R17.1',
    result: 'PASS',
    login: {
      httpStatus: loginStatus,
      jwtReturned,
      djangoSessionCookieIssued: sessionCookieIssued,
    },
    providers: Object.fromEntries(providerStatuses),
    providerAuthContext: Object.fromEntries(providerAuthContext),
    productionUserDataWritten: false,
    nextPageAllowed: false,
  }, null, 2)}\n`, 'utf8')
})
