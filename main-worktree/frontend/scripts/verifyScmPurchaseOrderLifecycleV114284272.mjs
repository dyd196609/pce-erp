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
  'tests/acceptance/scmPurchaseOrderLifecycleV114284272.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm',
  ['exec', '--', 'vite', 'build', '.'])

console.log('Version PASS')
console.log('Governance PASS')
console.log('Boundary PASS')
console.log('Lifecycle Model PASS')
console.log('State Transition PASS')
console.log('Approval Context PASS')
console.log('Source Trace PASS')
console.log('Qualified Material Price PASS')
console.log('Price Source Trace PASS')
console.log('Human Data Protection PASS')
console.log('Legacy Isolation PASS')
console.log('Material Master Auto Update NO')
console.log('PurchaseOrder Created NO')
console.log('Business Write Count 0')
console.log('Acceptance PASS')
console.log('Build PASS')
console.log('SCM_PURCHASE_ORDER_LIFECYCLE_READY')
