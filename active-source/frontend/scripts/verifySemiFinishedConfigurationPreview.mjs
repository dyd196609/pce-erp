import assert from 'node:assert/strict'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { foundationCanonicalModules, getFoundationCanonicalModule, foundationSubviewLocation, resolveFoundationPageState } from '../src/meta/master-data/foundationEntryUnificationRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const out = path.resolve(root, '../docs/evidence/semi_finished_model_closure_20260909')
const files = ['src/meta/pages/PdeOrderEngineeringCalculationPage.vue', 'src/meta/components/SemiFinishedConfigurationPreview.vue']
const checks = []
const run = (name, fn) => { fn(); checks.push({ name, result: 'PASS' }) }
const hash = data => createHash('sha256').update(data).digest('hex')
const module = getFoundationCanonicalModule('engineering-calculation')
run('Canonical registered subview uses existing route and read-only mode', () => {
  const target = foundationSubviewLocation(module.moduleId, 'semi-finished-structure')
  assert.equal(target.name, module.routeName)
  assert.deepEqual(target.query, { subview: 'semi-finished-structure' })
  const state = resolveFoundationPageState({ path: module.routePath, query: target.query })
  assert.equal(state.moduleId, 'engineering-calculation')
  assert.equal(state.mode, 'view')
  assert.equal(state.subview, 'semi-finished-structure')
})
run('Unknown or cross-module subview is rejected', () => {
  assert.throws(() => foundationSubviewLocation(module.moduleId, 'unknown'))
  assert.throws(() => foundationSubviewLocation('operations', 'semi-finished-structure'))
  assert.throws(() => resolveFoundationPageState({ path: module.routePath, query: { subview: 'wrong' } }))
})
run('All existing canonical default routes remain resolvable', () => {
  for (const m of foundationCanonicalModules) assert.equal(resolveFoundationPageState({ path: m.routePath }).moduleId, m.moduleId)
})
for (const relative of files) run(`Vue script/template compile: ${relative}`, () => {
  const source = readFileSync(path.join(root, relative), 'utf8')
  const { descriptor, errors } = parse(source, { filename: relative })
  assert.deepEqual(errors, [])
  const compiled = compileScript(descriptor, { id: 'configuration-preview' })
  const template = compileTemplate({ source: descriptor.template.content, filename: relative, id: 'configuration-preview', compilerOptions: { bindingMetadata: compiled.bindings } })
  assert.deepEqual(template.errors, [])
})
run('New child is a read-only projection, without persistence or authentication access', () => {
  const source = readFileSync(path.join(root, files[1]), 'utf8')
  assert.doesNotMatch(source, /localStorage|sessionStorage|fetch\(|axios|\.post\(|\.put\(|\.delete\(/)
  for (const value of ['半成品制造属性来源与正式身份', '预计材料组成', '工程引用行', 'UNKNOWN', '来源未填写', 'EXISTING_FORMAL_LINK']) assert.ok(source.includes(value))
})
const servedSource = []
for (const relative of files) {
  const response = await fetch(`http://localhost:5173/${relative}?raw`, { headers: { 'cache-control': 'no-cache' } })
  assert.ok(response.ok)
  const text = await response.text()
  const match = text.match(/^export default ("(?:[^"\\]|\\.)*")/s)
  assert.ok(match, 'Vite raw module must be a single JSON string')
  const served = JSON.parse(match[1])
  const local = readFileSync(path.join(root, relative), 'utf8')
  assert.equal(served, local)
  servedSource.push({ file: relative, sourceSha256: hash(local), servedSha256: hash(served), result: 'PASS' })
}
const commands = [
  ['page identity', ['scripts/verifyFrontendPageIdentityConvergence.mjs']],
  ['system config non-regression', ['scripts/verifySystemConfigNonRegression.mjs']],
  ['operation route preservation', ['scripts/verifyOperationRouteRecoveryP0.mjs']],
  ['tested / served runtime identity', ['scripts/verifyTestedServedFrontendIdentity.mjs']],
  ['existing foundation preview', ['src/meta/runtime/foundationWave1ImportPreview.test.mjs']],
]
if (process.argv.includes('--build')) commands.push(['isolated Vite production build', ['node_modules/vite/bin/vite.js', 'build', '.', '--outDir', '../.runtime/semi-finished-configuration-build']])
const results = []
for (const [name, args] of commands) {
  const result = spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8', windowsHide: true, maxBuffer: 20 * 1024 * 1024 })
  const log = `${result.stdout || ''}\n${result.stderr || ''}`
  writeFileSync(path.join(out, `frontend-${results.length + 1}.log`), log)
  results.push({ name, exitCode: result.status, result: result.status === 0 ? 'PASS' : 'FAIL' })
  console.log(`${name}: ${results.at(-1).result}`)
}
const report = { checks, existingCanonicalModuleCount: foundationCanonicalModules.length, servedSource, commands: results, productionBusinessWrite: 0 }
writeFileSync(path.join(out, 'FRONTEND_TEST_RESULTS.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
assert.ok(results.every(r => r.result === 'PASS'))
