import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55'
const frontendRoot = process.cwd()
const repositoryRoot = path.resolve(frontendRoot, '..')
const projectRoot = path.resolve(repositoryRoot, '..')
const backendRoot = path.join(repositoryRoot, 'backend')
const resultRoot = path.join(
  frontendRoot,
  'test-results',
  'payment-chain-state-machine-v55',
)

const read = file => fs.readFileSync(file, 'utf8')
const relative = file => path
  .relative(repositoryRoot, file)
  .replaceAll('\\', '/')
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const lineEvidence = (file, expression, classification, riskLevel) => {
  const rows = read(file).split(/\r?\n/)
  return rows.flatMap((line, index) => (
    expression.test(line)
      ? [{
          file: relative(file),
          line: index + 1,
          excerpt: line.trim(),
          classification,
          riskLevel,
        }]
      : []
  ))
}

const modules = [
  {
    objectType: 'payment_request_prepare',
    canonicalName: '付款申请准备',
    model: 'PaymentRequestPrepare',
    page: 'PaymentApplicationPage.vue',
    apiClient: 'paymentRequestPrepare.js',
    transitions: [['draft', 'prepared']],
  },
  {
    objectType: 'payment_request',
    canonicalName: '付款申请',
    model: 'PaymentRequest',
    page: 'PaymentRequestPage.vue',
    apiClient: 'paymentRequest.js',
    transitions: [
      ['prepared', 'submitted'],
      ['submitted', 'approved'],
      ['submitted', 'rejected'],
    ],
  },
  {
    objectType: 'payment_instruction_prepare',
    canonicalName: '付款指令准备',
    model: 'PaymentInstructionPrepare',
    page: 'PaymentInstructionPreparePage.vue',
    apiClient: 'paymentInstructionPrepare.js',
    transitions: [['prepared', 'validated']],
  },
  {
    objectType: 'payment_order_prepare',
    canonicalName: '正式付款单预备',
    model: 'PaymentOrderPrepare',
    page: 'PaymentOrderPreparePage.vue',
    apiClient: 'paymentOrderPrepare.js',
    transitions: [['prepared', 'submitted']],
  },
  {
    objectType: 'payment_order_draft',
    canonicalName: '正式付款单草稿',
    model: 'PaymentOrderDraft',
    page: 'PaymentOrderDraftPage.vue',
    apiClient: 'paymentOrderDraft.js',
    transitions: [['created', 'reviewed']],
  },
]

const checks = []
const check = (guard, passed, evidence) => checks.push({
  guard,
  passed: passed === true,
  evidence,
})

const commonFacts = read(path.join(
  backendRoot,
  'workflow_runtime',
  'facts.py',
))
const commonModels = read(path.join(
  backendRoot,
  'workflow_runtime',
  'state_models.py',
))
const commonTransitions = read(path.join(
  backendRoot,
  'workflow_runtime',
  'state_transitions.py',
))
const frontendFacts = read(path.join(
  frontendRoot,
  'src',
  'meta',
  'runtime',
  'pceStateMachineFactContract.js',
))

check(
  'status_transition_count_matches_history',
  commonFacts.includes('"statusTransitionCount": len(persisted_history)')
    && commonFacts.includes(
      'statusTransitionCount must equal statusTransitionHistory length',
    )
    && frontendFacts.includes(
      'facts.statusTransitionCount\n    !== facts.statusTransitionHistory.length',
    ),
  [
    'backend/workflow_runtime/facts.py',
    'frontend/src/meta/runtime/pceStateMachineFactContract.js',
  ],
)
check(
  'business_status_initialization_uses_common_service',
  commonTransitions.includes('create_business_object_with_initial_state')
    && commonTransitions.includes('connection.in_atomic_block')
    && commonModels.includes(
      'initial status must use state initialization service',
    ),
  [
    'backend/workflow_runtime/state_transitions.py',
    'backend/workflow_runtime/state_models.py',
  ],
)
check(
  'direct_status_write_is_blocked',
  commonModels.includes('if "status" in kwargs:')
    && commonModels.includes('if "status" in fields:')
    && commonModels.includes('_business_state_transition_authorized'),
  ['backend/workflow_runtime/state_models.py'],
)
check(
  'transition_audit_reference_is_authoritative',
  commonFacts.includes(
    'audits[audit_id].target_type == audit_target_type',
  )
    && commonFacts.includes(
      'audits[audit_id].action_code == history[index]["actionCode"]',
    )
    && commonFacts.includes(
      'audits[audit_id].result == "committed"',
    ),
  ['backend/workflow_runtime/facts.py'],
)

