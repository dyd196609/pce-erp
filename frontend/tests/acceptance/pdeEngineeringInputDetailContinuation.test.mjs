import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { engineeringInstanceScopeLabel, summarizeFormalValidation } from '../../src/meta/runtime/formalContinuationPresentation.js'

const root = path.resolve(import.meta.dirname, '../..')
const source = fs.readFileSync(path.join(root, 'src/meta/pages/PdeOrderEngineeringCalculationPage.vue'), 'utf8')
const productDesignSource = fs.readFileSync(path.join(root, 'src/meta/pages/PdeProductDesignPage.vue'), 'utf8')
const apiSource = fs.readFileSync(path.join(root, 'src/api/pde.js'), 'utf8')
const backendRoot = path.resolve(root, '../backend/pde')
const continuationService = fs.readFileSync(path.join(backendRoot, 'formal_engineering_continuation_service.py'), 'utf8')
const calculationAdapter = fs.readFileSync(path.join(backendRoot, 'calculation_batch_reuse.py'), 'utf8')
const calculationService = fs.readFileSync(path.join(backendRoot, 'engineering_calculation_service.py'), 'utf8')
const presentationSource = fs.readFileSync(path.join(root, 'src/meta/runtime/formalContinuationPresentation.js'), 'utf8')

test('formal presentation covers zero, partial, complete, blocked and failed states', () => {
  assert.equal(engineeringInstanceScopeLabel({ sourceScope: true, instanceCount: 0, lineCount: 4, factsLoaded: true }), '整单范围 · 0个实例')
  assert.equal(engineeringInstanceScopeLabel({ sourceScope: true, instanceCount: 2, lineCount: 4, factsLoaded: true }), '整单范围 · 2/4个订单行实例已建立；请选择订单行查看具体实例')
  assert.equal(engineeringInstanceScopeLabel({ sourceScope: false, selectedInstanceNo: 'OEI-1', instanceCount: 4, lineCount: 4, factsLoaded: true }), 'OEI-1')
  const complete = summarizeFormalValidation('completed', [85, 51, 248, 4].map(resultPositionCount => ({ fullValidation: { status: 'passed', resultPositionCount } })))
  assert.deepEqual(complete, { state: 'passed', label: '4/4 行完整校验通过 · 零业务写入', resultPositionTotal: 388 })
  assert.equal(summarizeFormalValidation('completed', [{ fullValidation: { status: 'blocked' } }]).state, 'blocked')
  assert.equal(summarizeFormalValidation('completed', [{ fullValidation: { status: 'read_failed' } }]).state, 'read_failed')
  assert.equal(summarizeFormalValidation('running', []).state, 'updating')
  assert.equal(summarizeFormalValidation('failed', []).state, 'read_failed')
})

test('current 71 design inputs are a directly visible governed enterprise list', () => {
  const section = source.indexOf('data-section="current-design-calculation-inputs"')
  const auxiliary = source.indexOf('data-section="source-case"')
  assert.ok(section > 0 && section < auxiliary, 'input detail must appear before the collapsed auxiliary source panel')
  assert.match(source, /<PceEnterpriseListTable[\s\S]*table-id="pde-current-design-inputs"/)
  assert.match(source, /:default-page-size="20"/)
  assert.match(source, /:page-sizes="\[20, 50, 100\]"/)
  assert.match(source, /scroll-acceptance-id="pde-design-input-horizontal-scroll"/)
  assert.match(source, /@export-current="exportCurrentDesignInputs"/)
  assert.match(source, /prop="processConfiguration" label="工艺配置"/)
  assert.match(source, /prop="paintProcess" label="油漆工艺"/)
})

test('sales-order-line save readiness is a real adjacent column with an in-page read-only detail', () => {
  const orderLineColumn = source.indexOf('prop="orderLineNo" label="订单行"')
  const readinessColumn = source.indexOf('label="核算保存前需完成"', orderLineColumn)
  const productColumn = source.indexOf('label="产品／位置"', readinessColumn)
  assert.ok(orderLineColumn > 0 && orderLineColumn < readinessColumn && readinessColumn < productColumn)
  assert.match(source, />查看本行条件<\/button>/)
  assert.match(source, /data-section="sales-order-line-save-readiness"/)
  assert.match(source, /销售订单第\{\{ selectedLineCondition\.lineNo \}\}行/)
  assert.match(source, /用于把该销售订单行的设计对象、来源、基线和后续核算记录对应起来的办理记录/)
  assert.match(source, /当前账号相关权限（服务端实时判定）/)
  assert.doesNotMatch(source, /正式核算尚未保存[^\n]*尚未完成的具体事项/)
})

