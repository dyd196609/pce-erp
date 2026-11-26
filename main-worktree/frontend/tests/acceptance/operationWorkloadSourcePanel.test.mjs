import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

// Synthetic server responses only. These tests never use HTTP, a browser or a database.
const componentUrl = new URL('../../src/meta/components/OperationWorkloadSourcePanel.vue', import.meta.url)
const source = fs.readFileSync(componentUrl, 'utf8')
const parent = fs.readFileSync(new URL('../../src/meta/components/ProductionFoundationMaintenance.vue', import.meta.url), 'utf8')
const descriptor = parse(source, { filename: componentUrl.pathname }).descriptor
const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const execute = new Function('computed', 'onBeforeUnmount', 'reactive', 'ref', 'watch', 'defineProps', 'defineEmits', 'pdeApi', 'createPceEnterpriseListContract', 'usePceEnterpriseListRuntime', `${script}
return { selectedOperationId, selectedPlanId, selectedRoutingStepId, serverFacts, readState, readError, form,
  catalog, operationOptions, configuration, configureAuthorization, busy, matchingSteps, selectedProducer, context, inputPreparation,
  hasTraceOptions, traceOptions, selectedTraceOption,
  hasConfigurationOptions, quantityContracts, selectedQuantityContract, scopeContracts, selectedScopeContract,
  routingOptions, selectedRoutingContext, operationUomId, draftIdentity, currentPreview, previewState, previewFacts,
  previewError, previewCards, previewIssues, draftFieldsComplete, canPreview, previewSourceConfiguration,
  quantityCards, configurationFields, visibleConfigurationFields, hasCapacityModes, capacityModes, selectedCapacityMode,
  hasRequiredPreparationContext, contextSelectionNotice, canSave, saving, saveMessage, saveReadbackFailed,
  selectedRoutePlanId, routeFacts, routeReadState, routeReadError, routeConfiguration, routeRows, routeListContract,
  routeFilterSchema, routeExportColumns, routeSelectedRows, routeQuickSearch, routeAppliedSearch, routeAdvancedVisible,
  routeFilters, routeTableRef, routeActiveFilterCount, routeSortText, routeFilteredRows, routeClearFilters, routeClearSort,
  routeClearSelection, routeHandleSort, routeExportCurrent, loadRouteOverview, openRouteStep, refreshSourceFacts,
  optionLabel, quantityText, sourceInputText, quantityContractText, reasonLabel, optionsFor, refreshResourceSelection,
  sourcePayload, routingKey, clearDraftPreview, loadSources, changeOperation, changePlan, saveSource }`)
