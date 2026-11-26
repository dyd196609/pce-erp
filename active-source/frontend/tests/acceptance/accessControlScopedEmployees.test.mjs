import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(path.join(root, 'frontend/src/meta/pages/AccessControlFoundationPage.vue'), 'utf8')
const api = fs.readFileSync(path.join(root, 'frontend/src/api/accessControl.js'), 'utf8')

test('非管理员员工入口读取正式作用域API且不把403清空解释为零员工', () => {
  assert.match(api, /scopedEmployees/)
  assert.match(api, /\/api\/pfm\/employees\//)
  assert.match(page, /accessControlApi\.profile\(\)/)
  assert.match(page, /accessControlApi\.scopedEmployees/)
  assert.match(page, /employeeResponse\.data\?\.results/)
  assert.match(page, /当前账号可查看本人及授权范围内员工/)
  assert.match(page, /当前可见员工/)
})

test('无管理权限的普通账号不暴露维护操作，管理员仍复用原正式聚合接口', () => {
  assert.match(page, /canEditActiveTab&&!loadError&&editableTabs/)
  assert.match(page, /restrictedEmployeeView=computed\(\(\)=>!canMaintain\.value&&!canMaintainResponsibility\.value\)/)
  assert.match(page, /visibleTabs.*employees/)
  assert.match(page, /维护权限<\/span><strong>无/)
  assert.match(page, /accessControlApi\.foundation\(\)/)
  assert.match(page, /accessControlApi\.enterpriseOrganizationModel\(\)/)
})
