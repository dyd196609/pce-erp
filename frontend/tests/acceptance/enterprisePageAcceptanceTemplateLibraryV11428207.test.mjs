import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createEnterprisePageAcceptanceRun,
  evaluateEnterprisePageAcceptance,
  listEnterprisePageAcceptanceTemplates,
} from '../../src/meta/acceptance/enterprisePageAcceptanceTemplateLibrary.js'

test('SCM运行实例合并公共和SCM检查项', () => {
  const run = createEnterprisePageAcceptanceRun({
    pageIdentity: { pageCode: 'purchase-request', pageName: '采购申请', pageUrl: '/scm/purchase-request' },
    moduleCode: 'SCM',
    acceptanceRunId: 'RUN-001',
  })
  assert.equal(run.checks.length, 24)
  assert.equal(run.summary.UNKNOWN, 24)
  assert.equal(new Set(run.checks.map(check => check.id)).size, 24)
})

test('缺失检查项保持UNKNOWN且阻断放行', () => {
  const run = createEnterprisePageAcceptanceRun({ pageIdentity: { pageCode: 'x' }, moduleCode: 'GEN', acceptanceRunId: 'RUN-002' })
  const result = evaluateEnterprisePageAcceptance(run, [{ id: run.checks[0].id, result: 'PASS' }])
  assert.equal(result.summary.UNKNOWN, run.checks.length - 1)
  assert.equal(result.releaseGate.nextPageAllowed, false)
})

test('N/A不能删除且必须填写原因和确认人', () => {
  const run = createEnterprisePageAcceptanceRun({ pageIdentity: { pageCode: 'x' }, moduleCode: 'GEN', acceptanceRunId: 'RUN-003' })
  const invalid = evaluateEnterprisePageAcceptance(run, run.checks.map(check => ({ id: check.id, result: 'N/A' })))
  assert.equal(invalid.summary.FAIL, run.checks.length)
  const valid = evaluateEnterprisePageAcceptance(run, run.checks.map(check => ({
    id: check.id,
    result: 'N/A',
    naReason: '当前页面无此业务能力',
    confirmedBy: 'acceptance-owner',
    evidenceRefs: ['manual-acceptance.md'],
  })))
  assert.equal(valid.checks.length, run.checks.length)
  assert.equal(valid.summary['N/A'], run.checks.length)
  assert.equal(valid.summary.FAIL, 0)
})

test('模板库声明四种结果并保留SCM扩展', () => {
  const templates = listEnterprisePageAcceptanceTemplates()
  assert.deepEqual(templates.master.statusVocabulary, ['PASS', 'FAIL', 'N/A', 'UNKNOWN'])
  assert.equal(templates.commonChecklist.naPolicy.removable, false)
  assert.equal(templates.scmBusinessPage.scmChecks.length, 8)
})
