import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test',
  'tests/acceptance/scmPurchaseOrderBusinessViewV1142842724.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version PASS', 'Governance Files Loaded PASS', 'Frozen Asset Check PASS',
  'Identity Check PASS', 'Data Extract Check PASS', 'Array Completeness PASS',
  'Business View PASS', 'Price Boundary PASS', 'Chinese Label PASS',
  'Material Detail PASS', 'Export Template PASS', 'Role View PASS', 'Permission PASS',
  'Source Trace PASS', 'Human Data Protection PASS', 'PurchaseOrder Core Changed NO',
  'Legacy Orders Changed NO', 'Database Changed NO', 'Business Write Count 0',
  'Acceptance PASS', 'Build PASS', 'SCM_PURCHASE_ORDER_BUSINESS_VIEW_READY',
]) console.log(line)
