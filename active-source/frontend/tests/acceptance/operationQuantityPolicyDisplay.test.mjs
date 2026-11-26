import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'

// Run actual component display mappings, templates and request validators.
// Synthetic contracts and optional captured native responses only: no HTTP/DB/browser.
const url = new URL('../../src/meta/components/OperationWorkloadSourcePanel.vue', import.meta.url)
const source = readFileSync(url, 'utf8')
const { descriptor } = parse(source, { filename: url.pathname })
const script = descriptor.scriptSetup.content
function actualFunction(name) {
  const match = script.match(new RegExp(`function ${name}\\([^]*?\\n\\}`))
  assert.ok(match, `Actual component function ${name} is present`)
  return match[0]
}
const names = ['serverDisplayLabel', 'conditionalExecutionLabels', 'quantityText', 'recordCountText',
  'sourceInputText', 'quantityContractText', 'reasonLabel', 'canonicalSnapshot', 'validateFacts',
  'validateRequestedScope', 'validateCapacitySemantics', 'validateInputPreparation',
  'validateConditionalPreparation', 'validateQuantityPolicy', 'validateQuantityPolicyPreparation', 'validateRouteFacts']
const functions = names.map(actualFunction).join('\n')
const actual = new Function('CONTRACT', `${functions}\nreturn { ${names.join(', ')} }`)('PCE-OPERATION-WORKLOAD-SOURCE-V1')
const routeMapping = script.slice(script.indexOf('const routeRows = computed('), script.indexOf('const routeListContract ='))
const mappedRows = new Function('computed', 'routeConfiguration', `${functions}\n${routeMapping}\nreturn routeRows`)
const scope = { companyId: 6801, productionPlanId: 6802, manufacturingOutputId: 6803, mainCalculationId: 6804,
  salesOrderItemId: 6805, baselineId: 6806, routingVersionId: 6807, routingStepId: 6808, operationId: 6809, productTypeId: 6810 }
const sourceStepId = 6811
const sourceOperationId = 6812
const contract = 'PCE-OPERATION-QUANTITY-POLICY-V1'
const reference = () => ({ uomId: 6813, uomCode: 'ISOLATED_LENGTH', uomLabel: '隔离长度单位',
  sourceCompanyId: scope.companyId, sourceProductionPlanId: scope.productionPlanId,
  sourceRoutingVersionId: scope.routingVersionId, sourceRoutingStepId: sourceStepId,
  sourceOperationId, statusLabel: '引用同路线已验证来源工序的有效统计单位', proofHash: 'a'.repeat(64) })
function policy() {
  return { contractVersion: contract, measurementMode: 'NOT_SEPARATELY_MEASURED', exactScope: { ...scope },
    formalPolicyValidated: true, statusLabel: '常规必经配套，本工序不单独计量',
    scopeDeterminationLabel: '实际处理范围依图纸及现场确定，不预造逐门逐边覆盖',
    plannedQuantity: null, plannedQuantityReasonLabel: '随前工序配套，不单列计划投产量，数值留空',
    actualQuantity: null, actualQuantityReasonLabel: '不单列本工序实际产量，数值留空',
    statisticalUomReference: reference(), capacityIndependenceLabel: '统计单位仅供口径引用；原0产能及其历史面积单位独立保留' }
}
const capacity = () => ({ contractVersion: 'PCE-CAPACITY-TRISTATE-V1', valid: true, meaningCode: 'NON_QUANTIFIED',
  statusLabel: '经过但无法准确核算，不计定量产能占用', sourceStatusLabel: '正式产能来源有效',
  recordPresenceStatusLabel: '已有正式标准产能记录', quantitativeOccupancyAllowed: false, independentDurationAllowed: false })
