import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'

// Exercise the actual display mapping and template with synthetic server facts.
// No HTTP, browser, business service, database or persisted evidence is involved.
const url = new URL('../../src/meta/components/OperationWorkloadSourcePanel.vue', import.meta.url)
const source = readFileSync(url, 'utf8')
const { descriptor } = parse(source, { filename: url.pathname })
const script = descriptor.scriptSetup.content
const helperNames = ['serverDisplayLabel', 'conditionalExecutionLabels', 'quantityText',
  'recordCountText', 'sourceInputText', 'quantityContractText', 'reasonLabel']
function actualFunction(name) {
  const match = script.match(new RegExp(`function ${name}\\([^]*?\\n\\}`))
  assert.ok(match, `Actual component helper ${name} is present`)
  return match[0]
}
const helpers = helperNames.map(actualFunction).join('\n')
const display = new Function(`${helpers}\nreturn { ${helperNames.join(', ')} }`)()
const validatorNames = ['validateFacts', 'validateRequestedScope', 'validateCapacitySemantics',
  'validateInputPreparation', 'validateConditionalPreparation', 'validateRouteFacts', 'canonicalSnapshot']
const validators = new Function('CONTRACT', `${helpers}\n${validatorNames.map(actualFunction).join('\n')}
  return { ${validatorNames.join(', ')} }`)('PCE-OPERATION-WORKLOAD-SOURCE-V1')
const routeMapping = script.slice(script.indexOf('const routeRows = computed('),
  script.indexOf('const routeListContract ='))
assert.ok(routeMapping.startsWith('const routeRows = computed('))
const mapRows = new Function('computed', 'routeConfiguration',
  `${helpers}\n${routeMapping}\nreturn routeRows`)

function rows(value) {
  return mapRows(Vue.computed, Vue.ref({ rows: value })).value
}
function baseRow(review = {}) {
  return { sequence: 3, operationName: '隔离条件工序', applicability: {},
    sourceConfiguration: { sources: [] }, sourceCandidates: { items: [] },
    formalRequirements: { items: [] }, savedAllocations: { items: [], quantity: null },
    workloadReview: { applicabilityLabel: '正式适用性', processingLabel: '正式处理方式',
      sourceBusinessLabel: '正式来源口径', formalRequirementStatusLabel: '当前需求尚未读取',
      formalRequirementCount: null, allocationStatusLabel: '当前分配尚未读取',
      allocationCount: null, savedQuantity: null, uomLabel: null,
      coverageStatusLabel: '覆盖尚未证明', blockers: [], ...review } }
}
function section(marker) {
  const start = descriptor.template.content.indexOf(marker)
  assert.notEqual(start, -1)
  const end = descriptor.template.content.indexOf('</section>', start)
  assert.notEqual(end, -1)
  return descriptor.template.content.slice(start, end + '</section>'.length)
}
async function html(template, data) {
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ data: () => ({ ...display, ...data }), render })
  app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
  return renderToString(app)
}
const policy = { triggerStatus: 'WAITING_TRIGGER',
  triggerPolicyLabel: '品质异常触发时执行，当前待触发',
  pendingScopeLabel: '异常触发后确定实际处理对象、数量及单位',
  executionFactLabel: '模拟未领料未开工，未声称正式实际执行',
  capacityIndependenceLabel: '0产能与待确定的处理数量分别表达' }
const routeSection = section('<section v-if="conditionalExecutionLabels(row.applicability).length"')
const detailSection = section('<p v-if="context.applicability?.resultLabel || context.applicability?.statusLabel"')
const cardStart = descriptor.template.content.indexOf('<PceBusinessStatus :status-label="card.facts?.statusLabel')
const cardEnd = descriptor.template.content.indexOf('<section v-for="(item, index) in card.facts?', cardStart)
assert.ok(cardStart >= 0 && cardEnd > cardStart)
const cardTemplate = `<article>${descriptor.template.content.slice(cardStart, cardEnd)}</article>`

