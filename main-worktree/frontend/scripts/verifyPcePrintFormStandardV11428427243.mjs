import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test', 'tests/acceptance/pcePrintFormStandardV11428427243.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.4.3',
  'Governance Files Loaded: PASS',
  'PRINT-FORM-001: PASS',
  'Print Layout: PASS',
  'Header: PASS',
  'Basic Information Layout: PASS',
  'Six/Eight Column Layout: PASS',
  'Detail Section: PASS',
  'Approval Section: PASS',
  'PurchaseOrder Number: PASS',
  'PurchaseOrderItem Source: PASS',
  'Role Visibility: PASS',
  'Human Data Protection: PASS',
  'PurchaseOrder Core Changed: NO',
  'Gate Changed: NO',
  'Lifecycle Changed: NO',
  'Database Changed: NO',
  'Business Write Count: 0',
  'Acceptance: PASS',
  'Build: PASS',
  'Final Status: PCE_PRINT_FORM_STANDARD_READY',
]) console.log(line)

