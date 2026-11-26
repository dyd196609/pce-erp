import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import {
  FINANCE_PROCESS_STRUCTURE_VERSION,
  financeProcessPageRegistry,
} from '../src/meta/process/financeProcessPageRegistry.js'
import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'

const VERSION = FINANCE_PROCESS_STRUCTURE_VERSION
const resultRoot = path.resolve('test-results', 'payment-request-prepare-v472')
const read = file => fs.readFileSync(path.resolve(file), 'utf8')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const router = read('src/router/index.js')
const listShell = read('src/meta/components/PceListPageShell.vue')
const operationShell = read('src/meta/components/BusinessOperationPageShell.vue')
const paymentPage = read('src/meta/pages/PaymentApplicationPage.vue')
const configs = listBusinessOperationPageConfigs()
const paymentConfig = configs.find(item => item.pageStepId === 'payment-application')
const paymentRouteBlock = router.match(/path:\s*'finance\/payment-applications'[\s\S]*?\n\s*},/)?.[0] || ''
const checkpointRoot = path.resolve('test-results', 'purchase-payment-golden-flow', 'checkpoints')
const v47Entities = JSON.parse(read(path.join(checkpointRoot, 'payment_request_prepare_validated_ready', 'business-entities.json')))
const v471Manifest = JSON.parse(read(path.join(checkpointRoot, 'payment_request_prepare_page_semantics_consistent_ready', 'manifest.json')))
const persistentDatabase = path.resolve('..', 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.resolve('..', 'backend', 'db.sqlite3')

const runtimeChecks = {
  registryHasEightUniquePages: financeProcessPageRegistry.length === 8
    && new Set(financeProcessPageRegistry.map(item => item.routePath)).size === 8,
  registryConfigsResolvable: financeProcessPageRegistry.every(item => configs.some(config => config.pageStepId === item.pageStepId)),
  registrySequenceShared: new Set(financeProcessPageRegistry.map(item => JSON.stringify(item.structureSequence))).size === 1,
  v47BaselineIntact: v47Entities.counts.formalPaymentRequestPrepares === 8
    && v47Entities.counts.downstreamEligibleSources === 8
    && v47Entities.counts.blockedScenarios === 12
    && v47Entities.counts.nextStageConsumed === 0,
  v471Immutable: v471Manifest.immutable === true && v471Manifest.result === 'passed',
}

const checks = [
  ['finance_process_pages_share_common_structure', runtimeChecks.registryHasEightUniquePages],
  ['finance_process_pages_share_region_sequence', runtimeChecks.registrySequenceShared],
  ['payment_request_prepare_uses_common_page_shell', router.includes("wrapBusinessOperationPage('payment-application'")],
  ['payment_request_prepare_does_not_bypass_common_layout', paymentRouteBlock.includes("wrapBusinessOperationPage('payment-application'") && !paymentRouteBlock.includes('component: () =>')],
  ['common_shell_has_no_hardcoded_business_semantics', !listShell.includes('付款申请') && !operationShell.includes('付款指令准备')],
  ['common_shell_business_semantics_come_from_registry', operationShell.includes('findFinanceProcessPage') && runtimeChecks.registryConfigsResolvable],
  ['single_current_business_version_per_page', listShell.includes('当前版本：') && paymentPage.includes('v-if="!embeddedInCommonShell"')],
  ['framework_version_has_explicit_label', listShell.includes('页面框架版本：')],
  ['operation_framework_version_has_explicit_label', operationShell.includes('业务动作框架版本：')],
  ['unclassified_version_badge_is_absent', !listShell.includes('{{ version }} ·') && operationShell.includes('业务动作框架版本：{{ runtimeAcceptanceVersion }}')],
  ['payment_request_prepare_title_is_unique', paymentPage.includes('v-if="!embeddedInCommonShell"') && listShell.includes('page-business-title')],
  ['payment_request_prepare_navigation_is_unique', paymentPage.includes('v-if="!embeddedInCommonShell" class="business-card process-navigation"')],
  ['payment_request_prepare_toolbar_matches_standard', paymentPage.includes('<StandardListToolbar')],
  ['payment_request_prepare_list_matches_standard', paymentPage.includes('table-id="payment-application-main"')],
  ['payment_request_prepare_horizontal_scroll_matches_standard', paymentPage.includes('business-table-scroll-payment-application-main')],
  ['legacy_payment_request_semantics_are_absent', paymentConfig.nextStepName === '付款申请' && !paymentPage.includes('进入付款指令准备')],
  ['formal_payment_request_prepare_count_remains_eight', runtimeChecks.v47BaselineIntact],
  ['downstream_counts_remain_zero', Object.values(v47Entities.downstreamCounts).every(value => value === 0)],
  ['production_data_remains_unchanged', sha256(persistentDatabase) === 'fadd452c64ffc31eb94a7290b3bc93db2501e48b5bbc98751ed7bff42ad17124'
    && sha256(developmentDatabase) === 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'],
]
const guards = checks.map(([guard, passed]) => ({ guard, passed }))
const failed = guards.filter(item => !item.passed)
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'static-guards.json'), `${JSON.stringify({
  result: failed.length ? 'failed' : 'passed',
  version: VERSION,
  guards,
  runtimeChecks,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
}, null, 2)}\n`, 'utf8')
if (failed.length) throw new Error(`V47.2 guards failed: ${failed.map(item => item.guard).join(', ')}`)
console.log(JSON.stringify({ result: 'passed', version: VERSION, guardCount: guards.length }, null, 2))