test('route mapping consumes complete server display labels without changing quantity or record facts', () => {
  const labels = { formalRequirementDisplayLabel: '待触发，本阶段无正式需求',
    allocationDisplayLabel: '待触发，本阶段不办理分配',
    savedQuantityDisplayLabel: '触发后确定数量及单位',
    sourceRuleDisplayLabel: '待触发，来源规则待处理范围明确',
    sourceInputDisplayLabel: '待触发，正式处理对象未预置',
    quantityContractDisplayLabel: '待触发后确定数量合同' }
  const input = baseRow(labels)
  input.applicability.conditionalExecution = { ...policy }
  const before = JSON.stringify(input)
  const [row] = rows([input])
  for (const [field, expected] of Object.entries({ formalRequirementLabel: labels.formalRequirementDisplayLabel,
    savedAllocationLabel: labels.allocationDisplayLabel, savedQuantityText: labels.savedQuantityDisplayLabel,
    sourceRuleText: labels.sourceRuleDisplayLabel, sourceInputText: labels.sourceInputDisplayLabel,
    quantityContractText: labels.quantityContractDisplayLabel })) assert.equal(row[field], expected)
  assert.equal(row.savedAllocations.quantity, null)
  assert.equal(row.workloadReview.savedQuantity, null)
  assert.equal(row.workloadReview.uomLabel, null)
  assert.deepEqual(row.formalRequirements.items, [])
  assert.deepEqual(row.savedAllocations.items, [])
  assert.equal(JSON.stringify(input), before)
})

test('ordinary rows keep their existing fallback and zero quantity does not imply waiting or exemption', () => {
  const row = baseRow({ savedQuantity: '0', uomLabel: '件', allocationStatusLabel: '正式分配状态',
    allocationCount: 0, formalRequirementCount: 0, formalRequirementDisplayLabel: ' ',
    savedQuantityDisplayLabel: 0, allocationDisplayLabel: null })
  row.capacitySemantics = { capacityQuantity: '0', statusLabel: '正式产能含义' }
  const [shown] = rows([row])
  assert.equal(shown.savedQuantityText, '0 件')
  assert.equal(shown.savedAllocationLabel, '正式分配状态；0条')
  assert.equal(shown.formalRequirementLabel, '当前需求尚未读取；0条')
  assert.equal(shown.sourceRuleText, '尚无正式来源规则')
  assert.equal(shown.sourceInputText, '正式来源字段及生产版本未知')
  assert.equal(shown.quantityContractText, '数量表达及去重口径未知')
  assert.deepEqual(display.conditionalExecutionLabels(row.applicability), [])
  const [unknown] = rows([baseRow()])
  assert.equal(unknown.savedQuantityText, '当前分配尚未读取')
  assert.equal(unknown.savedAllocations.quantity, null)
  assert.match(unknown.formalRequirementLabel, /记录数未知/)
})

test('route and detail render the same server conditional policy and prefer official applicability result label', async () => {
  const applicability = { resultLabel: '正式条件适用性，当前待触发',
    statusLabel: '旧记录已核实标签', conditionalExecution: { ...policy } }
  const routeHtml = await html(routeSection, { row: { applicability } })
  const detailHtml = await html(detailSection, { context: { applicability } })
  for (const label of display.conditionalExecutionLabels(applicability)) {
    assert.ok(routeHtml.includes(label), label)
    assert.ok(detailHtml.includes(label), label)
  }
  assert.ok(detailHtml.includes('步骤适用性：正式条件适用性，当前待触发'))
  assert.ok(!detailHtml.includes('旧记录已核实标签'))
  assert.match(routeHtml, /data-fact-source="server"/)
  assert.match(detailHtml, /data-fact-source="server"/)
  assert.doesNotMatch(detailHtml, /必须补量|已生成需求|已保存分配/)
})