const render = new Function('Vue', compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
const capacityRowsScript = parent.slice(parent.indexOf('const currentRows = computed('), parent.indexOf('const latestTemplateVersion ='))
const executeCapacityRows = new Function('computed', 'selectedEntity', 'rowsFor', 'targetedFacts', 'calculationBasisLabels', 'rowLabel', `${capacityRowsScript}\nreturn currentRows`)
const contract = 'PCE-OPERATION-WORKLOAD-SOURCE-V1'
const serverFacts = (extra = {}) => ({ contractVersion: contract, factSource: 'server',
  operations: [{ id: 9011, label: '模拟加工工序' }],
  configuration: { operationId: 9011, statusLabel: '尚未配置正式来源', legacyQuantityDriver: '模拟历史文字', sources: [], blockers: [], hasValidSourceConfiguration: false },
  catalog: {
    producers: [{ id: 6144, label: '模拟正式面积生产规则', canonicalField: 'SIM_AREA', version: 'V8', uomLabel: '平方米', traceEquals: { contractVersion: 'SIM-FACT' } }],
    manufacturingModes: [{ id: 6001, label: '模拟面积模式' }], productTypes: [{ id: 8011, label: '模拟类型' }],
    standardCapacities: [{ id: 6231, label: '模拟日产能', operationId: 9011, productTypeId: 8011, workCenterId: 6012 }], workCenters: [{ id: 6012, label: '模拟工作中心' }],
    productionPlans: [{ id: 5002, label: 'SIM-PLAN', routingSteps: [{ id: 9809, operationId: 9011, label: '模拟准确步骤' }] }],
    configureAuthorization: { allowed: true, statusLabel: '原生维护资格通过', blockers: [] },
  }, ...extra })
const planContext = (extra = {}) => ({ scope: { productionPlanId: 5002, routingStepId: 9809 },
  applicability: { resultLabel: '本次必须执行' }, sourceConfiguration: { statusLabel: '来源方案有效' },
  sourceCandidates: { statusLabel: '来源已证明', items: [{ sourceFactId: 6403, sourceCalculationId: 6210, quantity: '1.234567', uomLabel: '平方米' }] },
  formalRequirements: { statusLabel: '尚无正式工序需求', items: [] },
  savedAllocations: { statusLabel: '尚无已保存计划分配', items: [], quantity: null, uomLabel: '平方米' }, blockers: [], ...extra })

function runtime(api, extraProps = {}) {
  const props = Vue.reactive({ operations: [{ id: 9011, label: '模拟加工工序' }], mode: 'maintain', refreshKey: 0, ...extraProps })
  const events = []
  const state = execute(Vue.computed, () => {}, Vue.reactive, Vue.ref, (value, callback, options) => {
    if (!options?.immediate) return Vue.watch(value, callback, options)
  }, () => props, () => (...args) => events.push(args), api,
    createPceEnterpriseListContract, usePceEnterpriseListRuntime)
  return { props, events, ...state }
}
async function html(state) {
  const data = Object.fromEntries(Object.entries(state).filter(([key]) => !['props', 'events'].includes(key)).map(([key, value]) => [key, Vue.isRef(value) ? value.value : value]))
  const app = Vue.createSSRApp({ data: () => ({ ...state.props, ...data }), render })
  app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
  app.component('ElTableColumn', { render: () => null })
  // Exercise this panel's real table slots; the shared table owns its own pagination/scroll tests.
  app.component('PceEnterpriseListTable', { props: ['tableRows'], setup(props, { slots }) {
    function cells(nodes, row) {
      return nodes.flatMap(node => Array.isArray(node.children) ? cells(node.children, row)
        : node.children?.default ? node.children.default({ row }) : [])
    }
    return () => Vue.h('section', props.tableRows.map(row => Vue.h('article', [row.stepLabel,
      ...cells(slots.columns?.() || [], row), ...(slots.actions?.({ row }) || []),
      row.capacityMeaningLabel, row.capacityRecordPresenceLabel, row.sourceRuleText, row.sourceInputText, row.quantityContractText, row.purposeText, row.workCenterText, row.capacityText, row.uomLabel,
      row.formalRequirementLabel, row.savedAllocationLabel, row.blockerText])))
  } })
  return (await renderToString(app)).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
}
function prepareSave(state) {
  state.selectedOperationId.value = '9011'
  Object.assign(state.form, { productTypeId: '8011', modeId: '6001', producerRuleId: '6144', workCenterId: '6012', standardCapacityId: '6231',
    ruleCode: 'SIM-SOURCE', ruleName: '模拟来源方案', version: 'V8', effectiveFrom: '2026-10-16', reason: 'SIMULATED_FOR_TEST' })
}
function applySavedSource(fixture, traceEquals = { contractVersion: 'SIM-FACT' }) {
  fixture.configuration = { operationId: 9011, statusLabel: '正式来源已配置', hasValidSourceConfiguration: true, blockers: [],
    sources: [{ ruleId: 6999, ruleCode: 'SIM-SOURCE', ruleName: '模拟来源方案', ruleVersion: 'V8', operationId: 9011,
      productTypeId: 8011, manufacturingModeId: 6001, workCenterId: 6012, standardCapacityId: 6231,
      sourceSelector: { producerRuleId: 6144, producerRuleVersion: 'V8', canonicalField: 'SIM_AREA', traceEquals } }] }
}

function routeFixture(planId = 5002) {
  const offset = planId === 5002 ? 0 : 1000
  const rows = Array.from({ length: 28 }, (_, index) => ({ routingStepId: 9809 + offset + index,
    sequence: index + 1, operationId: 9011 + index, operationCode: `SIM-OP-${index + 1}`, operationName: `模拟路线工序${index + 1}`,
    uomId: 6180, uomLabel: '平方米', applicability: { result: 'REQUIRED', resultLabel: '本次必须执行' },
    capacityRole: 'INDEPENDENT', capacitySourceStatus: 'VALID', capacityApplicability: { result: 'REQUIRED', statusLabel: '来源确认经过该工序' },
    sourceConfiguration: { statusCode: 'CONFIGURED', statusLabel: '已配置正式来源', hasValidSourceConfiguration: true,
      sources: [{ ruleId: 8100 + index, ruleName: `模拟见光面积规则${index + 1}`, ruleVersion: 'V8', purposeLabel: '生成正式工序需求',
        sourceCanonicalField: 'SIM_VISIBLE', producerVersion: 'V8', sourceSelector: { producerRuleId: 6144, producerRuleVersion: 'V8' },
        quantityExpression: 'area_quantity', quantityBasisLabel: '来源范围总量', deduplicationLabel: '按正式对象范围计一次，不再乘订单数量' }], blockers: [] },
    resourceReferences: { selectionStatusCode: 'RULE_BOUND', statusLabel: '来源规则已绑定正式资源',
      workCenters: [{ id: 6012 + index, name: `模拟工作中心${index + 1}`, statusLabel: '启用' }], ruleResourceBindings: [],
      standardCapacityCandidates: [{ id: 6231 + index, name: `模拟日产能${index + 1}`, quantity: '180.000000', uomLabel: '平方米',
        timeBasis: 'day', timeBasisQuantity: '1', timeUnit: 'DAY', statusLabel: '当前有效日产能' }] },
    formalRequirements: { statusCode: 'NOT_READ', statusLabel: '总览未读取正式工序需求', items: [] },
    savedAllocations: { statusCode: 'NOT_READ', statusLabel: '总览未读取已保存负荷', items: [], quantity: null, uomId: null, uomLabel: null },
    statusCode: 'CONFIGURED', statusLabel: '已配置正式来源', blockers: [] }))
  rows[1].sourceConfiguration = { statusCode: 'MISSING', statusLabel: '缺少正式面积标准', sources: [], blockers: [] }
  rows[1].blockers = [{ code: 'SIM_STANDARD_MISSING', statusLabel: '模拟试装投入面积尚待确认' }]
  rows[2].applicability = { result: 'NOT_APPLICABLE', resultLabel: '当前对象不适用该工序' }
  rows[2].capacityRole = 'NON_APPLICABLE'; rows[2].capacityApplicability = { result: 'NOT_APPLICABLE', statusLabel: '来源确认不经过该工序' }
  rows[3].capacityRole = 'AUXILIARY'; rows[3].capacityApplicability = { result: 'AUXILIARY', statusLabel: '配套工序，不独立计算日期' }
  rows[3].resourceReferences.standardCapacityCandidates[0] = { id: 6234, name: '模拟配套日产能', quantity: '0.000000', uomLabel: '平方米',
    timeBasis: 'day', timeBasisQuantity: '1', timeUnit: 'DAY', statusLabel: '配套零产能，仍经过该工序' }
  rows[4].applicability = { result: 'PENDING', resultLabel: '对象适用性待确认' }
  rows[4].capacityRole = 'UNKNOWN'; rows[4].capacityApplicability = { result: 'PENDING', statusLabel: '产能来源适用性未知' }
  return { contractVersion: contract, factSource: 'server', routeConfiguration: {
    scope: { companyId: 6099, productionPlanId: planId, manufacturingOutputId: 7002 + offset, mainCalculationId: 7104,
      salesOrderItemId: 7108, baselineId: 7202, routingId: 7301, routingVersionId: 7401 + offset, productTypeId: 8011 },
    rows, summary: { stepCount: 28, configuredCount: 27, missingCount: 1, ambiguousCount: 0, invalidCount: 0,
      notApplicableCount: 1, capacityNonApplicableCount: 1, auxiliaryCount: 1, applicabilityConflictCount: 0,
      statusCode: 'PARTIAL', statusLabel: '部分来源待完善；不代表路线就绪' }, businessWriteCount: 0, auditWriteCount: 0,
    generated: false, allocationSaved: false, newEorRuleEvaluated: false, wholeRouteReady: false }, businessWriteCount: 0 }
}
function routeCatalog(...responses) {
  const fixture = serverFacts()
  fixture.catalog.companyId = 6099
  fixture.catalog.productionPlans = responses.map(response => {
    const route = response.routeConfiguration
    return { id: route.scope.productionPlanId, label: `SIM-PLAN-${route.scope.productionPlanId}`,
      manufacturingOutputId: route.scope.manufacturingOutputId, routingVersionId: route.scope.routingVersionId,
      routingSteps: route.rows.map(row => ({ id: row.routingStepId, operationId: row.operationId, label: `${row.sequence} / ${row.operationName}` })),
      allRoutingSteps: route.rows.map(row => ({ id: row.routingStepId, operationId: row.operationId, label: `${row.sequence} / ${row.operationName}`, isActive: true })) }
  })
  return fixture
}
function deferredResult() {
  let resolve, reject
  const promise = new Promise((success, failure) => { resolve = success; reject = failure })
  return { promise, resolve, reject }
}
function optionalFixture() {
  const fixture = serverFacts()
  fixture.operations[0].calculation_uom_id = 6180
  Object.assign(fixture.catalog, {
    companyId: 6099,
    units: [{ id: 6180, label: '平方米', code: 'm2', dimension: 'area' }, { id: 6181, label: '米', code: 'm', dimension: 'length' }, { id: 6182, label: '件', code: 'pcs', dimension: 'dimensionless' }],
    quantityContracts: [
      { code: 'SOURCE_SCOPE_TOTAL', statusLabel: '正式范围总量', requiresBasisQuantity: false, requiresBasisUomId: false, dynamicOrderBasis: true },
      { code: 'PER_BASIS_QUANTITY', statusLabel: '按正式基数承接', requiresBasisQuantity: true, requiresBasisUomId: true, dynamicOrderBasis: false },
    ],
    expressionContract: { inputAlias: 'source_quantity', defaultExpression: 'source_quantity', operators: ['+', '-', '*', '/'],
      functionsAllowed: false, multipleInputsAllowed: false, statusLabel: '单一正式来源的受控十进制表达式' },
    scopeContracts: [{ code: 'PRODUCT_TYPE', statusLabel: '正式产品类型通用范围', requiresRoutingContext: false },
      { code: 'ROUTING_STEP', statusLabel: '准确正式路线步骤', requiresRoutingContext: true }],
    unsupportedScopes: [{ statusLabel: '当前未提供物料子集来源范围；新版本不会自动替代旧版本' }],
    capacitySemanticVerification: { statusCode: 'NOT_SUPPORTED', statusLabel: '正式引用校验不替代投入面积语义认证' },
    supportedScopes: [{ statusLabel: '按正式类型或精确路线步骤配置' }],
    matchingPriorityLabels: ['精确步骤优先；冲突不能默认为通过'],
    routingContexts: [
      { contractVersion: 'PCE-MANUFACTURING-ROUTING-CONTEXT-V1', routingId: 7301, routingVersionId: 7401, routingStepId: 9809, operationId: 9011, productTypeIds: [8011], label: '模拟正式路线／准确步骤' },
      { contractVersion: 'PCE-MANUFACTURING-ROUTING-CONTEXT-V1', routingId: 7302, routingVersionId: 7402, routingStepId: 9810, operationId: 9011, productTypeIds: [8999], label: '其他产品路线' },
    ],
  })
  Object.assign(fixture.catalog.producers[0], { uomId: 6180, specificationHash: 'SIM-PRODUCER-HASH',
    sourceSemantics: { strategy: 'GROUP_SUM', statusLabel: '正式分组汇总来源，保留原始输入证明', groupKeys: ['formalObject', 'sourceFact'] } })
  fixture.catalog.manufacturingModes[0].uomId = 6180
  fixture.catalog.standardCapacities[0].uomId = 6180
  return fixture
}
function preparationFixture(recorded = true) {
  const fixture = optionalFixture()
  const scope = { companyId: 6099, productionPlanId: 5002, manufacturingOutputId: 7002, mainCalculationId: 7104,
    salesOrderItemId: 7108, baselineId: 7202, routingVersionId: 7401, routingStepId: 9809, operationId: 9011, productTypeId: 8011 }
  const preparation = { contractVersion: 'PCE-OPERATION-INPUT-PREPARATION-V1', factSource: 'server',
    recordStatus: recorded ? 'RECORDED' : 'NOT_RECORDED',
    statusLabel: recorded ? '准备记录已纠正，原产能结论已撤销' : '尚无正式准备记录',
    inputStandardStatus: recorded ? 'PENDING_CONFIRMATION' : null, inputStandardStatusLabel: recorded ? '待确认' : '尚未记录',
    capacityMeasurementStatus: recorded ? 'zero_capacity' : null,
    capacityMeasurementStatusLabel: recorded ? '经过但无法准确核算，不计定量产能占用' : '尚未记录',
    capacityBusinessValue: recorded ? 0 : null, legacyCapacityMeasurementStatus: recorded ? 'UNMEASURED' : null,
    capacityResolution: { valid: recorded, code: recorded ? 'CONFIRMED_ZERO' : 'NOT_RECORDED',
      statusLabel: recorded ? '经过但无法准确核算，不计定量产能占用' : '尚无准备裁决',
      originalConclusionRevoked: recorded, formalStandardCapacityPresent: false },
    formalRuleStatusLabel: '准备记录未发布正式规则', exactScope: structuredClone(scope),
    scopeLabel: '模拟工艺编码 / 路线第3序·模拟加工工序 / 模拟计划 / 三个模拟设计对象',
    contextHash: 'SIM-EXACT-CONTEXT-HASH', recordId: recorded ? 7901 : null, revision: recorded ? 2 : null,
    businessBasis: { entries: recorded ? [{ reference: '模拟责任人原答复档案', referenceSha256: 'SIM-ANSWER-HASH',
      exactStatement: '模拟历史原答复：投入标准待确认；原产能结论已被最新裁决撤销。',
      scope: structuredClone(scope) }] : [] },
    remainingItems: recorded ? [
      { code: 'SOURCE_STANDARD_PENDING', statusLabel: '正式投入来源及标准待确认' },
      { code: 'INPUT_QUANTITY_UNKNOWN', statusLabel: '投入数量尚未确认' },
      { code: 'CAPACITY_NON_QUANTIFIED', statusLabel: '本次0语义不形成定量占用或正式产能数量' },
      { code: 'REQUIREMENT_MISSING', statusLabel: '正式需求尚未生成' },
      { code: 'LOAD_UNKNOWN', statusLabel: '已保存负荷未知' },
      { code: 'TIME_CONDITIONS_MISSING', statusLabel: '理论用时及日期条件不足' },
    ] : [], sourceQuantity: null, inputQuantity: null, capacityQuantity: null,
    formalRulePublished: false, readyForGeneration: false, readyForAllocation: false, readyForScheduling: false,
    businessWriteCount: 0, auditWriteCount: 0, stateTransitionWriteCount: 0, supportWriteCount: 0 }
  preparation.businessBasisPresentation = preparation.businessBasis.entries.map((entry, entryIndex) => ({
    entryIndex, statusLabel: '历史原答复，原产能结论已撤销', exactStatement: entry.exactStatement,
    reference: entry.reference, referenceSha256: entry.referenceSha256,
  }))
  fixture.context = planContext({ scope, inputPreparation: preparation,
    sourceConfiguration: { operationId: 9011, statusLabel: '来源尚未配置', hasValidSourceConfiguration: false, sources: [],
      blockers: [{ code: 'OPERATION_RULE_MAPPING_MISSING', statusLabel: '缺少该工序正式来源规则' }] },
    sourceCandidates: { statusLabel: '来源数量尚未证明', items: [] },
    formalRequirements: { statusLabel: '正式需求缺失', items: [] },
    savedAllocations: { statusLabel: '已保存负荷未知', items: [], quantity: null },
  })
  return fixture
}
function capacitySemantics(meaningCode, extra = {}) {
  const labels = { QUANTIFIED: '经过且有产能数据', NON_QUANTIFIED: '经过但无法准确核算，不计定量产能占用', NOT_APPLICABLE: '不经过' }
  return { contractVersion: 'PCE-CAPACITY-TRISTATE-V1', meaningCode, valid: meaningCode !== null,
    statusLabel: labels[meaningCode] || '产能事实待核实，不能按缺记录推断来源空白',
    sourceStatusLabel: '已读取正式来源及当前裁决', recordPresenceStatusLabel: '正式产能记录身份已核对',
    sourceValue: null, passesOperation: null, quantitativeOccupancyAllowed: false, independentDurationAllowed: false,
    preparationTransferPolicyLabel: '准备与转运按正式流程依据办理', dependencyPolicyLabel: '不跳过正式前后依赖', ...extra }
}
function selectPreparationContext(state) {
  state.selectedOperationId.value = '9011'
  state.selectedPlanId.value = '5002'
  state.selectedRoutingStepId.value = '9809'
}
function prepareOptional(state, extra = {}) {
  prepareSave(state)
  Object.assign(state.form, { quantityBasis: 'SOURCE_SCOPE_TOTAL', scopeCode: 'PRODUCT_TYPE', expression: 'source_quantity', ...extra })
}
function previewResponse(operationId, payload, context, extra = {}) {
  return { contractVersion: contract, factSource: 'server', requestPayload: structuredClone(payload),
    scope: { companyId: context.companyId, operationId, ...(context.planId ? { productionPlanId: context.planId, routingStepId: context.routingStepId } : {}) },
    configurationPreview: { passed: true, isPersisted: false, statusLabel: '草稿引用及数量合同已校验', conflicts: [], blockers: [],
      normalizedSpecification: { expression: payload.expression }, specificationHash: 'SIM-DRAFT-SPEC' },
    nativeValidation: { savedRule: false },
    sourceQuantities: { statusLabel: '已证明来源数量', items: [{ sourceFactId: 6501, sourceQuantity: '2.500000', quantity: '2.500000', uomLabel: '平方米' }] },
    expressionOutputs: { statusLabel: '已得到安全表达式预计输出', items: [{ sourceFactId: 6501, sourceQuantity: '2.500000', outputQuantity: '3.750000', uomLabel: '平方米', statusLabel: '预计输出，未生成正式需求' }] },
    formalRequirements: { statusLabel: '未生成正式需求', items: [] }, savedAllocations: { statusLabel: '未保存分配', items: [], quantity: null },
    blockers: [], businessWriteCount: 0, auditWriteCount: 0, generated: false, allocationSaved: false, ...extra }
}
function applyOptionalSavedSource(fixture, payload) {
  applySavedSource(fixture, payload.traceEquals)
  Object.assign(fixture.configuration.sources[0], { quantityBasis: payload.quantityBasis, quantityExpression: payload.expression,
    effectiveFrom: payload.effectiveFrom, effectiveTo: payload.effectiveTo || null, routingContext: payload.routingContext ? structuredClone(payload.routingContext) : undefined,
    quantityBasisContract: { quantityBasis: payload.quantityBasis,
      ...(payload.basisQuantity ? { basisQuantity: payload.basisQuantity, basisUomId: payload.basisUomId } : {}) } })
}

test('新增面板和原页面可编译，原企业列表与来源对照验收分支保留', () => {
  for (const [filename, content] of [['OperationWorkloadSourcePanel.vue', source], ['ProductionFoundationMaintenance.vue', parent]]) {
    const parsed = parse(content, { filename })
    assert.deepEqual(parsed.errors, [])
    const scriptResult = compileScript(parsed.descriptor, { id: filename })
    const template = compileTemplate({ source: parsed.descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: scriptResult.bindings } })
    assert.deepEqual(template.errors, [])
  }
  assert.match(parent, /<OperationWorkloadSourcePanel\s+v-if="selectedEntity === 'operations'"/)
  assert.match(parent, /workload_source_status: \[row\.workloadSource\?\.statusLabel, row\.workloadSource\?\.summary\]/)
  for (const preserved of ['PceEnterpriseListTable', 'Group3AOperationTargetedRevalidationPage', 'source_compare', 'acceptance', 'col(\'quantity_driver\', \'历史来源说明\')']) assert.ok(parent.includes(preserved))
  assert.doesNotMatch(source, /localStorage|fetch\(|axios|OperationRequirementService|\.generate\(|\.allocate\(/)
})

test('来源、正式需求和已保存负荷分别显示；未知保持未知，正式零不丢失', async () => {
  const fixture = serverFacts({ context: planContext() })
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  state.selectedOperationId.value = '9011'; state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
  await state.loadSources()
  const text = await html(state)
  assert.match(text, /匹配的来源工程量.*1\.234567 平方米/)
  assert.match(text, /正式工序需求.*尚无正式工序需求.*数量未知/)
  assert.match(text, /计划已保存负荷.*尚无已保存计划分配.*未知 平方米/)
  assert.doesNotMatch(text, /0\.000000/)
  state.serverFacts.value.context.savedAllocations.quantity = '0.000000'
  assert.match(await html(state), /0\.000000 平方米/)
})

test('原生员工职责链阻断保存，但可读取正式来源事实；前端不扩权', async () => {
  const fixture = serverFacts({ context: planContext() })
  fixture.catalog.configureAuthorization = { allowed: false, statusLabel: '缺少在职员工、启用岗位和有效职责', blockers: [] }
  let writes = 0
  const state = runtime({ getOperationWorkloadSources: async () => fixture, saveOperationWorkloadSource: async () => { writes += 1 } })
  prepareSave(state); state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
  await state.loadSources()
  assert.equal(state.canSave.value, false)
  await state.saveSource()
  assert.equal(writes, 0)
  const text = await html(state)
  assert.match(text, /缺少在职员工、启用岗位和有效职责/)
  assert.match(text, /1\.234567 平方米/)
  state.props.mode = 'view'
  assert.doesNotMatch(await html(state), /保存并发布来源方案/)
})

test('单步骤由服务端计划自动匹配，多同工序步骤必须明确选择，不采用首条', async () => {
  const calls = []
  const fixture = serverFacts()
  const state = runtime({ getOperationWorkloadSources: async params => {
    calls.push(params)
    return params.productionPlanId ? { ...fixture, context: planContext({ scope: { productionPlanId: params.productionPlanId, routingStepId: params.routingStepId } }) } : fixture
  } })
  state.selectedOperationId.value = '9011'
  await state.loadSources()
  state.selectedPlanId.value = '5002'
  await state.changePlan()
  assert.deepEqual(calls.at(-1), { operationId: 9011, productionPlanId: 5002, routingStepId: 9809 })
  state.serverFacts.value.catalog.productionPlans[0].routingSteps.push({ id: 9810, operationId: 9011, label: '模拟第二步骤' })
  await state.changePlan()
  assert.equal(state.selectedRoutingStepId.value, '')
  assert.deepEqual(calls.at(-1), { operationId: 9011 })
  assert.match(await html(state), /同一工序有多个步骤/)
  state.selectedRoutingStepId.value = '9810'
  await state.loadSources()
  assert.deepEqual(calls.at(-1), { operationId: 9011, productionPlanId: 5002, routingStepId: 9810 })
})

test('较迟返回的旧工序响应不能覆盖新范围，读取失败不恢复旧量', async () => {
  const deferred = []
  const state = runtime({ getOperationWorkloadSources: params => new Promise((resolve, reject) => deferred.push({ params, resolve, reject })) })
  state.selectedOperationId.value = '9011'
  const first = state.loadSources()
  state.selectedOperationId.value = '9012'
  const second = state.loadSources()
  const current = serverFacts({ configuration: { operationId: 9012, statusLabel: '当前工序正式来源', sources: [], blockers: [] } })
  deferred[1].resolve(current); await second
  deferred[0].resolve(serverFacts({ configuration: { operationId: 9011, statusLabel: '旧工序来源', sources: [], blockers: [] } })); await first
  assert.equal(state.configuration.value.statusLabel, '当前工序正式来源')
  const failed = state.loadSources()
  assert.equal(state.serverFacts.value, null)
  deferred[2].reject(new Error('正式来源读取失败')); await failed
  assert.equal(state.readState.value, 'read_failed')
  assert.equal(state.serverFacts.value, null)
  const text = await html(state)
  assert.match(text, /当前来源、需求和负荷未知/)
  assert.doesNotMatch(text, /旧工序来源|当前工序正式来源|1\.234567/)
})

test('结构化保存只在明确动作发生，提交真实选项ID后重新GET读回，不生成需求或分配', async () => {
  const fixture = serverFacts()
  const calls = []
  const state = runtime({ getOperationWorkloadSources: async params => { calls.push(['GET', params]); return fixture },
    saveOperationWorkloadSource: async payload => { calls.push(['POST', payload]); applySavedSource(fixture); return { statusLabel: '来源方案已保存发布', nativeResult: { rules: [{ id: 6999, code: 'SIM-SOURCE', version: 'V8' }] } } } })
  await state.loadSources(); prepareSave(state)
  assert.equal(calls.filter(([method]) => method === 'POST').length, 0)
  assert.equal(state.canSave.value, true)
  await state.saveSource()
  assert.deepEqual(calls.map(([method]) => method), ['GET', 'POST', 'GET'])
  assert.deepEqual(calls[1][1], { operationId: 9011, ruleCode: 'SIM-SOURCE', ruleName: '模拟来源方案', version: 'V8', effectiveFrom: '2026-10-16',
    reason: 'SIMULATED_FOR_TEST', traceEquals: { contractVersion: 'SIM-FACT' }, productTypeId: 8011, modeId: 6001, producerRuleId: 6144, workCenterId: 6012, standardCapacityId: 6231 })
  assert.deepEqual(state.events, [['saved', { operationId: 9011, ruleId: 6999 }]])
})

test('保存请求返回而独立读回失败时不授予成功、不重复POST', async () => {
  let reads = 0, writes = 0
  const state = runtime({ getOperationWorkloadSources: async () => { if (++reads > 1) throw new Error('模拟读回失败'); return serverFacts() },
    saveOperationWorkloadSource: async () => { writes += 1; return { statusLabel: '保存结果返回' } } })
  await state.loadSources(); prepareSave(state)
  await state.saveSource()
  assert.equal(writes, 1)
  assert.equal(state.saveReadbackFailed.value, true)
  assert.match(state.saveMessage.value, /保存请求已返回.*独立读回失败/)
  assert.deepEqual(state.events, [])
  assert.equal(state.serverFacts.value, null)
})

test('保存后HTTP读取成功但未命中发布规则身份时，不通知保存完成', async () => {
  const fixture = serverFacts()
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    saveOperationWorkloadSource: async () => { applySavedSource(fixture); fixture.configuration.sources[0].standardCapacityId = 9999; return { ruleId: 6999 } } })
  await state.loadSources(); prepareSave(state)
  await state.saveSource()
  assert.equal(state.readState.value, 'loaded')
  assert.equal(state.saveReadbackFailed.value, true)
  assert.match(state.saveMessage.value, /独立读回尚未证明/)
  assert.deepEqual(state.events, [])
})

test('合同、来源或目录损坏不能以成功响应冒充可读事实', async () => {
  const invalidTrace = serverFacts(); invalidTrace.catalog.producers[0].traceOptions = {}
  for (const replacement of [{ ...serverFacts(), contractVersion: 'WRONG' }, { ...serverFacts(), factSource: 'client' }, { ...serverFacts(), catalog: {} }, invalidTrace]) {
    const state = runtime({ getOperationWorkloadSources: async () => replacement })
    await state.loadSources()
    assert.equal(state.readState.value, 'read_failed')
    assert.equal(state.canSave.value, false)
  }
})

test('返回错误计划范围时隐藏数量，正式范围失败的空结果保留原生阻断原因', async () => {
  let fixture = serverFacts({ context: planContext({ scope: { productionPlanId: 5999, routingStepId: 9809 } }) })
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  state.selectedOperationId.value = '9011'; state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
  await state.loadSources()
  assert.equal(state.readState.value, 'read_failed')
  assert.equal(state.serverFacts.value, null)
  fixture = serverFacts({ context: { scope: {}, sourceCandidates: { statusLabel: '来源未证明', items: [] },
    formalRequirements: { statusLabel: '尚未核对', items: [] }, savedAllocations: { statusLabel: '尚未核对', items: [], quantity: null },
    blockers: [{ statusLabel: '原生固定工程来源校验未通过' }] } })
  await state.loadSources()
  assert.equal(state.readState.value, 'loaded')
  const text = await html(state)
  assert.match(text, /原生固定工程来源校验未通过/)
  assert.doesNotMatch(text, /1\.234567/)
})

test('集中总览无需先选工序，读取28个真实返回步骤且仅GET；缺项、排除、配套和未知分别展示', async () => {
  const response = routeFixture(), fixture = routeCatalog(response), calls = []
  const state = runtime({ getOperationWorkloadSources: async params => { calls.push(['GET', params]); return params.routeOverview ? response : fixture },
    saveOperationWorkloadSource: async () => { throw new Error('总览不得写入') } })
  await state.loadSources()
  assert.equal(state.selectedOperationId.value, '')
  assert.equal(state.selectedRoutePlanId.value, '')
  assert.equal(await state.loadRouteOverview(), false)
  assert.equal(calls.length, 1)
  state.selectedRoutePlanId.value = '5002'
  assert.equal(await state.loadRouteOverview(), true)
  assert.deepEqual(calls, [['GET', {}], ['GET', { routeOverview: 1, productionPlanId: 5002 }]])
  assert.equal(state.routeRows.value.length, 28)
  assert.equal(state.routeListContract.contractVersion, 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1')
  assert.equal(state.routeRows.value.every(row => row.savedAllocations.quantity === null), true)
  const text = await html(state)
  for (const label of ['路线步骤 28 项', '模拟路线工序28', '模拟试装投入面积尚待确认', '当前对象不适用该工序',
    '配套工序，不独立计算日期', '对象适用性待确认', '总览未读取正式工序需求', '总览未读取已保存负荷；未知']) assert.ok(text.includes(label), label)
  assert.match(text, /模拟配套日产能：0\.000000 平方米 \/ 1 DAY（day）；配套零产能/)
  assert.match(text, /SIM_VISIBLE \/ V8/)
  assert.match(text, /area_quantity；来源范围总量；按正式对象范围计一次，不再乘订单数量/)
  assert.ok(text.includes('路线总览计划'))
  assert.doesNotMatch(text, /NOT_READ|NON_APPLICABLE|SIM_STANDARD_MISSING|SOURCE_SCOPE_TOTAL/)
  assert.match(source, /PceEnterpriseListTable/)
  assert.match(source, /PceEnterpriseAdvancedFilter/)
  assert.match(source, /row-key="routingStepId"/)
  assert.match(source, /@selection-change="routeSelectedRows = \$event"/)
  assert.match(source, /@export-current="routeExportCurrent"/)
  assert.equal(state.events.length, 0)
  Object.assign(state.routeFacts.value.routeConfiguration.rows[0].resourceReferences.standardCapacityCandidates[0],
    { timeBasis: 'hour', timeBasisQuantity: '8', timeUnit: 'HOUR' })
  assert.match(await html(state), /180\.000000 平方米 \/ 8 HOUR（hour）/)
})

test('集中总览拒绝错公司计划输出版本、外来或重复步骤及伪造已读取数量；不保留旧行', async () => {
  const original = routeFixture(), fixture = routeCatalog(original)
  const mutations = [
    value => { value.routeConfiguration.scope.companyId += 1 },
    value => { value.routeConfiguration.scope.productionPlanId += 1 },
    value => { value.routeConfiguration.scope.manufacturingOutputId += 1 },
    value => { value.routeConfiguration.scope.routingVersionId += 1 },
    value => { value.routeConfiguration.rows[0].operationId += 1000 },
    value => { value.routeConfiguration.rows[1].routingStepId = value.routeConfiguration.rows[0].routingStepId },
    value => { value.routeConfiguration.rows.pop() },
    value => { value.routeConfiguration.rows[0].savedAllocations.quantity = '0.000000' },
    value => { value.routeConfiguration.rows[0].formalRequirements.statusCode = 'AVAILABLE' },
    value => { value.routeConfiguration.businessWriteCount = 1 },
  ]
  let response = original
  fixture.catalog.productionPlans[0].routingSteps.pop()
  fixture.catalog.productionPlans[0].allRoutingSteps.at(-1).isActive = false
  const state = runtime({ getOperationWorkloadSources: async params => params.routeOverview ? response : fixture })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  assert.equal(state.routeReadState.value, 'loaded')
  assert.equal(state.routeRows.value.length, 28, 'allRoutingSteps preserves the inactive formal step absent from active selector options')
  for (const mutate of mutations) {
    response = structuredClone(original); mutate(response)
    assert.equal(await state.loadRouteOverview(), false)
    assert.equal(state.routeReadState.value, 'read_failed')
    assert.equal(state.routeFacts.value, null)
    assert.deepEqual(state.routeRows.value, [])
    assert.equal(state.serverFacts.value.configuration.operationId, 9011)
  }
  assert.match(await html(state), /当前路线事实未知/)
})

test('集中请求独立序列防止旧计划迟返回覆盖；失败和清空选择不恢复旧事实', async () => {
  const firstResponse = routeFixture(), nextResponse = routeFixture(5003), fixture = routeCatalog(firstResponse, nextResponse), deferred = []
  const state = runtime({ getOperationWorkloadSources: params => params.routeOverview
    ? new Promise((resolve, reject) => deferred.push({ params, resolve, reject })) : Promise.resolve(fixture) })
  await state.loadSources()
  state.selectedRoutePlanId.value = '5002'; const first = state.loadRouteOverview()
  state.selectedRoutePlanId.value = '5003'; const second = state.loadRouteOverview()
  deferred[1].resolve(nextResponse); await second
  deferred[0].resolve(firstResponse); await first
  assert.equal(state.routeConfiguration.value.scope.productionPlanId, 5003)
  assert.equal(state.routeRows.value[0].routingStepId, 10809)
  const failed = state.loadRouteOverview()
  assert.equal(state.routeFacts.value, null)
  deferred[2].reject(new Error('模拟总览读取失败')); await failed
  assert.equal(state.routeReadState.value, 'read_failed')
  assert.equal(state.routeFacts.value, null)
  const pending = state.loadRouteOverview()
  state.selectedRoutePlanId.value = ''; await state.loadRouteOverview()
  deferred[3].resolve(nextResponse); await pending
  assert.equal(state.routeReadState.value, 'idle')
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.serverFacts.value.configuration.operationId, 9011)
})

test('总览行查看按精确重复工序步骤复用旧GET；单步展示按计划收窄配置，不回退全局规则', async () => {
  const response = routeFixture()
  response.routeConfiguration.rows[1].operationId = response.routeConfiguration.rows[0].operationId
  const fixture = routeCatalog(response), calls = []
  fixture.configuration = { operationId: 9011, statusLabel: '全局投影不可替代计划规则', sources: [{ ruleId: 1, ruleName: '范围外旧规则' }] }
  const state = runtime({ getOperationWorkloadSources: async params => {
    calls.push(params)
    if (params.routeOverview) return response
    if (!params.productionPlanId) return fixture
    return { ...fixture, context: planContext({ scope: { productionPlanId: 5002, routingStepId: 9810, operationId: 9011 },
      sourceConfiguration: { operationId: 9011, statusLabel: '本计划准确步骤来源已配置', hasValidSourceConfiguration: true,
        sources: [{ ruleId: 8555, ruleName: '准确步骤来源规则', ruleVersion: 'V9' }],
        overriddenSources: [{ ruleId: 8554, ruleName: '旧通用来源规则', ruleVersion: 'V7' }], blockers: [] } }) }
  }, saveOperationWorkloadSource: async () => { throw new Error('查看动作不得保存') } })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  await state.openRouteStep(state.routeRows.value[1])
  assert.deepEqual(calls.at(-1), { operationId: 9011, productionPlanId: 5002, routingStepId: 9810 })
  assert.equal(state.matchingSteps.value.length, 2)
  assert.equal(state.selectedRoutingStepId.value, '9810')
  assert.equal(state.configuration.value.sources[0].ruleId, 8555)
  assert.equal(state.canSave.value, false)
  const text = await html(state)
  assert.match(text, /准确步骤来源规则/)
  assert.match(text, /精确步骤配置已覆盖通用回退/)
  assert.match(text, /旧通用来源规则 \/ V7/)
  assert.match(text, /数量表达未知；数量口径未知；去重口径未知/)
  assert.doesNotMatch(text, /范围外旧规则|全局投影不可替代计划规则/)
  const count = calls.length
  assert.equal(await state.openRouteStep({ routingStepId: 999999, operationId: 9011 }), false)
  assert.equal(calls.length, count)
})

test('集中表使用真实企业runtime进行筛选排序选择和当前结果导出，导出保留未知而不包含内部状态码', async () => {
  const response = routeFixture(), fixture = routeCatalog(response)
  const state = runtime({ getOperationWorkloadSources: async params => params.routeOverview ? response : fixture })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  state.routeFilters.sourceStatusLabel = '缺少正式面积标准'
  assert.equal(state.routeActiveFilterCount.value, 1)
  assert.deepEqual(state.routeFilteredRows.value.map(row => row.sequence), [2])
  state.routeClearFilters()
  state.routeQuickSearch.value = '配套工序，不独立计算日期'; state.routeAppliedSearch.value = state.routeQuickSearch.value
  assert.deepEqual(state.routeFilteredRows.value.map(row => row.sequence), [4])
  state.routeSelectedRows.value = [...state.routeFilteredRows.value]
  assert.equal(state.routeSelectedRows.value.length, 1)
  state.routeClearSelection(); assert.deepEqual(state.routeSelectedRows.value, [])
  state.routeClearFilters(); state.routeHandleSort({ prop: 'sequence', order: 'descending' })
  assert.equal(state.routeFilteredRows.value[0].sequence, 28)
  const previousDocument = globalThis.document, previousWindow = globalThis.window
  let clicked = 0
  globalThis.document = { body: { appendChild() {} }, createElement: () => ({ click() { clicked += 1 }, remove() {} }) }
  globalThis.window = { setTimeout(callback) { callback() } }
  try {
    const exported = state.routeExportCurrent()
    assert.equal(exported.rowCount, 28)
    assert.equal(clicked, 1)
    assert.match(exported.csv, /总览未读取已保存负荷；未知/)
    assert.match(exported.csv, /配套零产能/)
    assert.doesNotMatch(exported.csv, /NOT_READ|NON_APPLICABLE|SIM_STANDARD_MISSING/)
    state.routeFilters.sourceStatusLabel = '缺少正式面积标准'
    assert.equal(state.routeExportCurrent().rowCount, 1)
  } finally {
    if (previousDocument === undefined) delete globalThis.document; else globalThis.document = previousDocument
    if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow
  }
  state.routeClearSort()
  assert.equal(state.routeFilteredRows.value[0].sequence, 2)
})

test('维护使用当前PCT唯一正式来源条件自动解析，POST绑定原traceEquals而非空条件', async () => {
  const fixture = serverFacts(), writes = []
  const trace = { contractVersion: 'SIM-FACT', AreaType: 'VISIBLE_AREA', ProductPaintingProcessCode: 'SIM/FULL' }
  fixture.catalog.producers[0].traceOptions = [
    { key: 'sim-current-condition', productTypeId: 8011, traceEquals: trace, statusLabel: '模拟完整工艺见光面积条件' },
    { key: 'sim-other-product', productTypeId: 8999, traceEquals: { ProductPaintingProcessCode: 'OTHER' }, statusLabel: '其他产品条件' },
  ]
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    saveOperationWorkloadSource: async payload => { writes.push(payload); applySavedSource(fixture, payload.traceEquals); return { ruleId: 6999 } } })
  await state.loadSources(); prepareSave(state)
  assert.equal(state.form.traceOptionKey, '')
  assert.deepEqual(state.traceOptions.value.map(option => option.key), ['sim-current-condition'])
  assert.equal(state.selectedTraceOption.value.key, 'sim-current-condition')
  assert.equal(state.canSave.value, true)
  const text = await html(state)
  assert.match(text, /正式来源条件.*模拟完整工艺见光面积条件/)
  assert.doesNotMatch(text, /其他产品条件/)
  await state.saveSource()
  assert.equal(writes.length, 1)
  assert.deepEqual(writes[0].traceEquals, trace)
  assert.notEqual(writes[0].traceEquals, trace, 'payload owns a copy of the selected formal condition')
  assert.deepEqual(state.events, [['saved', { operationId: 9011, ruleId: 6999 }]])
})