for (const module of modules) {
  const moduleRoot = path.join(backendRoot, module.objectType)
  const model = read(path.join(moduleRoot, 'models.py'))
  const service = read(path.join(moduleRoot, 'services.py'))
  const page = read(path.join(
    frontendRoot,
    'src',
    'meta',
    'pages',
    module.page,
  ))
  const apiClient = read(path.join(
    frontendRoot,
    'src',
    'api',
    module.apiClient,
  ))
  check(
    `${module.objectType}_uses_managed_state_model`,
    model.includes(
      `class ${module.model}(BusinessStateManagedModel):`,
    ),
    [relative(path.join(moduleRoot, 'models.py'))],
  )
  check(
    `${module.objectType}_uses_common_transition_service`,
    service.includes('create_business_object_with_initial_state(')
      && service.includes('transition_business_object(')
      && service.includes('business_state_transition_facts('),
    [relative(path.join(moduleRoot, 'services.py'))],
  )
  check(
    `${module.objectType}_declares_required_transition_chain`,
    module.transitions.every(([source, target]) => (
      service.includes(`("${source}", "${target}")`)
    )),
    module.transitions.map(pair => pair.join(' -> ')),
  )
  const directTargetAssignment = new RegExp(
    `\\b(?:obj|locked|current|target)\\.status\\s*=(?!=)`,
  )
  const directTargetUpdate = new RegExp(
    `${module.model}\\.objects[\\s\\S]{0,300}?\\.update\\([\\s\\S]{0,120}?status\\s*=`,
  )
  check(
    `${module.objectType}_has_no_direct_business_status_write`,
    !directTargetAssignment.test(service)
      && !directTargetUpdate.test(service)
      && !/bulk_update\([\s\S]{0,180}?["']status["']/.test(service),
    [relative(path.join(moduleRoot, 'services.py'))],
  )
  check(
    `${module.objectType}_five_surface_contract`,
    page.includes('stateMachineFactsFromServer(')
      && page.includes('statusTransitionCount')
      && page.includes('stateMachineConsistent')
      && (
        page.includes('strictFacts')
        || page.includes('strictServerFacts')
      ),
    [relative(path.join(
      frontendRoot,
      'src',
      'meta',
      'pages',
      module.page,
    ))],
  )
  check(
    `${module.objectType}_client_does_not_submit_status`,
    !/\bstatus\s*:/.test(apiClient),
    [relative(path.join(
      frontendRoot,
      'src',
      'api',
      module.apiClient,
    ))],
  )
}

const frontendSources = [
  path.join(frontendRoot, 'src', 'meta', 'pages'),
  path.join(frontendRoot, 'src', 'meta', 'runtime'),
].flatMap(directory => fs.readdirSync(directory)
  .filter(name => /\.(vue|js)$/.test(name))
  .map(name => path.join(directory, name)))
const clientCountFallbacks = frontendSources.flatMap(file => (
  lineEvidence(
    file,
    /statusTransitionCount\s*:\s*(?:0|Number\(|[^,]*\.length)/,
    'client-calculated-transition-count',
    'high',
  )
))
check(
  'status_transition_count_has_no_client_default_or_calculation',
  clientCountFallbacks.length === 0,
  clientCountFallbacks,
)

const standards = [
  path.join(projectRoot, 'AGENTS.md'),
  path.join(
    repositoryRoot,
    'docs',
    'standards',
    'PCE-STATE-MACHINE-CONTRACT-V1.1.md',
  ),
  path.join(
    repositoryRoot,
    'docs',
    'standards',
    'PCE-WEB-ACCEPTANCE-V1.1.md',
  ),
]
check(
  'state_machine_long_term_rules_are_synchronized',
  standards.every(file => (
    read(file).includes('所有业务状态必须经过统一状态转换服务。')
    && read(file).includes('五表面事实必须一致')
  )),
  standards.map(relative),
)
check(
  'historical_transition_backfill_uses_committed_audits',
  read(path.join(
    backendRoot,
    'workflow_runtime',
    'migrations',
    '0004_payment_chain_transition_backfill.py',
  )).includes('BusinessActionAuditRecord')
    && read(path.join(
      backendRoot,
      'workflow_runtime',
      'migrations',
      '0004_payment_chain_transition_backfill.py',
    )).includes('result="committed"'),
  ['backend/workflow_runtime/migrations/0004_payment_chain_transition_backfill.py'],
)

const legacyDefinitions = [
  {
    module: 'payable_confirmation_prepare',
    canonicalName: '应付确认准备',
    riskLevel: 'high',
    reason: '业务对象仍由模块服务直接初始化 prepared，尚无统一转换事实。',
    files: ['services.py'],
    expression: /PayableConfirmationPrepare\.objects\.create\(/,
  },
  {
    module: 'purchase_accounts_payable_draft',
    canonicalName: '采购应付账款草稿',
    riskLevel: 'high',
    reason: '当前版本尚未接入 BusinessStateManagedModel 和统一转换事实。',
    files: ['models.py', 'services.py'],
    expression: /class PurchaseAccountsPayableDraft|PurchaseAccountsPayableDraft\(/,
  },
  {
    module: 'purchase_invoice_prepare',
    canonicalName: '采购发票准备',
    riskLevel: 'high',
    reason: '遗留 V44 服务仍直接写 prepare.status。',
    files: ['v44_services.py'],
    expression: /prepare\.status\s*=(?!=)/,
  },
  {
    module: 'reconciliation',
    canonicalName: '采购对账',
    riskLevel: 'high',
    reason: '核对事务仍以 QuerySet.update(status=...) 修改业务状态。',
    files: ['checking.py'],
    expression: /\.update\(|status=status/,
  },
  {
    module: 'payment_risk_review',
    canonicalName: '真实付款风险评审',
    riskLevel: 'high',
    reason: '评审动作仍直接写 current.status。',
    files: ['services.py'],
    expression: /current\.status\s*=(?!=)/,
  },
  {
    module: 'procurement',
    canonicalName: '采购订单',
    riskLevel: 'high',
    reason: '采购订单视图仍直接赋值状态并存在 QuerySet.update(status=...)。',
    files: ['views.py'],
    expression: /order\.status\s*=(?!=)|\.update\(status=/,
  },
]

const legacyModules = legacyDefinitions.map(definition => {
  const evidence = definition.files.flatMap(name => lineEvidence(
    path.join(backendRoot, definition.module, name),
    definition.expression,
    'legacy-direct-business-state-write',
    definition.riskLevel,
  ))
  return {
    module: definition.module,
    canonicalName: definition.canonicalName,
    migrationStatus: 'pending',
    riskLevel: definition.riskLevel,
    reason: definition.reason,
    evidence,
  }
})

const workflowInternalFindings = [
  ...lineEvidence(
    path.join(backendRoot, 'payment_request', 'services.py'),
    /\btask\.status\s*=(?!=)|\bworkflow\.status\s*=(?!=)|\.update\(status="closed"/,
    'shared-workflow-runtime-internal',
    'medium',
  ),
  ...lineEvidence(
    path.join(backendRoot, 'formal_payment_order', 'services.py'),
    /\btask\.status\s*=(?!=)|\bworkflow\.status\s*=(?!=)/,
    'shared-workflow-runtime-internal',
    'medium',
  ),
]

const failures = checks.filter(row => !row.passed)
const staticReport = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  canonicalName: 'PCE付款链状态机统一治理',
  guardCount: checks.length,
  passedGuardCount: checks.length - failures.length,
  failedGuardCount: failures.length,
  failures: failures.map(row => row.guard),
  checks,
  clientTransitionCountFallbackCount: clientCountFallbacks.length,
  managedPaymentChainModuleCount: modules.length,
  fiveSurfaceContractModuleCount: modules.length,
  productionUserDataWritten: false,
}
const riskReport = {
  result: 'passed',
  version: VERSION,
  reportType: 'state-machine-legacy-risk',
  scanScope: ['backend/finance', 'backend/purchase', 'backend/payment'],
  compliantModules: [
    ...modules.map(module => ({
      module: module.objectType,
      canonicalName: module.canonicalName,
      status: 'governed',
      riskLevel: 'low',
    })),
    {
      module: 'formal_payment_order',
      canonicalName: '正式付款单',
      status: 'governed-before-v55',
      riskLevel: 'low',
    },
  ],
  legacyModules,
  workflowInternalFindings,
  compliantModuleCount: modules.length + 1,
  legacyModuleCount: legacyModules.length,
  highRiskLegacyModuleCount: legacyModules.filter(
    row => row.riskLevel === 'high',
  ).length,
  workflowInternalFindingCount: workflowInternalFindings.length,
  allSystemModulesMigrated: false,
  assertion: '未迁移模块未标记为已符合统一状态机契约。',
}

writeJson(path.join(resultRoot, 'static-guard-report.json'), staticReport)
writeJson(path.join(resultRoot, 'legacy-risk-report.json'), riskReport)
console.log(JSON.stringify({
  result: staticReport.result,
  version: VERSION,
  guardCount: staticReport.guardCount,
  failedGuardCount: staticReport.failedGuardCount,
  compliantModuleCount: riskReport.compliantModuleCount,
  legacyModuleCount: riskReport.legacyModuleCount,
  allSystemModulesMigrated: false,
}, null, 2))
if (failures.length) process.exitCode = 1
