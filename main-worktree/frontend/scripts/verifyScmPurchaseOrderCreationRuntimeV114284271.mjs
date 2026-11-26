import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const fail = message => { console.error(message); process.exit(1) }

const acceptance = spawnSync(process.execPath,
  ['tests/acceptance/scmPurchaseOrderCreationRuntimeV114284271.test.mjs'],
  { cwd: frontendRoot, encoding: 'utf8' })
process.stdout.write(acceptance.stdout || '')
process.stderr.write(acceptance.stderr || '')
if (acceptance.status !== 0) fail('SCM purchase order creation runtime acceptance failed')

const viteCli = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [viteCli, 'build'],
  { cwd: frontendRoot, encoding: 'utf8', env: process.env })
process.stdout.write(build.stdout || '')
process.stderr.write(build.stderr || '')
if (build.status !== 0) fail('Build failed')

console.log('Build PASS')
console.log('SCM_PURCHASE_ORDER_CREATION_RUNTIME_READY')
