import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  PDE_PAGE_VERSION,
  findPdePageDefinition,
  resolvePdeFlowAdjacency,
} from '../../src/meta/pages/pdePageDefinitions.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('第11节点保持10→11→12正式邻接且本轮只读', () => {
  const definition = findPdePageDefinition('engineeringDocuments')
  assert.equal(PDE_PAGE_VERSION, 'V1.14.2.8.4.10.10')
  assert.equal(definition.title, '工程资料发布')
  assert.deepEqual(resolvePdeFlowAdjacency('工程资料发布'), {
    previous: '工艺路线版本管理',
    current: '工程资料发布',
    next: '工程变更ECN',
  })
  assert.equal(definition.governance.navigation.previous.label, '工艺路线版本管理')
  assert.equal(definition.governance.navigation.next.label, '工程变更ECN')
  assert.equal(definition.governance.forbidden.includes('× 无授权正式发布'), true)
  assert.equal(definition.governance.forbidden.includes('× 无授权创建资料'), true)
  assert.equal(definition.relationshipFacts.some(value => value.includes('上游产品、核算、BOM和工艺路线事实不等于正式工程资料')), true)
})

test('员工可见合同区分正式资料数量、可发布数量和已发布数量', () => {
  const definition = findPdePageDefinition('engineeringDocuments')
  const labels = new Map(definition.columns.map(([field, label]) => [field, label]))
  const required = {
    nodeHandoffStatusLabel: '节点承接状态',
    companyCode: '公司',
    documentNo: '资料编号',
    documentName: '资料名称',
    documentTypeLabel: '资料类型',
    version: '当前资料版本',
    documentVersionStatusLabel: '资料版本状态',
    engineeringDocumentCount: '工程资料数量',
    engineeringDocumentVersionCount: '资料版本数量',
    publishableEngineeringDocumentCount: '可发布资料数量',
    releasedEngineeringDocumentCount: '已发布资料数量',
    currentDocumentStatusLabel: '当前资料状态',
    documentAvailabilityStatusLabel: '可发布资料状态',
    productBomId: 'ProductBOM ID',
    bomVersionStatusLabel: 'BOM版本状态',
    routingVersionStatusLabel: '工艺路线版本状态',
    routingStepCount: '版本工序数量',
    nextBusinessActionLabel: '下一业务动作',
  }
  assert.deepEqual(
    Object.fromEntries(Object.keys(required).map(field => [field, labels.get(field)])),
    required,
  )
  assert.equal(definition.filterSchema.every(field => Boolean(field.filterType)), true)
})

test('专用Readback给出真实空状态、完整上游链和一次性人工输入说明', () => {
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  const component = readFrontend('src/meta/pages/components/EngineeringDocumentReleaseReadback.vue')

  assert.match(page, /EngineeringDocumentReleaseReadback/)
  assert.match(page, /pageKind === 'engineeringDocuments'/)
  assert.match(component, /当前暂无可发布工程资料/)
  assert.match(component, /上游工程数据已经承接，但上游数据不等于正式工程资料/)
  assert.match(component, /工程资料数量|可发布资料|已发布资料/)
  assert.match(component, /公司|销售订单 \/ 行|订单工程实例|ProductBOM|BOMVersion|工艺路线版本/)
  assert.match(component, /必填|可选|物理文件类型|业务对象关系|版本号|发布说明|人工确认发布/)
  assert.match(component, /engineering-document-release-detail-readback/)
})

test('服务端投影按正式关系计数并对归属冲突Fail-Closed', () => {
  const views = readProject('backend/pde/views.py')
  const block = views.slice(
    views.indexOf('class EngineeringDocumentListView'),
    views.indexOf('class ProductVersionListView'),
  )

  assert.match(block, /def _document_scope_facts\(instance\)/)
  assert.match(block, /Q\(order_engineering_instance=instance\)/)
  assert.match(block, /ownershipConflicts/)
  assert.match(block, /工程资料版本无法证明归属当前订单行/)
  assert.match(block, /documentOwnershipConflictCount/)
  assert.match(block, /publishableEngineeringDocumentCount/)
  assert.match(block, /releasedEngineeringDocumentCount/)
  assert.match(block, /publicationExecutedThisRound": False/)
  assert.match(block, /databaseBusinessWriteCount": 0/)
  assert.doesNotMatch(block, /\.objects\.create\(|\.objects\.update\(|\.save\(|\.delete\(/)
})

test('既有正式资料模型没有被伪装成物理文件存储', () => {
  const models = readProject('backend/pde/models.py')
  const documentBlock = models.slice(
    models.indexOf('class EngineeringDocument(models.Model):'),
    models.indexOf('class ProductVersion(models.Model):'),
  )
  const versionBlock = models.slice(
    models.indexOf('class EngineeringDocumentVersion(models.Model):'),
    models.indexOf('class EffectiveDateControl(models.Model):'),
  )

  assert.match(documentBlock, /\("process", "工艺文件"\)/)
  assert.match(documentBlock, /\("technical", "技术资料"\)/)
  assert.match(documentBlock, /\("version_record", "版本记录"\)/)
  assert.doesNotMatch(`${documentBlock}\n${versionBlock}`, /FileField|ImageField|storage_key|mime_type|attachment_id|file_hash/)
  assert.match(versionBlock, /related_bom = models\.ForeignKey\(BOMVersion/)
  assert.match(versionBlock, /related_routing = models\.ForeignKey\(RoutingVersion/)
})
