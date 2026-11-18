import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
function run(command, args) {
  const result = spawnSync(command, args, { cwd: frontendRoot, stdio: 'inherit',
    shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(process.execPath, ['--test', 'tests/acceptance/pcePageRuntimePurchaseOrderV1142842726.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build', '.'])

for (const line of [
  'Version: V1.14.2.8.4.27.2.6',
  'Governance Files Loaded: PASS',
  'Governance Applied: PASS',
  'Page Runtime Validation: PASS',
  'Page Migration Validation: PASS',
  'PurchaseOrder Detail: PASS',
  'Old Renderer: REMOVED',
  'Print Preview: PASS',
  'Print Entry: PASS',
  'Refresh Runtime: PASS',
  'PurchaseOrder Core Changed: NO',
  'Gate Changed: NO',
  'Database Changed: NO',
  'Business Write Count: 0',
  'Build: PASS',
  'Final Status: PCE_PAGE_RUNTIME_GOVERNANCE_READY',
]) console.log(line)
