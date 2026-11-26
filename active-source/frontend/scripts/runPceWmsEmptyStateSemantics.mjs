import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const storePath = path.join(root, 'src', 'meta', 'wms', 'wmsStore.js')
const source = fs.readFileSync(storePath, 'utf8')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(source.includes('export function createEmptyWmsState'), 'createEmptyWmsState missing')
assert(source.includes('export function createDemoWmsState'), 'createDemoWmsState missing')
assert(source.includes('return raw ? normalizeState(JSON.parse(raw)) : createEmptyWmsState()'), 'missing key does not resolve to canonical empty')
assert(source.includes('state = createDemoWmsState()'), 'explicit demo reset is not isolated')
assert(!source.includes('return raw ? normalizeState(JSON.parse(raw)) : defaultState()'), 'legacy implicit demo fallback remains')

const result = spawnSync(process.execPath, [
  path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'),
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/wmsEmptyStateSemantics.spec.js',
], { cwd: root, env: process.env, stdio: 'inherit' })
if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)

const report = JSON.parse(fs.readFileSync(path.join(root, 'test-results', 'purchase-payment-golden-flow', 'wms-empty-state-semantics-report.json'), 'utf8'))
for (const key of [
  'missingKeyReturnsCanonicalEmpty',
  'existingStatePreserved',
  'explicitDemoSeedStillAvailable',
  'importDoesNotPersistDemo',
  'normalBusinessMutationDoesNotInjectDemo',
  'corruptStateDoesNotFallbackToDemo',
]) assert(report[key] === true, `${key} failed`)
console.log(JSON.stringify(report, null, 2))
