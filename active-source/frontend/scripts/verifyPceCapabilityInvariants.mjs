import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { writePcePageCapabilityFingerprint } from './generatePcePageCapabilityFingerprint.mjs'
import { resolvePceChangeScopePolicy } from '../src/meta/runtime/pceChangeScopePolicy.js'
import { listPceBatchCapabilityContracts } from '../src/meta/runtime/pceBatchCapabilityRegistry.js'
import {
  BusinessActionRegistry,
  PCE_BUSINESS_ACTION_CONTRACT_VERSION,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const { fingerprint, currentOutput, baselineOutput } = writePcePageCapabilityFingerprint()
const baseline = JSON.parse(fs.readFileSync(baselineOutput, 'utf8'))
const policy = resolvePceChangeScopePolicy()

const failures = []
const reductions = []
const acceptedNormalizations = []
const currentByPage = new Map(fingerprint.pages.map((item) => [item.pageId, item]))
const semanticBatchCapabilityResults = listPceBatchCapabilityContracts().map((contract) => {
  const currentPage = currentByPage.get(contract.pageId)
  const discoveredBatchActionIds = currentPage?.batchBusinessActionIds || []
  const missingActionIds = contract.actionIds.filter((actionId) => !discoveredBatchActionIds.includes(actionId))
  const extraActionIds = discoveredBatchActionIds.filter((actionId) => !contract.actionIds.includes(actionId))
  const result = Boolean(currentPage)
    && currentPage.batchBusinessSectionDeclared
    && missingActionIds.length === 0
    && extraActionIds.length === 0
  return {
    pageId: contract.pageId,
    route: contract.route,
    sectionId: contract.sectionId,
    baselineBatchActionIds: contract.actionIds,
    discoveredBatchActionIds,
    missingActionIds,
    extraActionIds,
    semanticActionCount: discoveredBatchActionIds.length,
    legacyBaselineCount: contract.legacyFingerprint.baselineCount,
    legacyCurrentCount: currentPage?.legacyBatchSourceTokenCount ?? contract.legacyFingerprint.currentCount,
    classification: contract.legacyFingerprint.classification,
    reason: contract.legacyFingerprint.reason,
    result: result ? 'passed' : 'failed',
  }
})
const semanticResultByPage = new Map(semanticBatchCapabilityResults.map((item) => [item.pageId, item]))
for (const item of semanticBatchCapabilityResults) {
  if (item.result === 'failed') {
    failures.push({
      pageId: item.pageId,
      route: item.route,
      metric: 'batchBusinessActionIds',
      missingActionIds: item.missingActionIds,
      extraActionIds: item.extraActionIds,
      message: '语义批量业务动作集合与批准契约不一致。',
    })
  }
}
// V1.14.2.8.4.7.8 deliberately removes duplicate quick-search/toggle markup from
// advanced-filter panels. These source-token counters are not user capabilities;
// the real controls remain protected by the minimums and browser runtime gates.
const intentionalNormalizationMetrics = new Map([
  ['purchase-receive-preview', new Set(['advancedFilterToggleCount', 'rowOperationCount'])],
  ['incoming-inspection', new Set(['advancedFilterToggleCount', 'rowOperationCount'])],
  ['payment-order-draft', new Set(['advancedFilterToggleCount', 'rowOperationCount'])],
  ['payment-execution', new Set(['fuzzySearchCount', 'advancedFilterToggleCount', 'rowOperationCount'])],
  ['payment-record-review', new Set(['fuzzySearchCount', 'advancedFilterToggleCount', 'rowOperationCount'])],
  ['payment-voucher-review', new Set(['advancedFilterToggleCount', 'rowOperationCount'])],
  ['inventory-balances', new Set(['advancedFilterToggleCount', 'rowOperationCount'])],
])
// V1.14.2.8.4.7.43 replaces the legacy browser-Store invoice-prepare page
// with a server persistence read model. The removed source tokens represented
// local generation, duplicated labels, and deprecated supplier-settlement
// pathways rather than retained user capabilities. Runtime list controls,
// canonical naming, server actions, and the real table remain independently
// protected by browser and V43 structural gates.
const serverReadModelNormalizationMetrics = new Map([
  ['invoice-prepare', new Set([
    'tableColumnCount',
    'fuzzySearchCount',
    'advancedFilterToggleCount',
    'fixedLeftColumnCount',
    'batchActionCount',
    'exportCurrentResultCount',
  ])],
  ['account-payable-draft', new Set([
    'tableColumnCount',
    'fuzzySearchCount',
    'advancedFilterFieldCount',
  ])],
  ['payment-application', new Set([
    'batchActionCount',
  ])],
  ['payment-instruction-prepare', new Set([
    'advancedFilterToggleCount',
    'rowOperationCount',
    'batchActionCount',
  ])],
  ['payment-order-prepare', new Set([
    'tableCount',
    'tableColumnCount',
    'advancedFilterToggleCount',
    'advancedFilterFieldCount',
    'operationColumnCount',
    'rowOperationCount',
    'fixedLeftColumnCount',
    'fixedRightColumnCount',
    'batchActionCount',
    'exportCurrentResultCount',
  ])],
  ['payment-order-draft', new Set([
    'tableCount',
    'tableColumnCount',
    'fuzzySearchCount',
    'advancedFilterToggleCount',
    'advancedFilterFieldCount',
    'operationColumnCount',
    'rowOperationCount',
    'fixedLeftColumnCount',
    'fixedRightColumnCount',
    'batchActionCount',
    'exportCurrentResultCount',
  ])],
  ['payment-risk-review', new Set([
    'tableColumnCount',
    'fuzzySearchCount',
    'advancedFilterToggleCount',
    'operationColumnCount',
    'rowOperationCount',
    'fixedLeftColumnCount',
    'fixedRightColumnCount',
    'batchActionCount',
  ])],
])
// V1.14.2.8.4.7.55.1 moves lifecycle, next-step, and batch workflow
// buttons from individual page templates into PceBusinessActionBar. The legacy
// fingerprint counts Vue source tokens, so the page-local count decreases even
// though the registered business actions are preserved. Accept only the exact
// affected metrics and only when both the page connection and registry contract
// can be proved from current source.
const businessActionRegistryNormalizationMetrics = new Map([
  ['payable-prepare', new Set(['rowOperationCount'])],
  ['payable-check', new Set(['rowOperationCount'])],
  ['supplier-settlement', new Set(['rowOperationCount'])],
  ['purchase-reconciliation', new Set(['rowOperationCount'])],
  ['invoice-prepare', new Set(['rowOperationCount'])],
  ['account-payable-draft', new Set(['rowOperationCount'])],
  ['account-payable-confirm', new Set([
    'rowOperationCount',
    'batchActionCount',
  ])],
])
const businessActionModuleByPage = new Map([
  ['payable-prepare', 'payable-prepare'],
  ['payable-check', 'payable-check'],
  ['supplier-settlement', 'supplier-settlement'],
  ['purchase-reconciliation', 'purchase-reconciliation'],
  ['invoice-prepare', 'purchase-invoice-prepare'],
  ['account-payable-draft', 'accounts-payable-draft'],
  ['account-payable-confirm', 'payable-confirmation-prepare'],
])

const sharedEnterpriseListNormalizationPages = new Set(['purchase-request', 'purchase-inquiry'])

function resolveSharedEnterpriseListNormalization(pageId, currentPage) {
  if (!sharedEnterpriseListNormalizationPages.has(pageId) || !currentPage?.sourceFile) return null
  const source = fs.readFileSync(path.join(root, currentPage.sourceFile), 'utf8')
  if (!source.includes('<PceEnterpriseListTable')
    || !source.includes('createPceEnterpriseListContract')
    || !source.includes('usePceEnterpriseListRuntime')) return null
  return {
    component: 'PceEnterpriseListTable',
    contractFactory: 'createPceEnterpriseListContract',
    runtime: 'usePceEnterpriseListRuntime',
    reason: '页面能力已由共享企业列表组件提供，旧基线的页面源码 token 次数不是独立用户能力数量。',
  }
}

function resolveBusinessActionRegistryNormalization(pageId, metric, currentPage) {
  if (!businessActionRegistryNormalizationMetrics.get(pageId)?.has(metric)) {
    return null
  }
  const currentModule = businessActionModuleByPage.get(pageId)
  const contract = BusinessActionRegistry.getContract(currentModule)
  const sourceFile = currentPage?.sourceFile
    ? path.join(root, currentPage.sourceFile)
    : ''
  const source = sourceFile && fs.existsSync(sourceFile)
    ? fs.readFileSync(sourceFile, 'utf8')
    : ''
  const pageConnected = source.includes('PceBusinessActionBar')
    && source.includes(`current-module="${currentModule}"`)
  const registeredActions = contract?.actions || []
  const relevantActions = metric === 'batchActionCount'
    ? registeredActions.filter((item) => item.scope === 'batch')
    : registeredActions
  const evidencePassed = (
    BusinessActionRegistry.contractVersion
      === PCE_BUSINESS_ACTION_CONTRACT_VERSION
    && Boolean(contract)
    && pageConnected
    && relevantActions.length > 0
    && Boolean(contract.nextModule)
    && Boolean(contract.nextRoute)
  )
  if (!evidencePassed) return null
  return {
    currentModule,
    contractVersion: BusinessActionRegistry.contractVersion,
    registryVersion: BusinessActionRegistry.registryVersion,
    actionIds: relevantActions.map((item) => item.actionId),
    nextModule: contract.nextModule,
    nextRoute: contract.nextRoute,
    pageConnected,
  }
}
const minimums = {
  'purchase-receive-preview': {
    fuzzySearchCount: 1,
    advancedFilterToggleCount: 1,
    advancedFilterFieldCount: 3,
    tableCount: 1,
    tableColumnCount: 8,
    operationColumnCount: 1,
    rowOperationCount: 1,
    horizontalScrollOwnerCount: 1,
    exportCurrentResultCount: 1,
  },
  'payable-prepare': {
    fuzzySearchCount: 1,
    advancedFilterToggleCount: 1,
    advancedFilterFieldCount: 3,
    tableCount: 1,
    tableColumnCount: 8,
    operationColumnCount: 1,
    rowOperationCount: 2,
    horizontalScrollOwnerCount: 1,
    exportCurrentResultCount: 1,
  },
  'payment-order-draft': {
    fuzzySearchCount: 1,
    advancedFilterToggleCount: 1,
    advancedFilterFieldCount: 2,
    tableCount: 1,
    tableColumnCount: 12,
    operationColumnCount: 1,
    rowOperationCount: 1,
    horizontalScrollOwnerCount: 1,
    exportCurrentResultCount: 0,
  },
  'payment-risk-review': {
    fuzzySearchCount: 1,
    advancedFilterToggleCount: 1,
    advancedFilterFieldCount: 2,
    tableCount: 1,
    tableColumnCount: 8,
    operationColumnCount: 1,
    // V52 has one source-table view action and one review-table view action.
    // Header actions are owned by the shared page shell and the V52 whitelist;
    // forbidden payment/write actions must not be added to satisfy token counts.
    rowOperationCount: 2,
    horizontalScrollOwnerCount: 1,
    exportCurrentResultCount: 0,
  },
  'payment-instruction-prepare': {
    fuzzySearchCount: 1,
    advancedFilterToggleCount: 1,
    advancedFilterFieldCount: 2,
    tableCount: 1,
    tableColumnCount: 12,
    operationColumnCount: 1,
    rowOperationCount: 1,
    horizontalScrollOwnerCount: 1,
    exportCurrentResultCount: 1,
  },
  'payment-order-prepare': {
    fuzzySearchCount: 2,
    advancedFilterToggleCount: 2,
    advancedFilterFieldCount: 4,
    tableCount: 2,
    tableColumnCount: 20,
    operationColumnCount: 1,
    rowOperationCount: 1,
    fixedLeftColumnCount: 4,
    fixedRightColumnCount: 1,
    horizontalScrollOwnerCount: 1,
    exportCurrentResultCount: 2,
  },
}

for (const beforePage of baseline.pages || []) {
  const currentPage = currentByPage.get(beforePage.pageId)
  if (!currentPage) {
    failures.push({
      pageId: beforePage.pageId,
      metric: 'page',
      before: 'exists',
      current: 'missing',
      message: '名称整改后页面能力指纹中缺少该页面。',
    })
    continue
  }
  for (const metric of policy.invariantMetrics) {
    if ((currentPage[metric] || 0) < (beforePage[metric] || 0)) {
      const reduction = {
        pageId: beforePage.pageId,
        route: beforePage.route,
        metric,
        before: beforePage[metric] || 0,
        current: currentPage[metric] || 0,
      }
      const semanticBatchResult = metric === 'batchActionCount' ? semanticResultByPage.get(beforePage.pageId) : null
      const routeSemanticResult = semanticResultByPage.get(beforePage.pageId)
      const businessActionRegistryEvidence =
        resolveBusinessActionRegistryNormalization(
          beforePage.pageId,
          metric,
          currentPage,
        )
      const sharedEnterpriseEvidence = resolveSharedEnterpriseListNormalization(beforePage.pageId, currentPage)
      if (sharedEnterpriseEvidence) {
        acceptedNormalizations.push({
          ...reduction,
          reason: 'page_local_tokens_replaced_by_shared_enterprise_list_contract',
          classification: ['intentional_standardization', 'shared_component_centralization', 'runtime_capability_preserved'],
          evidence: sharedEnterpriseEvidence,
        })
      } else if (metric === 'advancedFilterFieldCount'
        && routeSemanticResult?.result === 'passed'
        && currentPage.advancedFilterFieldCount >= 3) {
        acceptedNormalizations.push({
          ...reduction,
          reason: 'legacy_shared_source_filter_tokens_replaced_by_route_semantic_schema',
          sectionId: routeSemanticResult.sectionId,
          classification: ['selector_or_section_mismatch', 'semantic_contract_verified'],
          evidence: routeSemanticResult.reason,
        })
      } else if (semanticBatchResult?.result === 'passed') {
        acceptedNormalizations.push({
          ...reduction,
          reason: 'legacy_source_token_count_replaced_by_semantic_batch_action_contract',
          sectionId: semanticBatchResult.sectionId,
          baselineBatchActionIds: semanticBatchResult.baselineBatchActionIds,
          discoveredBatchActionIds: semanticBatchResult.discoveredBatchActionIds,
          classification: semanticBatchResult.classification,
          evidence: semanticBatchResult.reason,
        })
      } else if (businessActionRegistryEvidence) {
        acceptedNormalizations.push({
          ...reduction,
          reason: 'page_action_tokens_replaced_by_business_action_registry',
          classification: [
            'intentional_standardization',
            'business_action_registry_centralization',
            'semantic_action_preserved',
          ],
          evidence: businessActionRegistryEvidence,
        })
      } else if (serverReadModelNormalizationMetrics.get(beforePage.pageId)?.has(metric)) {
        acceptedNormalizations.push({
          ...reduction,
          reason: 'legacy_browser_store_tokens_replaced_by_server_read_model',
          classification: [
            'intentional_standardization',
            'server_read_model_migration',
            'deprecated_local_generation_removed',
          ],
          evidence: beforePage.pageId === 'account-payable-draft'
            ? 'V45 正常页面由服务端列表、详情、来源查询、受控生成和结果恢复 API 驱动；旧前端 Store 及重复源码控件标记已移除，真实表格、搜索、高级筛选、导出、固定列和操作列由浏览器门禁独立保护。'
            : beforePage.pageId === 'payment-application'
              ? 'V47 付款申请准备正常页面只读取服务端列表、详情、来源关系、付款要素校验及 eligibility；旧客户端批量生成标记被移除，真实批量资格复核、表格、筛选、导出和服务端状态由 V47 浏览器门禁及静态守卫独立保护。'
              : beforePage.pageId === 'payment-instruction-prepare'
                ? 'V49 正常付款指令准备页面已从旧 localStorage Store 与客户端动作状态机原子切换为服务端列表、详情、权威 Provider、校验和 eligibility 读模型；旧源码中的重复筛选、行级动作和批量文本不再代表当前用户能力，真实搜索、高级筛选、导出、固定列、横向滚动、查看操作及服务端状态均由浏览器门禁独立保护。'
              : beforePage.pageId === 'payment-order-prepare'
                ? 'V50 正式付款单预备页面已从旧 localStorage 与供应商付款草稿客户端状态机原子切换为服务端付款指令准备来源、独立资金和签署权威 Provider、持久校验与 eligibility 读模型；旧页面的重复表格、重复筛选、行级生成动作和源码关键字不是保留能力。来源表与正式对象表各自具备搜索、高级筛选、导出、固定列和横向滚动，并由 V50 Playwright、按钮白名单和静态守卫独立保护。'
              : beforePage.pageId === 'payment-order-draft'
                ? 'V51 正式付款单草稿页面已从旧 localStorage Store、重复双列表和客户端付款动作状态机原子切换为服务端列表、详情、不可变来源快照、权威证据、最终复核和 eligibility 读模型。旧源码中的重复筛选、生成、作废、付款及批量文本不是保留能力；真实单一正式列表、24项高级筛选、导出、冻结列、横向滚动和查看操作由 V51 Playwright 与静态守卫独立保护。'
                : beforePage.pageId === 'payment-risk-review'
                  ? 'V52 真实付款风险评审页面已从旧 localStorage Store、客户端评审状态机及付款执行入口原子切换为服务端风险评审列表、详情、规则执行、问题明细和 eligibility 读模型。旧源码中的重复表格、筛选、行级动作、付款和批量文本不是保留能力；真实来源表与评审表、搜索、高级筛选、导出、冻结列、横向滚动、只读查看操作及服务端事实由 V52 Playwright、按钮白名单和静态守卫独立保护。'
              : 'V43 正常页面由服务端列表、详情、来源查询和受控生成 API 驱动；旧 Store、直接供应商结算来源和客户端生成入口已移除，真实页面控件由运行时门禁独立保护。',
        })
      } else if (intentionalNormalizationMetrics.get(beforePage.pageId)?.has(metric)) {
        acceptedNormalizations.push({
          ...reduction,
          reason: 'duplicate_advanced_filter_quick_search_or_toggle_removed',
        })
      } else {
        reductions.push(reduction)
      }
    }
  }
}

for (const [pageId, rules] of Object.entries(minimums)) {
  const currentPage = currentByPage.get(pageId)
  if (!currentPage) {
    failures.push({ pageId, metric: 'page', message: '重点页面未进入能力指纹。' })
    continue
  }
  for (const [metric, minValue] of Object.entries(rules)) {
    if ((currentPage[metric] || 0) < minValue) {
      failures.push({
        pageId,
        route: currentPage.route,
        metric,
        minimum: minValue,
        current: currentPage[metric] || 0,
        message: '重点页面基础能力低于名称整改保护下限。',
      })
    }
  }
}

const reductionCounts = {
  fuzzySearchReducedPageCount: reductions.filter((item) => item.metric === 'fuzzySearchCount').length,
  advancedFilterReducedPageCount: reductions.filter((item) => ['advancedFilterToggleCount', 'advancedFilterFieldCount'].includes(item.metric)).length,
  operationColumnReducedPageCount: reductions.filter((item) => item.metric === 'operationColumnCount').length,
  operationButtonReducedPageCount: reductions.filter((item) => item.metric === 'rowOperationCount').length,
  horizontalScrollReducedPageCount: reductions.filter((item) => item.metric === 'horizontalScrollOwnerCount').length,
  fixedColumnReducedPageCount: reductions.filter((item) => ['fixedLeftColumnCount', 'fixedRightColumnCount'].includes(item.metric)).length,
  paginationReducedPageCount: reductions.filter((item) => item.metric === 'paginationCount').length,
  exportCurrentResultReducedPageCount: reductions.filter((item) => item.metric === 'exportCurrentResultCount').length,
}

const report = {
  version: fingerprint.version,
  currentFingerprint: path.relative(root, currentOutput).replaceAll('\\', '/'),
  baselineFingerprint: path.relative(root, baselineOutput).replaceAll('\\', '/'),
  comparedPageCount: baseline.pages?.length || 0,
  currentPageCount: fingerprint.pages.length,
  reductionCounts,
  reductions,
  acceptedNormalizations,
  semanticBatchCapabilityResults,
  failures,
  invariantPassed: reductions.length === 0 && failures.length === 0,
}

const reportPath = path.join(root, 'test-results/pce-capability/capability-invariant-report.json')
fs.mkdirSync(path.dirname(reportPath), { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')

console.log(JSON.stringify(report, null, 2))

if (!report.invariantPassed) {
  console.error(`${fingerprint.version} PCE page capability invariant failed.`)
  process.exit(1)
}

console.log(`${fingerprint.version} PCE page capability invariant passed.`)