function ordinaryPreparation() {
  const entry = { exactStatement: '隔离用户正式答复原文', reference: '隔离答复档案', referenceSha256: 'b'.repeat(64) }
  return { contractVersion: 'PCE-OPERATION-INPUT-PREPARATION-V1', factSource: 'server',
    currentStateSource: 'server', exactScope: { ...scope }, recordStatus: 'RECORDED',
    recordId: 6814, revision: 1, contextHash: 'c'.repeat(64), inputStandardStatus: 'PENDING_CONFIRMATION',
    businessBasis: { entries: [entry] }, businessBasisPresentation: [{ ...entry, entryIndex: 0, statusLabel: '原答复依据' }],
    statusLabel: '正式准备记录', inputStandardStatusLabel: '投入标准待确认', capacityMeasurementStatusLabel: '正式裁决未定',
    formalRuleStatusLabel: '不授予规则发布资格', scopeLabel: '隔离准确计划步骤', remainingItems: [],
    sourceQuantity: null, inputQuantity: null, capacityQuantity: null, capacityMeasurementStatus: null,
    capacityBusinessValue: null, capacityResolution: { valid: false, statusLabel: '正式未定裁决' },
    formalRulePublished: false, readyForGeneration: false, readyForAllocation: false, readyForScheduling: false,
    businessWriteCount: 0, auditWriteCount: 0, stateTransitionWriteCount: 0, supportWriteCount: 0,
    isPersisted: true, auditIds: [6815], writeRequestId: 6816, sourceIdentityId: 6817,
    statusTransitionHistory: [{ id: 6818 }], statusTransitionCount: 1, stateMachineConsistent: true }
}
function preparation() {
  const value = ordinaryPreparation()
  Object.assign(value, { statusCode: 'NOT_SEPARATELY_MEASURED', formalPolicyValidated: true, quantityPolicy: policy(),
    context: { contractVersion: contract, exactScope: { ...scope } },
    inputStandardStatusLabel: '本工序不单独计量，无独立计划投产量及实际产量',
    capacityMeasurementStatus: 'zero_capacity', capacityBusinessValue: 0,
    capacityResolution: { valid: true, code: 'FORMAL_AUXILIARY_ZERO_REFERENCE',
      formalStandardCapacityPresent: true, originalConclusionRevoked: false, statusLabel: '独立引用原正式0产能' } })
  value.businessBasis.quantityPolicy = { contractVersion: contract, measurementMode: 'NOT_SEPARATELY_MEASURED',
    plannedQuantity: null, actualQuantity: null, nullReason: 'NOT_SEPARATELY_MEASURED',
    scopeDetermination: 'DRAWING_AND_SITE', objectCoverageClaimed: false,
    statisticalUomReference: { referenceType: 'ROUTE_STEP_SOURCE_CONFIGURATION', routingStepId: sourceStepId },
    capacityReference: { standardCapacityId: 6819 } }
  return value
}
function conditionalPreparation() {
  const value = ordinaryPreparation()
  const coverage = { scopeType: 'PLAN_STEP_CONDITION', status: 'UNKNOWN_UNTIL_TRIGGER', objects: null, parts: null }
  const raw = { contractVersion: 'PCE-CONDITIONAL-EXECUTION-PREPARATION-V1', conditionCode: 'ISOLATED_EXCEPTION',
    triggerStatus: 'WAITING_TRIGGER', affectedObjects: null, affectedParts: null, quantity: null, uomId: null,
    capacityPolicy: { appliesWhen: 'TRIGGERED', meaningCode: 'NON_QUANTIFIED', sourceValue: '0',
      quantitativeOccupancyAllowed: false, independentDurationAllowed: false },
    executionFact: { mode: 'SIMULATED', allMaterialUnissued: true, allWorkUnstarted: true, statement: '隔离模拟事实' },
    originalApplicabilityHash: 'd'.repeat(64) }
  Object.assign(value, { statusCode: 'WAITING_TRIGGER', triggerStatus: 'WAITING_TRIGGER', result: 'PENDING',
    conditionCode: raw.conditionCode, formalPolicyValidated: true, formalApplicabilityValidated: false,
    conditionalExecution: { ...structuredClone(raw), triggerPolicyLabel: '异常触发才执行，当前待触发',
      pendingScopeLabel: '异常触发后确定实际范围', executionFactLabel: '模拟未领料未开工', capacityIndependenceLabel: '产能与数量分开' },
    context: { contractVersion: raw.contractVersion, exactScope: { ...scope }, scopeType: 'PLAN_STEP_CONDITION',
      objectCoverage: { ...coverage }, sourceSelection: null }, objectCoverage: { ...coverage },
    quantity: null, uomId: null, draftSelection: null, conditionalCapacityPolicy: structuredClone(raw.capacityPolicy),
    capacityResolution: { valid: false, code: 'WAITING_TRIGGER', statusLabel: '待触发' },
    capacitySemantics: { valid: false, meaningCode: null, sourceValue: null, quantitativeOccupancyAllowed: false,
      grantsRulePublication: false, grantsRequirementGeneration: false, grantsAllocation: false, grantsScheduling: false } })
  value.businessBasis.conditionalExecution = structuredClone(raw)
  Object.assign(value.businessBasis.entries[0], { scope: { ...scope }, objectCoverage: { ...coverage } })
  return value
}
function detail(inputPreparation = preparation()) {
  return { configuration: { operationId: scope.operationId }, catalog: { companyId: scope.companyId },
    context: { scope: { ...scope }, applicability: { mode: 'MANDATORY', result: 'REQUIRED', resultLabel: '本次必须执行' },
      inputPreparation, quantityPolicy: inputPreparation.quantityPolicy, capacitySemantics: capacity() } }
}
const params = { operationId: scope.operationId, productionPlanId: scope.productionPlanId, routingStepId: scope.routingStepId }
const bucket = (code, label) => ({ statusCode: code, statusLabel: label, items: [], blockers: [] })
function routeFixture() {
  const routeScope = { ...scope, routingId: 6820 }
  delete routeScope.routingStepId
  delete routeScope.operationId
  const rows = Array.from({ length: 28 }, (_, index) => {
    const selected = index === 9
    const source = index === 3
    const code = selected ? 'NOT_SEPARATELY_MEASURED' : 'MISSING'
    const formal = bucket(code, selected ? '配套执行，不单独生成数量需求' : '尚无正式需求')
    const saved = { ...bucket(code, selected ? '不单独保存数量分配' : '尚无分配'), quantity: null, uomId: null, uomLabel: null }
    return { routingStepId: selected ? scope.routingStepId : source ? sourceStepId : 7000 + index,
      operationId: selected ? scope.operationId : source ? sourceOperationId : 7100 + index,
      sequence: index + 1, predecessorSequences: index ? [index] : [], operationName: `隔离工序${index + 1}`,
      applicability: { mode: 'MANDATORY', result: 'REQUIRED', resultLabel: '本次必须执行' },
      capacitySemantics: capacity(), sourceConfiguration: { sources: [] }, resourceReferences: {},
      sourceCandidates: bucket(code, selected ? '已确认配套不单独计量' : '尚无正式来源'),
      formalRequirements: formal, savedAllocations: saved,
      objectCoverage: { statusCode: 'UNPROVEN', statusLabel: '不声明额外对象覆盖',
        designItemIds: null, baselineItemIds: null, inputFactIds: null },
      quantityPolicy: selected ? policy() : undefined,
      workloadReview: { statusCode: code, statusLabel: selected ? '常规必经配套不单独计量' : '尚未配置',
        applicabilityLabel: '本次必须执行', processingLabel: '常规配套执行', sourceBusinessLabel: '服务端正式政策',
        formalRequirementStatusLabel: formal.statusLabel, formalRequirementCount: 0,
        allocationStatusLabel: saved.statusLabel, allocationCount: 0, savedQuantity: null, uomLabel: null,
        coverageStatusLabel: '不声明额外对象覆盖', blockers: [],
        ...(selected ? { formalRequirementDisplayLabel: '本工序不单列数量需求', allocationDisplayLabel: '不单独保存数量分配',
          savedQuantityDisplayLabel: '不单独计量，计划和实际数值留空', sourceRuleDisplayLabel: '常规配套数量政策已确认',
          sourceInputDisplayLabel: '处理范围按图纸和现场确认', quantityContractDisplayLabel: '不单独计量，仅引用统计单位' } : {}) } }
  })
  return { contractVersion: 'PCE-OPERATION-WORKLOAD-SOURCE-V1', factSource: 'server', businessWriteCount: 0,
    routeConfiguration: { scope: routeScope, rows, summary: { stepCount: 28, workloadStatusLabel: '本次完整服务端读取' },
      businessWriteCount: 0, auditWriteCount: 0, generated: false, allocationSaved: false, newEorRuleEvaluated: false,
      workloadReviewIncluded: true, workloadReviewContract: 'PCE-ROUTE-WORKLOAD-READ-V1' } }
}
function planFor(route) {
  return { id: scope.productionPlanId, manufacturingOutputId: scope.manufacturingOutputId, routingVersionId: scope.routingVersionId,
    allRoutingSteps: route.routeConfiguration.rows.map(row => ({ id: row.routingStepId, operationId: row.operationId })) }
}
function section(marker) {
  const start = descriptor.template.content.indexOf(marker)
  assert.ok(start >= 0, marker)
  const end = descriptor.template.content.indexOf('</section>', start)
  assert.ok(end > start)
  return descriptor.template.content.slice(start, end + '</section>'.length)
}
async function html(template, data) {
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ data: () => ({ ...actual, ...data }), render })
  app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
  return renderToString(app)
}

