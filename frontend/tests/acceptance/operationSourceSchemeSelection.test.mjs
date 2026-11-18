import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import test from 'node:test'

// SIMULATED_FOR_TEST: actual component functions, Vue refs and SSR. No HTTP,
// browser, database, formal source writes or plan/source switching occur here.
const repo = process.cwd()
const frontend = path.resolve(process.env.PCE_FRONTEND_SOURCE_ROOT || path.join(repo, 'frontend'))
const require = createRequire(path.join(frontend, 'package.json'))
const Vue = require('vue')
const { parse, compileScript, compileTemplate } = require('@vue/compiler-sfc')
const { compile } = require('@vue/compiler-dom')
const { renderToString } = require('@vue/server-renderer')
const sourcePath = path.join(frontend, 'src/meta/components/ProductionFoundationMaintenance.vue')
const source = readFileSync(sourcePath, 'utf8')
const { descriptor } = parse(source, { filename: sourcePath })
const script = descriptor.scriptSetup.content
const contract = 'PCE-OPERATION-SOURCE-SELECTION-V1'
const clone = value => JSON.parse(JSON.stringify(value))
function actualFunction(name) {
  const match = script.match(new RegExp(`(?:async )?function ${name}\\([^]*?\\n\\}`))
  assert.ok(match, `actual function ${name}`)
  return match[0]
}
const functionNames = ['operationSchemeCanonical', 'sameOperationSchemeScope', 'operationSchemeKey',
  'operationSchemeOptionLabel', 'validateOperationSourceSchemes', 'clearOperationSourceSchemes',
  'loadOperationSourceSchemes', 'operationSourceSelectionIntent', 'verifyOperationSourceSelectionReadback',
  'payloadFromForm', 'save', 'fieldReadOnly']
const functions = functionNames.map(actualFunction).join('\n')
const computedSource = script.slice(script.indexOf('const operationSchemeDraft = computed('), script.indexOf('const structuredDefinitionValid = ref('))
const scopeA = { companyId: 71, operationId: 72, productTypeId: 73, routingContext: null }
const scopeB = { companyId: 71, operationId: 72, productTypeId: 74,
  routingContext: { routingId: 75, routingVersionId: 76, routingStepId: 77 } }
