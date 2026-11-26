import { expect, test } from '@playwright/test'

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

test('R17.2 real keyboard input activates Enter ProfitOS and preserves authentication', async ({ page, context }) => {
  const providerStatuses = new Map()
  let loginStatus = 0

  await context.clearCookies()
  page.on('response', (response) => {
    if (response.url().endsWith('/api/auth/login/')) loginStatus = response.status()
    const match = response.url().match(/purchase-request-references\/([^/?]+)\//)
    if (match) providerStatuses.set(match[1], response.status())
  })

  await page.goto('/?r172=manual-keyboard#/login')
  const username = page.getByPlaceholder('Enterprise username')
  const password = page.getByPlaceholder('Enterprise password')
  const enter = page.getByRole('button', { name: 'Enter ProfitOS' })

  await expect(enter).toHaveClass(/el-button--info/)
  await expect(enter).toBeEnabled()

  await username.click()
  await username.pressSequentially(process.env.PCE_TEST_USERNAME || 'admin', { delay: 80 })
  await password.click()
  await password.pressSequentially(process.env.PCE_TEST_PASSWORD || 'admin123', { delay: 80 })

  await expect(enter).toHaveClass(/el-button--primary/)
  await expect(enter).toBeEnabled()
  await enter.click()

  await expect(page).toHaveURL(/#\/dashboard$/)
  expect(loginStatus).toBe(200)
  expect((await context.cookies()).some((cookie) => cookie.name === 'sessionid')).toBe(true)

  await page.goto('/?r172=providers#/scm/purchase-request')
  await expect.poll(() => providerStatuses.size).toBe(providerTypes.length)
  for (const type of providerTypes) expect(providerStatuses.get(type), `${type} HTTP status`).toBe(200)
})