test('多个正式来源条件不采用首条，错PCT和失效选择不能保存，明选后提交准确条件', async () => {
  const fixture = serverFacts(), writes = []
  fixture.catalog.producers[0].traceOptions = [
    { key: 'sim-a', productTypeId: 8011, traceEquals: { contractVersion: 'SIM-FACT', AreaType: 'A' }, label: '正式条件甲' },
    { key: 'sim-b', productTypeId: 8011, traceEquals: { contractVersion: 'SIM-FACT', AreaType: 'B' }, label: '正式条件乙' },
    { key: 'sim-outside', productTypeId: 8999, traceEquals: { AreaType: 'OUTSIDE' }, label: '其他产品条件' },
  ]
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    saveOperationWorkloadSource: async payload => { writes.push(payload); applySavedSource(fixture, payload.traceEquals); return { ruleId: 6999 } } })
  await state.loadSources(); prepareSave(state)
  assert.equal(state.selectedTraceOption.value, undefined)
  assert.equal(state.canSave.value, false)
  await state.saveSource(); assert.equal(writes.length, 0)
  assert.match(await html(state), /存在多个正式来源条件，请明确选择/)
  state.form.traceOptionKey = 'sim-outside'
  assert.equal(state.canSave.value, false)
  state.refreshResourceSelection(); assert.equal(state.form.traceOptionKey, '')
  state.form.traceOptionKey = 'sim-b'
  assert.equal(state.canSave.value, true)
  await state.saveSource()
  assert.deepEqual(writes[0].traceEquals, { contractVersion: 'SIM-FACT', AreaType: 'B' })
  state.form.productTypeId = '8888'
  assert.equal(state.traceOptions.value.length, 0)
  assert.equal(state.canSave.value, false)
  assert.match(await html(state), /当前产品类型没有匹配的正式来源条件/)
})