function option(id = 81, scope = scopeA, multi = false) {
  const rules = [id, ...(multi ? [id + 1] : [])].map(ruleId => ({ ruleId, ruleCode: `TEST_${ruleId}`,
    ruleName: `隔离正式规则${ruleId}`, ruleVersion: 'V2', specificationHash: 'a'.repeat(64), label: `隔离正式规则${ruleId} / V2` }))
  return { schemeId: `${multi ? 'COMPOSITION' : 'RULE'}:${id}`, schemeHash: String(id % 10).repeat(64),
    scope: clone(scope), ruleRefs: rules,
    compositionRef: multi ? { id, ruleCode: `TEST_GROUP_${id}`, ruleVersion: 'V3', specificationHash: 'b'.repeat(64) } : null,
    label: multi ? '隔离多规则完整方案' : '隔离正式单规则方案', statusLabel: '正式已发布',
    quantityBasisLabel: '服务端工程对象边长口径', uomId: 78, uomLabel: '米',
    productTypeId: scope.productTypeId, productTypeLabel: `隔离产品类型${scope.productTypeId}`,
    routingContext: clone(scope.routingContext), routingContextLabel: scope.routingContext ? '隔离工艺 / 版本V2 / 第4步' : '按产品类型范围，不限定工艺路线' }
}
function response(options = [option(), option(91, scopeB, true)], selections = []) {
  return { success: true, factSource: 'server', configuration: { operationId: 72,
    sourceSchemes: clone(options), sourceSelection: { contractVersion: contract, revision: selections.length ? 2 : 0,
      selectionHash: 'c'.repeat(64), selections: clone(selections), statusLabel: selections.length ? '已保存全部正式范围' : '尚未保存正式来源方案选择' } },
  catalog: { companyId: 71, configureAuthorization: { allowed: true, statusLabel: '可维护正式来源方案' } } }
}
function harness(api = {}) {
  const ref = Vue.ref
  const context = { computed: Vue.computed, OPERATION_SOURCE_SELECTION_CONTRACT: contract,
    operationSchemeState: ref('idle'), operationSchemeError: ref(''), operationSchemeFacts: ref(null),
    operationSchemeDraftKey: ref(''), operationSchemeOwner: ref(''), operationSchemeRequest: 0,
    selectedEntity: ref('operations'), editingId: ref(72), formSession: ref(1), canMaintain: ref(true),
    saving: ref(false), message: ref(''), saveError: ref(''), maintenanceFormOpen: ref(true), formOpenStatus: ref('已打开'),
    form: Vue.reactive({ reason: 'SIMULATED_FOR_TEST 明确维护', name: '隔离工序', quantity_driver: '完全未知的历史说明，不是规则名称' }),
    currentDefinition: ref({ shortLabel: '工序', fields: [{ key: 'name', type: 'text' }, { key: 'quantity_driver', type: 'text' }] }),
    selectedRuleCandidate: ref(null), createIdempotencyKey: ref('isolated-key'), canSaveCurrentForm: ref(true),
    currentRow: ref(null), pdeApi: api, readTabIdentity: () => ({ companyId: 71 }), readScope: () => context.actor,
    requireSuccess: value => { if (value?.success === false) throw new Error(value.message); return value },
    dailyCapacityMaintenancePayload: value => value, ruleFieldReadOnly: () => false,
    loadFacts: async () => { context.factReads += 1 }, resetForm: () => { context.resetCalls += 1; context.clear() },
  }
  context.actor = 'company71-user79-epoch1'
  context.factReads = 0
  context.resetCalls = 0
  const exports = new Function(...Object.keys(context), `${functions}\n${computedSource}\nreturn {${functionNames.join(',')}, operationSchemeDraft, operationSchemeChanged, operationSchemeCanConfigure}`)(...Object.values(context))
  context.clear = exports.clearOperationSourceSchemes
  return Object.assign(context, exports)
}
async function loaded(raw = response(), api = {}) {
  const h = harness({ getOperationWorkloadSources: async () => raw, ...api })
  await h.loadOperationSourceSchemes()
  assert.equal(h.operationSchemeState.value, 'loaded')
  return h
}
const sectionStart = descriptor.template.content.indexOf('<section v-if="selectedEntity === \'operations\' && editingId && field.key === \'quantity_driver\'"')
const sectionEnd = descriptor.template.content.indexOf('</section>', sectionStart) + '</section>'.length
const template = descriptor.template.content.slice(sectionStart, sectionEnd)
async function render(h) {
  const renderFn = new Function('Vue', compile(template, { mode: 'function' }).code)(Vue)
  return renderToString(Vue.createSSRApp({ setup: () => ({ ...h, field: { key: 'quantity_driver', label: '历史来源说明', note: '原文字保留追溯' } }), render: renderFn }))
}

test('actual SFC and complete template compile without changing the existing API or panel', () => {
  assert.equal(parse(source).errors.length, 0)
  assert.ok(compileScript(descriptor, { id: 'operation-source-scheme' }))
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: sourcePath, id: 'operation-source-scheme' }).errors, [])
  assert.match(source, /pdeApi\.getOperationWorkloadSources\(\{ operationId \}\)/)
  assert.doesNotMatch(actualFunction('loadOperationSourceSchemes'), /routeOverview|productionPlanId|routingStepId|retry/i)
})

test('empty formal read remains valid, unselected and separate from a failed read', async () => {
  const h = await loaded(response([]))
  assert.deepEqual(h.operationSchemeFacts.value.sourceSchemes, [])
  assert.equal(h.operationSchemeDraftKey.value, '')
  assert.equal(h.operationSourceSelectionIntent(), null)
  const html = await render(h)
  assert.match(html, /没有可选方案/)
  assert.match(html, /尚未保存正式来源方案选择/)
})

test('current selections for every scope and whole rule groups render with server units and version scope', async () => {
  const one = option(), group = option(91, scopeB, true)
  const h = await loaded(response([one, group], [one, group]))
  const html = await render(h)
  for (const expected of [group.label, group.quantityBasisLabel, group.uomLabel, group.productTypeLabel, group.routingContextLabel, ...group.ruleRefs.map(rule => rule.label)]) assert.ok(html.includes(expected))
  assert.match(html, /完全未知的历史说明，不是规则名称/)
  assert.match(html, /readonly/)
  assert.equal(h.operationSchemeDraftKey.value, '')
  assert.equal(h.fieldReadOnly({ key: 'quantity_driver' }), true)
  h.selectedEntity.value = 'workshops'
  assert.equal(h.fieldReadOnly({ key: 'quantity_driver' }), false)
})

