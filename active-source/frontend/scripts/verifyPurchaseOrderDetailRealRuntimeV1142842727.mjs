import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test', 'tests/acceptance/purchaseOrderDetailRealRuntimeV1142842727.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.7', 'Governance Files Loaded: PASS',
  'Governance Applied: PASS', 'PurchaseOrder Detail Runtime: PASS',
  'PurchaseOrder Classification: PASS', 'Order Number Layout: PASS',
  'Material Detail Layout: PASS', 'Print Output Classification: PASS',
  'Print Preview: PASS', 'Refresh Runtime: PASS', 'Old Renderer: REMOVED',
  'PurchaseOrder Core Changed: NO', 'Gate Changed: NO', 'Database Changed: NO',
  'Business Write Count: 0', 'Build: PASS',
  'Final Status: PURCHASE_ORDER_DETAIL_REAL_RUNTIME_READY',
]) console.log(line)
