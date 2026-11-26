import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(
  path.join(root, 'frontend/src/meta/components/ProductionFoundationMaintenance.vue'),
  'utf8',
)
const view = fs.readFileSync(path.join(root, 'backend/pde/views.py'), 'utf8')
const service = fs.readFileSync(
  path.join(root, 'backend/pde/formal_engineering_continuation_service.py'),
  'utf8',
)

test('候选材料与服务端正式规则分开展示且不会冒充草稿', () => {
  assert.match(page, /data-section="engineering-rule-registration-materials"/)
  assert.match(page, /candidate\.registrationStatusLabel/)
  assert.match(service, /待登记材料，尚未形成正式规则/)
  assert.match(page, /与下方服务端正式规则分开统计/)
  assert.match(page, /formalRecordCount/)
  assert.match(page, /查看材料不会新建草稿、改变规则状态或读取订单、来源、基线及核算结果/)
})

test('候选材料由服务端可执行规则包合同生成且只在规则实体响应', () => {
  assert.match(service, /def formal_rule_registration_materials\(\)/)
  assert.match(service, /formal_rule_blueprints\(\)/)
  assert.match(service, /specification_hash\(blueprint\["specification"\]\)/)
  assert.match(view, /if entity == "engineering-rule-definitions"/)
  assert.match(view, /engineeringRuleRegistrationCandidates/)
})

test('现成方案以中文业务说明形成未保存预览并保留方案自带V1', () => {
  assert.match(page, /填写登记资料/)
  assert.match(page, /未保存登记资料，尚未形成正式规则/)
  assert.match(page, /规则用于什么/)
  assert.match(page, /适用对象/)
  assert.match(page, /不适用／停止条件/)
  assert.match(page, /需要的输入/)
  assert.match(page, /主要计算关系／条件分支/)
  assert.match(page, /产生的结果/)
  assert.match(page, /精度与版本/)
  assert.match(page, /取消本次登记/)
  assert.match(page, /payload\.version = candidate\.version/)
  assert.match(page, /未来自定义规则仍沿用通用首版V1\.0/)
  assert.match(service, /"businessExplanation"/)
  assert.match(service, /def formal_rule_business_explanation/)
  assert.match(view, /row\["businessExplanation"\] = formal_rule_business_explanation/)
})

test('登记预览不会自动保存且评审角色看到真实工作队列空态', () => {
  assert.match(page, /当前暂无待评审／待发布/)
  assert.match(page, /candidate\.formalRecordCount/)
  assert.match(page, /prepareRuleCandidate/)
  const previewStart = page.indexOf('async function prepareRuleCandidate')
  const previewEnd = page.indexOf('function clearRuleRegistrationInputs', previewStart)
  assert.ok(previewStart >= 0 && previewEnd > previewStart)
  assert.doesNotMatch(page.slice(previewStart, previewEnd), /saveProductionFoundation/)
})