test('来源条件保存后读回若traceEquals不同，即使规则与资源身份相同也不通知成功', async () => {
  const fixture = serverFacts()
  fixture.catalog.producers[0].traceOptions = [{ key: 'sim-exact', productTypeId: 8011,
    traceEquals: { contractVersion: 'SIM-FACT', AreaType: 'EXPECTED' }, label: '本次正式来源条件' }]
  const state = runtime({ getOperationWorkloadSources: async () => fixture, saveOperationWorkloadSource: async () => {
    applySavedSource(fixture, { contractVersion: 'SIM-FACT', AreaType: 'WRONG' }); return { ruleId: 6999 }
  } })
  await state.loadSources(); prepareSave(state); await state.saveSource()
  assert.equal(state.saveReadbackFailed.value, true)
  assert.deepEqual(state.events, [])
  assert.match(state.saveMessage.value, /独立读回尚未证明/)
})

test('正式对象排除的单步三卡显示不适用，区别于缺需求未知且不填已保存零负荷', async () => {
  const notApplicable = { statusCode: 'NOT_APPLICABLE', statusLabel: '当前三个对象正式不适用该工序', items: [], blockers: [] }
  const fixture = serverFacts({ context: planContext({ applicability: { result: 'NOT_APPLICABLE', resultLabel: '当前三个对象正式排除' },
    sourceConfiguration: { ...notApplicable, sources: [] }, sourceCandidates: { ...notApplicable },
    formalRequirements: { ...notApplicable }, savedAllocations: { ...notApplicable, quantity: null, uomLabel: null } }) })
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  state.selectedOperationId.value = '9011'; state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
  await state.loadSources()
  const text = await html(state)
  assert.match(text, /匹配的来源工程量.*不适用，不形成该项数量/)
  assert.match(text, /正式工序需求.*不适用，不形成该项数量/)
  assert.match(text, /计划已保存负荷.*不适用，不形成该项保存负荷/)
  assert.doesNotMatch(text, /数量未知|未知 平方米|0\.000000|已保存且通过/)
})

