import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { findPdePageDefinition } from '../../src/meta/pages/pdePageDefinitions.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('第9节点列表明确显示工艺路线定义状态且不改变列表主结构', () => {
  const routing = findPdePageDefinition('routings')
  const statusColumn = routing.columns.find(([field]) => field === 'definitionStatusLabel')

  assert.deepEqual(statusColumn, ['definitionStatusLabel', '路线定义状态', 160])
  assert.equal(routing.columns.some(([field]) => field === 'routingVersions'), false)
  assert.equal(routing.filterSchema.some(item => (
    item.field === 'definitionStatusLabel'
    && item.filterType === 'select'
    && Array.isArray(item.options)
  )), true)
})

test('Routing详情复用正式服务端FK投影并只增加只读Version/Step区块', () => {
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  const readback = readFrontend('src/meta/pages/components/RoutingVersionReadback.vue')

  assert.match(page, /props\.pageKind === 'routings'/)
  assert.match(page, /props\.pageKind === 'routings' \? \(detailRow\.routingVersions \|\| \[\]\) : \[detailRow\]/)
  assert.match(readback, /data-projection-source="server-fk"/)
  assert.match(readback, /工艺路线版本状态/)
  assert.match(readback, /当前有效/)
  assert.match(readback, /工序数量/)
  assert.match(readback, /工序编码/)
  assert.match(readback, /车间/)
  assert.match(readback, /工作中心/)
  assert.match(readback, /stepRelationshipSemanticsLabel/)
  assert.doesNotMatch(readback, /<el-button/)
  assert.doesNotMatch(readback, /@click=/)
})

test('服务端投影只沿RoutingVersion.routing与RoutingStep.operation正式关系读取', () => {
  const views = readProject('backend/pde/views.py')
  const routingBlock = views.slice(
    views.indexOf('class RoutingListView'),
    views.indexOf('class EngineeringDocumentListView'),
  )

  assert.match(routingBlock, /obj\.versions\.select_related\(/)
  assert.match(routingBlock, /version\.steps\.select_related\(/)
  assert.match(routingBlock, /"operationSourceLabel": "system\.Process（RoutingStep\.operation正式FK）"/)
  assert.match(routingBlock, /"relationLabel": f"RoutingVersion\.routing_id=\{obj\.pk\}（正式FK）"/)
  assert.match(routingBlock, /"definitionStatusLabel": obj\.get_status_display\(\)/)
  assert.match(routingBlock, /"routingVersions": version_rows/)
  assert.doesNotMatch(routingBlock, /filter\(routing_code=/)
  assert.doesNotMatch(routingBlock, /filter\(name=/)
})

test('第10节点复用正式RoutingVersion只读投影并提供完整可定位身份', () => {
  const routingVersion = findPdePageDefinition('routingVersions')
  const fields = routingVersion.columns.map(([field]) => field)
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  const views = readProject('backend/pde/views.py')
  const listView = views.slice(
    views.indexOf('class RoutingVersionListView'),
    views.indexOf('class EngineeringChangeListView'),
  )

  for (const field of [
    'definitionId', 'routingCode', 'routingName', 'definitionStatusLabel',
    'versionId', 'revision', 'stepCount', 'statusLabel',
    'companyCode', 'orderNo', 'orderLineNo', 'orderEngineeringInstanceNo',
    'bomCode', 'bomVersionNo', 'sourceCalculationNo', 'sourceIntegrityLabel',
    'routingVersionHandoffStatusLabel', 'stepRelationshipSemanticsLabel',
    'engineeringDocumentReleaseEligibilityLabel',
  ]) {
    assert.equal(fields.includes(field), true, `Node10 list must show ${field}`)
  }
  for (const field of ['orderNo', 'routingCode', 'routingName', 'routingVersionNo', 'versionNo']) {
    assert.equal(routingVersion.searchFields.includes(field), true, `Node10 search must include ${field}`)
  }
  assert.match(page, /definition\.value\.columns\.map\(\(\[field, label\]\) => \[field, label\]\)/)
  assert.match(page, /Object\.entries\(detailRow\.value \|\| \{\}\)/)
  assert.match(listView, /"definitionId": obj\.routing_id/)
  assert.match(listView, /"versionId": obj\.pk/)
  assert.match(listView, /"routingName": obj\.routing\.name/)
  assert.match(listView, /"revision": obj\.revision/)
  assert.match(listView, /"stepCount": version_projection\.get\("stepCount", obj\.steps\.count\(\)\)/)
  assert.match(listView, /"definitionStatusLabel": obj\.routing\.get_status_display\(\)/)
  assert.match(listView, /"versionStatusLabel": obj\.get_status_display\(\)/)
})

test('第10节点员工可见身份表头、筛选、详情和导出统一使用中文名称', () => {
  const routingVersion = findPdePageDefinition('routingVersions')
  const columnLabels = new Map(routingVersion.columns.map(([field, label]) => [field, label]))
  const filterLabels = new Map(routingVersion.filterSchema.map(({ field, label }) => [field, label]))
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')

  assert.deepEqual(Object.fromEntries([
    'definitionId', 'routingCode', 'routingName', 'definitionStatusLabel',
    'versionId', 'revision', 'statusLabel',
  ].map(field => [field, columnLabels.get(field)])), {
    definitionId: '工艺路线ID',
    routingCode: '工艺路线编码',
    routingName: '工艺路线名称',
    definitionStatusLabel: '工艺路线状态',
    versionId: '工艺路线版本ID',
    revision: '修订号',
    statusLabel: '工艺路线版本状态',
  })
  assert.equal(filterLabels.get('routingCode'), '工艺路线编码')
  assert.equal(filterLabels.get('statusLabel'), '工艺路线版本状态')
  assert.deepEqual(routingVersion.relationshipFacts, [
    '按单正式链：公司 → 销售订单 → 订单行 → OEI → ProductBOM → BOMVersion → 工艺路线 → 工艺路线版本 → 工序',
    '当前版本直接拥有版本范围工序定义；模型未单独声明不可变序列化快照',
    '本节点只读核验版本身份和工序范围，不创建、不改版、不发布、不进入工程资料发布',
  ])
  assert.deepEqual(routingVersion.searchFields, [
    'companyCode', 'orderNo', 'orderEngineeringInstanceNo', 'bomCode',
    'bomVersionNo', 'sourceCalculationNo', 'routingCode', 'routingName',
    'routingVersionNo', 'versionNo', 'versionId', 'routingVersionHandoffStatusLabel',
  ])

  const employeeVisibleLabels = [
    ...routingVersion.columns.map(([, label]) => label),
    ...routingVersion.filterSchema.map(({ label }) => label),
    ...routingVersion.relationshipFacts,
  ].join('\n')
  assert.doesNotMatch(employeeVisibleLabels, /Routing Definition|Routing Version|Routing Code|Routing Name|Revision|ProductVersion|EMD|MES/)

  // 列定义是列表、详情和导出字段显示名称的同一权威来源。
  assert.match(page, /definition\.value\.columns\.map\(\(\[field, label\]\) => \[field, label\]\)/)
  assert.match(page, /definition\.value\.columns\.map\(\(\[field, label\]\) => \(\{ field, label \}\)\)/)
  assert.match(page, /label: labels\.value\.get\(field\)/)
})

