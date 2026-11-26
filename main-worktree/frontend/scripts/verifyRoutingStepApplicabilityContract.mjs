import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')

const readback = read('src/meta/pages/components/RoutingVersionReadback.vue')
const page = read('src/meta/pages/PdeFoundationPage.vue')
const api = read('src/api/pde.js')
const registry = read('src/meta/runtime/pceBusinessActionRegistry.js')
const foundation = read('src/meta/components/ProductionFoundationMaintenance.vue')
const manualService = fs.readFileSync(path.resolve(root, '../backend/pde/routing_manual_applicability_service.py'), 'utf8')

for (const label of ['工序适用方式', '适用条件', '正式条件来源', '条件判断结果', '当前待确认原因']) {
  assert.ok(readback.includes(label), `missing governed column: ${label}`)
}
for (const label of [
  '工艺路线编码', '工艺路线版本号', '修订号', '工艺路线版本ID',
  '工艺路线主档状态', '当前版本状态', '当前版本发布状态', '关联BOM版本',
]) {
  assert.ok(readback.includes(label), `missing routing/version identity label: ${label}`)
}
assert.ok(readback.includes('routing-version-status-boundary'))
assert.ok(readback.includes('revisionLabel(version.revision)'))
assert.ok(readback.includes('associatedBomVersionLabel(version)'))
assert.ok(readback.includes('主档保留既有发布事实，不代表当前展示版本已经发布'))
for (const label of [
  '工艺路线版本正式发布', '正式评审状态', '正式发布准入',
  '当前操作人', '专用权限', '发布职责',
]) {
  assert.ok(readback.includes(label), `missing dedicated release label: ${label}`)
}
assert.ok(readback.includes('正式评审与正式发布是两个不同业务动作'))
assert.ok(readback.includes('data-acceptance-id="release-routing-version"'))
assert.ok(readback.includes('!version.releasePreflight.releaseAllowed'))
const definitions = read('src/meta/pages/pdePageDefinitions.js')
assert.ok(definitions.includes("['definitionStatusLabel', '工艺路线主档状态'"))
assert.ok(definitions.includes("['statusLabel', '当前版本状态'"))
assert.ok(definitions.includes("['releaseStatusLabel', '当前版本发布状态'"))
assert.ok(readback.includes('create-routing-successor-version'))
assert.ok(readback.includes('maintain-routing-step-applicability'))
assert.ok(readback.includes('routing-manual-applicability-decisions'))
assert.ok(readback.includes('confirm-routing-manual-applicability'))
assert.ok(readback.includes('decisionRow.question'))
assert.ok(manualService.includes('本次订单工程对象是否需要雕刻纹路？'))
assert.ok(manualService.includes('本次订单工程对象是否需要生产前异形加工？'))
assert.ok(readback.includes('无需上传图纸，不新增审批流程'))
assert.ok(readback.includes('label="判定依据"'))
assert.ok(readback.includes('请填写本次判定的依据，如设计要求、订单工程信息或人工核实结果；无需上传图纸。'))
assert.ok(!readback.includes('label="维护说明"'))
assert.ok(readback.includes('未选择不会自动解释为“否”'))
assert.ok(readback.includes("form.mode === 'CONDITIONAL'"))
assert.ok(readback.includes('条件结论由合法正式工程事实或授权业务人员人工确认提供'))
assert.ok(page.includes('handleCreateRoutingSuccessor'))
assert.ok(page.includes('handleSaveRoutingStepApplicability'))
assert.ok(page.includes('handleSaveRoutingManualDecision'))
assert.ok(page.includes('handleReleaseRoutingVersion'))
assert.ok(page.includes("action: 'pde.routing_version.release'"))
assert.ok(api.includes('/api/pde/routing-versions/${versionId}/successor/'))
assert.ok(api.includes('/api/pde/routing-steps/${stepId}/applicability/'))
assert.ok(api.includes('/api/pde/routing-versions/${versionId}/manual-applicability/'))
assert.ok(api.includes('/api/pde/routing-versions/${versionId}/release/'))
assert.ok(registry.includes("currentModule: 'routing-version-management'"))
assert.ok(registry.includes("action('confirm-routing-manual-applicability'"))
assert.ok(registry.includes("formalPermission: 'production.master_data.routing.maintain'"))
assert.ok(registry.includes("action('release-routing-version'"))
assert.ok(registry.includes("formalPermission: 'pde.routing_version.release'"))
assert.ok(!foundation.includes("json('operation_parameters', '工序参数"), 'raw applicability JSON editor must stay closed')

console.log(JSON.stringify({
  gate: 'PDE_ROUTING_STEP_APPLICABILITY_FRONTEND',
  status: 'PASS',
  governedColumns: 5,
  rawApplicabilityJsonEditorCount: 0,
  successorActionRegistered: true,
  applicabilityActionRegistered: true,
  manualDecisionActionRegistered: true,
  manualDecisionCount: 2,
  dedicatedReleaseActionRegistered: true,
  blockedReleaseButtonDisabled: true,
}, null, 2))
