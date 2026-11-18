import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(repositoryRoot, 'docs', 'governance')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const requiredGovernance = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '流程节点真实运行验收规范.md', '页面Route与业务Context分离规范.md',
  '业务增强版本修改边界规范.md', '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = requiredGovernance.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
}) && readGovernance('PCE-ERP开发治理总规范.md').includes('BATCH-COMPLETENESS-001')

const specification = readGovernance('SCM采购订单准入Gate运行规范.md')
const process011 = readGovernance('流程节点真实运行验收规范.md')
const pageAcceptance = readGovernance('一页一验收规范.md')
const commandRule = readGovernance('CODEX执行命令规范.md')
const totalRule = readGovernance('PCE-ERP开发治理总规范.md')
const cases = readGovernance('问题案例库.md')
const acceptance = fs.readFileSync(path.join(repositoryRoot, 'docs', 'acceptance',
  'PAGE-PURCHASE-ORDER-GATE.md'), 'utf8')

const regression = run(['scripts/verifyPurchaseOrderGateReopenDataSyncV11428203.mjs'])
const build = run([path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const gateResponsibility = ['只判断', '不代替采购人员', '不创建采购订单',
  '不负责', '自动选择'].every(value => specification.includes(value))
const gateBoundary = ['purchaseOrderCreated=false', '不创建、提交或审批',
  '与PurchaseOrder边界'].every(value => specification.includes(value))
const stateModel = ['pending_review', 'blocked', 'ready_for_purchase_order',
  'DecisionBatch confirmed'].every(value => specification.includes(value))
const ruleFreeze = ['Batch Completeness', 'Decision Revision', 'Decision确认状态',
  '供应商完整性', '人工确认记录', '业务证据完整',
  'HistoricalPurchaseOrderIsolationCheck'].every(value => specification.includes(value))
const revisionRule = ['confirmed', 'reopen_review', 'manual_review',
  '禁止覆盖', 'sourceDecisionRevision', 'sourceDecisionSignature'].every(value =>
  specification.includes(value))
const inspectionRule = ['PurchaseOrderGateInspectionRecord', 'inspectionId',
  'DecisionRevision', 'checker', 'checkedAt', 'checkResult', 'checkItems',
  'blockReasons', 'supplierSnapshot', '追加保存'].every(value => specification.includes(value))
const caseUpdate = ['CASE-SCM-057', 'CASE-SCM-058', 'CASE-SCM-059',
  '流程节点状态不可逆治理案例', '流程节点数据回写一致性治理案例',
  'V1.14.2.8.18.20.4 Gate治理冻结确认'].every(value => cases.includes(value))
const processUpdate = ['Decision Revision PASS', 'Inspection History PASS',
  'SCM采购订单准入Gate冻结扩展'].every(value => process011.includes(value))
  && ['Decision Revision：PASS', 'Inspection History：PASS'].every(value => pageAcceptance.includes(value))
  && commandRule.includes('SCM-PO-GATE-001') && totalRule.includes('SCM-PO-GATE-001')
  && acceptance.includes('V1.14.2.8.18.20.4 Gate治理冻结记录')

const checks = [
  ['Gate Responsibility', governanceLoaded && gateResponsibility],
  ['Gate Boundary', gateBoundary],
  ['State Model', stateModel],
  ['Rule Freeze', ruleFreeze],
  ['Revision Rule', revisionRule],
  ['Inspection Rule', inspectionRule],
  ['Case Update', caseUpdate],
  ['PROCESS-011 Update', processUpdate],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.20.4')
console.log(`Governance Files Loaded ${governanceLoaded ? 'PASS' : 'FAIL'}`)
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'PURCHASE_ORDER_GATE_GOVERNANCE_FROZEN'
  : 'PURCHASE_ORDER_GATE_GOVERNANCE_FREEZE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