test('malformed scope, wrong tenant, truncated rule groups and missing formal labels fail closed', () => {
  const h = harness()
  const cases = [raw => { raw.catalog.companyId = 999 }, raw => { raw.configuration.operationId = 99 },
    raw => { raw.configuration.sourceSchemes[0].scope.companyId = 999 },
    raw => { raw.configuration.sourceSchemes[0].scope.routingContext = { routingVersionId: 76 } },
    raw => { raw.configuration.sourceSchemes[0].schemeHash = '' },
    raw => { raw.configuration.sourceSchemes[0].ruleRefs = [] },
    raw => { raw.configuration.sourceSchemes[0].uomLabel = '' },
    raw => { raw.configuration.sourceSelection.selections = [option(), option(82)] },
    raw => { raw.configuration.sourceSchemes[0].productTypeId = 100 }]
  for (const damage of cases) { const raw = response(); damage(raw); assert.throws(() => h.validateOperationSourceSchemes(raw, 72, 71), /合同或公司、工序范围不一致/) }
})

test('the loader issues one operation-only read and never automatically chooses its first candidate', async () => {
  const calls = []
  const h = harness({ getOperationWorkloadSources: async params => { calls.push(params); return response() } })
  await h.loadOperationSourceSchemes()
  assert.deepEqual(calls, [{ operationId: 72 }])
  assert.equal(h.operationSchemeDraftKey.value, '')
  assert.equal(h.operationSchemeState.value, 'loaded')
})

test('request failure clears current facts and renders failure instead of an empty selection', async () => {
  const h = harness({ getOperationWorkloadSources: async () => { throw new Error('隔离读取超时') } })
  await h.loadOperationSourceSchemes()
  assert.equal(h.operationSchemeState.value, 'read_failed')
  assert.equal(h.operationSchemeFacts.value, null)
  const html = await render(h)
  assert.match(html, /隔离读取超时/)
  assert.doesNotMatch(html, /没有可选方案|尚未保存正式来源方案选择/)
})

test('late response cannot populate a new editor session or changed identity', async () => {
  for (const invalidate of [h => h.clearOperationSourceSchemes(), h => { h.formSession.value += 1 },
    h => { h.editingId.value = 999 }, h => { h.selectedEntity.value = 'workshops' }, h => { h.actor = 'another-actor' }]) {
    let complete
    const h = harness({ getOperationWorkloadSources: () => new Promise(resolve => { complete = resolve }) })
    const pending = h.loadOperationSourceSchemes()
    invalidate(h)
    complete(response())
    assert.equal(await pending, null)
    assert.equal(h.operationSchemeFacts.value, null)
  }
})

test('unselected, unchanged or cancelled choices add no source write intent to the original payload', async () => {
  const current = option()
  const h = await loaded(response([current, option(82)], [current]))
  assert.equal(h.payloadFromForm().sourceSchemeSelection, undefined)
  h.operationSchemeDraftKey.value = h.operationSchemeKey(current)
  assert.equal(h.payloadFromForm().sourceSchemeSelection, undefined)
  h.operationSchemeDraftKey.value = h.operationSchemeKey(option(82))
  h.operationSchemeDraftKey.value = ''
  assert.equal(h.payloadFromForm().sourceSchemeSelection, undefined)
  assert.equal(h.payloadFromForm().quantity_driver, '完全未知的历史说明，不是规则名称')
})

test('explicit whole-group intent includes only server identity, hash and exact scope, never client rule IDs', async () => {
  const group = option(91, scopeB, true)
  const h = await loaded(response([group], [option()]))
  h.operationSchemeDraftKey.value = h.operationSchemeKey(group)
  assert.deepEqual(h.payloadFromForm().sourceSchemeSelection, { contractVersion: contract, expectedRevision: 2,
    scope: scopeB, schemeId: group.schemeId, schemeHash: group.schemeHash })
  assert.equal(h.operationSchemeDraft.value.ruleRefs.length, 2)
  h.canMaintain.value = false
  assert.throws(() => h.payloadFromForm(), /维护权限/)
})

