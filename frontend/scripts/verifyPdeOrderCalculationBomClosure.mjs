import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const files = Object.fromEntries(await Promise.all([
  ['page', '../src/meta/pages/PdeOrderEngineeringCalculationPage.vue'],
  ['api', '../src/api/pde.js'],
  ['request', '../src/api/request.js'],
  ['definitions', '../src/meta/pages/pdePageDefinitions.js'],
  ['registry', '../src/meta/runtime/pceBusinessActionRegistry.js'],
  ['router', '../src/router/index.js'],
  ['login', '../src/views/Login.vue'],
].map(async ([key, path]) => [key, await readFile(new URL(path, import.meta.url), 'utf8')])))

for (const marker of [
  '选择订单工程上下文', '服务端条件校验', '核算记录与持久化结果',
  '候选核算方法试算与独立对账', '订单BOM草稿衔接', 'previewHash', '不发布BOM',
]) {
  assert.match(files.page, new RegExp(marker), `page missing ${marker}`)
}
for (const method of [
  'validateOrderEngineeringCalculation', 'executeEngineeringCalculation',
  'trialEngineeringMethods', 'previewOrderBom', 'generateOrderBom',
]) {
  assert.match(files.api, new RegExp(method), `API missing ${method}`)
  assert.match(files.page, new RegExp(method), `page does not call ${method}`)
}
for (const actionId of [
  'validate-order-engineering-calculation', 'execute-order-engineering-calculation',
  'preview-order-bom-draft', 'generate-order-bom-draft', 'view-order-bom',
]) assert.match(files.registry, new RegExp(actionId), `registry missing ${actionId}`)

assert.match(files.definitions, /previous: '产品版本管理'[\s\S]*next: 'BOM管理'/)
assert.match(files.definitions, /sourceCalculationId/)
assert.doesNotMatch(files.page, /localStorage\.(setItem|getItem)/)
assert.match(files.page, /response\?\.success === false/)
assert.match(files.page, /isAuthenticationFailure/)
assert.match(files.page, /path: '\/system-login'/)
assert.match(files.router, /requiresServerAuthentication: true/)
assert.match(files.router, /to\.meta\?\.canonicalModuleId \|\| to\.meta\?\.requiresServerAuthentication/)
assert.match(files.login, /route\.query\.redirect/)
assert.match(files.login, /!requested\.startsWith\('\/\/'\)/)
assert.match(files.page, /value\.value !== undefined/)
assert.match(files.page, /尺寸已完成 · 物料\/BOM受阻/)
assert.match(files.request, /res\.data\?\.code/)
assert.match(files.page, /validationOperation\.state === 'running' \? '正在校验…'/)
assert.match(files.page, /已具备尺寸核算条件；材料数量与BOM条件仍保持独立/)
assert.match(files.page, /bomPreviewOperation\.state === 'running' \? '正在预览…'/)
assert.match(files.page, /本次预览检查已完成：预览受阻/)
assert.match(files.page, /MATERIAL_REQUIREMENT_REQUIRED/)
assert.match(files.page, /methodStatus/)
assert.match(files.page, /预期值未作为系统输入/)
assert.match(files.page, /不占用产能、不排产/)
assert.match(files.page, /kind === 'permission'/)
assert.match(files.page, /kind === 'network'/)

console.log('PDE order calculation/BOM closure frontend verification: PASS')
