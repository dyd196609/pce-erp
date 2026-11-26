import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  getFoundationCanonicalModuleByEntity,
} from '../../src/meta/master-data/foundationEntryUnificationRegistry.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('工作中心与工序候选工作中心保持不同正式对象和路由', () => {
  const workCenter = getFoundationCanonicalModuleByEntity('work-centers')
  const capability = getFoundationCanonicalModuleByEntity('work-center-operation-capabilities')

  assert.equal(workCenter.dataSource, 'pde.WorkCenter')
  assert.equal(workCenter.routePath, '/foundation/master-data/work-centers')
  assert.equal(capability.dataSource, 'pde.WorkCenterOperationCapability')
  assert.equal(capability.routePath, '/foundation/master-data/work-center-operation-capabilities')
  assert.notEqual(workCenter.entityKey, capability.entityKey)
})

test('维护按钮只使用服务端当前账号授权且新增编辑明确打开表单', () => {
  const source = readFrontend('src/meta/components/ProductionFoundationMaintenance.vue')

  assert.match(source, /currentEntityAuthorization\.value\?\.allowed === true/)
  assert.match(source, /data-state="maintenance-authorization-denied"/)
  assert.match(source, /data-state="maintenance-form-open"/)
  assert.match(source, /async function revealMaintenanceForm/)
  assert.match(source, /scrollIntoView/)
  assert.match(source, /async function editRow\(row\)/)
  assert.match(source, /pageState\.value\.mode !== 'maintain'/)
  assert.match(source, /currentEntityAuthorization\.value = entityFacts\.currentEntityAuthorization/)
  assert.match(source, /saveError\.value = error\?\.response\?\.data\?\.message/)
  assert.doesNotMatch(source, /canPerformAction\(stateManager\.snapshot\(\)\.role, 'EXECUTE'\)/)
})

test('候选关系在无正式工作中心时显示中文阻断且不伪造关系', () => {
  const source = readFrontend('src/meta/components/ProductionFoundationMaintenance.vue')
  const service = readProject('backend/pde/production_foundation_service.py')

  assert.match(source, /当前公司正式工作中心为0，请先在“工作中心”页面维护真实工作中心/)
  assert.match(source, /selectedEntity\.value === 'work-center-operation-capabilities'\) return 'capability_code'/)
  assert.match(source, /field: 'operation_id', label: '工序', filterType: 'text'/)
  assert.match(source, /field: 'work_center_id', label: '工作中心', filterType: 'text'/)
  assert.match(source, /field: 'assignment_role', label: '资源角色', filterType: 'select', options:/)
  assert.match(source, /maintenancePrerequisitesReady/)
  assert.match(source, /saving \|\| !maintenancePrerequisitesReady/)
  assert.match(service, /WorkCenterOperationCapability/)
  assert.match(service, /production\.master_data\.resource\.maintain/)
})

test('工作中心引用Workshop但不把Workshop投影为WorkCenter', () => {
  const source = readFrontend('src/meta/components/ProductionFoundationMaintenance.vue')

  assert.match(source, /refField\('workshop_id', '所属车间', 'workshops'\)/)
  assert.match(source, /rowsFor\(selectedEntity\.value\)/)
  assert.match(source, /pdeApi\.productionFoundationA1\(requestedEntity\)/)
  assert.match(source, /previousEntity !== selectedEntity\.value/)
})

test('工作中心编码由服务端生成且新增编辑均只读', () => {
  const source = readFrontend('src/meta/components/ProductionFoundationMaintenance.vue')
  const service = readProject('backend/pde/production_foundation_service.py')

  assert.match(source, /label: '工作中心编码'/)
  assert.match(source, /serverGenerated: true/)
  assert.match(source, /placeholder: '保存后由系统自动生成'/)
  assert.match(source, /field\.readOnly === true \|\| ruleFieldReadOnly\(field\)/)
  assert.match(source, /if \(field\.serverGenerated\) return/)
  assert.match(source, /正式编码：\$\{generatedCode\}/)
  assert.match(service, /"work-centers": \{"code"\}/)
  assert.match(service, /CodeRule\.next_code/)
  assert.match(service, /"work-centers": \("code", "production_work_center"\)/)
})

test('工序候选工作中心资源角色复用中文映射且不改写原始枚举', () => {
  const source = readFrontend('src/meta/components/ProductionFoundationMaintenance.vue')
  const model = readProject('backend/pde/models.py')

  assert.match(model, /PRIMARY = "primary", "主工作中心"/)
  assert.match(model, /ALTERNATIVE = "alternative", "备选工作中心"/)
  assert.match(source, /const workCenterAssignmentRoleOptions = Object\.freeze\(enumOptions\(\[/)
  assert.match(source, /\['primary', '主工作中心'\]/)
  assert.match(source, /\['alternative', '备选工作中心'\]/)
  assert.match(source, /enumCol\('assignment_role', '资源角色', workCenterAssignmentRoleOptions\)/)
  assert.match(source, /select\('assignment_role', '资源角色', workCenterAssignmentRoleOptions, true\)/)
  assert.match(source, /field: 'assignment_role', label: '资源角色', filterType: 'select', options: workCenterAssignmentRoleOptions/)
  assert.match(source, /row => displayValue\(row\[column\.key\], column\)/)
  assert.match(source, /const option = column\.options\?\.find\(item => String\(item\.value\) === String\(value\)\)/)
  assert.match(source, /return option\?\.label \|\| \(value === null \|\| value === undefined \|\| value === '' \? '-' : value\)/)
  assert.doesNotMatch(source, /assignment_role\s*[:=]\s*['"]主工作中心['"]/)
})
