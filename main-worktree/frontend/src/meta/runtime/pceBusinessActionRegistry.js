export const PCE_BUSINESS_ACTION_CONTRACT_VERSION =
  'PCE-BUSINESS-ACTION-CONTRACT-V1.0'
export const PCE_BUSINESS_ACTION_REGISTRY_VERSION = 'V1.14.2.8.4.8.3.1.1'
export const PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION =
  'PCE-BUSINESS-ACTION-PERMISSION-V1.0'

const SINGLE_ACTION_ROLES = Object.freeze([
  'pce_business_operator',
  'pce_business_batch_operator',
  'pce_business_admin',
])
const BATCH_ACTION_ROLES = Object.freeze([
  'pce_business_batch_operator',
  'pce_business_admin',
])
const BANK_TASK_ACTION_ROLES = Object.freeze([
  'pce_business_operator',
  'pce_bank_operator',
  'pce_business_admin',
])

const forbiddenExecutionActions = Object.freeze([
  'send-bank',
  'generate-bank-message',
  'create-bank-message',
  'debit-funds',
  'create-bank-transaction',
  'execute-payment',
  'create-payment-voucher',
  'write-general-ledger',
])

const contracts = [
  {currentModule:'routing-management',canonicalName:'订单路线引用及执行安排',route:'/pde/routings',nextModule:'',nextRoute:'',actions:[
    action('select-order-standard-routing','选择并固定标准路线版本',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('save-order-execution-draft','保存订单执行安排',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('confirm-order-execution','确认订单执行安排',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('revise-order-execution','办理安排自身修订',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
  ]},
  {currentModule:'routing-version-management',canonicalName:'订单路线引用及执行安排',route:'/pde/routing-versions',nextModule:'',nextRoute:'',actions:[
    action('select-order-standard-routing','选择并固定标准路线版本',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('save-order-execution-draft','保存订单执行安排',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('confirm-order-execution','确认订单执行安排',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('revise-order-execution','办理安排自身修订',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
  ]},
  {
    currentModule: 'bom-management', canonicalName: 'BOM管理', route: '/pde/product-boms',
    nextModule: 'bom-version-management', nextCanonicalName: 'BOM版本管理', nextRoute: '/pde/bom-versions',
    actions: [
      action('generate-test-business-bom', '生成测试BOM草稿', {allowedStatuses:['ready'], requiresEligibility:true, formalPermission:'production.master_data.bom.maintain'}),
      action('derive-test-business-bom', '复制为测试草稿版本', {allowedStatuses:['draft'], formalPermission:'production.master_data.bom.maintain'}),
    ],
  },
  {
    currentModule: 'foundation-routing-maintenance',
    canonicalName: '标准工艺路线维护',
    route: '/foundation/master-data/routings',
    nextModule: 'routing-version-management-closed',
    nextCanonicalName: '工艺路线版本受控维护边界',
    nextRoute: '',
    actions: [
      action('create-routing-successor-version', '创建后续路线版本', {
        allowedStatuses: ['reviewed', 'released', 'obsolete'],
        formalPermission: 'production.master_data.routing.maintain',
      }),
      action('maintain-routing-step-applicability', '维护工序适用性', {
        allowedStatuses: ['draft'],
        formalPermission: 'production.master_data.routing.maintain',
      }),
      action('confirm-routing-manual-applicability', '确认本次订单工程条件', {
        allowedStatuses: ['draft'],
        formalPermission: 'production.master_data.routing.maintain',
      }),
      action('submit-routing-version-review', '提交工艺路线版本正式评审', {
        allowedStatuses: ['draft'],
        formalPermission: 'pde.routing_version.review',
      }),
      action('release-routing-version', '正式发布工艺路线版本', {
        allowedStatuses: ['reviewed'],
        formalPermission: 'pde.routing_version.release',
      }),
    ],
  },
  {
    currentModule: 'engineering-calculation',
    canonicalName: '工程核算 / 物料核算',
    route: '/pde/engineering-calculations',
    nextModule: 'bom-management',
    nextCanonicalName: 'BOM管理',
    nextRoute: '/pde/product-boms',
    actions: [
      action('batch-trial-engineering-sources', '批量核对当前来源范围', {
        actionType: 'readonly-command', allowedStatuses: ['selected', 'completed'],
      }),
      action('validate-order-engineering-calculation', '校验核算条件', {
        actionType: 'readonly-command', allowedStatuses: ['selected', 'blocked', 'ready'],
      }),
      action('execute-order-engineering-calculation', '执行工程 / 物料核算', {
        allowedStatuses: ['ready'], requiresEligibility: true,
      }),
      action('preview-order-bom-draft', '预览订单BOM草稿', {
        actionType: 'readonly-command', allowedStatuses: ['completed'],
      }),
      action('generate-order-bom-draft', '生成订单BOM草稿', {
        allowedStatuses: ['previewed', 'draft_generated'], requiresEligibility: true,
      }),
      routeAction('view-order-bom', '进入BOM管理查看', ['draft_generated']),
    ],
  },
  {
    currentModule: 'payable-prepare',
    canonicalName: '采购应付预备',
    route: '/finance/payable-prepares',
    nextModule: 'payable-check',
    nextCanonicalName: '采购应付核对',
    nextRoute: '/finance/payable-checks',
    actions: [
      action('generate-payable-prepare', '生成采购应付预备', {
        permission: 'business_action:execute',
        allowedStatuses: ['not_created', 'source_ready'],
      }),
      action(
        'generate-payable-check-from-prepare',
        '生成采购应付核对',
        {
          permission: 'business_action:execute',
          allowedStatuses: ['prepared', 'payable_prepared'],
        },
      ),
      batchAction(
        'batch-generate-payable-prepare',
        '批量生成采购应付预备',
        ['not_created', 'source_ready'],
        { executeActionId: 'generate-payable-prepare' },
      ),
      routeAction('enter-payable-check', '进入采购应付核对', [
        'prepared',
        'payable_prepared',
        'checked',
      ]),
      batchRouteAction(
        'batch-enter-payable-check',
        '批量进入采购应付核对',
        ['prepared', 'payable_prepared', 'checked'],
      ),
    ],
  },
  {
    currentModule: 'payable-check',
    canonicalName: '采购应付核对',
    route: '/finance/payable-checks',
    nextModule: 'supplier-settlement',
    nextCanonicalName: '供应商结算',
    nextRoute: '/scm/supplier-settlements',
    actions: [
      action('generate-payable-check', '生成采购应付核对', {
        permission: 'business_action:execute',
        allowedStatuses: ['not_created', 'source_ready'],
      }),
      action('complete-payable-check', '完成采购应付核对', {
        permission: 'business_action:execute',
        allowedStatuses: ['draft', 'checking'],
      }),
      routeAction('enter-supplier-settlement', '进入供应商结算', [
        'checked',
        'matched',
        'invoicePrepareReady',
        'invoicePrepared',
      ]),
      batchAction(
        'batch-complete-payable-check',
        '批量完成应付核对',
        ['draft', 'checking'],
        { executeActionId: 'complete-payable-check' },
      ),
      batchRouteAction(
        'batch-enter-supplier-settlement',
        '批量进入供应商结算',
        ['checked', 'matched', 'invoicePrepareReady', 'invoicePrepared'],
      ),
    ],
  },
  {
    currentModule: 'supplier-settlement',
    canonicalName: '供应商结算',
    route: '/scm/supplier-settlements',
    nextModule: 'purchase-reconciliation',
    nextCanonicalName: '采购对账',
    nextRoute: '/scm/purchase-reconciliations',
    actions: [
      action('generate-supplier-settlement', '生成供应商结算单', {
        permission: 'business_action:execute',
        allowedStatuses: ['checked', 'source_ready', 'not_created'],
      }),
      batchAction(
        'batch-generate-supplier-settlement',
        '批量生成供应商结算单',
        ['checked', 'source_ready', 'not_created'],
        { executeActionId: 'generate-supplier-settlement' },
      ),
      routeAction('enter-purchase-reconciliation', '进入采购对账', [
        'prepared',
        'payable_prepared',
        'settlement_ready',
        'reconciling',
        'reconciliation_ready',
        'matched',
      ]),
      batchRouteAction(
        'batch-enter-purchase-reconciliation',
        '批量进入采购对账',
        [
          'prepared',
          'payable_prepared',
          'settlement_ready',
          'reconciling',
          'reconciliation_ready',
          'matched',
        ],
      ),
    ],
  },
  {
    currentModule: 'purchase-reconciliation',
    canonicalName: '采购对账',
    route: '/scm/purchase-reconciliations',
    nextModule: 'purchase-invoice-prepare',
    nextCanonicalName: '采购发票准备',
    nextRoute: '/finance/purchase-invoice-prepares',
    actions: [
      action('generate-purchase-invoice-prepare', '生成采购发票准备', {
        permission: 'business_action:execute',
        allowedStatuses: ['matched'],
        requiresEligibility: true,
      }),
      action('complete-purchase-reconciliation', '完成采购对账', {
        permission: 'business_action:execute',
        allowedStatuses: ['draft'],
      }),
      batchAction(
        'batch-complete-purchase-reconciliation',
        '批量完成核对',
        ['draft'],
        { executeActionId: 'complete-purchase-reconciliation' },
      ),
      routeAction('enter-purchase-invoice-prepare', '进入采购发票准备', [
        'matched',
      ], { requiresEligibility: true }),
      batchRouteAction(
        'batch-enter-purchase-invoice-prepare',
        '批量进入采购发票准备',
        ['matched'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'purchase-invoice-prepare',
    canonicalName: '采购发票准备',
    route: '/finance/purchase-invoice-prepares',
    nextModule: 'accounts-payable-draft',
    nextCanonicalName: '采购应付账款草稿',
    nextRoute: '/finance/ap-drafts',
    actions: [
      action(
        'save-purchase-invoice-data',
        '保存采购发票数据',
        {
          allowedStatuses: ['draft'],
          requiresEligibility: false,
        },
      ),
      action(
        'validate-purchase-invoice-data',
        '校验采购发票数据',
        {
          allowedStatuses: ['draft'],
          requiresEligibility: false,
        },
      ),
      routeAction(
        'enter-accounts-payable-draft',
        '进入采购应付账款草稿',
        ['draft', 'prepared', 'validated'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-accounts-payable-draft',
        '批量进入采购应付账款草稿',
        ['draft', 'prepared', 'validated'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'accounts-payable-draft',
    canonicalName: '采购应付账款草稿',
    route: '/finance/ap-drafts',
    nextModule: 'payable-confirmation-prepare',
    nextCanonicalName: '应付确认准备',
    nextRoute: '/finance/account-payable-confirms',
    actions: [
      action(
        'generate-purchase-accounts-payable-draft',
        '生成采购应付账款草稿',
        {
          allowedStatuses: ['prepared'],
          requiresEligibility: true,
        },
      ),
      routeAction(
        'enter-payable-confirmation-prepare',
        '进入应付确认准备',
        ['draft', 'prepared', 'validated'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-payable-confirmation-prepare',
        '批量进入应付确认准备',
        ['draft', 'prepared', 'validated'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'payable-confirmation-prepare',
    canonicalName: '应付确认准备',
    route: '/finance/account-payable-confirms',
    nextModule: 'payment-request-prepare',
    nextCanonicalName: '付款申请准备',
    nextRoute: '/finance/payment-applications',
    actions: [
      routeAction(
        'enter-payment-request-prepare',
        '进入付款申请准备',
        ['prepared'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-payment-request-prepare',
        '批量进入付款申请准备',
        ['prepared'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'payment-request-prepare',
    canonicalName: '付款申请准备',
    route: '/finance/payment-applications',
    nextModule: 'payment-request',
    nextCanonicalName: '付款申请',
    nextRoute: '/finance/payment-requests',
    actions: [
      routeAction('enter-payment-request', '进入付款申请', ['prepared'], {
        requiresEligibility: true,
      }),
      batchRouteAction(
        'batch-enter-payment-request',
        '批量进入付款申请',
        ['prepared'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'payment-request',
    canonicalName: '付款申请',
    route: '/finance/payment-requests',
    nextModule: 'payment-instruction-prepare',
    nextCanonicalName: '付款指令准备',
    nextRoute: '/finance/payment-order-prepares',
    actions: [
      routeAction(
        'enter-payment-instruction-prepare',
        '进入付款指令准备',
        ['approved'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-payment-instruction-prepare',
        '批量进入付款指令准备',
        ['approved'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'payment-instruction-prepare',
    canonicalName: '付款指令准备',
    route: '/finance/payment-order-prepares',
    nextModule: 'payment-order-prepare',
    nextCanonicalName: '正式付款单预备',
    nextRoute: '/finance/payment-prepares',
    actions: [
      routeAction(
        'enter-payment-order-prepare',
        '进入正式付款单预备',
        ['validated'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-payment-order-prepare',
        '批量进入正式付款单预备',
        ['validated'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'payment-order-prepare',
    canonicalName: '正式付款单预备',
    route: '/finance/payment-prepares',
    nextModule: 'payment-order-draft',
    nextCanonicalName: '正式付款单草稿',
    nextRoute: '/finance/payment-order-drafts',
    actions: [
      routeAction(
        'enter-payment-order-draft',
        '进入正式付款单草稿',
        ['submitted'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-payment-order-draft',
        '批量进入正式付款单草稿',
        ['submitted'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'payment-order-draft',
    canonicalName: '正式付款单草稿',
    route: '/finance/payment-order-drafts',
    nextModule: 'payment-risk-review',
    nextCanonicalName: '真实付款风险评审',
    nextRoute: '/finance/payment-risk-reviews',
    actions: [
      routeAction(
        'enter-payment-risk-review',
        '进入真实付款风险评审',
        ['reviewed'],
        { requiresEligibility: true },
      ),
      batchRouteAction(
        'batch-enter-payment-risk-review',
        '批量进入真实付款风险评审',
        ['reviewed'],
        { requiresEligibility: true },
      ),
    ],
  },
  {
    currentModule: 'bank-send-preparation',
    canonicalName: '银行发送准备',
    route: '/finance/bank-send-prepares',
    nextModule: 'bank-send-task',
    nextCanonicalName: '银行发送任务',
    nextRoute: '/finance/bank-send-tasks',
    actions: [
      action('view-bank-send-eligibility', '查看发送资格', {
        actionType: 'readonly-command',
        allowedStatuses: ['prepared'],
        allowedRoles: [
          'pce_business_viewer',
          ...SINGLE_ACTION_ROLES,
        ],
      }),
      action('view-bank-send-gate', '查看门禁结果', {
        actionType: 'readonly-command',
        allowedStatuses: ['prepared'],
        allowedRoles: [
          'pce_business_viewer',
          ...SINGLE_ACTION_ROLES,
        ],
      }),
      action('generate-bank-message-preview', '生成发送预览', {
        allowedStatuses: ['prepared'],
        requiresEligibility: true,
      }),
    ],
  },
  {
    currentModule: 'bank-send-task',
    canonicalName: '银行发送任务',
    route: '/finance/bank-send-tasks',
    nextModule: 'bank-send-execution-gate',
    nextCanonicalName: '银行发送执行授权',
    nextRoute: '/finance/bank-send-execution-gates',
    actions: [
      action('view-bank-send-task', '查看银行发送任务', {
        actionType: 'readonly-command',
        allowedStatuses: ['prepared', 'queued', 'ready_to_send'],
        allowedRoles: [
          'pce_business_viewer',
          ...BANK_TASK_ACTION_ROLES,
        ],
      }),
      action('view-bank-send-task-status', '查看任务状态', {
        actionType: 'readonly-command',
        allowedStatuses: ['prepared', 'queued', 'ready_to_send'],
        allowedRoles: [
          'pce_business_viewer',
          ...BANK_TASK_ACTION_ROLES,
        ],
      }),
      action('view-bank-message-binding', '查看报文绑定', {
        actionType: 'readonly-command',
        allowedStatuses: ['prepared', 'queued', 'ready_to_send'],
        allowedRoles: [
          'pce_business_viewer',
          ...BANK_TASK_ACTION_ROLES,
        ],
      }),
      action('create-bank-send-task', '创建发送任务', {
        allowedStatuses: ['prepared'],
        allowedRoles: [...BANK_TASK_ACTION_ROLES],
        requiresEligibility: true,
      }),
    ],
  },
  {
    currentModule: 'bank-send-execution-gate',
    canonicalName: '银行发送执行授权',
    route: '/finance/bank-send-execution-gates',
    nextModule: 'bank-send-request',
    nextCanonicalName: '银行发送请求准备',
    nextRoute: '/finance/bank-send-requests',
    actions: [
      action('view-bank-send-execution-gate', '查看发送授权', {
        actionType: 'readonly-command',
        allowedStatuses: ['pending_review', 'approved', 'ready_for_execution'],
        allowedRoles: [
          'pce_business_viewer',
          ...BANK_TASK_ACTION_ROLES,
        ],
      }),
      action('view-bank-send-execution-gate-conditions', '查看授权条件', {
        actionType: 'readonly-command',
        allowedStatuses: ['pending_review', 'approved', 'ready_for_execution'],
        allowedRoles: [
          'pce_business_viewer',
          ...BANK_TASK_ACTION_ROLES,
        ],
      }),
      action(
        'submit-bank-send-final-authorization-review',
        '提交最终授权审核',
        {
          allowedStatuses: ['ready_to_send'],
          allowedRoles: [...BANK_TASK_ACTION_ROLES],
          requiresEligibility: true,
        },
      ),
    ],
  },
  {
    currentModule: 'bank-send-request',
    canonicalName: '银行发送请求准备',
    route: '/finance/bank-send-requests',
    nextModule: 'bank-send-dispatch',
    nextCanonicalName: '银行发送分发（未开放）',
    nextRoute: '',
    actions: [
      action('view-bank-send-request', '查看发送请求', {
        actionType: 'readonly-command',
        allowedStatuses: ['draft', 'validated', 'ready_to_dispatch'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('view-bank-send-pre-dispatch-validation', '查看二次校验', {
        actionType: 'readonly-command',
        allowedStatuses: ['draft', 'validated', 'ready_to_dispatch'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('create-bank-send-request', '创建发送请求', {
        allowedStatuses: ['ready_for_execution'],
        allowedRoles: [...BANK_TASK_ACTION_ROLES],
        requiresEligibility: true,
      }),
      action('rerun-bank-send-pre-dispatch-validation', '重新执行二次校验', {
        allowedStatuses: ['draft', 'validated', 'ready_to_dispatch'],
        allowedRoles: [...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-send-simulation',
    canonicalName: '银行发送执行模拟',
    route: '/finance/bank-send-simulations',
    nextModule: 'bank-send-execution',
    nextCanonicalName: '银行发送执行（未开放）',
    nextRoute: '',
    actions: [
      action('create-bank-send-execution-simulation', '创建执行模拟', {
        allowedStatuses: ['ready_to_dispatch'],
        allowedRoles: [...BANK_TASK_ACTION_ROLES],
        requiresEligibility: true,
      }),
      action('view-bank-send-execution-simulation-result', '查看银行发送模拟结果', {
        actionType: 'readonly-command',
        allowedStatuses: [
          'created', 'validated', 'simulation_running',
          'simulation_success', 'simulation_failed',
        ],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('view-bank-send-execution-recovery', '查看银行发送模拟失败恢复', {
        actionType: 'readonly-command',
        allowedStatuses: ['simulation_failed'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-send-simulation-audit',
    canonicalName: '银行发送模拟审计',
    route: '/finance/bank-send-simulation-audits',
    nextModule: 'bank-send-isolation-gate',
    nextCanonicalName: '银行发送生产隔离门禁',
    nextRoute: '/finance/bank-send-isolation-gates',
    actions: [
      action('view-bank-send-simulation-audit', '查看模拟审计', {
        actionType: 'readonly-command',
        allowedStatuses: [
          'simulation_created', 'simulation_validated',
          'simulation_started', 'simulation_completed',
          'simulation_failed', 'simulation_recovered',
        ],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-send-isolation-gate',
    canonicalName: '银行发送生产隔离门禁',
    route: '/finance/bank-send-isolation-gates',
    nextModule: 'bank-send-production-execution-closed',
    nextCanonicalName: '真实银行发送（未开放）',
    nextRoute: '',
    actions: [
      action('view-bank-send-production-isolation', '查看隔离状态', {
        actionType: 'readonly-command',
        allowedStatuses: ['created', 'checked', 'isolated'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-send-chain-trace',
    canonicalName: '银行发送全链路追踪',
    route: '/finance/bank-send-chain-traces',
    nextModule: 'bank-send-final-approval',
    nextCanonicalName: '银行发送最终审批',
    nextRoute: '/finance/bank-send-final-approvals',
    actions: [
      action('view-bank-send-chain-trace', '查看链路', {
        actionType: 'readonly-command',
        allowedStatuses: ['*'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-send-final-approval',
    canonicalName: '银行发送最终审批',
    route: '/finance/bank-send-final-approvals',
    nextModule: 'bank-send-dual-isolation-check',
    nextCanonicalName: '银行发送双重隔离检查',
    nextRoute: '/finance/bank-send-dual-isolation-checks',
    actions: [
      action('view-bank-send-final-approval-conditions', '查看审批条件', {
        actionType: 'readonly-command',
        allowedStatuses: ['pending', 'first_approved', 'second_approved', 'final_locked'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('submit-bank-send-first-approval', '提交第一审批', {
        allowedStatuses: ['pending'],
        allowedRoles: ['bank_send_business_reviewer'],
      }),
      action('submit-bank-send-second-approval', '提交第二审批', {
        allowedStatuses: ['first_approved'],
        allowedRoles: ['bank_send_fund_owner'],
      }),
    ],
  },
  {
    currentModule: 'bank-send-dual-isolation-check',
    canonicalName: '银行发送双重隔离检查',
    route: '/finance/bank-send-dual-isolation-checks',
    nextModule: 'bank-send-production-release-review',
    nextCanonicalName: '真实银行发送前生产隔离评审',
    nextRoute: '/finance/bank-send-production-release-reviews',
    actions: [
      action('view-bank-send-dual-isolation-check', '查看隔离检查', {
        actionType: 'readonly-command',
        allowedStatuses: ['passed', 'failed'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-send-production-release-review',
    canonicalName: '真实银行发送前生产隔离评审',
    route: '/finance/bank-send-production-release-reviews',
    nextModule: 'bank-send-execution-framework-review',
    nextCanonicalName: '银行发送执行框架评审',
    nextRoute: '/finance/bank-send-execution-framework-reviews',
    actions: [
      action('view-bank-send-production-release-review', '查看生产隔离评审', {
        actionType: 'readonly-command',
        allowedStatuses: ['draft', 'reviewing', 'review_passed', 'locked'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('submit-production-business-review', '提交业务评审意见', {
        allowedStatuses: ['draft'],
        allowedRoles: ['bank_send_business_owner'],
      }),
      action('submit-production-fund-review', '提交资金评审意见', {
        allowedStatuses: ['reviewing'],
        allowedRoles: ['bank_send_fund_owner'],
      }),
      action('submit-production-security-review', '提交安全评审意见', {
        allowedStatuses: ['review_passed'],
        allowedRoles: ['bank_send_security_owner'],
      }),
    ],
  },
  {
    currentModule: 'bank-send-execution-framework-review',
    canonicalName: '银行发送执行框架评审',
    route: '/finance/bank-send-execution-framework-reviews',
    nextModule: 'bank-connector-adapter-review',
    nextCanonicalName: '银行接口适配评审',
    nextRoute: '/finance/bank-connector-adapter-reviews',
    actions: [
      action('view-bank-send-execution-framework', '查看执行框架', {
        actionType: 'readonly-command',
        allowedStatuses: ['draft', 'designed', 'security_reviewed'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('view-bank-send-request-signature', '查看签名结果', {
        actionType: 'readonly-command',
        allowedStatuses: ['security_reviewed'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
      action('view-bank-send-failure-model', '查看失败模型', {
        actionType: 'readonly-command',
        allowedStatuses: ['security_reviewed'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'bank-connector-adapter-review',
    canonicalName: '银行接口适配评审',
    route: '/finance/bank-connector-adapter-reviews',
    nextModule: 'bank-send-production-execution-closed',
    nextCanonicalName: '真实银行发送（未开放）',
    nextRoute: '',
    actions: [
      action('view-bank-connector-adapter', '查看接口适配', {
        actionType: 'readonly-command',
        allowedStatuses: ['simulation_only'],
        allowedRoles: ['pce_business_viewer', ...BANK_TASK_ACTION_ROLES],
      }),
    ],
  },
  {
    currentModule: 'supplier-payable-confirmation',
    canonicalName: '供应商应付确认',
    route: '/scm/supplier-payable-confirmations',
    nextModule: 'supplier-payment-request',
    nextCanonicalName: '供应商付款申请',
    nextRoute: '/scm/supplier-payment-requests',
    actions: [
      action('SCM_PAYABLE_SUBMIT_REVIEW', '提交应付确认审核', {
        allowedStatuses: ['draft'],
        allowedRoles: ['scm_payable_buyer'],
      }),
      action('SCM_PAYABLE_APPROVE', '确认应付结果', {
        allowedStatuses: ['internal_review'],
        allowedRoles: ['scm_payable_supervisor'],
      }),
      action('SCM_PAYABLE_CREATE_PAYMENT_REQUEST', '生成付款申请资格', {
        allowedStatuses: ['confirmed'],
        allowedRoles: ['scm_payable_supervisor'],
      }),
    ],
  },
  {
    currentModule: 'supplier-payment-request',
    canonicalName: '供应商付款申请',
    route: '/scm/supplier-payment-requests',
    nextModule: 'supplier-payment-approval-closed',
    nextCanonicalName: '后续付款审批（未开放）',
    nextRoute: '',
    actions: [
      action('SCM_PAYMENT_REQUEST_SUBMIT', '提交付款申请', {
        allowedStatuses: ['draft'],
        allowedRoles: ['scm_payment_request_applicant'],
      }),
      action('SCM_PAYMENT_REQUEST_APPROVE', '审批付款申请', {
        allowedStatuses: ['submitted'],
        allowedRoles: ['scm_payment_request_owner'],
      }),
      action('SCM_PAYMENT_REQUEST_RETURN', '退回付款申请', {
        allowedStatuses: ['submitted'],
        allowedRoles: ['scm_payment_request_owner'],
      }),
    ],
  },
  {
    currentModule: 'supplier-payment-status',
    canonicalName: '供应商付款状态记录',
    route: '/scm/supplier-payment-status',
    nextModule: 'supplier-settlement-completion',
    nextCanonicalName: '供应商结算完成确认',
    nextRoute: '/scm/supplier-settlement-completions',
    actions: [
      action('SCM_PAYMENT_STATUS_SUBMIT', '提交付款状态', {
        allowedStatuses: ['draft'],
        allowedRoles: ['scm_payment_request_owner'],
      }),
      action('SCM_PAYMENT_STATUS_CONFIRM_COMPLETED', '确认付款完成', {
        allowedStatuses: ['payment_scheduled'],
        allowedRoles: ['scm_payment_request_owner'],
      }),
      action('SCM_PAYMENT_STATUS_COMPLETE_SETTLEMENT', '完成结算', {
        allowedStatuses: ['payment_completed'],
        allowedRoles: ['scm_payment_request_owner'],
      }),
    ],
  },
  {
    currentModule: 'supplier-settlement-completion',
    canonicalName: '供应商结算完成确认',
    route: '/scm/supplier-settlement-completions',
    nextModule: 'supplier-performance',
    nextCanonicalName: '供应商绩效',
    nextRoute: '/scm/supplier-performance',
    actions: [
      action('SCM_SETTLEMENT_CONFIRM_COMPLETED', '确认结算完成', {
        allowedStatuses: ['pending'],
        allowedRoles: ['scm_payment_request_owner'],
      }),
    ],
  },
  ...[
    ['supplier-reconciliation', '供应商对账', '/scm/supplier-reconciliations', ['draft', 'internal_review', 'supplier_confirming', 'completed']],
    ['supplier-performance', '供应商绩效', '/scm/supplier-performance', ['metric_ready']],
    ['buyer-performance', '采购员绩效', '/scm/buyer-performance', ['metric_ready']],
  ].map(([currentModule, canonicalName, route, allowedStatuses]) => ({
    currentModule,
    canonicalName,
    route,
    nextModule: `${currentModule}-governance-closed`,
    nextCanonicalName: '治理边界（未开放）',
    nextRoute: '',
    actions: [
      action(`view-${currentModule}-source`, '查看来源', { actionType: 'readonly-command', allowedStatuses }),
      action(`view-${currentModule}-status`, '查看状态', { actionType: 'readonly-command', allowedStatuses }),
      action(`view-${currentModule}-metric`, '查看评价基础数据', { actionType: 'readonly-command', allowedStatuses }),
    ],
  })),
].map(contract => Object.freeze({
  ...contract,
  actions: Object.freeze(contract.actions.map(item => {
    const requiredPermission =
      `pce.action.${contract.currentModule}.${item.actionId}`
    return Object.freeze({
      ...item,
      actionCode: item.actionId,
      moduleCode: contract.currentModule,
      requiredPermission,
      permission: requiredPermission,
      serverPermission: item.formalPermission || requiredPermission,
      role: item.allowedRoles
        ? [...item.allowedRoles]
        : item.scope === 'batch'
          ? [...BATCH_ACTION_ROLES]
          : [...SINGLE_ACTION_ROLES],
      displayName: item.actionName,
      allowedRoles: item.allowedRoles
        ? [...item.allowedRoles]
        : item.scope === 'batch'
          ? [...BATCH_ACTION_ROLES]
          : [...SINGLE_ACTION_ROLES],
      allowedStatus: [...item.allowedStatuses],
      singleOrBatch: item.scope,
      serverEligibilityCheck: true,
      organizationScope: 'legal_entity',
      serverValidator: 'workflow_runtime.ActionPermissionValidator',
      permissionContractVersion:
        PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION,
    })
  })),
  forbiddenActions: Object.freeze(
    contract.currentModule === 'bank-send-task'
      ? [...forbiddenExecutionActions]
      : [...forbiddenExecutionActions, 'create-bank-send-task'],
  ),
}))

const DEFAULT_PERMISSIONS = Object.freeze(
  contracts.flatMap(contract => (
    contract.actions.map(item => item.requiredPermission)
  )),
)

function action(actionId, actionName, options = {}) {
  return Object.freeze({
    actionId,
    actionName,
    actionType: 'command',
    handlerType: 'emit',
    scope: 'single',
    permission: 'business_action:execute',
    allowedStatuses: ['*'],
    requiresEligibility: false,
    ...options,
  })
}

function routeAction(
  actionId,
  actionName,
  allowedStatuses,
  options = {},
) {
  return action(actionId, actionName, {
    actionType: 'navigation',
    handlerType: 'route',
    permission: 'business_action:navigate',
    allowedStatuses,
    ...options,
  })
}

function batchAction(
  actionId,
  actionName,
  allowedStatuses,
  options = {},
) {
  return action(actionId, actionName, {
    actionType: 'batch-command',
    scope: 'batch',
    permission: 'business_action:batch',
    allowedStatuses,
    ...options,
  })
}

function batchRouteAction(
  actionId,
  actionName,
  allowedStatuses,
  options = {},
) {
  return batchAction(actionId, actionName, allowedStatuses, {
    actionType: 'batch-navigation',
    handlerType: 'route',
    ...options,
  })
}

function cloneAction(item) {
  return {
    ...item,
    allowedStatuses: [...item.allowedStatuses],
  }
}

export function listPceBusinessActionContracts() {
  return contracts.map(contract => ({
    ...contract,
    actions: contract.actions.map(cloneAction),
    forbiddenActions: [...contract.forbiddenActions],
  }))
}

export function getPceBusinessActionContract(currentModule = '') {
  const contract = contracts.find(item => item.currentModule === currentModule)
  return contract
    ? {
        ...contract,
        actions: contract.actions.map(cloneAction),
        forbiddenActions: [...contract.forbiddenActions],
      }
    : null
}

export function getPceBusinessAction(actionId = '') {
  for (const contract of contracts) {
    const found = contract.actions.find(item => item.actionId === actionId)
    if (found) return cloneAction(found)
  }
  return null
}

export function pceBusinessActionLabel(actionId = '') {
  return getPceBusinessAction(actionId)?.actionName || ''
}

export function resolvePceBusinessActions({
  currentModule = '',
  currentStatus = '',
  selectedRows = [],
  permissions = DEFAULT_PERMISSIONS,
  eligibility = null,
  routeQuery = {},
} = {}) {
  const contract = getPceBusinessActionContract(currentModule)
  if (!contract) {
    throw new Error(`BusinessActionRegistry 未注册模块：${currentModule}`)
  }
  const permissionSet = new Set(permissions || [])
  const rows = Array.isArray(selectedRows) ? selectedRows.filter(Boolean) : []
  const statuses = rows.length
    ? rows.map(resolveBusinessStatus)
    : [String(currentStatus || '').trim()].filter(Boolean)
  const eligible = eligibility === null || eligibility === undefined
    ? null
    : eligibility === true
  const availableActions = []
  const batchActions = []
  const unavailableActions = []

  for (const item of contract.actions) {
    const reason = unavailableReason({
      item,
      permissionSet,
      statuses,
      selectedCount: rows.length,
      eligible,
    })
    const resolved = {
      ...item,
      enabled: !reason,
      disabledReason: reason,
      selectedCount: rows.length,
      currentStatuses: [...statuses],
      selectedRows: [...rows],
      targetRoute: item.handlerType === 'route'
        ? buildTargetRoute(contract, item, rows, routeQuery)
        : null,
    }
    if (reason) {
      unavailableActions.push(resolved)
    } else if (item.scope === 'batch') {
      batchActions.push(resolved)
    } else {
      availableActions.push(resolved)
    }
  }

  return {
    contractVersion: PCE_BUSINESS_ACTION_CONTRACT_VERSION,
    registryVersion: PCE_BUSINESS_ACTION_REGISTRY_VERSION,
    currentModule: contract.currentModule,
    currentStatus: statuses[0] || String(currentStatus || ''),
    currentStatuses: statuses,
    selectedCount: rows.length,
    availableActions,
    batchActions,
    nextModule: contract.nextModule,
    nextRoute: contract.nextRoute,
    forbiddenActions: [
      ...contract.forbiddenActions,
      ...unavailableActions.map(item => item.actionId),
    ],
    unavailableActions,
    currentStateSource: 'server_permission_and_registered_server_state',
  }
}

function unavailableReason({
  item,
  permissionSet,
  statuses,
  selectedCount,
  eligible,
}) {
  if (!permissionSet.has(item.requiredPermission)) {
    return '服务端尚未授予当前用户该业务动作权限。'
  }
  if (item.scope === 'batch' && selectedCount < 2) {
    return '批量业务动作至少需要选择两条记录。'
  }
  if (item.scope === 'single' && selectedCount > 1) {
    return '当前动作仅支持单条记录。'
  }
  if (item.requiresEligibility && eligible === false) {
    return '服务端下一步资格尚未通过。'
  }
  if (!statuses.length) return '当前业务状态尚未加载。'
  if (
    !item.allowedStatuses.includes('*')
    && !statuses.every(status => item.allowedStatuses.includes(status))
  ) {
    return `当前状态不允许执行“${item.actionName}”。`
  }
  return ''
}

function resolveBusinessStatus(row = {}) {
  return String(
    row.currentStatus
      || row.status
      || row.checkStatus
      || row.payableStatus
      || row.reconciliationStatus
      || row.settlementStatus
      || '',
  ).trim()
}

function buildTargetRoute(contract, item, rows, routeQuery) {
  const businessNos = rows.map(resolveBusinessNo).filter(Boolean)
  const query = {
    ...routeQuery,
    navigationOnly: 'true',
    sourceModule: contract.currentModule,
    businessActionId: item.actionId,
  }
  if (businessNos.length) {
    query.sourceBusinessNo = businessNos[0]
    query.sourceBusinessNos = businessNos.join(',')
    const sourceQueryKey = {
      'payable-prepare': 'sourcePayablePrepareNo',
      'payable-check': 'sourcePayableCheckNo',
      'supplier-settlement': 'sourceSettlementNo',
      'purchase-reconciliation': 'sourcePurchaseReconciliationNo',
      'purchase-invoice-prepare': 'sourcePurchaseInvoicePrepareNo',
      'accounts-payable-draft': 'sourceApDraftNo',
      'payable-confirmation-prepare': 'sourcePayableConfirmationPrepareNo',
      'payment-request-prepare': 'sourcePaymentRequestPrepareNo',
      'payment-request': 'sourcePaymentRequestNo',
      'payment-instruction-prepare': 'sourcePaymentInstructionPrepareNo',
      'payment-order-prepare': 'sourcePaymentOrderPrepareNo',
      'payment-order-draft': 'sourcePaymentOrderDraftNo',
    }[contract.currentModule]
    if (sourceQueryKey) query[sourceQueryKey] = businessNos[0]
  }
  if (item.scope === 'batch') query.context = 'batch'
  return { path: contract.nextRoute, query }
}

function resolveBusinessNo(row = {}) {
  const keys = [
    'payableCheckNo',
    'prepareNo',
    'requestNo',
    'draftNo',
    'settlementNo',
    'reconciliationNo',
    'primaryBusinessNo',
    'orderNo',
    'id',
  ]
  for (const key of keys) {
    if (row[key] !== null && row[key] !== undefined && row[key] !== '') {
      return String(row[key])
    }
  }
  return ''
}

export function capturePceBusinessTableState({
  selectedRows = [],
  sortState = {},
  scrollElement = null,
} = {}) {
  return {
    selectedRowKeys: selectedRows.map(row => (
      row.rowKey || row.id || resolveBusinessNo(row)
    )).filter(Boolean).map(String),
    sortState: { ...sortState },
    scrollLeft: Number(scrollElement?.scrollLeft || 0),
    scrollTop: Number(scrollElement?.scrollTop || 0),
  }
}

export function restorePceBusinessTableState({
  snapshot,
  rows = [],
  tableRef = null,
  scrollElement = null,
} = {}) {
  if (!snapshot) return []
  const selectedKeySet = new Set(snapshot.selectedRowKeys || [])
  const restoredRows = rows.filter(row => selectedKeySet.has(String(
    row.rowKey || row.id || resolveBusinessNo(row),
  )))
  tableRef?.clearSelection?.()
  for (const row of restoredRows) tableRef?.toggleRowSelection?.(row, true)
  if (scrollElement) {
    scrollElement.scrollLeft = snapshot.scrollLeft || 0
    scrollElement.scrollTop = snapshot.scrollTop || 0
  }
  return restoredRows
}

export const PCE_BUSINESS_ACTION_DEFAULT_PERMISSIONS = DEFAULT_PERMISSIONS

export const BusinessActionRegistry = Object.freeze({
  contractVersion: PCE_BUSINESS_ACTION_CONTRACT_VERSION,
  registryVersion: PCE_BUSINESS_ACTION_REGISTRY_VERSION,
  list: listPceBusinessActionContracts,
  getContract: getPceBusinessActionContract,
  getAction: getPceBusinessAction,
  label: pceBusinessActionLabel,
  resolve: resolvePceBusinessActions,
})


