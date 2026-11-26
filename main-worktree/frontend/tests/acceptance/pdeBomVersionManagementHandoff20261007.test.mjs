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

const definition = () => findPdePageDefinition('bomVersions')

test('01 BOM版本管理继续使用现有正式节点、路由和页面资源', () => {
  const page = definition()
  assert.equal(page.pageCode, 'pde-bom-versions')
  assert.equal(page.nodeCode, 'bom-version-management')
  assert.equal(page.resource, 'bom-versions')
  assert.equal(page.governance.navigation.current.pageUrl, '/pde/bom-versions')
  assert.equal(page.governance.navigation.previous.label, 'BOM管理')
  assert.equal(page.governance.navigation.next.label, '工艺路线管理')
})

test('02 用户可直接识别同一正式对象链和来源数量', () => {
  const fields = new Set(definition().columns.map(([field]) => field))
  fields.add(definition().primaryField)
  for (const field of [
    'companyCode', 'orderNo', 'orderLineNo', 'orderEngineeringInstanceNo',
    'bomCode', 'productBomId', 'bomVersionId', 'bomVersionNo',
    'sourceCalculationNo', 'sourceCalculationId', 'materialCount',
    'sourceRequirementCount', 'sourceIntegrityLabel', 'statusLabel',
  ]) {
    assert.equal(fields.has(field), true, `missing visible field ${field}`)
  }
})

test('03 页面只允许独立合法人员依次正式评审和发布并禁止推进下游', () => {
  const governance = definition().governance
  assert.match(governance.purpose, /独立正式人员依次完成人工评审与发布决定/)
  assert.equal(governance.forbidden.some(value => value.includes('重新生成BOM')), true)
  assert.equal(governance.forbidden.some(value => value.includes('绕过权限/Workflow')), true)
  assert.equal(governance.allowed.some(value => value.includes('独立合法发布人')), true)
  assert.equal(governance.forbidden.some(value => value.includes('重复发布')), true)
  assert.equal(governance.forbidden.some(value => value.includes('进入工艺路线')), true)
})

test('04 高级筛选继续使用受治理filterType契约', () => {
  const schema = definition().filterSchema
  assert.equal(schema.every(field => Boolean(field.filterType)), true)
  for (const field of schema.filter(item => item.filterType === 'select')) {
    assert.equal(Array.isArray(field.options) && field.options.length > 0, true)
  }
})

test('05 服务端沿正式主外键链Fail-Closed并返回同一五表面事实', () => {
  const source = readProject('backend/pde/views.py')
  const start = source.indexOf('class BomVersionListView')
  const end = source.indexOf('class RoutingVersionListView')
  const block = source.slice(start, end)
  assert.match(block, /BOM_VERSION_HANDOFF_SCOPE_INCONSISTENT/)
  assert.match(block, /obj\.bom\.order_engineering_instance_id == obj\.order_engineering_instance_id/)
  assert.match(block, /obj\.source_calculation\.sales_order_item_id == order_item\.pk/)
  assert.match(block, /project_product_bom_material_detail/)
  assert.match(block, /bomVersionHandoffs/)
  assert.match(block, /apiFacts.*pageFacts.*diagnosticFacts.*strictFacts.*acceptanceFacts/s)
  assert.match(block, /databaseBusinessWriteCount["']?: 0/)
  assert.doesNotMatch(block, /objects\.create\(|\.save\(|objects\.update\(|generate_bom\(/)
})

test('06 页面直接消费服务端rows且状态只显示服务端中文标签', () => {
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  assert.match(page, /rows\.value = payload\.rows \|\| \[\]/)
  assert.match(page, /column\[0\] === 'statusLabel' \|\| column\[0\]\.endsWith\('StatusLabel'\)/)
  assert.match(page, /:status-label="row\[column\[0\]\]"/)
  assert.doesNotMatch(page, /SO202609180003|CALC-3|OBOM-OEI202609000001/)
})

test('07 正式运行代码不硬编码本次生产样本', () => {
  const source = [
    readProject('backend/pde/views.py'),
    readFrontend('src/meta/pages/pdePageDefinitions.js'),
  ].join('\n')
  for (const literal of ['SO202609180003', 'OBOM-OEI202609000001', 'CALC-3']) {
    assert.doesNotMatch(source, new RegExp(literal))
  }
})
