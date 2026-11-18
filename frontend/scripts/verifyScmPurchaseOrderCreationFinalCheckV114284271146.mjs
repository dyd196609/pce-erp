import { spawnSync } from 'node:child_process'

const tests = [
  'tests/acceptance/scmPurchaseOrderCreationFinalCheckV114284271146.test.mjs',
  'tests/acceptance/scmPurchaseOrderCreationContextV114284271145.test.mjs',
  'tests/acceptance/scmPurchaseOrderMaterialEligibilityV114284271144.test.mjs',
  'tests/acceptance/scmPurchaseOrderDraftRuntimeSourceV1142842711431.test.mjs',
  'tests/acceptance/scmPurchaseOrderDraftUiRefinementV114284271142.test.mjs',
  'tests/acceptance/scmPurchaseOrderDraftQuantityRuleV114284271131.test.mjs',
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
console.log('SCM_PURCHASE_ORDER_FINAL_CHECK_READY')