test('loaded draft cannot submit after identity, editor scope or session changed', async () => {
  for (const invalidate of [h => { h.actor = 'changed-user' }, h => { h.formSession.value += 1 }, h => { h.editingId.value = 999 }]) {
    const h = await loaded()
    h.operationSchemeDraftKey.value = h.operationSchemeKey(option())
    invalidate(h)
    assert.throws(() => h.operationSourceSelectionIntent(), /账号或编辑范围已变化/)
  }
})

test('independent readback requires the complete selected group, new revision, receipt and every other scope unchanged', () => {
  const h = harness(), old = option(), other = option(91, scopeB, true), next = option(82)
  const before = response([], [old, other]).configuration.sourceSelection
  const selection = { ...clone(before), revision: before.revision + 1, selectionHash: 'd'.repeat(64), selections: [other, next] }
  h.verifyOperationSourceSelectionReadback(before, next, { sourceSelection: selection }, selection)
  const damages = [s => { s.selections = [next] }, s => { s.revision -= 1 },
    s => { s.selections[0].ruleRefs.pop() }, s => { s.selections[1].schemeHash = 'e'.repeat(64) }]
  for (const damage of damages) { const bad = clone(selection); damage(bad); assert.throws(() => h.verifyOperationSourceSelectionReadback(before, next, { sourceSelection: bad }, bad), /读回/) }
  assert.throws(() => h.verifyOperationSourceSelectionReadback(before, next, { sourceSelection: selection }, before), /回执不一致/)
})

test('actual save sends the intent in the original PATCH, then independently reads it before closing', async () => {
  const current = option(), other = option(91, scopeB, true), chosen = option(82)
  const before = response([current, other, chosen], [current, other])
  const after = response([current, other, chosen], [chosen, other])
  after.configuration.sourceSelection.revision = before.configuration.sourceSelection.revision + 1
  after.configuration.sourceSelection.selectionHash = 'd'.repeat(64)
  const calls = []
  let reads = 0
  const h = await loaded(before, { getOperationWorkloadSources: async params => { calls.push(['GET', params]); return reads++ ? after : before },
    saveProductionFoundation: async (entity, payload, id) => { calls.push(['PATCH', entity, clone(payload), id]); return { row: { workloadSource: { sourceSelection: clone(after.configuration.sourceSelection) } } } } })
  h.operationSchemeDraftKey.value = h.operationSchemeKey(chosen)
  await h.save()
  assert.deepEqual(calls.map(call => call[0]), ['GET', 'PATCH', 'GET'])
  assert.equal(calls[1][1], 'operations')
  assert.equal(calls[1][3], 72)
  assert.equal(calls[1][2].sourceSchemeSelection.schemeId, chosen.schemeId)
  assert.equal(calls[1][2].quantity_driver, h.form.quantity_driver)
  assert.equal(h.saveError.value, '')
  assert.equal(h.maintenanceFormOpen.value, false)
})

test('failed independent readback never reports successful save or closes the editor', async () => {
  let reads = 0
  const h = await loaded(response(), { getOperationWorkloadSources: async () => { if (reads++) throw new Error('隔离回读失败'); return response() },
    saveProductionFoundation: async () => ({ row: { workloadSource: { sourceSelection: {} } } }) })
  h.operationSchemeDraftKey.value = h.operationSchemeKey(option())
  await h.save()
  assert.match(h.saveError.value, /独立读回/)
  assert.equal(h.maintenanceFormOpen.value, true)
  assert.doesNotMatch(h.message.value, /已通过企业基础资料正式服务保存并回读/)
})

test('ordinary save without a choice keeps the original payload and makes no source read or write intent', async () => {
  const calls = []
  const h = harness({ getOperationWorkloadSources: async () => { throw new Error('not expected') },
    saveProductionFoundation: async (entity, payload, id) => { calls.push({ entity, payload: clone(payload), id }); return { row: {} } } })
  await h.save()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].payload.sourceSchemeSelection, undefined)
  assert.equal(calls[0].payload.quantity_driver, '完全未知的历史说明，不是规则名称')
  assert.equal(h.saveError.value, '')
  assert.equal(h.maintenanceFormOpen.value, false)
})
