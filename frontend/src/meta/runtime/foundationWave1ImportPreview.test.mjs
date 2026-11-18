import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const read = relative => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8')
const page = read('../pages/FoundationManufacturingImportPreviewPage.vue')
const portal = read('../pages/EnterpriseFoundationUnifiedPage.vue')
const api = read('../../api/pde.js')
const router = read('../../router/index.js')
const registry = read('./pcePageAcceptanceRegistry.js')
const businessNames = read('../governance/businessNameRegistry.js')
const backendService = read('../../../../backend/pde/foundation_import_preview_service.py')
const uomGovernance = read('../../../../backend/masterdata/uom_governance.py')
const backendView = read('../../../../backend/pde/foundation_import_preview_views.py')
const backendUrls = read('../../../../backend/pde/urls.py')
const formalMaintenance = read('../components/ProductionFoundationMaintenance.vue')
const group2Comparison = read('../pages/Group2ComparisonPreviewPage.vue')
const batch1Comparison = read('../pages/BaseDataComparisonPreviewPage.vue')
const acceptanceCenter = read('../pages/BaseDataManualAcceptanceCenterPage.vue')
const chineseDisplayContract = read('../governance/businessNameRegistry.js')

assert.match(page, /data-page-type="VALIDATION_PAGE"/)
assert.match(page, /data-action-type="VALIDATION_ACTION"/)
assert.match(page, /data-formal-master-data-write="0"/)
assert.match(page, /PceEnterpriseListTable/)
for (const field of ['sourceFile', 'candidateObject', 'validationStatus', 'uomStatus', 'recommendedDecision']) {
  assert.match(page, new RegExp(`field:'${field}'`), `missing governed filter ${field}`)
}
for (const label of ['来源文件', 'SHA256', '工作表', '来源行号', '来源对象类型', '来源名称', '来源计量单位', '来源身份状态', '现有正式数据匹配', '候选对象', '正式编码策略', '计量单位处理', '校验状态', '建议处理', '车间 / 工作中心', '原因']) {
  assert.match(page, new RegExp(label), `missing user-visible preview field ${label}`)
}
for (const readinessLabel of ['3. 三 Gate 独立裁决与正式写入准备', 'Gate A · 工程代码提交就绪', 'Gate B · 生产迁移就绪', 'Gate C · 正式主数据写入就绪', '当前来源级编码裁决', '正式写入候选', 'READY', 'REVIEW', 'BLOCKED', '正式编码已具备', '计量单位已具备', '来源身份持久化已具备', '正式写入服务', '权限与审计链', '车间候选', '工作中心候选', '正式写入链能力', '真实数据阻塞项', '业务复核项', '仅需逐行处理的异常来源', '正式写入 · 未授权']) {
  assert.match(page, new RegExp(readinessLabel), `missing commit-readiness field ${readinessLabel}`)
}
for (const legacyLabel of ['Source Row', 'Raw UOM', 'Source Identity Status', 'Existing Canonical Match', 'Candidate Object', 'Canonical Code Policy', 'UOM Decision', 'Validation Status', 'Recommended Decision']) {
  assert.doesNotMatch(page, new RegExp(`<el-table-column[^>]*label=["']${legacyLabel}["']`), `legacy English table label remains: ${legacyLabel}`)
}
assert.match(page, /PRODUCT FORMAL IMPORT = NOT IN CURRENT CHECKPOINT/)
assert.match(page, /WORKCENTER = NOT_MAINTAINED/)
assert.match(page, /EXISTING RECORD UPDATE PLAN/)
assert.match(portal, /to="\/foundation\/import-preview"/)
assert.match(router, /FoundationManufacturingImportPreviewPage\.vue/)
assert.match(registry, /foundation-manufacturing-import-preview/)
assert.match(businessNames, /FoundationImportPreview.*制造基础数据导入预览.*\/foundation\/import-preview/)
assert.match(api, /foundation-import-preview\//)
assert.match(backendView, /production\.master_data\.view/)
assert.match(backendView, /VALIDATION_ACTION/)
assert.doesNotMatch(backendView, /\.save\(|next_code|objects\.create/)
assert.match(backendUrls, /foundation-import-preview\//)
assert.match(backendUrls, /formal-import\/<slug:entity>\/commit\//)
assert.doesNotMatch(api, /commitFoundation|applyFoundation|importToMaster/)
assert.match(formalMaintenance, /idempotencyKey = createIdempotencyKey\.value/)
assert.doesNotMatch(backendService, /\.save\(|next_code\(|objects\.create|localStorage/)
assert.match(backendService, /read_only=True/)
assert.match(backendService, /placeholder_names/)
assert.match(backendService, /ROUTING_REFERENCE_EVIDENCE/)
assert.match(backendService, /GENERATE_FORMAL_MATERIAL_CODE/)
assert.match(backendService, /FORMAL_OPERATION_AND_WORKSHOP_CODE_RULE_READY/)
assert.match(backendService, /formalWriteAuthorized": False/)
assert.match(backendService, /engineeringCodeCommitReadiness": "GO"/)
assert.match(backendService, /MigrationRecorder\.Migration\.objects\.filter/)
assert.match(backendService, /productionMigrationAuthorization/)
assert.match(backendService, /"COMPLETE" if wave2_migration_applied/)
assert.doesNotMatch(backendService, /finalCommitReady/)
assert.doesNotMatch(backendService, /startswith\(["'](?:01|05|10)/)
assert.match(page, /data-acceptance-id="FOUNDATION_FORMAL_WRITE_DISABLED"/)
assert.match(page, /<el-button type="primary" disabled/)
assert.match(page, /if\(!response\.data\?\.commitReadiness\)throw new Error/)
for (const uomClass of ['EXACT_MATCH', 'NORMALIZED_MATCH', 'SEMANTIC_REVIEW', 'INVALID']) {
  assert.match(uomGovernance, new RegExp(uomClass), `missing UOM governance class ${uomClass}`)
}
assert.match(uomGovernance, /"面积": "area"/)
assert.doesNotMatch(backendService, /DoorMaterial|DoorBOM|DoorRouting|CabinetMaterial|CabinetRouting|WallPanelRouting|WoodEngineeringEngine|WholeHouseFoundation/)
assert.doesNotMatch(backendService, /if\s+(door|cabinet|wall_panel|veneer|blank_board)/i)
assert.doesNotMatch(page, /manufacturingFoundationStore|localStorage\.(?:getItem|setItem|removeItem|clear)/)
assert.match(router, /path: 'process-center'/)
assert.match(router, /path: 'pde\/workbench'/)
assert.match(router, /path: 'pde\/engineering-calculations'/)

for (const [name, source] of Object.entries({ group2Comparison, batch1Comparison, acceptanceCenter, formalMaintenance })) {
  assert.doesNotMatch(source, /<th>(UOM|MAKE \/ BUY|MAKE\/BUY|Data Provenance|Material Type|DEVELOPED|DATA PRESENT|USER VALIDATED|READY|Source|Formal Data|Missing|Conflict|Simulated|Group)<\/th>/, `${name} 泄漏英文业务表头`)
  assert.doesNotMatch(source, /\{\{\s*row\.(makeBuy|materialType|sourceKind)\s*\}\}/, `${name} 直接展示已知英文枚举`)
}
for (const required of ["uom: '计量单位'", "MAKE: '自制'", "semi: '半成品'", "USER_EXCLUDED_INCOMPLETE_SOURCE: '用户排除的不完整来源'"]) {
  assert.match(chineseDisplayContract, new RegExp(required), `中文展示契约缺少 ${required}`)
}

console.log('FOUNDATION_WAVE1_PREVIEW_STATIC_ACCEPTANCE=PASS')
console.log('FORMAL_MASTER_DATA_WRITE=0')
console.log('DUPLICATE_IMPORT_FRAMEWORK=0')
console.log('INDUSTRY_CORE_HARDCODING=0')
