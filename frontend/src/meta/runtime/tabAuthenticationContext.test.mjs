import assert from 'node:assert/strict'
import test from 'node:test'

import {
  TAB_AUTH_IDENTITY_KEY,
  authenticationContextChanged,
  claimLegacySharedAuthentication,
  clearTabAuthentication,
  getTabAuthEpoch,
  getTabAuthToken,
  rememberTabIdentity,
  setTabAuthToken,
} from './tabAuthenticationContext.js'

function storage() {
  const values = new Map()
  return {
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  }
}

function token(username) {
  const payload = Buffer.from(JSON.stringify({ username, exp: Math.floor(Date.now() / 1000) + 3600 }))
    .toString('base64url')
  return `header.${payload}.signature`
}

test('two tabs in one browser retain independent actors and logout state', () => {
  const adminTab = storage()
  const approverTab = storage()
  setTabAuthToken(token('admin'), adminTab)
  rememberTabIdentity({ username: 'admin', real_name: '管理员' }, adminTab)
  setTabAuthToken(token('pce_emp_comp001_0002'), approverTab)
  rememberTabIdentity({ username: 'pce_emp_comp001_0002', real_name: '岳战勇' }, approverTab)
  clearTabAuthentication(approverTab)
  assert.match(getTabAuthToken(adminTab), /header\./)
  assert.equal(getTabAuthToken(approverTab), '')
  assert.match(adminTab.getItem(TAB_AUTH_IDENTITY_KEY), /admin/)
})

test('legacy shared authentication can be claimed by at most one tab', () => {
  const local = storage()
  const firstTab = storage()
  const secondTab = storage()
  local.setItem('token', token('admin'))
  local.setItem(TAB_AUTH_IDENTITY_KEY, JSON.stringify({ username: 'admin' }))
  assert.equal(claimLegacySharedAuthentication(firstTab, local), true)
  assert.equal(claimLegacySharedAuthentication(secondTab, local), false)
  assert.match(getTabAuthToken(firstTab), /header\./)
  assert.equal(getTabAuthToken(secondTab), '')
})

test('an identity epoch change marks an older asynchronous response stale', () => {
  const tab = storage()
  setTabAuthToken(token('admin'), tab)
  const requestEpoch = getTabAuthEpoch(tab)
  setTabAuthToken(token('pce_emp_comp001_0002'), tab)
  assert.equal(authenticationContextChanged(requestEpoch, tab), true)
})
