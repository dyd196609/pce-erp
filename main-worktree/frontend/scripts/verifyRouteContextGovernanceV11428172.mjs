import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim()
}) && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')

const routeContext = readGovernance('页面Route与业务Context分离规范.md')
const template = readGovernance('页面开发模板.md')
const process011 = readGovernance('流程节点真实运行验收规范.md')
const totalGovernance = readGovernance('PCE-ERP开发治理总规范.md')
const codexRules = readGovernance('CODEX执行命令规范.md')
const acceptance = readGovernance('一页一验收规范.md')
const matrix = readGovernance('治理符合性检查矩阵.md')
const cases = readGovernance('问题案例库.md')
const regression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const allModules = ['SCM', 'WMS', 'MES', 'Finance', 'CRM', 'QMS', 'APS']
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Route Identity', routeContext.includes('Route只表达')
    && routeContext.includes('/scm/supplier-recommendation')
    && routeContext.includes('/wms/outbound-order')
    && routeContext.includes('/finance/payment-voucher')
    && process011.includes('Route Identity PASS')],
  ['Context Separation', routeContext.includes('Page Route')
    && routeContext.includes('Context Resolver') && routeContext.includes('Task')
    && routeContext.includes('Business Object') && routeContext.includes('Provider')
    && process011.includes('Context Separation PASS')],
  ['Governance Document', routeContext.includes('ROUTE-CONTEXT-001')
    && allModules.every(module => routeContext.includes(module))
    && totalGovernance.includes('ROUTE-CONTEXT-001')
    && codexRules.includes('ROUTE-CONTEXT-001') && matrix.includes('ROUTE-CONTEXT-001')],
  ['Template Update', template.includes('Page Route:') && template.includes('Business Context:')
    && template.includes('ROUTE-CONTEXT-001') && acceptance.includes('Route Identity')
    && acceptance.includes('Context Separation')],
  ['Case Update', cases.includes('CASE-GOV-003')
    && cases.includes('业务运行数据泄露到页面Route')
    && cases.includes('verifyRouteContextGovernanceV11428172.mjs')],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.17.2')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'ROUTE_CONTEXT_GOVERNANCE_READY' : 'ROUTE_CONTEXT_GOVERNANCE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