test('the complete SFC compiles with the quantity policy contract', () => {
  const compiled = compileScript(descriptor, { id: 'quantity-policy-contract' })
  const template = compileTemplate({ id: 'quantity-policy-contract', source: descriptor.template.content,
    filename: url.pathname, compilerOptions: { bindingMetadata: compiled.bindings } })
  assert.deepEqual(template.errors, [])
})

test('actual request and full 28-step route validators accept null quantities with explicit policy and same-route unit proof', () => {
  const value = detail()
  const before = JSON.stringify(value)
  actual.validateRequestedScope(value, params)
  const route = routeFixture()
  const routeBefore = JSON.stringify(route)
  assert.equal(actual.validateRouteFacts(route, planFor(route), scope.companyId), route)
  assert.equal(JSON.stringify(value), before)
  assert.equal(JSON.stringify(route), routeBefore)
  const row = mappedRows(Vue.computed, Vue.ref(route.routeConfiguration)).value.find(row => row.routingStepId === scope.routingStepId)
  assert.equal(row.savedQuantityText, '不单独计量，计划和实际数值留空')
  assert.equal(row.formalRequirementLabel, '本工序不单列数量需求')
  assert.equal(row.savedAllocationLabel, '不单独保存数量分配')
  assert.equal(row.savedAllocations.quantity, null)
  assert.equal(row.savedAllocations.uomLabel, null)
})

