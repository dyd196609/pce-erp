import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(
  path.join(root, 'frontend/src/meta/pages/AccessControlFoundationPage.vue'),
  'utf8',
)
const backend = fs.readFileSync(
  path.join(root, 'backend/system/access_control_views.py'),
  'utf8',
)
const query = fs.readFileSync(
  path.join(root, 'backend/pfm/formal_employee.py'),
  'utf8',
)

test('账户关联员工查询来自Employee Archive且不复用formal employee隐藏过滤', () => {
  assert.match(query, /def account_link_employee_queryset/)
  assert.match(query, /status="active"/)
  assert.match(query, /user__isnull=True/)
  assert.match(backend, /"accountLinkEmployees": account_link_employees/)
  assert.match(page, /return facts\.accountLinkEmployees/)
  assert.doesNotMatch(page, /availableAccountEmployees=computed\([^\n]*formalCandidateBaseEligible/)
})

test('新增账户选项显示历史组织与资格说明并阻断不合格保存', () => {
  assert.match(page, /accountEmployeeOptionLabel/)
  assert.match(page, /（历史）/)
  assert.match(page, /organizationStatusLabel/)
  assert.match(page, /accountLinkStatusLabel/)
  assert.match(page, /accountProvisioningStatusLabel/)
  assert.match(page, /accountProvisioningMessage/)
  assert.match(page, /editorSaveDisabled/)
  assert.match(page, /!selectedAccountEmployee\.value\.accountProvisioningEligible/)
})

