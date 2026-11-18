import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(path.join(root, 'frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue'), 'utf8')
const handoff = fs.readFileSync(path.join(root, 'frontend/src/meta/pages/components/OrderBomHandoffPreview.vue'), 'utf8')
const api = fs.readFileSync(path.join(root, 'frontend/src/api/pde.js'), 'utf8')
const service = fs.readFileSync(path.join(root, 'backend/pde/order_bom_handoff_service.py'), 'utf8')

test('existing engineering page compiles with the additive material preview', () => {
  const { descriptor, errors } = parse(page)
  assert.deepEqual(errors, [])
  compileScript(descriptor, { id: 'material-r1-preview' })
  assert.deepEqual(compileTemplate({
    source: descriptor.template.content,
    filename: 'PdeOrderEngineeringCalculationPage.vue',
    id: 'material-r1-preview',
  }).errors, [])
})

test('material summary uses one read-only server projection and separates candidates from formal readback', () => {
  assert.match(api, /orderBomHandoff\(params = \{\}\)/)
  assert.match(api, /method: 'GET'/)
  assert.match(api, /params: \{ handoff: 1, \.\.\.params \}/)
  assert.match(page, /data-section="material-requirement-handoff-preview"/)
  assert.match(page, /data-preview-mode="r1-no-recalc-readback"/)
  assert.match(page, /候选行不冒充正式材料清单/)
  assert.match(page, /materialRequirementHandoff: materialRequirementHandoff\.value/)
  assert.doesNotMatch(page, /saveMaterialRequirement|generateMaterialRequirement/)
})

test('mapping contract and 71-object mutually exclusive statuses are explicit', () => {
  for (const token of [
    'PCE-MATERIAL-REQUIREMENT-MAPPING-V1',
    'CONFIRMED', 'READY_FOR_REQUIREMENT', 'MISSING_MATERIAL', 'MISSING_MAPPING', 'MISSING_UOM',
    'AMBIGUOUS_MATERIAL', 'MISSING_QUANTITY_CONTRACT', 'NOT_APPLICABLE',
    'PER_SALES_ITEM_UNIT', 'ORDER_TOTAL', 'SAVED_DERIVED_FACT', 'SOURCE_FACT_VALUE',
  ]) assert.match(service, new RegExp(token))
  assert.match(service, /classificationClosed/)
  assert.match(service, /databaseBusinessWriteCount": 0/)
  assert.match(service, /implicitUomConversionCount": 0/)
  assert.match(service, /REUSE_ENGINEERING_RULE_DEFINITION_JSON/)
  assert.match(service, /schemaChangeRequired": False/)
})

test('BOM gate still consumes formal requirements only', () => {
  assert.match(service, /MATERIAL_REQUIREMENT_REQUIRED/)
  assert.match(service, /Preview候选不作为正式EngineeringMaterialRequirement/)
  assert.match(page, /Preview候选不替代EngineeringMaterialRequirement/)
  assert.match(page, /:disabled="!bomPreview\?\.previewHash \|\| busy \|\| !materialRequirementPreview\.bomGate\?\.canGenerate"/)
})

test('material matching and UOM are exact and never fuzzy-converted', () => {
  assert.match(service, /仅正式Material\.code精确匹配/)
  assert.match(service, /不做名称或字符串相似绑定/)
  assert.match(service, /SOURCE_FACT_UOM_CONVERSION_NOT_ALLOWED/)
  assert.match(service, /OUTPUT_UOM_MUST_EQUAL_MATERIAL_BASE_UOM/)
  assert.doesNotMatch(service, /difflib|SequenceMatcher|fuzzy/)
})

test('business confirmation pack compresses rows and readbacks only exact confirmed representatives', () => {
  for (const token of [
    'material-mapping-business-confirmation-package', '待业务确认',
    'READY_FOR_BUSINESS_CONFIRMATION', 'MATERIAL_IDENTITY_REQUIRED',
    'QUANTITY_RULE_REQUIRED', 'UOM_DEFINITION_REQUIRED', 'BUSINESS_FACT_REQUIRED',
    'MULTIPLE_EXISTING_CANDIDATES', 'INSUFFICIENT_BUSINESS_FACTS',
  ]) assert.match(page + service, new RegExp(token))
  assert.match(service, /automaticMaterialBindingCount": 0/)
  assert.match(service, /confirmedMappingCount/)
  assert.match(service, /pendingDecisionUnitCount/)
  assert.match(service, /mappingWriteCount/)
  assert.match(service, /requirementWriteCount/)
  assert.match(service, /PER_SALES_ITEM_UNIT/)
  assert.match(service, /APPLY_ONCE/)
  assert.match(service, /"savedDerivedFacts": _fact_options\(obj\)/)
  assert.match(page, /查看全部已保存Fact选项/)
  assert.match(page, /card\.salesOrderItem\?\.quantity/)
  assert.match(page, /card\.requiredConfirmers\?\.join/)
  assert.match(page, /页面没有确认、批准或发布动作，当前只读展示正式结果/)
  assert.match(page, /CONFIRMED/)
  assert.doesNotMatch(page, /approveMaterialMapping|publishMaterialMapping|confirmMaterialMapping/)
})

test('Item4 formal readback renders existing identities and removes stale fixed confirmation copy', () => {
  for (const token of [
    'Mapping ID：', 'EngineeringMaterialRequirement', 'ExternalIdentity',
    'card.acceptanceStatusLabel', 'row.confirmedMappingIds', 'row.formalRequirementIds',
    'mappingReadbackCount', 'requirementReadbackCount',
  ]) assert.match(page + handoff + service, new RegExp(token))
  assert.match(service, /sourceExternalIdentity/)
  assert.match(service, /"acceptanceStatus": "CONFIRMED"/)
  assert.match(service, /"mappingWriteCount"\] = 0/)
  assert.match(service, /"requirementWriteCount"\] = 0/)
  assert.doesNotMatch(page + handoff, /仅MRC-003、MRC-004|原23单元中只确认MRC-003\/004|19 个 MRG 组/)
})
