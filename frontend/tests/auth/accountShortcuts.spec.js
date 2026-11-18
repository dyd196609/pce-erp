import { test, expect } from '@playwright/test'

async function expectFixedBookmark(page) {
  const bookmark = page.getByRole('button', { name: '账户书签', exact: true })
  await expect(bookmark).toHaveCount(1)
  await expect(bookmark).toBeVisible()
  const box = await bookmark.boundingBox()
  expect(box.x).toBeLessThanOrEqual(12)
  expect(box.y).toBeGreaterThanOrEqual(0)
  expect(box.y + box.height).toBeLessThanOrEqual(52)
  expect(box.height).toBeGreaterThanOrEqual(38)
  expect(await bookmark.evaluate(el => {
    const r = el.getBoundingClientRect()
    return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2))
  })).toBe(true)
}

// Isolated synthetic authentication only. No request reaches the business API.
test('shortcut hub, one-time current identity handoff, and separate-account login', async ({ page, context }) => {
  const actor = { id: 9001, username: 'shortcut_test_user', real_name: '快捷测试用户', company_id: 9001 }
  const payload = Buffer.from(JSON.stringify({ username: actor.username, user_id: actor.id, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url')
  const token = `fixture.${payload}.fixture`
  let issuedTarget = '', issued = 0, exchanged = 0
  const writes = []
  await context.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (!path.startsWith('/api/')) { await route.continue(); return }
    if (request.method() !== 'GET') writes.push(path)
    let body = { success: true, data: {}, error: null, meta: {} }
    if (path === '/api/auth/login/') body = { token, user: actor }
    else if (path === '/api/auth/tab-handoff/issue/') {
      expect(request.headers().authorization).toBe(`Bearer ${token}`)
      issuedTarget = request.postDataJSON().targetPath; issued += 1
      body = { handoffCode: 'synthetic-one-use', expiresInSeconds: 60, targetPath: issuedTarget }
    } else if (path === '/api/auth/tab-handoff/exchange/') {
      expect(request.postDataJSON()).toEqual({ handoffCode: 'synthetic-one-use', targetPath: issuedTarget })
      exchanged += 1; body = { token, user: actor, targetPath: issuedTarget }
    } else if (path === '/api/access-control/profile/') body.data = { authenticated: true, identity: { userId: actor.id, username: actor.username, realName: actor.real_name }, organization: { id: 9001, name: '隔离测试公司' } }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto('/#/system-login?redirect=/account-shortcuts&username=shortcut_test_user')
  await expectFixedBookmark(page)
  await expect(page.getByPlaceholder('用户名', { exact: true })).toHaveValue(actor.username)
  await page.getByPlaceholder('密码', { exact: true }).fill('synthetic-fixture-only')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '快捷登录账户', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '以当前账户打开业务流程中心', exact: true })).toBeVisible()
  const sourceToken = await page.evaluate(() => sessionStorage.getItem('pce_tab_auth_token_v1'))
  const [workspace] = await Promise.all([context.waitForEvent('page'), page.getByRole('button', { name: '以当前账户打开业务流程中心', exact: true }).click()])
  await expect(workspace).toHaveURL(/#\/process-center$/)
  expect(issued).toBe(1); expect(exchanged).toBe(1)
  expect(await workspace.evaluate(() => sessionStorage.getItem('pce_tab_auth_token_v1'))).toBe(sourceToken)
  await expectFixedBookmark(workspace)
  // The shared entry remains outside the sidebar and survives collapse + scrolling.
  await workspace.getByRole('button', { name: '收', exact: true }).click()
  await workspace.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await expectFixedBookmark(workspace)
  const sourceUrl = workspace.url()
  const sourceScroll = await workspace.evaluate(() => window.scrollY)
  await page.close()
  const [recovered] = await Promise.all([context.waitForEvent('page'), workspace.getByRole('button', { name: '账户书签', exact: true }).click()])
  await expect(recovered.getByRole('heading', { name: '快捷登录账户', exact: true })).toBeVisible()
  await expect(recovered.getByText(actor.username, { exact: false }).first()).toBeVisible()
  expect(workspace.url()).toBe(sourceUrl)
  expect(await workspace.evaluate(() => window.scrollY)).toBe(sourceScroll)
  expect(await workspace.evaluate(() => sessionStorage.getItem('pce_tab_auth_token_v1'))).toBe(sourceToken)
  expect(issued).toBe(2); expect(exchanged).toBe(2)
  page = recovered
  const [login] = await Promise.all([context.waitForEvent('page'), page.getByRole('button', { name: '登录 管理员', exact: true }).click()])
  await expect(login.getByPlaceholder('用户名', { exact: true })).toHaveValue('admin')
  await expect(login.getByPlaceholder('密码', { exact: true })).toHaveValue('')
  expect(await login.evaluate(() => sessionStorage.getItem('pce_tab_auth_token_v1'))).toBeNull()
  expect(await page.evaluate(() => sessionStorage.getItem('pce_tab_auth_token_v1'))).toBe(sourceToken)
  const saved = await page.evaluate(() => localStorage.getItem('pce_account_shortcut_names_v1'))
  expect(saved).not.toContain('synthetic-fixture-only'); expect(saved).not.toContain(token)
  await page.reload()
  await expect(page.getByRole('button', { name: '以当前账户打开业务流程中心', exact: true })).toBeVisible()
  await expectFixedBookmark(page)
  await page.setViewportSize({ width: 366, height: 800 })
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await expectFixedBookmark(page)
  await workspace.setViewportSize({ width: 585, height: 800 })
  await expectFixedBookmark(workspace)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(writes.every(path => ['/api/auth/login/', '/api/auth/tab-handoff/issue/', '/api/auth/tab-handoff/exchange/'].includes(path))).toBe(true)
})

test('anonymous shortcuts stay unauthenticated and only prefill a normal login', async ({ page, context }) => {
  const calls = []
  await context.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) { await route.continue(); return }
    calls.push(path)
    await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: 'not authenticated' }) })
  })
  await page.goto('/#/account-shortcuts')
  await expectFixedBookmark(page)
  await expect(page.getByText('本页签尚未登录，请选择下方账户。', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '以当前账户打开业务流程中心', exact: true })).toHaveCount(0)
  const [login] = await Promise.all([context.waitForEvent('page'), page.getByRole('button', { name: '登录 岳战勇', exact: true }).click()])
  await expect(login.getByPlaceholder('用户名', { exact: true })).toHaveValue('pce_emp_comp001_0002')
  await expect(login.getByPlaceholder('密码', { exact: true })).toHaveValue('')
  await expectFixedBookmark(login)
  const [recovered] = await Promise.all([context.waitForEvent('page'), login.getByRole('button', { name: '账户书签', exact: true }).click()])
  await expect(recovered.getByText('本页签尚未登录，请选择下方账户。', { exact: true })).toBeVisible()
  await expectFixedBookmark(recovered)
  expect(calls).toEqual([])
  await expect(page).toHaveURL(/#\/account-shortcuts$/)
})
