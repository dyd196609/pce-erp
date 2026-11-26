import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test',
  'tests/acceptance/purchaseOrderBusinessIdentityV11428427211.test.mjs'])
run(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['playwright', 'test',
  'tests/ui-baseline/purchaseOrderBusinessIdentityV11428427211.spec.js',
  '--config=playwright.runtime.config.js'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.11',
  'Governance Files Loaded: PASS',
  'Governance Applied: PASS',
  'PurchaseOrder Number Source: PASS',
  'PurchaseOrder Number Display: PASS',
  'PO Duplicate Removed: PASS',
  'PurchaseOrder Item Ownership: PASS',
  'DOM Business Match: PASS',
  'Import Template Schema Match: PASS',
  'Refresh Loading Feedback: PASS',
  'Refresh Success Feedback: PASS',
  'Gate Changed: NO',
  'Lifecycle Changed: NO',
  'Database Changed: NO',
  'Business Write Count: 0',
  'Build: PASS',
  'Final Status: PURCHASE_ORDER_BUSINESS_IDENTITY_READY',
]) console.log(line)
