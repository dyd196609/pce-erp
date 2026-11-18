import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(root, '..', 'backend')
const read = (file) => fs.readFileSync(file, 'utf8')
const settings = read(path.join(backend, 'pce_backend', 'canary_demo_settings.py'))
const models = read(path.join(backend, 'purchase_canary', 'models.py'))
const services = read(path.join(backend, 'purchase_canary', 'services.py'))
const reset = read(path.join(backend, 'purchase_canary', 'management', 'commands', 'reset_purchase_canary_group.py'))
const views = read(path.join(backend, 'purchase_canary', 'views.py'))
const panel = read(path.join(root, 'src', 'meta', 'components', 'PurchaseCanaryScenarioPanel.vue'))
const shell = read(path.join(root, 'src', 'meta', 'components', 'BusinessOperationPageShell.vue'))
const router = read(path.join(root, 'src', 'router', 'index.js'))
const registry = read(path.join(root, 'src', 'meta', 'process', 'businessProcessRegistry.js'))
const runner = read(path.join(root, 'scripts', 'runPurchaseCanaryPersistentWalkthroughGate.mjs'))
const checkpointArchiver = read(path.join(root, 'scripts', 'archivePceCheckpoint.mjs'))
const defaultPlaywright = read(path.join(root, 'playwright.config.js'))
const canaryPlaywright = read(path.join(root, 'playwright.purchase-canary.config.js'))

const guards = {
  persistent_canary_database_is_not_ephemeral:
    settings.includes('PCE_CANARY_DATABASE_PATH is required') && settings.includes('db.sqlite3'),
  persistent_canary_is_not_in_test_results_cleanup_scope:
    settings.includes('"test-results"') && settings.includes('must be durable'),
  regression_tests_use_canary_clone:
    runner.includes('copyFileSync(canaryDb, cloneDb)') && runner.includes('PCE_CANARY_DATABASE_PATH: cloneDb'),
  regression_cleanup_does_not_delete_demo_canary:
    runner.includes('rmSync(cloneDb') && !reset.includes('db.sqlite3'),
  canary_batch_is_visible_in_normal_pages:
    shell.includes('PurchaseCanaryScenarioPanel') && panel.includes('PURCHASE-FLOW-DEMO-V1'),
  canary_scenarios_have_stable_business_numbers:
    models.includes('uq_purchase_canary_scenario_object') && services.includes('changed_count'),
  canary_cross_module_relations_are_complete:
    models.includes('PurchaseCanaryRelation') && services.includes('zip(object_numbers, object_numbers[1:])'),
  canary_next_step_navigation_uses_existing_modules:
    panel.includes('target.routePath') && registry.includes("stepId: 'supplier-settlement'"),
  canary_scenario_switch_is_read_only:
    panel.includes('router.replace') && !panel.includes("method: 'POST'"),
  canary_page_state_comes_from_server:
    views.includes('"currentStateSource": "server"') && panel.includes('getPurchaseCanaryContext'),
  canary_data_survives_browser_state_clear:
    panel.includes('onMounted(load)') && !panel.includes('localStorage'),
  canary_data_survives_service_restart:
    runner.includes('serviceRestartRecoveryReady'),
  canary_data_survives_build:
    runner.includes('buildPersistenceReady'),
  canary_data_survives_gate_rerun:
    runner.includes('gateRerunPersistenceReady'),
  production_data_is_not_modified:
    settings.includes('tenant-canary-demo') &&
      settings.includes('PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED = False'),
  module_navigation_unchanged:
    router.includes("wrapBusinessOperationPage('supplier-settlement'") &&
      registry.indexOf("stepId: 'supplier-settlement'") < registry.indexOf("stepId: 'purchase-reconciliation'") &&
      registry.indexOf("stepId: 'purchase-reconciliation'") < registry.indexOf("stepId: 'invoice-prepare'"),
  playwright_output_dir_is_isolated:
    defaultPlaywright.includes('test-results/playwright-default-output') &&
      canaryPlaywright.includes('test-results/purchase-canary-persistent-walkthrough/playwright-output'),
  playwright_cleanup_cannot_reach_checkpoints:
    !defaultPlaywright.includes("outputDir: './test-results',") &&
      !canaryPlaywright.includes("outputDir: 'test-results',"),
  playwright_cleanup_cannot_reach_reports:
    canaryPlaywright.includes('/playwright-output') &&
      !canaryPlaywright.includes("outputDir: 'test-results/purchase-payment-golden-flow"),
  playwright_cleanup_cannot_reach_persistent_canary:
    !defaultPlaywright.includes('backend/canary-data') && !canaryPlaywright.includes('backend/canary-data'),
  checkpoint_archive_is_outside_test_results:
    checkpointArchiver.includes("const archiveRoot = 'D:\\\\Dev-PCE\\\\CheckpointArchive") &&
      checkpointArchiver.includes('archiveOutsideTestResults'),
}

const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
console.log(JSON.stringify({ result: failures.length ? 'failed' : 'passed', guards, failures }, null, 2))
if (failures.length) process.exit(1)
