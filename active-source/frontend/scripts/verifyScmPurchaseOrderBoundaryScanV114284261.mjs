import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const root = path.resolve(frontendRoot, '..')
const governanceFiles = [
  'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
  'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
  'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
  'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
  'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
  'docs/governance/06-模块专项治理/SCM/PCE-ERP-SCM专项治理规范.md',
]

function fail(message) {
  console.error(message)
  process.exit(1)
}

const governance = governanceFiles.map(relativePath => {
  const absolutePath = path.join(root, relativePath)
  if (!fs.existsSync(absolutePath)) fail(`Governance file missing: ${relativePath}`)
  return fs.readFileSync(absolutePath, 'utf8')
})
if (!governance.join('\n').includes('DATA-PROTECTION-001')) fail('DATA-PROTECTION-001 missing')
if (!governance.join('\n').includes('DATA-PROTECTION-RUNTIME-001')) fail('DATA-PROTECTION-RUNTIME-001 missing')

const acceptance = spawnSync(process.execPath,
  ['tests/acceptance/scmPurchaseOrderBoundaryScanV114284261.test.mjs'],
  { cwd: frontendRoot, encoding: 'utf8' })
process.stdout.write(acceptance.stdout || '')
process.stderr.write(acceptance.stderr || '')
if (acceptance.status !== 0) fail('SCM purchase order boundary acceptance failed')

const viteCli = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
if (!fs.existsSync(viteCli)) fail('Vite CLI missing')
const build = spawnSync(process.execPath, [viteCli, 'build'],
  { cwd: frontendRoot, encoding: 'utf8', env: process.env })
process.stdout.write(build.stdout || '')
process.stderr.write(build.stderr || '')
if (build.status !== 0) fail('Build failed')

console.log('Build PASS')
console.log('SCM_PURCHASE_ORDER_BOUNDARY_SCAN_READY')