test('waiting empty buckets show authoritative labels while failed unknown reads and saved zero retain their meaning', async () => {
  for (const key of ['sourceCandidates', 'formalRequirements', 'savedAllocations']) {
    const label = `${key}：当前待触发，触发后确定实际范围`
    const facts = { statusCode: 'WAITING_TRIGGER', statusLabel: label, items: [], quantity: null, uomLabel: null }
    const result = await html(cardTemplate, { card: { key, facts }, selectedPlan: null, selectedOperation: null })
    assert.ok(result.includes(label))
    assert.ok(!result.includes('数量未知'))
    assert.ok(!result.includes('不适用'))
    assert.equal(facts.quantity, null)
    assert.equal(facts.uomLabel, null)
  }
  const failed = await html(cardTemplate, { card: { key: 'sourceCandidates', facts: {
    statusCode: 'READ_FAILED', statusLabel: '读取失败，请重新读取', items: [] } } })
  assert.ok(failed.includes('读取失败，请重新读取'))
  assert.ok(failed.includes('数量未知'))
  const zero = await html(cardTemplate, { card: { key: 'savedAllocations', facts: {
    statusCode: 'SAVED', statusLabel: '正式已保存', quantity: '0', uomLabel: '件', items: [] } } })
  assert.ok(zero.includes('0 件'))
})

test('missing or different trigger context invents no policy and server text is escaped by the actual template', async () => {
  for (const applicability of [undefined, {}, { conditionalExecution: { capacityBusinessValue: 0 } },
    { conditionalExecution: { ...policy, triggerStatus: 'TRIGGERED' } }]) {
    assert.deepEqual(display.conditionalExecutionLabels(applicability), [])
    assert.ok(!(await html(routeSection, { row: { applicability } })).includes('当前待触发'))
  }
  const applicability = { conditionalExecution: { triggerStatus: 'WAITING_TRIGGER',
    triggerPolicyLabel: '<b>服务端触发说明</b>', pendingScopeLabel: '',
    executionFactLabel: ' ', capacityIndependenceLabel: null } }
  assert.deepEqual(display.conditionalExecutionLabels(applicability), ['<b>服务端触发说明</b>'])
  const result = await html(routeSection, { row: { applicability } })
  assert.ok(result.includes('&lt;b&gt;服务端触发说明&lt;/b&gt;'))
  assert.ok(!result.includes('<b>服务端触发说明</b>'))
})

const exact = { companyId: 6701, productionPlanId: 6702, manufacturingOutputId: 6703, mainCalculationId: 6704,
  salesOrderItemId: 6705, baselineId: 6706, routingVersionId: 6707, routingStepId: 6708, operationId: 6709, productTypeId: 6710 }
function legacyPreparation() {
  const entry = { exactStatement: '隔离正式原答复', reference: '隔离依据', referenceSha256: 'ISOLATED-REFERENCE-HASH' }
  return { contractVersion: 'PCE-OPERATION-INPUT-PREPARATION-V1', factSource: 'server',
    exactScope: { ...exact }, recordStatus: 'RECORDED', recordId: 6711, revision: 1, contextHash: 'ISOLATED-CONTEXT-HASH',
    inputStandardStatus: 'PENDING_CONFIRMATION', businessBasis: { entries: [entry] },
    businessBasisPresentation: [{ ...entry, entryIndex: 0, statusLabel: '正式原答复' }],
    statusLabel: '正式准备记录', inputStandardStatusLabel: '待确认', capacityMeasurementStatusLabel: '尚未确认',
    formalRuleStatusLabel: '尚未发布规则', scopeLabel: '准确计划步骤', remainingItems: [],
    sourceQuantity: null, inputQuantity: null, capacityQuantity: null,
    capacityMeasurementStatus: null, capacityBusinessValue: null,
    capacityResolution: { valid: false, statusLabel: '正式产能裁决未定' },
    formalRulePublished: false, readyForGeneration: false, readyForAllocation: false, readyForScheduling: false,
    businessWriteCount: 0, auditWriteCount: 0, stateTransitionWriteCount: 0, supportWriteCount: 0 }
}
function conditionalPreparation() {
  const value = legacyPreparation()
  const coverage = { scopeType: 'PLAN_STEP_CONDITION', status: 'UNKNOWN_UNTIL_TRIGGER', objects: null, parts: null }
  const capacity = { appliesWhen: 'TRIGGERED', meaningCode: 'NON_QUANTIFIED', sourceValue: '0',
    quantitativeOccupancyAllowed: false, independentDurationAllowed: false }
  const conditional = { contractVersion: 'PCE-CONDITIONAL-EXECUTION-PREPARATION-V1',
    conditionCode: 'ISOLATED_EXCEPTION_TRIGGER', triggerStatus: 'WAITING_TRIGGER',
    affectedObjects: null, affectedParts: null, quantity: null, uomId: null, capacityPolicy: capacity,
    executionFact: { mode: 'SIMULATED', allMaterialUnissued: true, allWorkUnstarted: true, statement: '隔离模拟声明' },
    originalApplicabilityHash: 'ISOLATED-ORIGINAL-APPLICABILITY-HASH' }
  Object.assign(value, { currentStateSource: 'server', statusCode: 'WAITING_TRIGGER', triggerStatus: 'WAITING_TRIGGER',
    conditionCode: conditional.conditionCode, result: 'PENDING', isPersisted: true,
    context: { contractVersion: conditional.contractVersion, exactScope: { ...exact },
      scopeType: 'PLAN_STEP_CONDITION', objectCoverage: { ...coverage }, sourceSelection: null },
    objectCoverage: { ...coverage }, quantity: null, uomId: null, draftSelection: null,
    formalPolicyValidated: true, formalApplicabilityValidated: false,
    conditionalExecution: { ...structuredClone(conditional), ...policy, conditionCode: conditional.conditionCode,
      contractVersion: conditional.contractVersion },
    conditionalCapacityPolicy: { ...capacity },
    capacityResolution: { valid: false, code: 'WAITING_TRIGGER', statusLabel: '正式待触发状态' },
    capacitySemantics: { valid: false, meaningCode: null, sourceValue: null, quantitativeOccupancyAllowed: false,
      grantsRulePublication: false, grantsRequirementGeneration: false, grantsAllocation: false, grantsScheduling: false },
    auditIds: [6712], writeRequestId: 6713, sourceIdentityId: 6714,
    statusTransitionHistory: [{ id: 6715 }], statusTransitionCount: 1, stateMachineConsistent: true })
  value.businessBasis.conditionalExecution = structuredClone(conditional)
  value.businessBasis.entries[0].scope = { ...exact }
  value.businessBasis.entries[0].objectCoverage = { ...coverage }
  return value
}

