import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const read = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args, { cwd: frontendRoot, encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'] })

const requiredGovernanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md',
  '一页一验收规范.md',
  '治理符合性检查矩阵.md',
  '问题案例库.md',
]
const governanceFilesLoaded = requiredGovernanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
}) && read('CODEX执行命令规范.md').includes('人工验收反向校验机制')

const process011 = read('流程节点真实运行验收规范.md')
const general = read('PCE-ERP开发治理总规范.md')
const command = read('CODEX执行命令规范.md')
const pageAcceptance = read('一页一验收规范.md')
const matrix = read('治理符合性检查矩阵.md')
const cases = read('问题案例库.md')

const layers = ['Object Exists', 'Page Exists', 'Data Handoff', 'Human Action Loop']
const documentPass = process011.includes('PROCESS-011')
  && ['Domain Model', '必需字段', '合法状态', '上下游关系', 'Route', 'PageCode',
    'Page Identity', '页面业务区域', '来源编号一致', '业务对象一致',
    '用户选择', '用户填写', '用户确认', '业务状态变化', '下一节点交接']
    .every(token => process011.includes(token))
  && layers.every(label => process011.includes(`${label} PASS`))
  && process011.includes('禁止输出 READY')
  && process011.includes('生产运行禁止静态模拟数据')

const governanceUpdate = general.includes('PROCESS-011 流程节点真实运行标准')
  && general.includes('流程节点真实运行验收规范.md')
  && layers.every(label => general.includes(label) && matrix.includes(label))
const codexRuleUpdate = layers.every(label => command.includes(`${label}: PASS/FAIL/BLOCKED`))
  && command.includes('PROCESS-011') && command.includes('禁止 READY')
const acceptanceTemplateUpdate = ['入口来源', '数据来源', '用户动作', '下一节点结果']
  .every(token => pageAcceptance.includes(token)) && layers.every(label => pageAcceptance.includes(label))
const caseUpdate = cases.includes('CASE-GOV-002 流程节点存在但业务链未闭环')
  && cases.includes('发现版本：`V1.14.2.8.18.16`')
  && cases.includes('供应商推荐节点已有对象、页面和 Provider')
  && cases.includes('缺少流程节点真实运行验收标准')

const regression = run(['--test',
  'tests/acceptance/businessEnhancementBoundaryGovernanceV11428152.test.mjs',
  'tests/acceptance/enterpriseScmNodePageGovernanceV11428103.test.mjs'])
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])
for (const result of [regression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const checks = [
  ['Governance Files Loaded', governanceFilesLoaded],
  ['PROCESS-011 Document', documentPass],
  ['Governance Update', governanceUpdate],
  ['CODEX Rule Update', codexRuleUpdate],
  ['Acceptance Template Update', acceptanceTemplateUpdate],
  ['Case Update', caseUpdate],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.2')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(`Automatic Acceptance ${passed ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'PROCESS_NODE_RUNTIME_ACCEPTANCE_READY'
  : 'PROCESS_NODE_RUNTIME_ACCEPTANCE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
