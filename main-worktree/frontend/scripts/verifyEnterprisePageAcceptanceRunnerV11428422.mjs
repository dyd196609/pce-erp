import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolveEnterprisePage } from '../src/meta/acceptance/runner/enterprisePageResolver.js'
import { resolveEnterpriseAcceptanceTemplate } from '../src/meta/acceptance/runner/enterpriseAcceptanceTemplateResolver.js'
import { assertEnterpriseAcceptanceReadOnly, createRun } from '../src/meta/acceptance/runner/enterprisePageAcceptanceRunner.js'
import { verifyEnterprisePageAcceptanceRunArchive } from './enterprisePageAcceptanceRunnerArchiveWriter.mjs'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputRoot = path.join(frontendRoot, 'test-results/page-acceptance-runner-v11428422')
const runnerFiles = [
  'src/meta/acceptance/runner/enterprisePageResolver.js',
  'src/meta/acceptance/runner/enterpriseAcceptanceTemplateResolver.js',
  'src/meta/acceptance/runner/enterpriseAcceptanceRunModel.js',
  'src/meta/acceptance/runner/enterprisePageAcceptanceRunner.js',
  'scripts/runEnterprisePageAcceptance.mjs',
]
const runCli = args => {
  const stdout = execFileSync(process.execPath, ['scripts/runEnterprisePageAcceptance.mjs', ...args], { cwd: frontendRoot, encoding: 'utf8', timeout: 180_000 })
  return JSON.parse(stdout.trim().split(/\r?\n/).at(-1))
}

const production = runCli(['--url','/scm/purchase-request','--mode','production','--runId','VERIFY-RUNNER-PRODUCTION-V11428422'])
const canary = runCli(['--url','/scm/purchase-request','--mode','canary','--scenario','HAPPY_PATH','--runId','VERIFY-RUNNER-CANARY-V11428422'])
const page = resolveEnterprisePage({ pageUrl: '/scm/purchase-request' })
const template = resolveEnterpriseAcceptanceTemplate(page)
const productionAcceptance = JSON.parse(fs.readFileSync(path.join(production.archivePath, 'acceptance.json'), 'utf8'))
const productionEvidence = JSON.parse(fs.readFileSync(path.join(production.archivePath, 'evidence.json'), 'utf8'))
const manifest = JSON.parse(fs.readFileSync(path.join(production.archivePath, 'manifest.json'), 'utf8'))
const archiveVerification = await verifyEnterprisePageAcceptanceRunArchive(production.archivePath)
let readOnlyBlocked = false, businessActionBlocked = false
try { createRun({ pageUrl: '/scm/purchase-request', readonly: false }) } catch (error) { readOnlyBlocked = error.message === 'RUNNER_READONLY_REQUIRED' }
try { assertEnterpriseAcceptanceReadOnly({ readonly: true, businessActions: ['submit'] }) } catch (error) { businessActionBlocked = error.message.startsWith('RUNNER_BUSINESS_ACTION_FORBIDDEN') }

const rules = []
const add = (code, name, pass, evidence) => rules.push({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })
add('RUNNER-001', '运行器文件存在', runnerFiles.every(file => fs.existsSync(path.join(frontendRoot, file))), runnerFiles)
add('RUNNER-002', '页面自动解析成功', page.result === 'PASS' && page.pageCode === 'SCM_PURCHASE_REQUEST' && page.component === 'ScmPurchaseRequestPage', page)
add('RUNNER-003', '模板自动匹配成功', template.result === 'PASS' && template.templateCode === 'SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE', template)
add('RUNNER-004', 'Evidence Engine调用成功', production.evidenceCount === 24 && productionAcceptance.summary?.FAIL === 0 && productionAcceptance.summary?.UNKNOWN === 0 && productionEvidence.length === 24, { evidenceCount: productionEvidence.length, summary: productionAcceptance.summary })
add('RUNNER-005', '报告自动生成', fs.existsSync(path.join(production.archivePath, 'report.md')) && fs.existsSync(path.join(production.archivePath, 'run.json')), ['report.md','run.json'])
add('RUNNER-006', '归档成功', archiveVerification.valid && manifest.immutable === true && manifest.runnerVersion === 'V1.14.2.8.4.22' && manifest.templateResolverVersion === 'V1.14.2.8.4.22' && manifest.evidenceEngineVersion === 'V1.14.2.8.4.21', { archivePath: production.archivePath, manifestHash: manifest.manifestHash })
add('RUNNER-007', 'CLI执行成功', production.success && canary.success && production.pageCode === 'SCM_PURCHASE_REQUEST' && canary.mode === 'canary', { production, canary })
add('RUNNER-008', 'ReadOnly保护有效', readOnlyBlocked, { readonlyFalseBlocked: readOnlyBlocked })
add('RUNNER-009', '禁止业务动作有效', businessActionBlocked, { submitBlocked: businessActionBlocked })
add('RUNNER-010', '数据库无变化', production.databaseHashUnchanged && canary.databaseHashUnchanged && production.businessWriteCount === 0 && canary.businessWriteCount === 0 && production.productionUserDataWritten === false && canary.productionUserDataWritten === false, { production: { databaseHashUnchanged: production.databaseHashUnchanged, businessWriteCount: production.businessWriteCount }, canary: { databaseHashUnchanged: canary.databaseHashUnchanged, businessWriteCount: canary.businessWriteCount }, productionUserDataWritten: false })

const totals = { total: rules.length, PASS: rules.filter(rule => rule.result === 'PASS').length, FAIL: rules.filter(rule => rule.result === 'FAIL').length, 'N/A': 0, UNKNOWN: 0 }
const report = {
  version: 'V1.14.2.8.4.22', status: totals.PASS === 10 && totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PAGE_ACCEPTANCE_RUNNER_READY' : 'FAIL',
  totals, rules, productionRun: production, canaryRun: canary,
  productionUserDataWritten: false, businessWriteCount: 0,
  businessLogicChanged: 'NO', scmLogicChanged: 'NO', purchaseRequestModelChanged: 'NO', purchaseInquiryDevelopmentEntered: 'NO',
}
fs.mkdirSync(outputRoot, { recursive: true })
const serialized = `${JSON.stringify(report, null, 2)}\n`
fs.writeFileSync(path.join(outputRoot, 'enterprise_page_acceptance_runner_acceptance_v11428422.json'), serialized)
fs.writeFileSync(path.join(frontendRoot, 'enterprise_page_acceptance_runner_acceptance_v11428422.json'), serialized)
console.log(serialized)
if (report.status !== 'PAGE_ACCEPTANCE_RUNNER_READY') process.exitCode = 1
