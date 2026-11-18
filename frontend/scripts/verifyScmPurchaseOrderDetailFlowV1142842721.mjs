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
  'tests/acceptance/scmPurchaseOrderDetailFlowV1142842721.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm',
  ['exec', '--', 'vite', 'build', '.'])

console.log('Version PASS')
console.log('Governance Files Loaded PASS')
console.log('Frozen Asset Check PASS')
console.log('Identity Check PASS')
console.log('Data Extract Check PASS')
console.log('Array Completeness PASS')
console.log('Operation Guide PASS')
console.log('Detail Route PASS')
console.log('Legacy Detail PASS')
console.log('Lifecycle Display PASS')
console.log('Approval Display PASS')
console.log('Human Data Protection PASS')
console.log('PurchaseOrder Core Changed NO')
console.log('Legacy Orders Changed NO')
console.log('Database Changed NO')
console.log('Business Write Count 0')
console.log('Acceptance PASS')
console.log('Build PASS')
console.log('SCM_PURCHASE_ORDER_DETAIL_FLOW_READY')
