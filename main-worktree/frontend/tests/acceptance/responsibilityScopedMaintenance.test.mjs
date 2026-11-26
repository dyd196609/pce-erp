import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '../../..')
const page = fs.readFileSync(
  path.join(root, 'frontend/src/meta/pages/AccessControlFoundationPage.vue'),
  'utf8',
)

assert.match(page, /RESPONSIBILITY_MANAGE_PERMISSION='system\.organization\.responsibility\.manage'/)
assert.match(page, /permissionCodes\.includes\(RESPONSIBILITY_MANAGE_PERMISSION\)/)
assert.match(page, /responsibilityScopedView\.value\?tabs\.filter\(item=>\['positions','responsibilities'\]\.includes\(item\.key\)\)/)
assert.match(page, /if\(responsibilityScopedView\.value\).*accessControlApi\.responsibilities\(\{assignmentContext:'1'\}\)/s)
assert.match(page, /facts\.positions=assignmentContext\.positions\|\|\[\]/)
assert.match(page, /canMaintainResponsibility&&!loadError&&activeTab==='responsibilities'/)
assert.match(page, /activeTab==='positions'.*openPositionResponsibilityEditor\(row\).*维护职责分配/)
assert.match(page, /:responsibility-assignment-only="responsibilityScopedView"/)
assert.match(page, /当前账号已获得岗位职责维护权限；本页面仅开放责任目录与岗位职责分配正式动作/)
assert.doesNotMatch(
  page.match(/if\(responsibilityScopedView\.value\).*?return}/s)?.[0] || '',
  /accessControlApi\.(foundation|action)\(/,
)

console.log('responsibility scoped maintenance contract: PASS')
