import { spawnSync } from 'node:child_process'

const tests = [
  'tests/acceptance/scmPurchaseOrderDraftRuntimeV11428427113.test.mjs',
  'tests/acceptance/scmPurchaseOrderQuantityModelV11428427112.test.mjs',
  'tests/acceptance/scmPurchaseOrderItemSourceV11428427111.test.mjs',
  'tests/acceptance/scmPurchaseOrderGateEntryProtectionV114284262.test.mjs',
]

for (const test of tests) {
  const result = spawnSync(process.execPath, [test], {
    cwd: new URL('..', import.meta.url), encoding: 'utf8',
  })
  process.stdout.write(result.stdout || '')
  process.stderr.write(result.stderr || '')
  if (result.status !== 0) process.exit(result.status || 1)
}

console.log('Regression PASS')
console.log('Build Contract PASS')
