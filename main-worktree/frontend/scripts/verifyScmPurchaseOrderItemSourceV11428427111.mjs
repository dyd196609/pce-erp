import { spawnSync } from 'node:child_process'

const result = spawnSync(process.execPath,
  ['tests/acceptance/scmPurchaseOrderItemSourceV11428427111.test.mjs'],
  { cwd: new URL('..', import.meta.url), encoding: 'utf8' })
process.stdout.write(result.stdout || '')
process.stderr.write(result.stderr || '')
if (result.status !== 0) process.exit(result.status || 1)
console.log('Runtime PASS')
console.log('Regression PASS')
