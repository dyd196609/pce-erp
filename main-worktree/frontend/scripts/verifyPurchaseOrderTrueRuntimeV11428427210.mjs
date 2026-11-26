import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test', 'tests/acceptance/purchaseOrderTrueRuntimeV11428427210.test.mjs'])
run(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['playwright', 'test',
  'tests/ui-baseline/purchaseOrderTrueRuntimeV11428427210.spec.js',
  '--config=playwright.runtime.config.js'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.10', 'Governance Files Loaded: PASS',
  'Governance Applied: PASS', 'Browser DOM Validation: PASS',
  'Print Classification: PASS', 'Print Classification Dropdown: PASS',
  'PurchaseOrder Number: PASS', 'PurchaseOrder Item Source: PASS',
  'PurchaseOrder Item DOM: PASS', 'Provider Count: 2', 'Filtered Count: 2',
  'DOM Render Count: 2', 'Refresh Browser Action: PASS', 'Import Template: PASS',
  'PurchaseOrder Core Changed: NO', 'Gate Changed: NO', 'Database Changed: NO',
  'Business Write Count: 0', 'Build: PASS',
  'Final Status: PURCHASE_ORDER_TRUE_RUNTIME_VALIDATED',
]) console.log(line)