test('刷新开始立即使旧总览失效，来源失败后明确未知并保留计划和筛选，重试成功才呈现新配置', async () => {
  const response = routeFixture(), fixture = routeCatalog(response), pending = deferredResult()
  let ordinaryRead = 'initial'
  const state = runtime({ getOperationWorkloadSources: async params => params.routeOverview ? response
    : ordinaryRead === 'pending' ? pending.promise : fixture })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  state.routeFilters.sourceStatusLabel = '缺少正式面积标准'
  state.routeQuickSearch.value = '模拟'; state.routeAppliedSearch.value = '模拟'
  state.routeSelectedRows.value = [state.routeRows.value[1]]
  ordinaryRead = 'pending'
  const refreshing = state.refreshSourceFacts()
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeReadState.value, 'loading')
  pending.reject(new Error('模拟基础来源刷新失败')); await refreshing
  assert.equal(state.serverFacts.value, null)
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeReadState.value, 'read_failed')
  assert.equal(state.selectedRoutePlanId.value, '5002')
  assert.equal(state.routeFilters.sourceStatusLabel, '缺少正式面积标准')
  assert.equal(state.routeAppliedSearch.value, '模拟')
  assert.equal(state.routeSelectedRows.value.length, 1)
  const text = await html(state)
  assert.match(text, /来源事实刷新失败.*当前路线事实未知/)
  assert.doesNotMatch(text, /模拟路线工序28|模拟见光面积规则28/)
  ordinaryRead = 'recovered'
  response.routeConfiguration.rows[0].sourceConfiguration.sources[0].ruleName = '本次重新验证的来源规则'
  assert.equal(await state.refreshSourceFacts(), true)
  assert.equal(state.routeReadState.value, 'loaded')
  assert.match(state.routeRows.value[0].sourceRuleText, /本次重新验证/)
  assert.equal(state.routeFilters.sourceStatusLabel, '缺少正式面积标准')
})

test('整体刷新使此前未完成的总览GET失效，旧成功响应不能越过本次失败恢复旧配置', async () => {
  const response = routeFixture(), fixture = routeCatalog(response), oldOverview = deferredResult(), sourceRefresh = deferredResult()
  let sourceCalls = 0, overviewCalls = 0
  const state = runtime({ getOperationWorkloadSources: params => params.routeOverview
    ? ++overviewCalls === 1 ? Promise.resolve(response) : oldOverview.promise
    : ++sourceCalls === 1 ? Promise.resolve(fixture) : sourceRefresh.promise })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  const old = state.loadRouteOverview()
  const refreshing = state.refreshSourceFacts()
  sourceRefresh.reject(new Error('模拟刷新拒绝')); await refreshing
  oldOverview.resolve(response); await old
  assert.equal(state.routeReadState.value, 'read_failed')
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeRows.value.length, 0)
})

test('较新刷新完成后旧刷新失败不覆盖其总览，也不发出旧刷新衍生的总览读取', async () => {
  const response = routeFixture(), fixture = routeCatalog(response), firstSource = deferredResult(), secondSource = deferredResult()
  const newOverview = deferredResult(), overviewRequested = deferredResult()
  let sourceCalls = 0, overviewCalls = 0
  const state = runtime({ getOperationWorkloadSources: params => {
    if (!params.routeOverview) return ++sourceCalls === 1 ? Promise.resolve(fixture) : sourceCalls === 2 ? firstSource.promise : secondSource.promise
    if (++overviewCalls === 1) return Promise.resolve(response)
    overviewRequested.resolve(); return newOverview.promise
  } })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  const old = state.refreshSourceFacts(), current = state.refreshSourceFacts()
  secondSource.resolve(fixture); await overviewRequested.promise
  const currentResponse = structuredClone(response)
  currentResponse.routeConfiguration.rows[0].sourceConfiguration.statusLabel = '本次最新来源配置'
  newOverview.resolve(currentResponse); await current
  firstSource.reject(new Error('较旧刷新后来失败')); await old
  assert.equal(state.routeReadState.value, 'loaded')
  assert.equal(state.routeRows.value[0].sourceStatusLabel, '本次最新来源配置')
  assert.equal(overviewCalls, 2)
})

test('保存开始失效旧总览；提交已返回而独立读回失败时不保留旧来源、不重复POST', async () => {
  const response = routeFixture(), fixture = routeCatalog(response), submission = deferredResult()
  let sourceCalls = 0, writes = 0
  const state = runtime({ getOperationWorkloadSources: async params => {
    if (params.routeOverview) return response
    if (++sourceCalls > 1) throw new Error('模拟保存后的独立读回失败')
    return fixture
  }, saveOperationWorkloadSource: () => { writes += 1; return submission.promise } })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview(); prepareSave(state)
  state.routeFilters.sourceStatusLabel = '缺少正式面积标准'
  const saving = state.saveSource()
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeReadState.value, 'loading')
  submission.resolve({ ruleId: 6999 }); await saving
  assert.equal(writes, 1)
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeReadState.value, 'read_failed')
  assert.match(state.saveMessage.value, /保存请求已返回.*独立读回失败/)
  assert.match(state.routeReadError.value, /保存请求已返回.*独立读回失败/)
  assert.equal(state.selectedRoutePlanId.value, '5002')
  assert.equal(state.routeFilters.sourceStatusLabel, '缺少正式面积标准')
  assert.deepEqual(state.events, [])
})

test('保存响应未确认时总览保持读取失败，准确保留未确认结果且不自动重试写入', async () => {
  const response = routeFixture(), fixture = routeCatalog(response)
  let writes = 0
  const state = runtime({ getOperationWorkloadSources: async params => params.routeOverview ? response : fixture,
    saveOperationWorkloadSource: async () => { writes += 1; throw new Error('模拟传输中断，提交结果未确认') } })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview(); prepareSave(state)
  await state.saveSource()
  assert.equal(writes, 1)
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeReadState.value, 'read_failed')
  assert.match(state.saveMessage.value, /来源方案未确认保存.*提交结果未确认/)
  assert.deepEqual(state.events, [])
})

test('工程EOR专用来源用途与产能来源不经过并列可见，不能扩成APS独立产能结论', async () => {
  const response = routeFixture(), row = response.routeConfiguration.rows[5]
  row.applicability = { result: 'REQUIRED', resultLabel: '路线解析仍要求执行' }
  row.capacityRole = 'NON_APPLICABLE'
  row.capacityApplicability = { result: 'NON_APPLICABLE', statusLabel: '正式产能来源声明此产品不经过该工序' }
  row.sourceConfiguration.sources[0].capacityUsageScopeLabel = '规则声明工程EOR专用产能；不代表APS独立产能或投产通过'
  const fixture = routeCatalog(response)
  const state = runtime({ getOperationWorkloadSources: async params => params.routeOverview ? response : fixture })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'; await state.loadRouteOverview()
  const text = await html(state)
  assert.match(text, /规则声明工程EOR专用产能；不代表APS独立产能或投产通过/)
  assert.match(text, /正式产能来源声明此产品不经过该工序/)
  assert.match(text, /路线解析仍要求执行/)
  assert.equal(state.routeRows.value[5].applicability.result, 'REQUIRED')
  assert.equal(state.routeRows.value[5].capacityRole, 'NON_APPLICABLE')
  assert.equal(state.routeRows.value[5].savedAllocations.quantity, null)
  assert.match(state.routeRows.value[5].purposeText, /工程EOR专用/)
})

test('只读账号可选择正式草稿并预览，原量与预计输出分开；缺职责链仍不能保存', async () => {
  const fixture = optionalFixture(), previews = [], writes = []
  fixture.catalog.configureAuthorization = { allowed: false, statusLabel: '缺少正式岗位责任链', blockers: [] }
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => { previews.push(structuredClone(args)); return previewResponse(...args) },
    saveOperationWorkloadSource: async payload => writes.push(payload) }, { mode: 'view' })
  await state.loadSources(); prepareOptional(state, { expression: 'source_quantity * 1.5', reason: '' })
  state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
  assert.equal(state.canPreview.value, true)
  assert.equal(state.canSave.value, false)
  assert.equal(await state.previewSourceConfiguration(), true)
  assert.deepEqual(previews[0][2], { companyId: 6099, planId: 5002, routingStepId: 9809 })
  assert.equal(Object.hasOwn(previews[0][1], 'operationId'), false)
  assert.equal(Object.hasOwn(previews[0][1], 'reason'), false)
  await state.saveSource(); assert.equal(writes.length, 0)
  const text = await html(state)
  assert.match(text, /来源方案草稿与校验/)
  assert.match(text, /正式来源工程量.*2\.500000 平方米.*安全表达式预计输出.*3\.750000 平方米/)
  assert.match(text, /正式分组汇总来源，保留原始输入证明/)
  assert.match(text, /正式引用校验不替代投入面积语义认证/)
  assert.match(text, /精确步骤优先；冲突不能默认为通过/)
  assert.match(text, /未生成正式需求或保存分配/)
  assert.match(text, /缺少正式岗位责任链/)
  assert.doesNotMatch(text, /保存并发布来源方案|NOT_SUPPORTED|SOURCE_SCOPE_TOTAL/)
  state.props.mode = 'maintain'
  assert.equal(state.canSave.value, false)
})