test('line readiness joins by stable sales-order-item identity and preflight is not requested per object', () => {
  assert.match(calculationAdapter, /'salesOrderItemId': item\.sales_order_item_id/)
  assert.match(calculationService, /"salesOrderItemId": item\.pk, "orderLineNo": item\.line_no/)
  assert.match(source, /conditionLinesBySalesOrderItemId\.value\.get\(Number\(row\.salesOrderItemId\)\)/)
  assert.doesNotMatch(source, /conditionLinesBySalesOrderItemId\.value\.get\(Number\(row\.orderLineNo\)\)/)
  const mapper = source.slice(source.indexOf('const designInputRows'), source.indexOf('const designInputFilterSchema'))
  assert.doesNotMatch(mapper, /preflightOrderEngineeringCalculation/)
  assert.match(source, /await loadConditionPreflight\(\{ announce: false \}\)/)
})

test('read failures remain unknown instead of being presented as incomplete readiness', () => {
  assert.match(source, /conditionPreflightOperation\.state === 'failed'/)
  assert.match(source, /读取失败，状态未知/)
  assert.match(source, /本次读取结果未知，未按“不具备条件”处理/)
  assert.match(source, /kind === 'permission' \? '无权查看预检事实'/)
})

test('advanced filters declare governed filterType and current data remains server sourced', () => {
  const schema = source.slice(source.indexOf('const designInputFilterSchema'), source.indexOf('const designInputListContract'))
  assert.equal((schema.match(/filterType:/g) || []).length, 5)
  assert.match(schema, /calculationStatusLabel[\s\S]*filterType: 'select'[\s\S]*options:/)
  assert.match(source, /const designInputRows = computed\(\(\) => \(selectedOrder\.value\?\.currentDesignInputs \|\| \[\]\)/)
  assert.doesNotMatch(source, /currentDesignInputs\s*=\s*\[/)
})

test('source context reads the original formal continuation service without exposing write actions', () => {
  const loader = source.slice(source.indexOf('async function loadFormalContinuation'), source.indexOf('async function createFormalInstance'))
  assert.match(loader, /pdeApi\.formalEngineeringContinuation\(orderNo\)/)
  assert.doesNotMatch(loader, /selectedOrder\.value\.isSourceTrial\) \{ formalContinuation\.value = \{\}/)
  const sourceBranchStart = source.indexOf('<template v-if="selectedOrder.isSourceTrial">')
  const sourceBranch = source.slice(sourceBranchStart, source.indexOf('<template v-else>', sourceBranchStart))
  assert.match(sourceBranch, /read-only-formal-context/)
  assert.match(sourceBranch, /formalContinuation\.lines/)
  assert.match(sourceBranch, /formalContinuationBlockers/)
  assert.doesNotMatch(sourceBranch, /@click="(?:createFormalInstance|confirmFormalInstanceSource|validateFormalContinuation|executeFormalContinuation)"/)
})

test('order existence, source confirmation, instance and saved calculation are not conflated', () => {
  assert.match(source, /当前正式办理：订单/)
  assert.match(source, /工程来源\$\{sourceConfirmed \? '已确认' : '尚未全部确认'\}/)
  assert.match(source, /ORDER_ENGINEERING_INSTANCE_NOT_CREATED/)
  const blockers = source.slice(source.indexOf('const formalContinuationBlockers'), source.indexOf('const formalExecutionReason'))
  assert.doesNotMatch(blockers, /FORMAL_CALCULATION_NOT_SAVED/)
  assert.match(source, /formalCalculationState\.explanation/)
  assert.match(source, /orderEngineeringInstanceScopeLabel/)
  assert.match(presentationSource, /整单范围 · \$\{instanceCount\}\/\$\{lineCount\}个订单行实例已建立/)
  assert.doesNotMatch(source, /当前企业没有唯一匹配的正式销售订单/)
})

test('whole-order formal table exposes four line validations and server result positions without hardcoded totals', () => {
  const branchStart = source.indexOf('<template v-if="selectedOrder.isSourceTrial">')
  const branch = source.slice(branchStart, source.indexOf('<template v-else>', branchStart))
  assert.match(branch, /完整办理条件校验/)
  assert.match(branch, /预计结果位置/)
  assert.match(branch, /row\.fullValidation\?\.resultPositionCount/)
  assert.match(branch, /formalValidationResultPositionTotal/)
  assert.match(branch, /预计可追溯位置，不代表已保存数值/)
  assert.doesNotMatch(branch, />85<|>51<|>248<|>4</)
  assert.match(continuationService, /"fullValidation": full_validation/)
  assert.match(continuationService, /cls\.validate\(/)
  assert.match(continuationService, /"businessWriteSideEffectCount": validation\["businessWriteSideEffectCount"\]/)
})

test('formal summary distinguishes updating, pass, blockers and read failure while preserving unsaved state', () => {
  assert.match(presentationSource, /operationState === 'running'/)
  assert.match(presentationSource, /operationState === 'failed'/)
  assert.match(presentationSource, /statuses\.every\(status => status === 'passed'\)/)
  assert.match(presentationSource, /status === 'blocked' \|\| status === 'not_ready' \|\| status === 'not_run'/)
  assert.match(source, /conditionPreflightOperation\.state === 'failed'/)
  assert.match(source, /formalContinuationBlockers\.length/)
  assert.match(source, /正式核算尚未保存/)
})

test('formal line navigation has a read-only return to the source summary and stale responses are ignored', () => {
  assert.match(source, /formalSummaryReturnContext/)
  assert.match(source, />查看本行办理详情</)
  assert.match(source, />返回整单汇总/)
  assert.match(source, /returnSourceRecord/)
  assert.match(source, /returnEngineeringVersion/)
  assert.match(source, /formal-line-action/)
  assert.match(source, /data-action="view-formal-order-line"/)
  assert.match(source, /data-action="return-formal-order-summary"/)
  assert.match(source, /async function returnToFormalSummary/)
  assert.match(source, /requestSequence !== draftReadSequence/)
  assert.match(source, /requestSequence !== formalReadSequence/)
  assert.match(source, /requestSequence !== conditionPreflightSequence/)
})

test('design preview, old G1 directory and current formal continuation remain explicitly separated', () => {
  assert.match(source, /当前设计试算／预览（非正式保存）/)
  assert.match(source, /历史／参考：旧G1规则目录/)
  assert.match(source, /公司目录已发布；本实例适用性待旧G1校验/)
  assert.match(source, /当前正式办理前置事实一致/)
})

test('existing result comparison and zero-write boundaries remain visible', () => {
  assert.match(source, /当前核算对照/)
  assert.match(source, /有效数值/)
  assert.match(source, /无独立对照/)
  assert.match(source, /当前缺条件/)
  assert.match(source, /零业务写入/)
  assert.match(source, /来源预览不代替已保存记录/)
})

test('read-only preflight is a GET contract and remains distinct from full validation and save', () => {
  assert.match(apiSource, /preflightOrderEngineeringCalculation\(params\)[\s\S]*method: 'GET'[\s\S]*condition-preflight/)
  assert.match(source, /data-section="read-only-condition-preflight"/)
  assert.match(source, /校验核算条件（只读预检）/)
  assert.match(source, /预检通过不等于正式执行已获准/)
  assert.match(continuationService, /def condition_preflight/)
  assert.match(continuationService, /"businessWriteSideEffectCount": 0/)
  assert.match(continuationService, /"isPrerequisiteBlocker": False/)
})

test('legacy G1 actions cannot be mistaken for current formal continuation actions', () => {
  assert.match(source, /data-section="legacy-g1-validation"/)
  assert.match(source, /旧G1规则验收入口（不替代本订单正式规则包）/)
  assert.match(source, /APPROVED_SOURCE_NET@V1、SOURCE_LINEAR_CONTINUATION@V1/)
  assert.match(source, /执行工程／物料核算（正式办理）<\/button>/)
})

test('room-door applicability follows the accepted adapter and hardware stays supplemental', () => {
  assert.match(calculationAdapter, /def _calculation_input_applicability/)
  assert.match(calculationAdapter, /房门规则由门扇与门套尺寸直接计算见光面积/)
  assert.match(calculationAdapter, /房门规则按门套尺寸和结构分支计算封边皮25\/50净长度/)
  assert.match(calculationAdapter, /'classification': 'supplemental'/)
  assert.match(calculationAdapter, /'fieldApplicability': applicability/)
  assert.match(source, /当前工程量规则不读取，不阻断本次计算/)
})

test('return to product design preserves and consumes the current order context', () => {
  assert.match(source, /const productDesignReturnLocation = computed/)
  assert.match(source, /orderNo: selectedOrder\.value\.orderNo/)
  assert.match(productDesignSource, /useRoute\(\)/)
  assert.match(productDesignSource, /route\.query\.orderNo[\s\S]*orderNo: String\(route\.query\.orderNo\)/)
})
