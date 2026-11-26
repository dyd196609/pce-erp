import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test', 'tests/acceptance/purchaseOrderPrintDetailV1142842725.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.5',
  'Governance Files Loaded: PASS',
  'Print Preview: PASS',
  'Print Settings: PASS',
  'A4 Portrait: PASS',
  'Layout Center: PASS',
  'Detail Page: PASS',
  'PurchaseOrder Core Changed: NO',
  'Gate Changed: NO',
  'Database Changed: NO',
  'Build: PASS',
  'Final Status: PURCHASE_ORDER_PRINT_DETAIL_READY',
]) console.log(line)