test('route and detail render both null reasons and referenced statistical UOM alongside unchanged capacity history', async () => {
  const quantityPolicy = policy()
  const routeHtml = await html(section('<section v-if="row.quantityPolicy"'), { row: { quantityPolicy } })
  const context = { quantityPolicy, standardCapacityFacts: [{ id: 6819, name: '原正式产能', quantity: '0.000000',
    uomLabel: '历史面积单位', timeUnitLabel: '天', timeBasisQuantity: '1', statusLabel: '原0产能保持' }] }
  const detailHtml = await html(section('<section v-if="context.quantityPolicy"')
    + section('<section v-if="context.standardCapacityFacts?.length"'), { context })
  for (const text of [quantityPolicy.statusLabel, quantityPolicy.plannedQuantityReasonLabel,
    quantityPolicy.actualQuantityReasonLabel, quantityPolicy.statisticalUomReference.uomLabel,
    quantityPolicy.statisticalUomReference.statusLabel, quantityPolicy.scopeDeterminationLabel,
    quantityPolicy.capacityIndependenceLabel]) {
    assert.ok(routeHtml.includes(text), text)
    assert.ok(detailHtml.includes(text), text)
  }
  assert.ok(detailHtml.includes('0.000000 历史面积单位'))
  assert.ok(detailHtml.includes('原0产能保持'))
  assert.ok(routeHtml.includes(`实际产量：${quantityPolicy.actualQuantityReasonLabel}`))
  assert.ok(detailHtml.includes(`实际产量：${quantityPolicy.actualQuantityReasonLabel}`))
  assert.doesNotMatch(routeHtml + detailHtml, /WAITING_TRIGGER|当前待触发|计划投产数量：0|实际产量：0|实际投产数量：/)
})

