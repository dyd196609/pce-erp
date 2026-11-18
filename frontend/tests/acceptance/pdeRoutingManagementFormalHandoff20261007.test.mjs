import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { findPdePageDefinition, PDE_PAGE_VERSION } from '../../src/meta/pages/pdePageDefinitions.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('工艺路线管理只读承接正式订单链并停在第9节点', () => {
  const routing = findPdePageDefinition('routings')
  const fields = routing.columns.map(([field]) => field)

  assert.equal(PDE_PAGE_VERSION, 'V1.14.2.8.4.10.8')
  assert.equal(routing.pageCode, 'pde-routings')
  assert.equal(routing.nodeCode, 'routing-management')
  assert.equal(routing.governance.currentFlowStep, '工艺路线管理')
  assert.equal(routing.governance.navigation.previous.label, 'BOM版本管理')
  assert.equal(routing.governance.navigation.next.label, '工艺路线版本管理')
  assert.match(routing.governance.forbidden.join('\n'), /进入工艺路线版本管理/)
  for (const field of [
    'handoffStatusLabel', 'companyCode', 'orderNo', 'orderLineNo',
    'orderEngineeringInstanceNo', 'bomCode', 'bomVersionNo',
    'sourceCalculationNo', 'sourceIntegrityLabel', 'productCategoryName',
    'manufacturingProcessTypeName', 'routingSourceLabel', 'routingCode',
    'routingName', 'routingVersionNo', 'routingVersionStatusLabel',
    'stepCount', 'operationSequenceLabel', 'resourceMaintenanceLabel',
    'planningReadinessStatusLabel', 'planningBlockingSummary',
    'routingVersionManagementEligibilityLabel',
  ]) {
    assert.equal(fields.includes(field), true, `missing routing handoff field: ${field}`)
  }
})

test('服务端工艺路线承接复用现有解析服务、正式FK并保持零写入', () => {
  const views = readProject('backend/pde/views.py')
  const block = views.slice(
    views.indexOf('class RoutingFormalHandoffError'),
    views.indexOf('class EngineeringDocumentListView'),
  )

  assert.match(block, /ManufacturingStructureService\.resolve_effective_routing\(instance\)/)
  assert.match(block, /project_product_bom_material_detail\(/)
  assert.match(block, /routing_version\.steps\.select_related\(/)
  assert.match(block, /"databaseBusinessWriteCount": 0/)
  assert.match(block, /"routingCreatedCount": 0/)
  assert.match(block, /"routingVersionCreatedCount": 0/)
  assert.match(block, /"routingStepCreatedCount": 0/)
  assert.match(block, /未使用名称、颜色或工艺描述推断/)
  assert.doesNotMatch(block, /\.objects\.create\(/)
  assert.doesNotMatch(block, /\.objects\.[\s\S]{0,80}\.update\(/)
  assert.doesNotMatch(block, /\.save\(/)
})

test('工艺路线管理使用企业列表共同契约且高级筛选类型受治理', () => {
  const routing = findPdePageDefinition('routings')
  const page = readProject('frontend/src/meta/pages/PdeFoundationPage.vue')

  assert.match(page, /data-enterprise-list-contract="PCE-ENTERPRISE-LIST-CONTRACT-V1\.1"/)
  assert.match(page, /<PceEnterpriseListTable/)
  assert.match(page, /<PceBusinessStatus/)
  assert.equal(routing.filterSchema.every(item => Boolean(item.filterType)), true)
  assert.equal(routing.filterSchema
    .filter(item => item.filterType === 'select')
    .every(item => Array.isArray(item.options) && item.options.length > 0), true)
})
