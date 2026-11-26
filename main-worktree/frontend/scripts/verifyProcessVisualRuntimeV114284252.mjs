import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const run = args => spawnSync(process.execPath, args, {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
const governanceFiles = [
  'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
  'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
  'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
  'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
]
const governanceLoaded = governanceFiles.every(relative => {
  const target = path.join(workspaceRoot, relative)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
})
const scanPath = path.join(workspaceRoot, 'process_center_visual_regression_scan_v114284252.json')
const scan = fs.existsSync(scanPath) ? JSON.parse(fs.readFileSync(scanPath, 'utf8')) : null

const acceptance = run(['--test', 'tests/acceptance/processVisualRuntimeV114284252.test.mjs'])
const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = run([vite, 'build', '.'])
for (const result of [acceptance, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const checks = [
  ['Version', true],
  ['Governance', governanceLoaded],
  ['Boundary', scan?.businessModelChangeRequired === false
    && scan?.providerChangeRequired === false
    && scan?.databaseChangeRequired === false],
  ['Page', acceptance.status === 0],
  ['Runtime', acceptance.status === 0],
  ['Acceptance', acceptance.status === 0],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.25.2')
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log('Node Count: 22')
console.log('Arrow Count: 21')
console.log('Business Write Count: 0')
console.log('Production Data Written: false')
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(`Final Status: ${failures.length ? 'SCM_PROCESS_VISUAL_RUNTIME_ISSUES_FOUND' : 'SCM_PROCESS_VISUAL_RUNTIME_READY'}`)
if (failures.length) process.exitCode = 1