test('a quantity policy shows only its actual native capacity reference while ordinary and conditional historical rows are unchanged', async () => {
  const start = descriptor.template.content.indexOf('<div v-if="inputPreparation.quantityPolicy && inputPreparation.standardCapacityReference"')
  const end = descriptor.template.content.indexOf('<div v-if="inputPreparation.formalRuleStatusLabel"', start)
  assert.ok(start >= 0 && end > start)
  const template = `<dl>${descriptor.template.content.slice(start, end)}</dl>`
  const value = preparation()
  value.standardCapacityReference = { id: 6819, quantity: '0.000000', uomId: 6899, uomLabel: '原正式面积单位' }
  const before = JSON.stringify(value)
  const result = await html(template, { inputPreparation: value })
  assert.match(result, /所引用正式标准产能/)
  assert.match(result, /0\.000000 原正式面积单位/)
  assert.doesNotMatch(result, /正式标准产能数量|未知|隔离长度单位/)
  assert.equal(value.quantityPolicy.plannedQuantity, null)
  assert.equal(value.quantityPolicy.actualQuantity, null)
  assert.equal(value.capacityQuantity, null)
  assert.equal(JSON.stringify(value), before)
  for (const old of [ordinaryPreparation(), conditionalPreparation()]) {
    old.standardCapacityReference = structuredClone(value.standardCapacityReference)
    const historical = await html(template, { inputPreparation: old })
    assert.match(historical, /正式标准产能数量/)
    assert.match(historical, /未知/)
    assert.doesNotMatch(historical, /所引用正式标准产能|0\.000000 原正式面积单位/)
  }
  const missing = preparation()
  const missingReference = await html(template, { inputPreparation: missing })
  assert.match(missingReference, /正式标准产能数量/)
  assert.doesNotMatch(missingReference, /所引用正式标准产能/)
})

test('policy empty buckets consume server labels while ordinary unknown reads still show quantity unknown', async () => {
  const start = descriptor.template.content.indexOf('<PceBusinessStatus :status-label="card.facts?.statusLabel')
  const end = descriptor.template.content.indexOf('<section v-for="(item, index) in card.facts?', start)
  const template = `<article>${descriptor.template.content.slice(start, end)}</article>`
  for (const key of ['sourceCandidates', 'formalRequirements', 'savedAllocations']) {
    const label = '已确认本工序不单独计量'
    const result = await html(template, { card: { key, facts: { ...bucket('NOT_SEPARATELY_MEASURED', label), quantity: null } },
      selectedPlan: null, selectedOperation: null })
    assert.ok(result.includes(label))
    assert.doesNotMatch(result, /数量未知|当前待触发|不适用/)
  }
  const failed = await html(template, { card: { key: 'sourceCandidates', facts: bucket('READ_FAILED', '正式读取失败') } })
  assert.match(failed, /正式读取失败/)
  assert.match(failed, /数量未知/)
})

test('wrong scope, measured values, missing reason, reference proof and different-route references fail closed', () => {
  const mutations = [p => { p.contractVersion = 'UNKNOWN' }, p => { p.measurementMode = 'WAITING_TRIGGER' },
    p => { p.formalPolicyValidated = false }, p => { p.exactScope.companyId += 1 },
    p => { p.exactScope.productionPlanId += 1 }, p => { p.exactScope.routingStepId += 1 },
    p => { p.plannedQuantity = '0' }, p => { p.actualQuantity = 0 },
    p => { p.plannedQuantityReasonLabel = '' }, p => { p.actualQuantityReasonLabel = ' ' },
    p => { p.statisticalUomReference.sourceCompanyId += 1 }, p => { p.statisticalUomReference.sourceProductionPlanId += 1 },
    p => { p.statisticalUomReference.sourceRoutingVersionId += 1 },
    p => { p.statisticalUomReference.sourceRoutingStepId = scope.routingStepId },
    p => { p.statisticalUomReference.uomId = null }, p => { p.statisticalUomReference.uomLabel = '' },
    p => { p.statisticalUomReference.proofHash = '' }]
  for (const mutate of mutations) {
    const value = policy()
    mutate(value)
    assert.throws(() => actual.validateQuantityPolicy(value, scope), mutate.toString())
  }
  const route = routeFixture()
  const plan = planFor(route)
  route.routeConfiguration.rows[9].quantityPolicy.statisticalUomReference.sourceOperationId += 1
  assert.throws(() => actual.validateRouteFacts(route, plan, scope.companyId))
})

