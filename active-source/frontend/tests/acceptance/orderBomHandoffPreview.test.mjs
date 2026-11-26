import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
const page = fs.readFileSync('src/meta/pages/PdeFoundationPage.vue', 'utf8')
const component = fs.readFileSync('src/meta/pages/components/OrderBomHandoffPreview.vue', 'utf8')
const api = fs.readFileSync('src/api/pde.js', 'utf8')
const view = fs.readFileSync('../backend/pde/views.py', 'utf8')
const definitions = fs.readFileSync('src/meta/pages/pdePageDefinitions.js', 'utf8')
const eligibility = fs.readFileSync('../backend/pde/formal_manufacturing_eligibility_service.py', 'utf8')
const lifecycle = fs.readFileSync('../backend/pde/production_foundation_service.py', 'utf8')
test('BOM handoff and existing foundation compile', () => {
  for (const source of [page, component]) {
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    compileScript(descriptor, { id: 'handoff' })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'handoff.vue', id: 'handoff' }).errors, [])
  }
})
test('only original BOM page opts into readonly response', () => {
  assert.match(page, /props.pageKind === 'boms' \? \{ handoff: '1'/)
  assert.match(page, /current !== refreshSequence/)
  assert.match(page, /refreshSequence \+= 1/)
  assert.match(page, /observability\?\.unregister\?\.\(provider\)/)
})
test('line and object return preserve mounted enterprise table and local filters', () => {
  assert.match(component, /返回整单承接汇总/)
  assert.match(component, /返回对象清单/)
  assert.match(component, /data-acceptance-id="return-object-list" @click="returnObjectList"/)
  assert.match(component, /data-acceptance-id="return-handoff-summary" @click="returnSummary"/)
  assert.match(component, /ref="objectListTop"[^>]+data-acceptance-id="handoff-object-list"/)
  assert.match(component, /v-show="!detailObject"/)
  assert.match(component, /PceEnterpriseListTable/)
  const returnObjectListFunction = component.match(/async function returnObjectList\(\)[^\n]+/)[0]
  assert.match(returnObjectListFunction, /detailObject\.value = null/)
  assert.match(returnObjectListFunction, /objectListTop\.value\?\.scrollIntoView/)
  assert.doesNotMatch(returnObjectListFunction, /selectedRecord\.value = null|clearFilters|clearSort|history|router/)
  const returnFunction = component.match(/async function returnSummary\(\)[^\n]+/)[0]
  assert.doesNotMatch(returnFunction, /clearFilters|clearSort|history|router/)
})
test('no write api storage or frontend quantity calculations', () => {
  assert.doesNotMatch(component, /pdeApi|localStorage|sessionStorage|\.post\(|generateBom|executeEngineering|\beval\(/)
  assert.match(component, /fact.valueText/)
  assert.match(component, /fact.quantityBasis/)
  assert.match(component, /candidateQuantity|候选材料用量：未确认/)
})
test('BOM page exposes the server gate and invokes the existing readonly preview service', () => {
  assert.match(component, /Business Purpose/)
  assert.match(component, /DEVELOPMENT_VALIDATION|businessPurpose\?\.code/)
  assert.match(component, /data-acceptance-id="preview-bom-conditions"/)
  assert.match(component, /data-acceptance-id="generate-bom-draft-disabled"/)
  assert.match(component, /:disabled="!facts\.bomHandoffStatus\?\.canGenerate"/)
  assert.match(component, /data-acceptance-id="bom-preview-gate-detail"/)
  assert.match(component, /状态代码/)
  assert.match(page, /pdeApi\.previewOrderBom\(record\.calculationId\)/)
  assert.match(page, /response\.error\?\.code/)
  assert.match(api, /method: 'GET'[\s\S]+bom-preview/)
  assert.match(view, /OrderEngineeringClosureService\.preview_bom/)
  assert.doesNotMatch(page + component, /generateOrderBom\(/)
})
test('gate counts keep candidate preview separate from formal requirement and BOM counts', () => {
  for (const token of [
    '缺Material业务组', 'Mapping确认卡', 'READY_FOR_REQUIREMENT',
    '正式材料需求', 'ProductBOM', 'businessWriteSideEffectCount',
  ]) assert.match(component + page, new RegExp(token))
  assert.match(component, /不生成材料需求、不创建BOM草稿、不占用BOM编号、不发布BOM/)
  assert.match(component, /不进入Routing或Planning/)
})
test('formal confirmations use server readback and the page stays readonly', () => {
  for (const token of [
    'confirmed-representative-material-requirements', '已确认代表性 Mapping',
    '整单待完成对象', '可预览Calculation', 'pendingDecisionUnitCount',
    'ExternalIdentity', 'acceptanceStatusLabel',
    'grossQuantity', 'scrapRate', 'databaseBusinessWriteCount',
  ]) assert.match(component, new RegExp(token))
  assert.doesNotMatch(component, /MRC-001、MRC-002 与 19 个 MRG 组继续待确认/)
  assert.match(page, /BOM_PARTIAL_PREVIEW_AVAILABLE/)
  assert.match(page, /MATERIAL_REQUIREMENT_REQUIRED/)
  assert.match(page, /partialPreview/)
  assert.doesNotMatch(page + component, /generateOrderBom\(/)
})
test('BOM version management projects order lineage purpose eligibility and coverage', () => {
  for (const token of [
    'orderNo', 'orderLineNo', 'orderEngineeringInstanceNo', 'sourceCalculationNo',
    'businessPurposeLabel', 'formalManufacturingEligibilityLabel',
    'formalManufacturingDecisionCode', 'coverageStatus',
    'confirmedRequirementObjectCount', 'remainingObjectCount',
  ]) assert.match(definitions, new RegExp(token))
  assert.match(definitions, /DEVELOPMENT_VALIDATION仅允许draft与只读验证/)
  assert.match(view, /FormalManufacturingEligibilityService\.resolve\(obj\)/)
})
test('formal manufacturing lifecycle uses one fail-closed eligibility service', () => {
  for (const token of [
    'DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN',
    'BUSINESS_PURPOSE_EVIDENCE_MISSING',
    'BUSINESS_PURPOSE_EVIDENCE_CONFLICT',
    'FORMAL_MANUFACTURING_ORDER_TRACE_BROKEN',
  ]) assert.match(eligibility, new RegExp(token))
  assert.match(lifecycle, /FormalManufacturingEligibilityService\.resolve\(instance\)/)
  assert.match(lifecycle, /target_status in \{"reviewed", "released"\}/)
  assert.match(lifecycle, /target_status in \{"engineering_review", "released_to_manufacturing"\}/)
})
test('BOM canonical identity is one additive registration', () => {
  const registry = fs.readFileSync('src/meta/governance/businessNameRegistry.js', 'utf8')
  assert.equal((registry.match(/\['PdeProductBoms'/g) || []).length, 1)
  assert.match(registry, /'BOM管理','pde-product-boms','\/pde\/product-boms'/)
})