test('按基数表达式、基准单位、精确路线与失效日期均提交；仅当前预览通过后保存并独立读回', async () => {
  const fixture = optionalFixture(), calls = []
  const state = runtime({ getOperationWorkloadSources: async () => { calls.push('GET'); return fixture },
    previewOperationWorkloadSourceConfiguration: async (...args) => { calls.push('PREVIEW'); return previewResponse(...args) },
    saveOperationWorkloadSource: async payload => { calls.push(['SAVE', structuredClone(payload)]); applyOptionalSavedSource(fixture, payload); return { ruleId: 6999 } } })
  await state.loadSources(); prepareOptional(state, { quantityBasis: 'PER_BASIS_QUANTITY', basisQuantity: '1.000000', basisUomId: '6182',
    expression: '(source_quantity * 3) / 2', scopeCode: 'ROUTING_STEP', routingContextKey: '7301:7401:9809', effectiveTo: '2026-12-31' })
  assert.equal(state.canSave.value, false)
  await state.saveSource(); assert.deepEqual(calls, ['GET'])
  assert.equal(await state.previewSourceConfiguration(), true)
  assert.equal(state.canSave.value, true)
  await state.saveSource()
  assert.deepEqual(calls.map(value => Array.isArray(value) ? value[0] : value), ['GET', 'PREVIEW', 'SAVE', 'GET'])
  const payload = calls[2][1]
  assert.equal(payload.quantityBasis, 'PER_BASIS_QUANTITY')
  assert.equal(payload.basisQuantity, '1.000000')
  assert.equal(payload.basisUomId, 6182)
  assert.equal(payload.expression, '(source_quantity * 3) / 2')
  assert.equal(payload.effectiveTo, '2026-12-31')
  assert.deepEqual(payload.routingContext, { contractVersion: 'PCE-MANUFACTURING-ROUTING-CONTEXT-V1', routingId: 7301, routingVersionId: 7401, routingStepId: 9809 })
  assert.equal(Object.hasOwn(payload, 'productionPlanId'), false)
  assert.deepEqual(state.events, [['saved', { operationId: 9011, ruleId: 6999 }]])
})

test('动态目录按正式单位及资源关联收窄，不封闭生产场景，错误单位选择失效', async () => {
  const fixture = optionalFixture()
  fixture.operations.push({ id: 9020, label: '模拟重量计量场景', calculation_uom_id: 6190 })
  fixture.catalog.units.push({ id: 6190, label: '千克', code: 'kg', dimension: 'mass' })
  fixture.catalog.producers.push({ id: 6150, label: '模拟重量明细来源', version: 'V2', uomId: 6190, sourceSemantics: { strategy: 'OBJECT_FORMULA', statusLabel: '对象明细来源' } })
  fixture.catalog.manufacturingModes.push({ id: 6002, label: '模拟重量模式', uomId: 6190 })
  fixture.catalog.workCenters.push({ id: 6015, label: '模拟重量工作中心' })
  fixture.catalog.standardCapacities.push({ id: 6240, label: '模拟重量产能', operationId: 9020, productTypeId: 8011, workCenterId: 6015, uomId: 6190 })
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  await state.loadSources(); prepareOptional(state)
  assert.deepEqual(state.optionsFor('producerRuleId').map(row => row.id), [6144])
  assert.deepEqual(state.optionsFor('modeId').map(row => row.id), [6001])
  assert.deepEqual(state.optionsFor('standardCapacityId').map(row => row.id), [6231])
  state.selectedOperationId.value = '9020'; state.refreshResourceSelection()
  assert.equal(state.form.producerRuleId, '')
  assert.equal(state.form.modeId, '')
  assert.equal(state.form.workCenterId, '')
  assert.equal(state.form.standardCapacityId, '')
  assert.deepEqual(state.optionsFor('producerRuleId').map(row => row.id), [6150])
  assert.deepEqual(state.optionsFor('modeId').map(row => row.id), [6002])
  assert.deepEqual(state.optionsFor('workCenterId').map(row => row.id), [6015])
  assert.deepEqual(state.optionsFor('standardCapacityId').map(row => row.id), [6240])
  Object.assign(state.form, { producerRuleId: '6150', modeId: '6002', workCenterId: '6015', standardCapacityId: '6240' })
  assert.equal(state.draftFieldsComplete.value, true)
  assert.match(await html(state), /模拟重量明细来源.*对象明细来源/)
})

test('范围和数量合同由目录驱动，缺基数或精确路线不能校验，多同工序计划不能降级为无计划预览', async () => {
  const fixture = optionalFixture(), calls = []
  fixture.catalog.productionPlans[0].routingSteps.push({ id: 9811, operationId: 9011, label: '模拟同工序另一步骤' })
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => { calls.push(args); return previewResponse(...args) } })
  await state.loadSources(); prepareOptional(state, { quantityBasis: 'PER_BASIS_QUANTITY', scopeCode: 'ROUTING_STEP' })
  assert.deepEqual(state.routingOptions.value.map(row => row.routingStepId), [9809])
  assert.equal(state.canPreview.value, false)
  Object.assign(state.form, { basisQuantity: '2', basisUomId: '6182', routingContextKey: '7302:7402:9810' })
  assert.equal(state.canPreview.value, false)
  state.form.routingContextKey = '7301:7401:9809'
  assert.equal(state.canPreview.value, true)
  state.selectedPlanId.value = '5002'
  assert.equal(state.canPreview.value, false)
  assert.equal(await state.previewSourceConfiguration(), false)
  assert.equal(calls.length, 0)
  state.selectedRoutingStepId.value = '9811'
  assert.equal(await state.previewSourceConfiguration(), true)
  assert.deepEqual(calls[0][2], { companyId: 6099, planId: 5002, routingStepId: 9811 })
  state.form.productTypeId = '8999'; state.refreshResourceSelection()
  assert.equal(state.form.routingContextKey, '')
})

test('草稿字段、条件和生产规则版本改变即清除旧预览，晚响应不得恢复旧成功', async () => {
  const fixture = optionalFixture(), first = deferredResult(), second = deferredResult(), requests = []
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: (...args) => { requests.push(structuredClone(args)); return requests.length === 1 ? first.promise : second.promise } })
  await state.loadSources(); prepareOptional(state)
  const old = state.previewSourceConfiguration()
  state.form.expression = 'source_quantity * 2'
  assert.equal(state.previewState.value, 'idle')
  const latest = state.previewSourceConfiguration()
  second.resolve(previewResponse(...requests[1])); await latest
  assert.equal(state.currentPreview.value.requestPayload.expression, 'source_quantity * 2')
  first.resolve(previewResponse(...requests[0])); assert.equal(await old, false)
  assert.equal(state.currentPreview.value.requestPayload.expression, 'source_quantity * 2')
  state.serverFacts.value.catalog.producers[0].specificationHash = 'SIM-CHANGED-HASH'
  assert.equal(state.currentPreview.value, null)
  assert.equal(state.canSave.value, false)
  assert.equal(state.previewState.value, 'idle')
})

test('预览严格绑定公司、工序、计划步骤及payload回显，非零写入或持久化声明均拒绝展示', async () => {
  const variants = [
    value => { value.scope.companyId = 6100 }, value => { value.scope.operationId = 9012 },
    value => { value.scope.productionPlanId = 5003 }, value => { value.scope.routingStepId = 9810 },
    value => { value.requestPayload.expression = 'source_quantity + 100' },
    value => { value.businessWriteCount = 1 }, value => { value.auditWriteCount = 1 },
    value => { value.configurationPreview.isPersisted = true }, value => { value.nativeValidation.savedRule = true },
  ]
  for (const alter of variants) {
    const fixture = optionalFixture()
    const state = runtime({ getOperationWorkloadSources: async () => fixture,
      previewOperationWorkloadSourceConfiguration: async (...args) => { const value = previewResponse(...args); alter(value); return value } })
    await state.loadSources(); prepareOptional(state)
    state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
    assert.equal(await state.previewSourceConfiguration(), false)
    assert.equal(state.previewState.value, 'read_failed')
    assert.equal(state.currentPreview.value, null)
    assert.equal(state.canSave.value, false)
    assert.match(state.previewError.value, /与本次配置或范围不一致/)
  }
})

test('服务端表达式单位或规则冲突保留原说明，校验未通过不能保存，不显示机器代码', async () => {
  const fixture = optionalFixture(), writes = []
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => previewResponse(...args, {
      configurationPreview: { passed: false, isPersisted: false, statusCode: 'BLOCKED', statusLabel: '草稿校验受阻',
        conflicts: [{ code: 'SIM_CONFLICT', statusLabel: '当前生效范围存在同精度规则冲突' }],
        blockers: [{ code: 'SIM_UNIT', statusLabel: '表达式输出单位与工序单位不一致' }] },
      sourceQuantities: { statusLabel: '来源未求值', items: [] }, expressionOutputs: { statusLabel: '输出未求值', items: [] },
    }), saveOperationWorkloadSource: async payload => writes.push(payload) })
  await state.loadSources(); prepareOptional(state, { expression: 'source_quantity / 0' })
  assert.equal(await state.previewSourceConfiguration(), false)
  assert.equal(state.previewState.value, 'loaded')
  assert.equal(state.canSave.value, false)
  await state.saveSource(); assert.equal(writes.length, 0)
  const text = await html(state)
  assert.match(text, /当前生效范围存在同精度规则冲突/)
  assert.match(text, /表达式输出单位与工序单位不一致/)
  assert.match(text, /来源数量未知.*预计输出未知/)
  assert.doesNotMatch(text, /SIM_CONFLICT|SIM_UNIT|BLOCKED|0\.000000/)
})

test('无计划纯配置校验不伪造来源或预计量，网络失败及清空选择不保留上次成功', async () => {
  const fixture = optionalFixture(), pending = deferredResult()
  let mode = 'success'
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: (...args) => mode === 'pending' ? pending.promise : Promise.resolve(previewResponse(...args, {
      sourceQuantities: { statusCode: 'NOT_EVALUATED', statusLabel: '未指定计划，来源未求值', items: [] },
      expressionOutputs: { statusCode: 'NOT_EVALUATED', statusLabel: '未指定计划，表达式未求值', items: [] },
    })) })
  await state.loadSources(); prepareOptional(state)
  assert.equal(await state.previewSourceConfiguration(), true)
  assert.match(await html(state), /未指定计划，来源未求值.*来源数量未知.*未指定计划，表达式未求值.*预计输出未知/)
  mode = 'pending'
  const current = state.previewSourceConfiguration()
  assert.equal(state.currentPreview.value, null)
  pending.reject(new Error('模拟只读校验连接失败')); await current
  assert.equal(state.previewState.value, 'read_failed')
  assert.equal(state.currentPreview.value, null)
  state.selectedOperationId.value = ''
  assert.equal(state.previewState.value, 'idle')
  assert.equal(state.previewError.value, '')
})

test('保存独立读回同时核对数量合同、表达式、基准单位、路线及有效期，同规则ID不能掩盖语义变化', async () => {
  const variants = [
    source => { source.quantityExpression = 'source_quantity' },
    source => { source.quantityBasisContract.basisQuantity = '9' },
    source => { source.quantityBasisContract.basisUomId = 6181 },
    source => { source.routingContext.routingStepId = 9810 },
    source => { source.effectiveTo = '2027-01-01' },
  ]
  for (const alter of variants) {
    const fixture = optionalFixture(); let writes = 0
    const state = runtime({ getOperationWorkloadSources: async () => fixture,
      previewOperationWorkloadSourceConfiguration: async (...args) => previewResponse(...args),
      saveOperationWorkloadSource: async payload => { writes += 1; applyOptionalSavedSource(fixture, payload); alter(fixture.configuration.sources[0]); return { ruleId: 6999 } } })
    await state.loadSources(); prepareOptional(state, { quantityBasis: 'PER_BASIS_QUANTITY', basisQuantity: '1', basisUomId: '6182',
      expression: 'source_quantity * 2', scopeCode: 'ROUTING_STEP', routingContextKey: '7301:7401:9809', effectiveTo: '2026-12-31' })
    await state.previewSourceConfiguration(); await state.saveSource()
    assert.equal(writes, 1)
    assert.equal(state.saveReadbackFailed.value, true)
    assert.deepEqual(state.events, [])
    assert.match(state.saveMessage.value, /独立读回尚未证明/)
  }
})