test('a broken recorded policy cannot fall back to legacy preparation or grant generation, allocations or scheduling', () => {
  const mutations = [p => { delete p.quantityPolicy }, p => { delete p.businessBasis.quantityPolicy },
    p => { p.businessBasis.quantityPolicy.nullReason = 'UNKNOWN' },
    p => { p.businessBasis.quantityPolicy.objectCoverageClaimed = true },
    p => { p.businessBasis.quantityPolicy.statisticalUomReference.routingStepId += 1 },
    p => { p.context.exactScope.companyId += 1 }, p => { p.capacityResolution.formalStandardCapacityPresent = false },
    p => { p.capacityResolution.originalConclusionRevoked = true }, p => { p.capacityBusinessValue = null },
    p => { p.businessWriteCount = 1 }, p => { p.auditWriteCount = 1 },
    p => { p.readyForGeneration = true }, p => { p.readyForAllocation = true }, p => { p.readyForScheduling = true },
    p => { p.sourceQuantity = '0' }, p => { p.inputQuantity = '0' }, p => { p.capacityQuantity = '0' },
    p => { p.businessBasisPresentation[0].exactStatement = '覆盖用户原文' },
    p => { p.auditIds = [] }, p => { p.stateMachineConsistent = false }, p => { p.statusTransitionCount = 0 }]
  for (const mutate of mutations) {
    const value = preparation()
    mutate(value)
    assert.throws(() => actual.validateInputPreparation(value, scope, scope.companyId), mutate.toString())
  }
  const missingCurrent = detail()
  delete missingCurrent.context.quantityPolicy
  assert.throws(() => actual.validateRequestedScope(missingCurrent, params))
  const mismatch = detail()
  mismatch.context.quantityPolicy = { ...mismatch.context.quantityPolicy, actualQuantityReasonLabel: '另一读取事实' }
  assert.throws(() => actual.validateRequestedScope(mismatch, params))
  const missingRoute = routeFixture()
  delete missingRoute.routeConfiguration.rows[9].quantityPolicy
  assert.throws(() => actual.validateRouteFacts(missingRoute, planFor(missingRoute), scope.companyId))
})

test('ordinary and conditional preparations retain their original contracts and capacity zero alone does not create a policy', () => {
  for (const value of [ordinaryPreparation(), conditionalPreparation()]) {
    actual.validateInputPreparation(value, scope, scope.companyId)
    assert.equal(value.quantityPolicy, undefined)
    const broken = structuredClone(value)
    broken.auditWriteCount = 1
    assert.throws(() => actual.validateInputPreparation(broken, scope, scope.companyId))
  }
  const zero = ordinaryPreparation()
  Object.assign(zero, { capacityMeasurementStatus: 'zero_capacity', capacityBusinessValue: 0,
    capacityResolution: { valid: true, originalConclusionRevoked: true, formalStandardCapacityPresent: false, statusLabel: '原无正式记录裁决' } })
  actual.validateInputPreparation(zero, scope, scope.companyId)
  zero.capacityResolution.formalStandardCapacityPresent = true
  assert.throws(() => actual.validateInputPreparation(zero, scope, scope.companyId))
  assert.deepEqual(actual.conditionalExecutionLabels({ mode: 'MANDATORY', result: 'REQUIRED' }), [])
})

test('fresh native full detail and route responses pass the actual validators without changing saved facts',
  { skip: !process.env.PCE_QUANTITY_POLICY_NATIVE_FACTS_PATH }, () => {
    const captured = JSON.parse(readFileSync(process.env.PCE_QUANTITY_POLICY_NATIVE_FACTS_PATH, 'utf8'))
    const value = captured.detailResponse
    const route = captured.routeResponse
    assert.ok(value?.context?.quantityPolicy)
    assert.ok(route?.routeConfiguration)
    const currentScope = value.context.scope
    const before = JSON.stringify(captured)
    actual.validateFacts(value)
    actual.validateRequestedScope(value, { operationId: currentScope.operationId,
      productionPlanId: currentScope.productionPlanId, routingStepId: currentScope.routingStepId })
    const selectedPlan = value.catalog.productionPlans.find(item => Number(item.id) === currentScope.productionPlanId)
    assert.ok(selectedPlan)
    actual.validateRouteFacts(route, selectedPlan, value.catalog.companyId)
    const row = route.routeConfiguration.rows.find(item => item.routingStepId === currentScope.routingStepId)
    assert.ok(row)
    assert.deepEqual(row.quantityPolicy, value.context.quantityPolicy)
    assert.equal(row.applicability.result, 'REQUIRED')
    assert.equal(row.quantityPolicy.plannedQuantity, null)
    assert.equal(row.quantityPolicy.actualQuantity, null)
    assert.equal(row.savedAllocations.quantity, null)
    assert.equal(row.savedAllocations.uomLabel, null)
    assert.deepEqual(row.formalRequirements.items, [])
    assert.deepEqual(row.savedAllocations.items, [])
    assert.equal(JSON.stringify(captured), before)
  })
