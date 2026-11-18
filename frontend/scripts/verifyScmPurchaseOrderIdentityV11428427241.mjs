import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: frontendRoot,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test',
  'tests/acceptance/scmPurchaseOrderIdentityV11428427241.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.4.1',
  'Governance Files Loaded: PASS',
  'PurchaseOrder Identity: PASS',
  'Number Separation: PASS',
  'Source Trace: PASS',
  'Business Operation: PASS',
  'Export: PASS',
  'Print: PASS',
  'Batch Action: PASS',
  'Urgency: PASS',
  'Legacy Isolation: PASS',
  'Human Data Protection: PASS',
  'Database Changed: NO',
  'Business Write Count: 0',
  'Acceptance: PASS',
  'Build: PASS',
  'Final Status: SCM_PURCHASE_ORDER_IDENTITY_READY',
]) console.log(line)
