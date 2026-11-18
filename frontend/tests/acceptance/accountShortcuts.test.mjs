import test from 'node:test'
import assert from 'node:assert/strict'
import { accountLoginLocation, normalizeAccountShortcut, openUnauthenticatedAccountTab, readAccountShortcuts, rememberAccountShortcut, ACCOUNT_SHORTCUT_KEY } from '../../src/meta/runtime/accountShortcuts.js'
import { TAB_AUTH_TOKEN_KEY, TAB_AUTH_IDENTITY_KEY, TAB_AUTH_EPOCH_KEY } from '../../src/meta/runtime/tabAuthenticationContext.js'

function storage() {
  const values = new Map()
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
}
test('account bookmarks allowlist names and never retain credentials or authority', () => {
  const local = storage()
  rememberAccountShortcut({ username: 'test_user', label: '测试用户', password: 'not-to-store', token: 'not-to-store', companyId: 99, roles: ['admin'] }, local)
  const saved = JSON.parse(local.getItem(ACCOUNT_SHORTCUT_KEY))
  assert.deepEqual(saved[0], { username: 'test_user', label: '测试用户' })
  assert.ok(saved.every(row => Object.keys(row).sort().join(',') === 'label,username'))
  assert.equal(readAccountShortcuts(local).filter(row => row.username === 'test_user').length, 1)
  local.setItem(ACCOUNT_SHORTCUT_KEY, '{bad json')
  assert.equal(readAccountShortcuts(local).length, 2)
  assert.equal(normalizeAccountShortcut({ username: ['admin'] }), null)
  assert.equal(normalizeAccountShortcut({ username: 'x'.repeat(51) }), null)
})
test('other account opens a clean tab without changing the source actor', () => {
  const source = storage(), receiving = storage()
  for (const key of [TAB_AUTH_TOKEN_KEY, TAB_AUTH_IDENTITY_KEY, TAB_AUTH_EPOCH_KEY]) {
    source.setItem(key, 'source'); receiving.setItem(key, 'cloned')
  }
  const navigations = []
  const tab = { sessionStorage: receiving, opener: {}, location: { replace: href => navigations.push(href) }, close() { assert.fail('unexpected close') } }
  const router = { resolve: location => ({ href: `#${location.path}?${new URLSearchParams(location.query)}` }) }
  const result = openUnauthenticatedAccountTab(accountLoginLocation('test_user'), router, { open: () => tab })
  assert.equal(result.opened, true)
  assert.equal(tab.opener, null)
  for (const key of [TAB_AUTH_TOKEN_KEY, TAB_AUTH_IDENTITY_KEY, TAB_AUTH_EPOCH_KEY]) {
    assert.equal(source.getItem(key), 'source'); assert.equal(receiving.getItem(key), null)
  }
  assert.match(navigations[0], /username=test_user/)
  assert.doesNotMatch(navigations[0], /token|password|authHandoff/)
})
test('popup and isolation errors fail without navigating a credential-cloned tab', () => {
  const router = { resolve: () => ({ href: '#/system-login' }) }
  assert.equal(openUnauthenticatedAccountTab({}, router, { open: () => null }).opened, false)
  let closed = false, navigated = false
  const tab = { sessionStorage: { removeItem() { throw new Error('blocked') } }, close() { closed = true }, location: { replace() { navigated = true } } }
  assert.equal(openUnauthenticatedAccountTab({}, router, { open: () => tab }).opened, false)
  assert.equal(closed, true); assert.equal(navigated, false)
})
