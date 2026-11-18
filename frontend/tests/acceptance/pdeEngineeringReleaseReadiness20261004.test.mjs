import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  findPdePageDefinition,
  resolvePdeFlowAdjacency,
} from '../../src/meta/pages/pdePageDefinitions.js'
import { listPdeProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('第11节点复用正式流程身份并保持第10到第11节点邻接', () => {
  const definition = findPdePageDefinition('engineeringDocuments')
  const node = listPdeProcessNodes().find(item => item.nodeCode === 'engineering-data-release')
  const router = readFrontend('src/router/index.js')

  assert.equal(definition.title, '工程资料发布')
  assert.equal(definition.pageCode, 'pde-engineering-documents')
  assert.equal(definition.governance.currentFlowStep, '工程资料发布')
  assert.deepEqual(resolvePdeFlowAdjacency('工程资料发布'), {
    previous: '工艺路线版本管理',
    current: '工程资料发布',
    next: '工程变更ECN',
  })
  assert.equal(node?.sequence, 11)
  assert.equal(node?.pageUrl, '/pde/engineering-documents')
  assert.match(router, /path: 'pde\/engineering-documents',[\s\S]*?businessObject: 'PdeEngineeringDocuments',[\s\S]*?requiresServerAuthentication: true/)
})

test('第11节点以发布候选、精确版本、发布记录和阻断为员工可见只读合同', () => {
  const definition = findPdePageDefinition('engineeringDocuments')
  const fields = new Map(definition.columns.map(([field, label]) => [field, label]))
  assert.equal(definition.primaryField, 'releaseCandidateIdentity')
  assert.equal(definition.primaryLabel, '发布候选身份')
  const required = {
    manufacturingReleaseSubjectTypeLabel: '制造发布主体',
    manufacturingReleaseSubjectIdentity: '制造发布主体身份',
    productCategoryIdentity: '产品分类',
    engineeringBaselineIdentity: '工程基线',
    engineeringRevisionIdentity: '工程修订',
    releaseSubjectContractStatusLabel: '主体身份合同',
    sourceRecordIdentity: '工程来源身份与版本',
    productVersionIdentity: '产品版本身份',
    bomVersionIdentity: 'BOM版本身份',
    routingVersionIdentity: '工艺路线版本身份',
    engineeringDocumentVersionIdentity: '工程资料版本身份',
    manufacturingOutputIdentity: '制造发布记录',
    versionBindingLabel: '版本绑定方式',
    formalManufacturingEligibilityLabel: '正式制造资格',
    releaseBasisLabel: '发布依据',
    blockingSummary: '发布阻断原因',
    releaseActionLabel: '发布动作',
    statusLabel: '发布状态',
  }
  assert.deepEqual(Object.fromEntries(Object.keys(required).map(field => [field, fields.get(field)])), required)
  assert.equal(definition.governance.allowed.includes('✓ 查看发布候选'), true)
  assert.equal(definition.governance.forbidden.includes('× 无授权正式发布'), true)
  assert.equal(definition.relationshipFacts.some(value => value.includes('唯一解析结果只可作为候选')), true)
  assert.equal(definition.relationshipFacts.some(value => value.includes('制造发布主体二选一')), true)
  assert.equal(definition.relationshipFacts.some(value => value.includes('产品分类只回答产品归类')), true)

  const visibleText = [
    definition.title,
    definition.governance.purpose,
    ...definition.governance.allowed,
    ...definition.governance.forbidden,
    ...definition.relationshipFacts,
    ...definition.columns.map(([, label]) => label),
    ...definition.filterSchema.map(item => item.label),
  ].join('\n')
  assert.doesNotMatch(visibleText, /ORDER_ENGINEERED_PRODUCT|Schema/)
})

test('第11节点后端只读投影复用正式准入、资格、版本解析与公司范围', () => {
  const views = readProject('backend/pde/views.py')
  const block = views.slice(
    views.indexOf('class EngineeringDocumentListView'),
    views.indexOf('class ProductVersionListView'),
  )

  assert.match(block, /require_current_order_admission\(/)
  assert.match(block, /FormalManufacturingEligibilityService\.resolve\(instance\)/)
  assert.match(block, /ManufacturingStructureService\.resolve_effective_routing\(instance\)/)
  assert.match(block, /company_id=request\.user\.company_id/)
  assert.match(block, /routingResolverIsPersistedReleaseBinding": False/)
  assert.match(block, /databaseBusinessWriteCount": 0/)
  assert.match(block, /manufacturingReleaseSubjectTypeLabel": "订单工程产品"/)
  assert.match(block, /releaseSubjectContractGo": order_subject_contract_go/)
  assert.match(block, /schemaGapRequired": False/)
  assert.doesNotMatch(block, /现有制造发布模型要求长期产品定义/)
  assert.match(block, /本轮只读核验，正式发布动作未开放/)
  assert.doesNotMatch(block, /localStorage|mockRows|staticRows/)
  assert.doesNotMatch(block, /\.objects\.create\(|\.objects\.update\(|\.save\(|\.delete\(/)
})

test('发布状态边界包含草稿、失效、开发验证和已发布版本防覆盖保护', () => {
  const models = readProject('backend/pde/models.py')
  const eligibility = readProject('backend/pde/formal_manufacturing_eligibility_service.py')
  const service = readProject('backend/pde/production_foundation_service.py')

  assert.match(eligibility, /DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN/)
  assert.match(service, /\("released_to_manufacturing", "inactive"\)/)
  assert.match(service, /ORDER_ENGINEERING_NOT_CALCULATED/)
  assert.match(models, /失效或未发布版本禁止输出至制造/)
  assert.match(models, /已发布产品版本不可原地覆盖/)
  assert.match(models, /已发布工程资料版本不可原地覆盖/)
  assert.match(models, /已发布制造定义不可原地覆盖/)
  assert.match(models, /class ManufacturingReleaseSubjectType/)
  assert.match(models, /pde_mfg_release_subject_xor/)
  assert.match(models, /订单工程产品主体必须冻结已确认工程基线/)
})

test('共享页面壳以同一列定义驱动列表、详情、筛选和导出', () => {
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')

  assert.match(page, /definition\.value\.columns\.map\(\(\[field, label\]\) => \[field, label\]\)/)
  assert.match(page, /definition\.value\.columns\.map\(\(\[field, label\]\) => \(\{ field, label \}\)\)/)
  assert.match(page, /PceEnterpriseAdvancedFilter|PceEnterpriseListTable/)
})
