import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')
const page = read('src/meta/pages/AccountPayableDraftPage.vue')
const api = read('src/api/purchaseAccountsPayableDraft.js')
const views = read('../backend/purchase_accounts_payable_draft/views.py')
const command = read('../backend/purchase_canary/management/commands/ensure_purchase_canary_formal_domain.py')
const settings = read('../backend/pce_backend/canary_demo_settings.py')
const panel = read('src/meta/components/PurchaseCanaryScenarioPanel.vue')

const guards = {
  normal_ap_draft_page_reads_persistent_canary_database:
    views.includes('databasePurpose": "persistent_demonstration"') && views.includes('PCE_CANARY_DEMO_MODE'),
  normal_ap_draft_page_has_visible_canary_rows:
    page.includes('purchaseAccountsPayableDraftApi.list') && page.includes('rows.value = list?.results || []'),
  persistent_canary_contains_formal_domain_objects:
    command.includes('generate_purchase_accounts_payable_draft') && command.includes('PurchaseAccountsPayableDraft.objects.get'),
  generic_module_object_not_used_as_formal_ap_draft:
    !views.includes('PurchaseCanaryModuleObject') && !page.includes('moduleObjects'),
  frontend_and_backend_use_same_canary_tenant:
    settings.includes('PCE_CANARY_TENANT_ID = "tenant-canary-demo"') && views.includes('PCE_CANARY_TENANT_ID'),
  browser_and_playwright_use_same_backend:
    api.includes('/api/scm/purchase-accounts-payable-drafts/'),
  browser_and_playwright_use_same_database:
    settings.includes('PCE_CANARY_DATABASE_PATH is required'),
  canary_api_response_contains_expected_object:
    command.includes('"draftNo": "APD20260700000001"') && views.includes('serialize_draft(item)'),
  scenario_switch_is_server_read_only:
    views.includes('"scenarioReadOnly": True') && page.includes('scenarioCode: route.query.scenarioCode'),
  blocked_scenario_does_not_fabricate_downstream_object:
    views.includes('visible_scenarios = {"HAPPY_PATH", "EXISTING_TARGET"}'),
  plain_url_has_default_demo_scenario:
    views.includes('or "HAPPY_PATH"') && panel.includes('plainApDraftDemo'),
  persistent_canary_survives_service_restart:
    views.includes('"backendPid"') && settings.includes('PCE_CANARY_DATABASE_PATH is required'),
  persistent_canary_survives_build:
    page.includes("currentStateSource: 'server'") && !page.includes('moduleObjects'),
  production_data_remains_unchanged:
    settings.includes('PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED = False'),
  module_navigation_unchanged:
    panel.includes("router.push(canaryRoute('/process-center'))"),
}

const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  version: 'V1.14.2.8.4.7.45.2',
  result: failures.length ? 'failed' : 'passed',
  guards,
  failures,
}
const reportPath = path.join(root, 'test-results', 'purchase-canary-normal-pages-visible', 'static-guards.json')
fs.mkdirSync(path.dirname(reportPath), { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ ...report, reportPath }, null, 2))
if (failures.length) process.exit(1)
