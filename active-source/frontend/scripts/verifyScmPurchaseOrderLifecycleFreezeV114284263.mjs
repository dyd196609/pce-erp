import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
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

run(process.execPath, ['../frontend/scripts/generateScmPurchaseOrderLifecycleClassificationV114284263.mjs'])
run(process.execPath, ['tests/acceptance/scmPurchaseOrderLifecycleFreezeV114284263.test.mjs'])
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['exec', '--', 'vite', 'build'])

const reportPath = resolve(frontendRoot, '../scm_purchase_order_lifecycle_classification_v114264263.json')
const report = JSON.parse(readFileSync(reportPath, 'utf8'))
report.validation.build = 'PASS'
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')

console.log('Build PASS')
console.log('SCM_PURCHASE_ORDER_LIFECYCLE_FREEZE_READY')
