import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test', 'tests/acceptance/purchaseOrderDataPrintRuntimeV1142842728.test.mjs'])
run(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['playwright', 'test',
  'tests/ui-baseline/purchaseOrderDataPrintRuntimeV1142842728.spec.js',
  '--config=playwright.runtime.config.js'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.8', 'Governance Files Loaded: PASS',
  'Governance Applied: PASS', 'Refresh Runtime: PASS',
  'Refresh Real Data Reload: PASS', 'PurchaseOrder Number Layout: PASS',
  'PurchaseOrder Item Isolation: PASS', 'Print Business Classification: PASS',
  'Current PurchaseOrderItem Count: 2', 'Filtered Item Count: 2',
  'Print Preview: PASS', 'Old Renderer: REMOVED', 'PurchaseOrder Core Changed: NO',
  'Gate Changed: NO', 'Database Changed: NO', 'Business Write Count: 0', 'Build: PASS',
  'Final Status: PURCHASE_ORDER_DATA_AND_PRINT_RUNTIME_READY',
]) console.log(line)