test('actual request validator accepts only a complete conditional read contract and preserves legacy records', () => {
  for (const inputPreparation of [legacyPreparation(), conditionalPreparation()]) {
    const value = { configuration: { operationId: exact.operationId }, catalog: { companyId: exact.companyId },
      context: { scope: { ...exact }, inputPreparation } }
    const before = JSON.stringify(value)
    assert.doesNotThrow(() => validators.validateRequestedScope(value, { operationId: exact.operationId,
      productionPlanId: exact.productionPlanId, routingStepId: exact.routingStepId }))
    assert.equal(JSON.stringify(value), before)
  }
})

test('conditional records cannot bypass original public scope, zero writes, grants, labels or original answer assertions', () => {
  const mutations = [
    p => { p.exactScope.routingStepId += 1 }, p => { p.exactScope.companyId += 1 },
    p => { p.businessWriteCount = 1 }, p => { p.auditWriteCount = 1 },
    p => { p.stateTransitionWriteCount = 1 }, p => { p.supportWriteCount = 1 },
    p => { p.readyForGeneration = true }, p => { p.readyForAllocation = true },
    p => { p.readyForScheduling = true }, p => { p.formalRulePublished = true },
    p => { p.sourceQuantity = '0' }, p => { p.inputQuantity = '0' }, p => { p.capacityQuantity = '0' },
    p => { delete p.capacityQuantity }, p => { delete p.formalRuleStatusLabel },
    p => { delete p.remainingItems }, p => { delete p.businessBasisPresentation },
    p => { p.businessBasisPresentation[0].exactStatement = '代改原文' },
    p => { p.businessBasisPresentation[0].referenceSha256 = '替换证明' },
    p => { p.recordId = null }, p => { p.inputStandardStatus = null },
  ]
  for (const factory of [legacyPreparation, conditionalPreparation]) for (const mutate of mutations) {
    const preparation = factory()
    mutate(preparation)
    assert.throws(() => validators.validateInputPreparation(preparation, exact, exact.companyId), mutate.toString())
  }
})

