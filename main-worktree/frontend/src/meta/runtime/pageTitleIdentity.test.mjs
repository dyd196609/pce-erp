import assert from 'node:assert/strict'
import test from 'node:test'

import {
  PCE_CURRENT_IDENTITY_STORAGE_KEY,
  buildIdentityAwareDocumentTitle,
  clearCurrentIdentity,
  rememberCurrentIdentity,
} from './pageTitleManager.js'
import { TAB_AUTH_TOKEN_KEY } from './tabAuthenticationContext.js'

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

test('browser title places the actual current identity before the governed page name', () => {
  const local = storage()
  local.setItem(TAB_AUTH_TOKEN_KEY, token('pce_emp107'))
  rememberCurrentIdentity({ id: 23, username: 'pce_emp107', real_name: '赵盛世', company_id: 1 }, local)
  assert.equal(buildIdentityAwareDocumentTitle('/pde/product-requirement-reviews', local), '赵盛世｜生产可行性评审')
})

test('tab token replacement never keeps the previous real name in the title', () => {
  const local = storage()
  local.setItem(TAB_AUTH_TOKEN_KEY, token('admin'))
  local.setItem(PCE_CURRENT_IDENTITY_STORAGE_KEY, JSON.stringify({ username: 'pce_emp107', realName: '赵盛世' }))
  assert.equal(buildIdentityAwareDocumentTitle('/organization', local), 'admin｜组织与权限基础')
})

test('logout title is explicit and clears remembered identity', () => {
  const local = storage()
  local.setItem(TAB_AUTH_TOKEN_KEY, token('admin'))
  rememberCurrentIdentity({ username: 'admin', real_name: '管理员' }, local)
  local.removeItem(TAB_AUTH_TOKEN_KEY)
  clearCurrentIdentity(local)
  assert.equal(buildIdentityAwareDocumentTitle('/system-login', local), '未登录｜账户登录')
  assert.equal(local.getItem(PCE_CURRENT_IDENTITY_STORAGE_KEY), null)
})
