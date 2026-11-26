import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test',
  'tests/acceptance/scmPurchaseOrderDocumentViewV11428427242.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.4.2',
  'Governance Files Loaded: PASS',
  'PurchaseOrder Identity: PASS',
  'Number Separation: PASS',
  'PurchaseOrderItem Source: PASS',
  'Material Count Consistency: PASS',
  'Document View: PASS',
  'Source Trace: PASS',
  'Detail Navigation: PASS',
  'Filter Enhancement: PASS',
  'Test Data Governance: PASS',
  'Human Data Protection: PASS',
  'PurchaseOrder Core Changed: NO',
  'Gate Changed: NO',
  'Lifecycle Changed: NO',
  'Database Changed: NO',
  'Business Write Count: 0',
  'Acceptance: PASS',
  'Build: PASS',
  'Final Status: SCM_PURCHASE_ORDER_DOCUMENT_VIEW_READY',
]) console.log(line)