test('重复预览问题只按完整JSON去重，保留不同事实对象及规则身份和原始服务端说明', async () => {
  const fixture = optionalFixture()
  const common = { code: 'MANUFACTURING_VERSION_CONFLICT', statusLabel: '原生发布范围版本冲突', ruleId: 6999,
    sourceFactId: 6501, object: { baselineItemId: 7201, designItemId: 7301 } }
  const sameWithDifferentKeyOrder = { object: { designItemId: 7301, baselineItemId: 7201 }, sourceFactId: 6501,
    ruleId: 6999, statusLabel: '原生发布范围版本冲突', code: 'MANUFACTURING_VERSION_CONFLICT' }
  const otherFact = { ...common, sourceFactId: 6502 }
  const otherObject = { ...common, object: { baselineItemId: 7202, designItemId: 7302 } }
  const otherRule = { ...common, ruleId: 6998 }
  const otherLabel = { ...common, statusLabel: '同身份但不同原生补充说明' }
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => previewResponse(...args, {
      configurationPreview: { passed: false, isPersisted: false, statusLabel: '草稿校验受阻', conflicts: [common],
        blockers: [sameWithDifferentKeyOrder, otherFact] },
      blockers: [structuredClone(common), otherObject, otherRule, otherLabel],
    }) })
  await state.loadSources(); prepareOptional(state)
  assert.equal(await state.previewSourceConfiguration(), false)
  assert.deepEqual(JSON.parse(JSON.stringify(state.previewIssues.value)), [common, otherFact, otherObject, otherRule, otherLabel])
  assert.equal(state.canSave.value, false)
  const text = await html(state)
  assert.equal(text.match(/原生发布范围版本冲突/g).length, 4, 'identical issue appears once; three distinct identities remain')
  assert.match(text, /同身份但不同原生补充说明/)
  assert.doesNotMatch(text, /MANUFACTURING_VERSION_CONFLICT/)
})

test('准确计划步骤展示正式准备状态、原答复出处及范围，来源需求负荷缺项保持且读取零写', async () => {
  const fixture = preparationFixture(), calls = [], writes = []
  const state = runtime({ getOperationWorkloadSources: async params => { calls.push(params); return fixture },
    saveOperationWorkloadSource: async value => writes.push(value) }, { mode: 'view' })
  selectPreparationContext(state)
  assert.equal(await state.loadSources(), true)
  assert.deepEqual(calls, [{ operationId: 9011, productionPlanId: 5002, routingStepId: 9809 }])
  assert.equal(state.inputPreparation.value.recordId, 7901)
  assert.equal(state.configuration.value.hasValidSourceConfiguration, false)
  assert.equal(state.canSave.value, false)
  const text = await html(state)
  for (const label of ['本次必须执行', '工序投入准备记录', '准备记录已纠正，原产能结论已撤销', '投入标准 待确认',
    '当前产能裁决 经过但无法准确核算，不计定量产能占用', '准备记录业务裁决值 0', '正式标准产能数量 未知',
    '准备记录未发布正式规则', '模拟历史原答复：投入标准待确认；原产能结论已被最新裁决撤销。',
    '出处：模拟责任人原答复档案', '适用范围：模拟工艺编码 / 路线第3序·模拟加工工序 / 模拟计划 / 三个模拟设计对象',
    '来源尚未配置', '缺少该工序正式来源规则', '正式需求缺失', '已保存负荷未知', '理论用时及日期条件不足']) assert.ok(text.includes(label), label)
  assert.match(text, /匹配的来源工程量.*来源数量尚未证明.*数量未知/)
  assert.doesNotMatch(text, /PENDING_CONFIRMATION|UNMEASURED|RECORDED|OPERATION_RULE_MAPPING_MISSING|SOURCE_STANDARD_PENDING|0\.000000/)
  assert.deepEqual(writes, [])
  assert.deepEqual(state.events, [])
  assert.equal(state.form.producerRuleId, '')
  assert.equal(state.form.standardCapacityId, '')
})

test('无正式准备记录保持尚未记录，不能从空产能推断尚未测定或待确认', async () => {
  const fixture = preparationFixture(false)
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  selectPreparationContext(state)
  assert.equal(await state.loadSources(), true)
  const text = await html(state)
  assert.match(text, /尚无正式准备记录.*投入标准 尚未记录.*当前产能裁决 尚未记录/)
  assert.doesNotMatch(text, /准备记录已保存|产能测定 尚未测定|投入标准 待确认|0\.000000|not_determinable|zero_capacity/)
  fixture.context.inputPreparation.inputStandardStatus = 'PENDING_CONFIRMATION'
  assert.equal(await state.loadSources(), false)
  assert.equal(state.serverFacts.value, null)
  assert.match(state.readError.value, /尚无准备记录不能声明/)
})

test('准备记录拒绝错公司完整范围、非零写入、虚构已就绪与零产能替代，损坏后不保留旧事实', async () => {
  const variants = [
    value => { value.context.inputPreparation.contractVersion = 'WRONG' },
    value => { value.context.inputPreparation.factSource = 'client' },
    value => { value.context.inputPreparation.exactScope.companyId += 1 },
    value => { value.context.inputPreparation.exactScope.manufacturingOutputId += 1 },
    value => { value.context.inputPreparation.exactScope.baselineId += 1 },
    value => { value.context.inputPreparation.exactScope.routingVersionId += 1 },
    value => { value.context.inputPreparation.exactScope.routingStepId += 1 },
    value => { value.context.inputPreparation.exactScope.salesOrderItemId += 1 },
    value => { value.context.inputPreparation.businessWriteCount = 1 },
    value => { value.context.inputPreparation.auditWriteCount = 1 },
    value => { value.context.inputPreparation.stateTransitionWriteCount = 1 },
    value => { value.context.inputPreparation.supportWriteCount = 1 },
    value => { value.context.inputPreparation.formalRulePublished = true },
    value => { value.context.inputPreparation.readyForGeneration = true },
    value => { value.context.inputPreparation.readyForAllocation = true },
    value => { value.context.inputPreparation.readyForScheduling = true },
    value => { value.context.inputPreparation.capacityQuantity = '0.000000' },
    value => { value.context.inputPreparation.inputQuantity = '0.000000' },
    value => { value.context.inputPreparation.capacityMeasurementStatus = 'UNMEASURED' },
    value => { value.context.inputPreparation.capacityMeasurementStatus = 'not_determinable' },
    value => { value.context.inputPreparation.businessBasis.entries = [] },
    value => { value.context.inputPreparation.scopeLabel = '' },
    value => { value.context.inputPreparation.businessBasis.entries[0].reference = '' },
    value => { value.context.inputPreparation.remainingItems[0] = { code: 'INTERNAL_CODE_ONLY' } },
    value => { value.context.scope = {}; value.context.blockers = [{ statusLabel: '精确上下文失效' }] },
  ]
  for (const alter of variants) {
    let fixture = preparationFixture()
    const state = runtime({ getOperationWorkloadSources: async () => fixture })
    selectPreparationContext(state)
    assert.equal(await state.loadSources(), true)
    fixture = preparationFixture(); alter(fixture)
    assert.equal(await state.loadSources(), false)
    assert.equal(state.readState.value, 'read_failed')
    assert.equal(state.serverFacts.value, null)
    assert.equal(state.inputPreparation.value, null)
    assert.equal(state.canSave.value, false)
    assert.doesNotMatch(await html(state), /准备记录已纠正|模拟历史原答复|0\.000000/)
  }
})

test('新准备状态不放行正式发布；动态目录、只读预览和现有服务端原规则门禁继续生效', async () => {
  const fixture = preparationFixture(), writes = [], previews = []
  fixture.catalog.configureAuthorization = { allowed: false, statusLabel: '原正式规则发布职责链尚未通过', blockers: [] }
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => { previews.push(args); return previewResponse(...args) },
    saveOperationWorkloadSource: async value => writes.push(value) })
  selectPreparationContext(state)
  await state.loadSources()
  assert.equal(state.canSave.value, false)
  assert.deepEqual(state.optionsFor('producerRuleId').map(row => row.id), [6144])
  assert.deepEqual(state.optionsFor('standardCapacityId').map(row => row.id), [6231])
  prepareOptional(state)
  assert.equal(await state.previewSourceConfiguration(), true)
  assert.equal(previews.length, 1)
  assert.equal(state.canSave.value, false)
  await state.saveSource()
  assert.deepEqual(writes, [])
  const text = await html(state)
  assert.match(text, /准备记录已纠正，原产能结论已撤销/)
  assert.match(text, /原正式规则发布职责链尚未通过/)
  assert.match(text, /仅校验本次草稿；未生成正式需求或保存分配/)
  assert.equal(state.configuration.value.hasValidSourceConfiguration, false)
})

test('较迟旧步骤准备事实不能覆盖新上下文，读取失败后不恢复已保存准备状态', async () => {
  const first = deferredResult(), second = deferredResult()
  let calls = 0
  const state = runtime({ getOperationWorkloadSources: () => ++calls === 1 ? first.promise : second.promise })
  selectPreparationContext(state)
  const old = state.loadSources()
  state.selectedRoutingStepId.value = '9810'
  const latest = state.loadSources()
  const current = preparationFixture(false)
  current.context.scope.routingStepId = 9810
  current.context.inputPreparation.exactScope.routingStepId = 9810
  second.resolve(current); assert.equal(await latest, true)
  first.resolve(preparationFixture()); assert.equal(await old, false)
  assert.equal(state.inputPreparation.value.recordStatus, 'NOT_RECORDED')
  assert.match(await html(state), /尚无正式准备记录/)
  assert.doesNotMatch(await html(state), /准备记录已保存|模拟原答复/)
})

test('三态完全读取服务端含义，缺行和来源空白分别展示，0不作为定量产能或零时长', async () => {
  const fixture = preparationFixture(), calls = []
  const state = runtime({ getOperationWorkloadSources: async params => { calls.push(params); return fixture } }, { mode: 'view' })
  selectPreparationContext(state)
  for (const [meaning, extra] of [
    ['QUANTIFIED', { sourceValue: '120', quantitativeOccupancyAllowed: true, independentDurationAllowed: true }],
    ['NON_QUANTIFIED', { sourceValue: 0, recordPresenceStatusLabel: '当前范围无标准产能记录；业务0裁决不建立占位产能' }],
    ['NOT_APPLICABLE', { sourceValue: null, sourceStatusLabel: '正式来源明确空白，已证明不经过' }],
    [null, { recordPresenceStatusLabel: '当前范围无标准产能记录；缺记录不等于来源空白或不经过' }],
  ]) {
    fixture.context.capacitySemantics = capacitySemantics(meaning, extra)
    assert.equal(await state.loadSources(), true)
    const text = await html(state)
    assert.ok(text.includes(fixture.context.capacitySemantics.statusLabel))
    assert.ok(text.includes(fixture.context.capacitySemantics.recordPresenceStatusLabel))
    assert.ok(text.includes(fixture.context.capacitySemantics.sourceStatusLabel))
    assert.match(text, /准备记录业务裁决值 0.*正式标准产能数量 未知/)
    assert.match(text, /正式需求缺失|已保存负荷未知/)
    assert.doesNotMatch(text, /QUANTIFIED|NON_QUANTIFIED|NOT_APPLICABLE|0天|0\.000000/)
  }
  assert.equal(calls.length, 4)
  assert.equal(state.canSave.value, false)
})