test('conditional validator rejects wrong nested context, known quantities, actual execution and leaked eligibility', () => {
  const mutations = [
    p => { p.context.exactScope.productionPlanId += 1 }, p => { p.context.exactScope.routingStepId += 1 },
    p => { p.businessBasis.entries[0].scope.companyId += 1 },
    p => { p.conditionalExecution.contractVersion = 'UNKNOWN' },
    p => { delete p.conditionalExecution }, p => { delete p.businessBasis.conditionalExecution },
    p => { p.conditionalExecution.triggerStatus = 'TRIGGERED' },
    p => { p.triggerStatus = 'TRIGGERED' }, p => { p.result = 'REQUIRED' },
    p => { p.conditionalExecution.affectedObjects = [] }, p => { p.conditionalExecution.affectedParts = [] },
    p => { p.conditionalExecution.quantity = '0' }, p => { p.conditionalExecution.uomId = 6716 },
    p => { p.quantity = '0' }, p => { p.uomId = 6716 }, p => { p.objectCoverage.objects = [6717] },
    p => { p.context.objectCoverage.parts = [] }, p => { p.context.sourceSelection = {} },
    p => { p.conditionalExecution.capacityPolicy.meaningCode = 'NOT_APPLICABLE' },
    p => { p.conditionalExecution.capacityPolicy.quantitativeOccupancyAllowed = true },
    p => { p.conditionalCapacityPolicy.independentDurationAllowed = true },
    p => { p.conditionalExecution.executionFact.mode = 'ACTUAL' },
    p => { p.conditionalExecution.executionFact.allWorkUnstarted = false },
    p => { p.conditionalExecution.executionFact.allMaterialUnissued = false },
    p => { p.conditionalExecution.executionFact.statement = '' },
    p => { p.formalPolicyValidated = false }, p => { p.formalApplicabilityValidated = true },
    p => { p.capacitySemantics.grantsAllocation = true }, p => { p.capacitySemantics.grantsScheduling = true },
    p => { p.auditIds = [] }, p => { p.stateMachineConsistent = false },
    p => { p.statusTransitionCount = 0 }, p => { p.currentStateSource = 'cache' },
  ]
  for (const mutate of mutations) {
    const preparation = conditionalPreparation()
    mutate(preparation)
    assert.throws(() => validators.validateInputPreparation(preparation, exact, exact.companyId), mutate.toString())
  }
  assert.throws(() => validators.validateInputPreparation(conditionalPreparation(), exact, exact.companyId + 1))
})

test('fresh native detail and route responses pass the actual request and full route validators',
  { skip: !process.env.PCE_CONDITIONAL_NATIVE_FACTS_PATH }, () => {
    const captured = JSON.parse(readFileSync(process.env.PCE_CONDITIONAL_NATIVE_FACTS_PATH, 'utf8'))
    const detail = captured.detailResponse
    const route = captured.routeResponse
    assert.ok(detail?.context?.inputPreparation, 'Capture the complete fresh native detailResponse')
    assert.ok(route?.routeConfiguration, 'Capture the complete fresh native routeResponse')
    const scope = detail.context.scope
    const before = JSON.stringify(captured)
    validators.validateFacts(detail)
    validators.validateRequestedScope(detail, { operationId: scope.operationId,
      productionPlanId: scope.productionPlanId, routingStepId: scope.routingStepId })
    const plan = detail.catalog.productionPlans.find(item => Number(item.id) === scope.productionPlanId)
    assert.ok(plan, 'The selected plan must come from this response catalog')
    assert.equal(validators.validateRouteFacts(route, plan, detail.catalog.companyId), route)
    const row = route.routeConfiguration.rows.find(item => item.routingStepId === scope.routingStepId)
    assert.ok(row)
    for (const key of ['sourceCandidates', 'formalRequirements', 'savedAllocations']) {
      assert.equal(row[key].statusCode, 'WAITING_TRIGGER')
      assert.deepEqual(row[key].items, [])
    }
    assert.equal(row.savedAllocations.quantity, null)
    assert.equal(row.savedAllocations.uomLabel, null)
    assert.equal(row.workloadReview.savedQuantity, null)
    assert.equal(row.workloadReview.uomLabel, null)
    assert.equal(JSON.stringify(captured), before)
  })
