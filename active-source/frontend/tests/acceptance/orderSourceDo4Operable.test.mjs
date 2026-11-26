import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const root = path.resolve(import.meta.dirname, '../../..')
const read = name => fs.readFileSync(path.join(root, name), 'utf8')
test('original source component compiles and exposes scoped actions without client quantity authority', () => {
  const filename = 'frontend/src/meta/pages/WholeHouseOrderPreview.vue'
  const source = read(filename)
  const { descriptor, errors } = parse(source, { filename })
  assert.deepEqual(errors, [])
  compileScript(descriptor, { id: 'do4-source' })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename, id:'do4-source' }).errors, [])
  for (const marker of ['正常登录入口','分类汇总，不等于已确认销售明细','quantityPrecision','quantityEvidence','sourceLineIds','preview.review.checks','preview.actions','preview.value.diagnosticFacts','confirmed.value','dirty.value']) assert.ok(source.includes(marker), marker)
  assert.doesNotMatch(source, /localStorage|parseFloat|Number\(line.quantity/)
})
test('source actions retain original page, server API and filter-preserving return', () => {
  const source = read('frontend/src/meta/pages/WholeHouseOrderPreview.vue')
  const api = read('frontend/src/api/sales.js')
  assert.ok(source.includes("const {mode,...query}=route.query"))
  assert.ok(source.includes('Boolean(preview.value) && JSON.stringify(cleanDraft())'))
  assert.ok(source.includes("navigate('/system-login', {redirect: route.fullPath})"))
  assert.ok(source.includes('salesApi.sourceAction(action,payload)'))
  assert.ok(source.includes('salesApi.createSourceDraft('))
  assert.ok(api.includes('/api/sales/orders/source-intake/whole-house/actions/'))
  assert.ok(api.includes("'Idempotency-Key': payload.idempotencyKey"))
})
test('empty frozen index never erases prior 31 preservation records', () => {
  const current = JSON.parse(read('docs/governance/completed_module_registry.v1.json'))
  const original = JSON.parse(read('frontend/test-results/pce-order-delivery-planning-do4-operable-closure-20260913/baseline/docs__governance__completed_module_registry.v1.json'))
  for(const entry of original.modules) assert.deepEqual(current.modules.find(row=>row.moduleId===entry.moduleId),entry)
  assert.deepEqual(current.currentFrozenVerifiedModuleIds, original.currentFrozenVerifiedModuleIds)
  assert.ok(current.preservationAssociations.policy.includes('PRESERVE_AND_EXTEND'))
  assert.ok(current.modules.find(row=>row.moduleId==='sales-order-source-intake').status==='DEVELOPED_NOT_CURRENTLY_VERIFIED')
})
