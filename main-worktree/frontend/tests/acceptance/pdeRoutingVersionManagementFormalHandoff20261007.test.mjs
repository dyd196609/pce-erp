import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { findPdePageDefinition, PDE_PAGE_VERSION } from '../../src/meta/pages/pdePageDefinitions.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('工艺路线版本管理只读承接正式订单链并停在第10节点', () => {
  const definition = findPdePageDefinition('routingVersions')
  const fields = definition.columns.map(([field]) => field)

  assert.equal(PDE_PAGE_VERSION, 'V1.14.2.8.4.10.8')
  assert.equal(definition.pageCode, 'pde-routing-versions')
  assert.equal(definition.nodeCode, 'routing-version-management')
  assert.equal(definition.governance.currentFlowStep, '工艺路线版本管理')
  assert.equal(definition.governance.navigation.previous.label, '工艺路线管理')
  assert.equal(definition.governance.navigation.next.label, '工程资料发布')
  assert.match(definition.governance.forbidden.join('\n'), /进入工程资料发布/)
  for (const field of [
    'routingVersionHandoffStatusLabel', 'companyCode', 'orderNo', 'orderLineNo',
    'orderEngineeringInstanceNo', 'bomCode', 'bomVersionNo', 'sourceCalculationNo',
    'sourceIntegrityLabel', 'routingSourceLabel', 'routingCode', 'routingName',
    'definitionStatusLabel', 'versionId', 'revision', 'effectiveStatusLabel',
    'stepCount', 'stepRelationshipSemanticsLabel', 'statusLabel',
    'engineeringDocumentReleaseEligibilityLabel',
  ]) {
    assert.equal(fields.includes(field), true, `missing routing version handoff field: ${field}`)
  }
})

test('服务端版本承接复用节点9正式链与现有版本工序外键且保持零写入', () => {
  const views = readProject('backend/pde/views.py')
  const block = views.slice(
    views.indexOf('class RoutingVersionListView'),
    views.indexOf('class EngineeringChangeListView'),
  )

  assert.match(block, /RoutingListView\._serialize_formal_handoff\(item\)/)
  assert.match(block, /RoutingListView\(\)\.serialize\(obj\.routing\)/)
  assert.match(block, /"stepRelationshipSemanticsCode": "VERSION_SCOPED_RELATIONAL_DEFINITION"/)
  assert.match(block, /"immutableSnapshotProven": False/)
  assert.match(block, /"databaseBusinessWriteCount": 0/)
  assert.match(block, /"engineeringDocumentCreatedCount": 0/)
  assert.doesNotMatch(block, /\.objects\.create\(/)
  assert.doesNotMatch(block, /\.objects\.[\s\S]{0,80}\.update\(/)
  assert.doesNotMatch(block, /\.save\(/)
})

test('第10节点详情复用同一服务端工序投影并如实说明非独立冻结快照', () => {
  const page = readProject('frontend/src/meta/pages/PdeFoundationPage.vue')
  const readback = readProject('frontend/src/meta/pages/components/RoutingVersionReadback.vue')

  assert.match(page, /\['routings', 'routingVersions'\]\.includes\(props\.pageKind\)/)
  assert.match(page, /props\.pageKind === 'routings' \? \(detailRow\.routingVersions \|\| \[\]\) : \[detailRow\]/)
  assert.match(readback, /版本与工序语义/)
  assert.match(readback, /stepRelationLabel/)
  assert.match(readback, /stepRelationshipSemanticsLabel/)
  assert.doesNotMatch(readback, /不可变快照已冻结/)
  assert.doesNotMatch(readback, /<el-button/)
  assert.doesNotMatch(readback, /@click=/)
})

test('工艺路线版本页继续使用企业列表共同契约且所有筛选类型受治理', () => {
  const definition = findPdePageDefinition('routingVersions')
  const page = readProject('frontend/src/meta/pages/PdeFoundationPage.vue')

  assert.match(page, /data-enterprise-list-contract="PCE-ENTERPRISE-LIST-CONTRACT-V1\.1"/)
  assert.match(page, /<PceEnterpriseListTable/)
  assert.match(page, /<PceBusinessStatus/)
  assert.equal(definition.filterSchema.every(item => Boolean(item.filterType)), true)
  assert.equal(definition.filterSchema
    .filter(item => item.filterType === 'select')
    .every(item => Array.isArray(item.options) && item.options.length > 0), true)
})
