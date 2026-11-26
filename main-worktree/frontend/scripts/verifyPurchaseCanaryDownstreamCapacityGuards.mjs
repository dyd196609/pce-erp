import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const models = read('../backend/purchase_canary/models.py')
const command = read('../backend/purchase_canary/management/commands/ensure_purchase_canary_formal_domain.py')
const views = read('../backend/purchase_accounts_payable_draft/views.py')
const tests = read('../backend/purchase_canary/tests/test_purchase_canary.py')
const page = read('src/meta/pages/AccountPayableDraftPage.vue')
const browserTest = read('tests/ui-baseline/purchaseCanaryDownstreamCapacity.spec.js')

const named = [
  'downstream_canary_capacity_minimum_is_met',
  'pass_through_lineage_count_is_at_least_eight',
  'blocked_scenarios_not_counted_as_pass_through',
  'existing_target_not_counted_as_new_lineage',
  'idempotent_retry_not_counted_as_new_lineage',
  'each_pass_through_has_unique_source_chain',
  'each_pass_through_has_formal_domain_objects',
  'normal_ap_draft_page_shows_all_pass_through_objects',
  'scenario_overview_shows_blocked_and_success_cases',
  'blocked_scenario_does_not_create_ap_draft',
  'next_module_sources_are_reserved_not_consumed',
  'persistent_canary_numbers_are_stable',
  'regression_clone_does_not_modify_demo_database',
  'development_database_remains_unchanged',
  'confirmation_prepare_is_not_created',
  'module_navigation_unchanged',
]
const guards = Object.fromEntries(named.map(name => [name, tests.includes(`test_${name}`)]))
Object.assign(guards, {
  lineage_registry_is_persistent_server_model:
    models.includes('class PurchaseCanaryLineage') && command.includes('PurchaseCanaryLineage'),
  formal_generation_uses_domain_services:
    command.includes('generate_purchase_invoice_prepare') && command.includes('generate_purchase_accounts_payable_draft'),
  list_api_is_registry_driven:
    views.includes('lineage_by_id') && views.includes('"scenarioOverview"') && views.includes('"capacity"'),
  page_has_capacity_overview_and_formal_list:
    page.includes('purchase-canary-capacity') && page.includes('purchase-canary-scenario-overview')
      && page.includes('purchase-ap-draft-formal-list'),
  playwright_checks_database_api_and_page:
    browserTest.includes('downstreamEligibleLineageCount') && browserTest.includes('scenarioClass=blocked')
      && browserTest.includes('formalDraftNos'),
})
const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: 'V1.14.2.8.4.7.45.3',
  guardCount: Object.keys(guards).length,
  guardLayers: ['django_database', 'django_api', 'playwright_page', 'static_contract'],
  guards,
  failures,
}
const reportPath = path.join(root, 'test-results', 'purchase-canary-downstream-capacity', 'static-guards.json')
fs.mkdirSync(path.dirname(reportPath), { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ ...report, reportPath }, null, 2))
if (failures.length) process.exit(1)
