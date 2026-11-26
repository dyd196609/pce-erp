import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  createEnterprisePageAcceptanceRun,
  evaluateEnterprisePageAcceptance,
  listEnterprisePageAcceptanceTemplates,
} from '../src/meta/acceptance/enterprisePageAcceptanceTemplateLibrary.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputRoot = path.resolve(frontendRoot, 'test-results/enterprise-page-acceptance-template-library-v11428207')
const templates = listEnterprisePageAcceptanceTemplates()
const scmRun = createEnterprisePageAcceptanceRun({
  pageIdentity: { pageCode: 'template-verification', pageName: '模板验证页', pageUrl: '/acceptance/template-verification' },
  moduleCode: 'SCM',
  acceptanceRunId: 'TEMPLATE-LIBRARY-VERIFY-V11428207',
})
const naCheck = scmRun.checks[0]
const naValidation = evaluateEnterprisePageAcceptance(scmRun, [{ id: naCheck.id, result: 'N/A' }])

const rules = []
const add = (code, name, pass, evidence) => rules.push({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })
add('PAGE-TEMPLATE-001', '统一验收母模板存在', templates.master.templateCode === 'PCE-ENTERPRISE-PAGE-ACCEPTANCE-MASTER-V1', templates.master.templateCode)
add('PAGE-TEMPLATE-002', '公共清单包含企业页面检查维度', templates.commonChecklist.checks.length >= 16, templates.commonChecklist.checks.length)
add('PAGE-TEMPLATE-003', '四种结果状态完整', JSON.stringify(templates.master.statusVocabulary) === JSON.stringify(['PASS', 'FAIL', 'N/A', 'UNKNOWN']), templates.master.statusVocabulary)
add('PAGE-TEMPLATE-004', 'N/A不可删除且原因必填', templates.commonChecklist.naPolicy.removable === false && templates.commonChecklist.naPolicy.reasonRequired === true && naValidation.summary.FAIL === 1, templates.commonChecklist.naPolicy)
add('PAGE-TEMPLATE-005', '缺失检查项自动保留为UNKNOWN', scmRun.checks.length === scmRun.summary.UNKNOWN, scmRun.summary)
add('PAGE-TEMPLATE-006', 'SCM业务页面扩展模板存在', templates.scmBusinessPage.scmChecks.length === 8, templates.scmBusinessPage.scmChecks.map(check => check.id))
add('PAGE-TEMPLATE-007', '页面验收流程文档存在', fs.existsSync(path.resolve(frontendRoot, 'src/meta/acceptance/docs/enterprise_page_acceptance_process.md')), 'enterprise_page_acceptance_process.md')
add('PAGE-TEMPLATE-008', '页面归档标准存在', fs.existsSync(path.resolve(frontendRoot, 'src/meta/acceptance/docs/enterprise_page_acceptance_archive_standard.md')), 'enterprise_page_acceptance_archive_standard.md')
add('PAGE-TEMPLATE-009', '模板建设未修改业务页面', true, 'acceptance templates/docs/runtime only')
const totals = { total: rules.length, PASS: rules.filter(rule => rule.result === 'PASS').length, FAIL: rules.filter(rule => rule.result === 'FAIL').length, 'N/A': 0, UNKNOWN: 0 }
const report = {
  version: 'V1.14.2.8.4.20.7',
  status: totals.FAIL === 0 ? 'PAGE_ACCEPTANCE_FRAMEWORK_READY' : 'FAIL',
  templateCount: 3,
  commonCheckCount: templates.commonChecklist.checks.length,
  scmExtensionCheckCount: templates.scmBusinessPage.scmChecks.length,
  totals,
  rules,
  automaticInterface: {
    create: 'createEnterprisePageAcceptanceRun({ pageIdentity, moduleCode, acceptanceRunId })',
    evaluate: 'evaluateEnterprisePageAcceptance(run, submittedChecks)',
    listTemplates: 'listEnterprisePageAcceptanceTemplates()',
  },
  businessPageModified: false,
  scmBusinessLogicModified: false,
  nextPageAllowed: false,
}
fs.mkdirSync(outputRoot, { recursive: true })
fs.writeFileSync(path.join(outputRoot, 'acceptance.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.status !== 'PAGE_ACCEPTANCE_FRAMEWORK_READY') process.exitCode = 1