test('准备修订展示最新0裁决与已撤销历史原答复，保留原文且不把历史未测作为当前类别', async () => {
  const fixture = preparationFixture(), preparation = fixture.context.inputPreparation
  preparation.businessBasis.entries[0].exactStatement = '历史原答复原文：UNMEASURED。'
  preparation.businessBasisPresentation[0].exactStatement = preparation.businessBasis.entries[0].exactStatement
  const latest = { ...preparation.businessBasis.entries[0], reference: '模拟最新裁决', referenceSha256: 'SIM-LATEST-ANSWER-HASH',
    exactStatement: '最新明确答复：确认该步骤按0语义承接；未选择投入面积。' }
  preparation.businessBasis.entries.push(latest)
  preparation.businessBasisPresentation.push({ entryIndex: 1, statusLabel: '最新用户裁决，当前有效',
    exactStatement: latest.exactStatement, reference: latest.reference, referenceSha256: latest.referenceSha256 })
  preparation.capacityTristatePrinciples = { contractVersion: 'PCE-CAPACITY-TRISTATE-V1',
    positive: { code: 'QUANTIFIED', statusLabel: '经过且有产能数据' },
    zero: { code: 'NON_QUANTIFIED', statusLabel: '经过但无法准确核算，不计定量产能占用' },
    blank: { code: 'NOT_APPLICABLE', statusLabel: '不经过' } }
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  selectPreparationContext(state)
  assert.equal(await state.loadSources(), true)
  const text = await html(state)
  assert.match(text, /当前产能裁决 经过但无法准确核算，不计定量产能占用/)
  assert.match(text, /历史原答复，原产能结论已撤销 业务依据原答复：\s*历史原答复原文：UNMEASURED/)
  assert.match(text, /最新用户裁决，当前有效 业务依据原答复：\s*最新明确答复/)
  assert.match(text, /投入标准 待确认/)
  assert.doesNotMatch(text, /当前产能裁决 尚未测定|PCE-CAPACITY-TRISTATE|QUANTIFIED|NOT_APPLICABLE/)
  assert.equal(preparation.businessBasis.entries[0].exactStatement, '历史原答复原文：UNMEASURED。')
})

test('旧准备记录未有最新明确裁决时仅显示待核实，不自动选0或不经过', async () => {
  const fixture = preparationFixture(), preparation = fixture.context.inputPreparation
  Object.assign(preparation, { capacityMeasurementStatus: null, capacityBusinessValue: null,
    capacityMeasurementStatusLabel: '产能事实待核实，历史未测解释不再有效',
    capacityResolution: { valid: false, code: 'UNRESOLVED_CONFLICT', statusLabel: '产能来源与必经裁决存在冲突，待核实', originalConclusionRevoked: false } })
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  selectPreparationContext(state)
  assert.equal(await state.loadSources(), true)
  const text = await html(state)
  assert.match(text, /当前产能裁决 产能事实待核实/)
  assert.match(text, /产能来源与必经裁决存在冲突，待核实/)
  assert.doesNotMatch(text, /准备记录业务裁决值 0|当前产能裁决 尚未测定|UNRESOLVED_CONFLICT/)
})

test('拒绝伪造第四类、无撤销证明的0及被更改的历史依据展示', async () => {
  const mutations = [
    value => { value.context.capacitySemantics = capacitySemantics('UNMEASURED') },
    value => { value.context.capacitySemantics = capacitySemantics(null, { meaningCode: 'NOT_APPLICABLE' }) },
    value => { value.context.inputPreparation.capacityResolution.originalConclusionRevoked = false },
    value => { value.context.inputPreparation.capacityBusinessValue = null },
    value => { value.context.inputPreparation.capacityResolution.formalStandardCapacityPresent = true },
    value => { value.context.inputPreparation.businessBasisPresentation[0].exactStatement = '前端代改的历史答复' },
    value => { value.context.inputPreparation.businessBasisPresentation[0].entryIndex = 9 },
  ]
  for (const mutate of mutations) {
    const fixture = preparationFixture(); mutate(fixture)
    const state = runtime({ getOperationWorkloadSources: async () => fixture })
    selectPreparationContext(state)
    assert.equal(await state.loadSources(), false)
    assert.equal(state.serverFacts.value, null)
    assert.doesNotMatch(await html(state), /准备记录已纠正|前端代改/)
  }
})

test('路线总览显示并导出服务端三态及SC缺行说明，序位工序名保持主信息', async () => {
  const response = routeFixture(), fixture = routeCatalog(response)
  response.routeConfiguration.rows[0].capacitySemantics = capacitySemantics('NON_QUANTIFIED', {
    recordPresenceStatusLabel: '当前范围无标准产能记录；缺记录不等于来源空白或不经过' })
  const state = runtime({ getOperationWorkloadSources: async params => params.routeOverview ? response : fixture })
  await state.loadSources(); state.selectedRoutePlanId.value = '5002'
  assert.equal(await state.loadRouteOverview(), true)
  assert.equal(state.routeRows.value[0].stepLabel, '1 / 模拟路线工序1')
  const text = await html(state)
  assert.match(text, /经过但无法准确核算，不计定量产能占用/)
  assert.match(text, /当前范围无标准产能记录；缺记录不等于来源空白或不经过/)
  assert.ok(state.routeExportColumns.some(column => column.field === 'capacityMeaningLabel'))
  assert.ok(state.routeExportColumns.some(column => column.field === 'capacityRecordPresenceLabel'))
  assert.equal(state.routeRows.value[0].savedAllocations.quantity, null)
})

test('标准产能列表保留实际行数与值，工序名和工艺编码来自同一服务端事实，状态不按数值重算', () => {
  const rows = [{ id: 1, code: 'SIM-SC', name: '模拟正式产能', quantity: '999',
    dailyCapacityFact: { operationName: '模拟工序名称', productTypeCode: 'SIM-PROCESS-CODE',
      capacitySemantics: capacitySemantics(null, { statusLabel: '来源证据冲突，不能据数量推断业务类别',
        recordPresenceStatusLabel: '正式产能记录已存在' }) } }]
  const mapped = executeCapacityRows(Vue.computed, Vue.ref('standard-capacities'), () => rows, Vue.ref({}), {}, () => '')
  assert.equal(mapped.value.length, 1)
  assert.equal(mapped.value[0].quantity, '999')
  assert.equal(mapped.value[0].operation_name, '模拟工序名称')
  assert.equal(mapped.value[0].product_type_code, 'SIM-PROCESS-CODE')
  assert.equal(mapped.value[0].capacity_business_status_label, '来源证据冲突，不能据数量推断业务类别')
  assert.equal(mapped.value[0].capacity_record_status_label, '正式产能记录已存在')
  const sectionStart = parent.indexOf("  'standard-capacities': {")
  const section = parent.slice(sectionStart, parent.indexOf('\n  },', sectionStart) + 5)
  assert.doesNotMatch(section, /\['not_determinable',|\['UNMEASURED',/)
  assert.match(section, /缺行不等于来源空白或不经过/)
})

function nonQuantifiedFixture() {
  const fixture = optionalFixture()
  fixture.catalog.capacityModes = [
    { value: 'STANDARD_CAPACITY', statusLabel: '正式标准产能引用', requiresStandardCapacity: true, requiresPlanPreparation: false },
    { value: 'PREPARATION_NON_QUANTIFIED', statusLabel: '正式精确准备裁决核验的不可定量工序', requiresStandardCapacity: false, requiresPlanPreparation: true },
  ]
  fixture.catalog.workCenterOperationCapabilities = [{ operationId: 9011, workCenterId: 6012 }]
  fixture.catalog.standardCapacities = []
  fixture.context = planContext({ sourceConfiguration: fixture.configuration })
  return fixture
}

test('不可定量来源使用显式服务端选项与工序能力，缺SC或缺上下文不会自行豁免', async () => {
  const fixture = nonQuantifiedFixture()
  fixture.catalog.workCenters.push({ id: 6100, label: '未具备当前工序能力的中心' })
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => previewResponse(...args) })
  await state.loadSources(); prepareOptional(state, { standardCapacityId: '' })
  assert.equal(state.draftFieldsComplete.value, false)
  state.form.capacityMode = 'STANDARD_CAPACITY'
  assert.equal(state.draftFieldsComplete.value, false)
  state.form.capacityMode = 'PREPARATION_NON_QUANTIFIED'
  state.refreshResourceSelection()
  assert.deepEqual(state.optionsFor('workCenterId').map(row => row.id), [6012])
  assert.equal(state.visibleConfigurationFields.value.some(field => field.key === 'standardCapacityId'), false)
  assert.equal(state.draftFieldsComplete.value, true)
  assert.equal(state.canPreview.value, false)
  assert.equal(state.canSave.value, false)
  assert.equal(state.sourcePayload().standardCapacityId, null)
  assert.equal(Object.hasOwn(state.sourcePayload(), 'generationContext'), false)
  const text = await html(state)
  assert.match(text, /产能承接方式.*不可定量工序/)
  assert.match(text, /每次运行仍须核验所选计划和步骤/)
  assert.doesNotMatch(text, /PREPARATION_NON_QUANTIFIED|STANDARD_CAPACITY/)
})

test('不可定量预览携带准确上下文，保存单独提交上下文且按空SC和明确类型读回', async () => {
  const fixture = nonQuantifiedFixture(), requests = [], writes = []
  const state = runtime({ getOperationWorkloadSources: async () => fixture,
    previewOperationWorkloadSourceConfiguration: async (...args) => { requests.push(structuredClone(args)); return previewResponse(...args) },
    saveOperationWorkloadSource: async payload => {
      writes.push(structuredClone(payload)); applyOptionalSavedSource(fixture, payload)
      Object.assign(fixture.configuration.sources[0], { capacityMode: payload.capacityMode,
        capacityModeLabel: '正式精确准备裁决核验的不可定量工序', standardCapacityId: null })
      fixture.context.sourceConfiguration = fixture.configuration
      return { ruleId: 6999 }
    } })
  await state.loadSources()
  prepareOptional(state, { capacityMode: 'PREPARATION_NON_QUANTIFIED', standardCapacityId: '' })
  state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
  assert.equal(state.canPreview.value, true)
  assert.equal(await state.previewSourceConfiguration(), true)
  assert.deepEqual(requests[0][2], { companyId: 6099, planId: 5002, routingStepId: 9809 })
  assert.equal(requests[0][1].standardCapacityId, null)
  assert.equal(Object.hasOwn(requests[0][1], 'generationContext'), false)
  assert.equal(state.canSave.value, true)
  await state.saveSource()
  assert.equal(writes.length, 1)
  assert.deepEqual(writes[0].generationContext, { productionPlanId: 5002, routingStepId: 9809 })
  assert.equal(writes[0].standardCapacityId, null)
  assert.equal(state.saveReadbackFailed.value, false)
  assert.deepEqual(state.events, [['saved', { operationId: 9011, ruleId: 6999 }]])
  assert.match(await html(state), /正式精确准备裁决核验的不可定量工序/)
})

test('不可定量方案读回不接受伪造SC或错误处理类型，缺失目录不降级', async () => {
  for (const corrupt of [row => { row.standardCapacityId = 6231 }, row => { row.capacityMode = 'STANDARD_CAPACITY' }]) {
    const fixture = nonQuantifiedFixture()
    const state = runtime({ getOperationWorkloadSources: async () => fixture,
      previewOperationWorkloadSourceConfiguration: async (...args) => previewResponse(...args),
      saveOperationWorkloadSource: async payload => {
        applyOptionalSavedSource(fixture, payload)
        Object.assign(fixture.configuration.sources[0], { standardCapacityId: null, capacityMode: payload.capacityMode })
        corrupt(fixture.configuration.sources[0]); fixture.context.sourceConfiguration = fixture.configuration
        return { ruleId: 6999 }
      } })
    await state.loadSources(); prepareOptional(state, { capacityMode: 'PREPARATION_NON_QUANTIFIED', standardCapacityId: '' })
    state.selectedPlanId.value = '5002'; state.selectedRoutingStepId.value = '9809'
    await state.previewSourceConfiguration(); await state.saveSource()
    assert.equal(state.saveReadbackFailed.value, true)
    assert.deepEqual(state.events, [])
  }
  const fixture = nonQuantifiedFixture()
  delete fixture.catalog.workCenterOperationCapabilities
  const state = runtime({ getOperationWorkloadSources: async () => fixture })
  assert.equal(await state.loadSources(), false)
  assert.equal(state.readState.value, 'read_failed')
})
