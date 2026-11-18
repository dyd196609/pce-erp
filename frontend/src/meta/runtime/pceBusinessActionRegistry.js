import { MES_ENTRY_PAGE } from './mesExecutionEntryContract.js'
import { FINISHED_GOODS_PAGE,FINISHED_GOODS_ACTIONS,FINISHED_GOODS_FORMAL_ACTIONS } from './finishedGoodsContract.js'
import { OPERATION_HANDOVER_PAGE, OPERATION_HANDOVER_ACTION_CONTRACTS, OPERATION_RANGE_RECEIVE_API } from './operationHandoverContract.js'
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
  {currentModule:'routing-management',canonicalName:'订单路线引用及执行安排',route:'/pde/routings',nextModule:'routing-management',nextRoute:'/pde/routings',terminal:true,actions:[
    action('select-order-standard-routing','选择并固定标准路线版本',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('save-order-execution-draft','保存订单执行安排',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('confirm-order-execution','确认订单执行安排',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
    action('revise-order-execution','办理安排自身修订',{allowedStatuses:['draft','confirmed'],formalPermission:'production.master_data.routing.maintain'}),
  ]},
  {currentModule:'routing-version-management',canonicalName:'订单路线引用及执行安排',route:'/pde/routing-versions',nextModule:'routing-version-management',nextRoute:'/pde/routing-versions',terminal:true,actions:[
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

// Production work orders retain the server's current role/scope and availability.
// This additive contract does not change the legacy registry resolver or role defaults.
contracts.push(Object.freeze({
  currentModule: 'production-work-order', canonicalName: '生产工单',
  route: '/planning/requirements?section=work-order-reception',
  nextModule: 'production-work-order-execution-boundary', nextCanonicalName: '车间接收与执行（后续业务）', nextRoute: '',
  serverProjection: true,
  actions: Object.freeze([
    ['generate', 'production.order.generate', '生成生产工单', ['not_generated'], 'generate_work_order'],
    ['release', 'production.order.release', '下达生产工单', ['draft'], 'release_work_order'],
  ].map(([key, actionCode, displayName, allowedStatuses, validator]) => Object.freeze({
    key, actionId: actionCode, actionCode, actionName: displayName, displayName,
    moduleCode: 'production-work-order', actionType: 'command', handlerType: 'emit',
    scope: 'single', singleOrBatch: 'single', targetRoute: null,
    permission: 'production.order.release', requiredPermission: 'production.order.release', serverPermission: 'production.order.release',
    role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server_action_contract',
    allowedStatuses: Object.freeze(allowedStatuses), allowedStatus: Object.freeze([...allowedStatuses]),
    sourceAllowedStatuses: Object.freeze(['confirmed']), assessmentSourceObjectType: 'ProductionPlan', objectType: 'ProductionWorkOrder',
    organizationScope: 'legal_entity', serverValidator: `planning.work_order_execution_service.${validator}`,
    serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
    apiPathTemplate: `/api/planning/production-plans/{planId}/work-order/${key}/`,
    executionAvailabilitySource: 'execution.availableActions',
    permissionContractVersion: PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION,
  }))),
  forbiddenActions: Object.freeze([...forbiddenExecutionActions, 'create-bank-send-task']),
}))

export function resolvePceServerBusinessActions({ currentModule, productionPlanId, actionContracts, availableActions } = {}) {
  const registered = contracts.find(row => row.currentModule === currentModule && row.serverProjection === true)
  if (!registered || !Number.isSafeInteger(productionPlanId) || productionPlanId <= 0
    || !Array.isArray(actionContracts) || !Array.isArray(availableActions)
    || actionContracts.length !== registered.actions.length || availableActions.length !== registered.actions.length
    || new Set(actionContracts.map(row => row.key)).size !== registered.actions.length
    || new Set(availableActions.map(row => row.key)).size !== registered.actions.length) {
    throw new Error('公共业务动作登记与本次服务端动作集合不一致。')
  }
  return registered.actions.map(item => {
    const contract = actionContracts.find(row => row.key === item.key), available = availableActions.find(row => row.key === item.key)
    const apiPath = item.apiPathTemplate.replace('{planId}', encodeURIComponent(productionPlanId))
    const fields = ['actionCode', 'moduleCode', 'displayName', 'requiredPermission', 'scope', 'organizationScope', 'serverValidator', 'httpMethod', 'assessmentSourceObjectType', 'objectType']
    if (!contract || !available || fields.some(key => contract[key] !== item[key]) || contract.apiPath !== apiPath
      || JSON.stringify(contract.allowedStatuses) !== JSON.stringify(item.allowedStatuses)
      || JSON.stringify(contract.sourceAllowedStatuses) !== JSON.stringify(item.sourceAllowedStatuses)
      || available.actionCode !== item.actionCode || available.displayName !== item.displayName || available.apiPath !== apiPath
      || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string'
      || (available.enabled ? typeof available.executionToken !== 'string' || !available.executionToken.trim() : !available.disabledReason.trim())) {
      throw new Error('公共业务动作登记与本次服务端动作身份或可用性不一致。')
    }
    return { ...cloneAction(item), role: contract.role, allowedRoles: contract.role,
      enabled: available.enabled, disabledReason: available.disabledReason, executionToken: available.executionToken, apiPath }
  })
}

// Workshop reception is an independent server-owned scope within the same MES page.
// Keep the existing work-order generation/release contracts and resolver unchanged.
export const WORK_ORDER_WORKSHOP_RECEIPT_ACTION_CONTRACT = Object.freeze({
  key: 'receive', actionId: 'production.order.receive', actionCode: 'production.order.receive',
  actionName: '接收本车间工序', displayName: '接收本车间工序', moduleCode: 'production-work-order',
  actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single', targetRoute: null,
  permission: 'production.order.receive', requiredPermission: 'production.order.receive', serverPermission: 'production.order.receive',
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server_action_contract',
  allowedStatuses: Object.freeze(['not_received']), allowedStatus: Object.freeze(['not_received']),
  sourceAllowedStatuses: Object.freeze(['released']), assessmentSourceObjectType: 'ProductionWorkOrder',
  objectType: 'ProductionWorkOrderWorkshopReceipt', organizationScope: 'legal_entity',
  processCode: 'MES_PRODUCTION_OPERATION', workflowNodeCode: 'PRODUCTION_WORK_ORDER_RECEIVE', navigationNodeCode: 'production-work-order',
  requiredResponsibility: 'RESP_PROD_PLAN_001', documentType: 'ProductionWorkOrder',
  serverValidator: 'planning.work_order_workshop_receipt_service.receive_workshop_scope',
  serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
  apiPathTemplate: '/api/planning/work-orders/{workOrderId}/workshops/{workshopId}/receive/',
  executionAvailabilitySource: 'scopes.availableAction', permissionContractVersion: PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION,
})
export function resolvePceWorkshopReceiptAction({ workOrderId, workshopId, actionContract, availableAction } = {}) {
  if (![workOrderId, workshopId].every(value => Number.isSafeInteger(value) && value > 0)) throw new Error('车间接收对象身份不完整。')
  const registered = WORK_ORDER_WORKSHOP_RECEIPT_ACTION_CONTRACT
  const apiPath = registered.apiPathTemplate.replace('{workOrderId}', String(workOrderId)).replace('{workshopId}', String(workshopId))
  const fields = ['key', 'actionCode', 'moduleCode', 'displayName', 'requiredPermission', 'scope', 'organizationScope', 'serverValidator', 'httpMethod', 'assessmentSourceObjectType', 'objectType', 'processCode', 'workflowNodeCode', 'navigationNodeCode', 'requiredResponsibility', 'documentType']
  if (!actionContract || !availableAction || fields.some(key => actionContract[key] !== registered[key])
    || actionContract.apiPath !== apiPath || availableAction.apiPath !== apiPath
    || JSON.stringify(actionContract.allowedStatuses) !== JSON.stringify(registered.allowedStatuses)
    || JSON.stringify(actionContract.sourceAllowedStatuses) !== JSON.stringify(registered.sourceAllowedStatuses)
    || availableAction.key !== registered.key || availableAction.actionCode !== registered.actionCode || availableAction.displayName !== registered.displayName
    || !Array.isArray(actionContract.role) || !actionContract.role.every(role => typeof role === 'string' && role.trim())
    || typeof availableAction.enabled !== 'boolean' || typeof availableAction.disabledReason !== 'string'
    || (availableAction.enabled ? typeof availableAction.executionToken !== 'string' || !availableAction.executionToken.trim() : !availableAction.disabledReason.trim())) {
    throw new Error('车间接收公共动作登记与服务端身份或可用性不一致。')
  }
  return { ...cloneAction(registered), role: actionContract.role, allowedRoles: actionContract.role,
    enabled: availableAction.enabled, disabledReason: availableAction.disabledReason, executionToken: availableAction.executionToken, apiPath }
}

// An additive action inside the existing workshop-receipt node; it reuses the
// receive authority and never grants a new role or replaces an original receipt.
export const RESOURCE_HANDOFF_ACTION_CONTRACT = Object.freeze({
  key: 'confirm', actionId: 'production.order.resource_handoff', actionCode: 'production.order.resource_handoff',
  actionName: '确认本工序归属承接', displayName: '确认本工序归属承接', moduleCode: 'production-work-order',
  actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: 'production.order.receive', requiredPermission: 'production.order.receive', serverPermission: 'production.order.receive',
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
  allowedStatuses: Object.freeze(['released']), assessmentSourceObjectType: 'ProductionWorkOrderOperation',
  objectType: 'ProductionOperationResourceHandoff', processCode: 'MES_PRODUCTION_OPERATION',
  workflowNodeCode: 'PRODUCTION_WORK_ORDER_RECEIVE', requiredResponsibility: 'RESP_PROD_PLAN_001',
  serverValidator: 'planning.operation_resource_handoff_service.confirm_resource_handoff',
  serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
  apiPathTemplate: '/api/planning/resource-handoffs/{operationId}/confirm/', executionAvailabilitySource: 'availableAction',
})
// Like the existing receipt section action, resolve this within the work-order
// module without altering its exact generate/release action set or adding a route.
export function resolvePceResourceHandoffAction(row) {
  const registered = RESOURCE_HANDOFF_ACTION_CONTRACT, available = row?.availableAction
  const apiPath = registered.apiPathTemplate.replace('{operationId}', String(row?.operationId))
  const fields = ['key', 'actionCode', 'moduleCode', 'requiredPermission', 'scope', 'organizationScope',
    'serverValidator', 'httpMethod', 'assessmentSourceObjectType', 'objectType', 'processCode', 'workflowNodeCode', 'requiredResponsibility']
  const displayName = row?.resourceHandoff ? '已承接' : registered.displayName
  if (!Number.isSafeInteger(row?.operationId) || row.operationId <= 0 || !available
    || fields.some(key => available[key] !== registered[key]) || available.displayName !== displayName
    || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string'
    || !Array.isArray(available.role) || !available.role.every(value => typeof value === 'string' && value.trim())
    || JSON.stringify(available.allowedStatuses) !== JSON.stringify(registered.allowedStatuses)
    || (!available.enabled && !available.disabledReason.trim()) || (row.resourceHandoff && available.enabled)) {
    throw new Error('工序归属承接公共动作登记与服务端身份或可用性不一致。')
  }
  return { ...cloneAction(registered), displayName: available.displayName, apiPath,
    role: available.role, allowedRoles: available.role, enabled: available.enabled, disabledReason: available.disabledReason }
}

// Explicit first resource choice and precise operation receipt remain in the
// original work-order receiving node. Legacy group/handoff actions are intact.
export const OPERATION_RESOURCE_ACTION_CONTRACTS = Object.freeze([
  ['selectResource', 'production.order.select_operation_resource', '正式选择执行资源', 'ProductionOperationResourceSelection', 'select_operation_resource', 'select', '已选择资源'],
  ['receiveOperation', 'production.order.receive_operation', '确认本工序精确接收', 'ProductionOperationPreciseReceipt', 'receive_operation', 'receive', '已精确接收'],
].map(([key, actionCode, displayName, objectType, validator, path, completedDisplayName]) => Object.freeze({
  key, actionId: actionCode, actionCode, actionName: displayName, displayName, completedDisplayName,
  moduleCode: 'production-work-order', actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: 'production.order.receive', requiredPermission: 'production.order.receive', serverPermission: 'production.order.receive',
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
  allowedStatuses: Object.freeze(['released']), assessmentSourceObjectType: 'ProductionWorkOrderOperation', objectType,
  processCode: 'MES_PRODUCTION_OPERATION', workflowNodeCode: 'PRODUCTION_WORK_ORDER_RECEIVE', requiredResponsibility: 'RESP_PROD_PLAN_001',
  serverValidator: `planning.operation_resource_selection_service.${validator}`, serverEligibilityCheck: true, requiresEligibility: true,
  httpMethod: 'POST', apiPathTemplate: `/api/planning/operation-resources/{operationId}/${path}/`, executionAvailabilitySource: 'availableActions',
})))
export function resolvePceOperationResourceActions(row) {
  const result = {}
  for (const registered of OPERATION_RESOURCE_ACTION_CONTRACTS) {
    const available = row?.availableActions?.[registered.key]
    const proof = row?.[registered.key === 'selectResource' ? 'resourceSelectionProof' : 'preciseReceiptProof']
    const apiPath = registered.apiPathTemplate.replace('{operationId}', String(row?.operationId))
    const fields = ['key', 'actionCode', 'moduleCode', 'requiredPermission', 'scope', 'organizationScope',
      'serverValidator', 'httpMethod', 'assessmentSourceObjectType', 'objectType', 'processCode', 'workflowNodeCode', 'requiredResponsibility']
    const displayName = (registered.key === 'selectResource' ? row?.selectionFact : proof) ? registered.completedDisplayName : registered.displayName
    if (!Number.isSafeInteger(row?.operationId) || row.operationId <= 0 || !available
      || fields.some(key => available[key] !== registered[key]) || available.displayName !== displayName
      || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string'
      || !Array.isArray(available.role) || !available.role.every(value => typeof value === 'string' && value.trim())
      || JSON.stringify(available.allowedStatuses) !== JSON.stringify(registered.allowedStatuses)
      || (!available.enabled && !available.disabledReason.trim()) || (proof && available.enabled))
      throw new Error('执行资源选择／精确接收公共动作与服务端身份或正式可用性不一致。')
    result[registered.key] = { ...cloneAction(registered), displayName: available.displayName, apiPath,
      role: available.role, allowedRoles: available.role, enabled: available.enabled, disabledReason: available.disabledReason }
  }
  return result
}

export const ALLOCATION_SOURCE_HANDOFF_ACTION_CONTRACT = Object.freeze({
  key: 'confirm', actionId: 'production.operation_source.handoff', actionCode: 'production.operation_source.handoff',
  actionName: '确认历史来源承接', displayName: '确认历史来源承接', moduleCode: 'foundation-formal-operations',
  actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: 'production.engineering.rule.release', requiredPermission: 'production.engineering.rule.release',
  serverPermission: 'production.engineering.rule.release', additionalRequiredPermissions: Object.freeze(['production.engineering.rule.create']),
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
  allowedStatuses: Object.freeze(['handoff_required']), objectType: 'OperationAllocationSourceHandoff',
  assessmentSourceObjectType: 'ProductionPlanOperationRequirementAllocation',
  serverValidator: 'pde.operation_allocation_source_handoff_service.confirm_allocation_source_handoff',
  serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
  apiPathTemplate: '/api/pde/operation-allocation-source-handoffs/{allocationId}/confirm/', executionAvailabilitySource: 'availableActions',
})
export function resolvePceAllocationSourceHandoffAction(row, available) {
  const registered = ALLOCATION_SOURCE_HANDOFF_ACTION_CONTRACT
  const apiPath = registered.apiPathTemplate.replace('{allocationId}', String(row?.allocationId))
  const fields = ['key', 'actionCode', 'moduleCode', 'requiredPermission', 'scope', 'organizationScope',
    'serverValidator', 'httpMethod', 'objectType', 'assessmentSourceObjectType']
  if (!Number.isSafeInteger(row?.allocationId) || row.allocationId <= 0 || !available
    || fields.some(key => available[key] !== registered[key])
    || available.displayName !== (row.handoffProof ? '已承接' : registered.displayName)
    || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string'
    || !Array.isArray(available.role) || !available.role.every(value => typeof value === 'string' && value.trim())
    || JSON.stringify(available.allowedStatuses) !== JSON.stringify(registered.allowedStatuses)
    || JSON.stringify(available.additionalRequiredPermissions) !== JSON.stringify(registered.additionalRequiredPermissions)
    || (!available.enabled && !available.disabledReason.trim()) || (row.handoffProof && available.enabled))
    throw new Error('历史来源承接公共动作与服务端身份、职责或正式可用性不一致。')
  return { ...cloneAction(registered), displayName: available.displayName, apiPath,
    role: available.role, allowedRoles: available.role, enabled: available.enabled, disabledReason: available.disabledReason }
}

export const ALLOCATION_SOURCE_VERSION_ACTION_CONTRACT = Object.freeze({
  ...ALLOCATION_SOURCE_HANDOFF_ACTION_CONTRACT, key: 'prepareVersion',
  actionId: 'production.operation_source.publish_handoff_version', actionCode: 'production.operation_source.publish_handoff_version',
  actionName: '创建并发布承接版本', displayName: '创建并发布承接版本',
  objectType: 'EngineeringRuleDefinition',
  serverValidator: 'pde.operation_allocation_source_version_service.publish_source_version',
  apiPathTemplate: '/api/pde/operation-allocation-source-handoffs/{allocationId}/publish-version/',
})
export function resolvePceAllocationSourceVersionAction(row, available) {
  if (!available) return null
  const registered = ALLOCATION_SOURCE_VERSION_ACTION_CONTRACT
  const apiPath = registered.apiPathTemplate.replace('{allocationId}', String(row?.allocationId))
  const fields = ['key', 'actionCode', 'moduleCode', 'requiredPermission', 'scope', 'organizationScope',
    'serverValidator', 'httpMethod', 'objectType', 'assessmentSourceObjectType']
  if (!Number.isSafeInteger(row?.allocationId) || row.allocationId <= 0
    || fields.some(key => available[key] !== registered[key]) || available.displayName !== registered.displayName
    || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string'
    || !Array.isArray(available.role) || !available.role.every(value => typeof value === 'string' && value.trim())
    || JSON.stringify(available.allowedStatuses) !== JSON.stringify(registered.allowedStatuses)
    || JSON.stringify(available.additionalRequiredPermissions) !== JSON.stringify(registered.additionalRequiredPermissions)
    || (!available.enabled && !available.disabledReason.trim()))
    throw new Error('承接版本正式发布动作与服务端身份、职责或可用性不一致。')
  return { ...cloneAction(registered), displayName: available.displayName, apiPath,
    role: available.role, allowedRoles: available.role, enabled: available.enabled, disabledReason: available.disabledReason }
}

// Task allocation is separate from receipt and later start/report actions.

export const WORKSHOP_TASK_ACTION_CONTRACTS = Object.freeze([
  ['saveDraft', 'production.task.draft.save', '保存任务草稿', ['not_created', 'draft'], 'save_task_draft', '/api/planning/workshop-tasks/draft/'],
  ['dispatch', 'production.task.dispatch', '正式派工', ['draft'], 'dispatch_task', '/api/planning/workshop-tasks/{taskId}/dispatch/'],
].map(([key, actionCode, displayName, allowedStatuses, validator, apiPathTemplate]) => Object.freeze({
  key, actionId: actionCode, actionCode, actionName: displayName, displayName,
  moduleCode: 'production-workshop-task', actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: actionCode, requiredPermission: actionCode, serverPermission: actionCode,
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server',
  allowedStatuses: Object.freeze(allowedStatuses), organizationScope: 'legal_entity',
  serverValidator: `planning.workshop_task_service.${validator}`, serverEligibilityCheck: true, requiresEligibility: true,
  httpMethod: 'POST', apiPathTemplate, executionAvailabilitySource: 'availableActions',
})))
contracts.push(Object.freeze({ currentModule: 'production-workshop-task', canonicalName: '车间任务／派工',
  route: '/planning/workshop-tasks', nextModule: 'production-operation-start', nextCanonicalName: '工序开工', nextRoute: '/planning/operation-starts',
  actions: WORKSHOP_TASK_ACTION_CONTRACTS, forbiddenActions: Object.freeze(['production.operation.start', 'production.operation.report']),
}))
export function resolvePceWorkshopTaskActions(facts) {
  const result = {}
  for (const registered of WORKSHOP_TASK_ACTION_CONTRACTS) {
    const available = facts?.availableActions?.[registered.key]
    const apiPath = registered.key === 'dispatch' && !facts?.selectedTask ? null
      : registered.apiPathTemplate.replace('{taskId}', String(facts?.selectedTask?.id || ''))
    if (!available || available.actionCode !== registered.actionCode || available.displayName !== registered.displayName
      || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string') {
      throw new Error('车间任务公共动作登记与服务端可用动作不一致。')
    }
    result[registered.key] = { ...cloneAction(registered), apiPath,
      enabled: available.enabled, disabledReason: available.disabledReason }
  }
  return result
}

export const OPERATION_START_ACTION_CONTRACT = Object.freeze({
  key: 'start', actionId: 'production.operation.start', actionCode: 'production.operation.start',
  actionName: '开工', displayName: '开工', moduleCode: 'production-operation-start',
  actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: 'production.operation.start', requiredPermission: 'production.operation.start', serverPermission: 'production.operation.start',
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
  allowedStatuses: Object.freeze(['waiting']), serverValidator: 'planning.operation_start_service.start_operation',
  serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
  apiPathTemplate: '/api/planning/operation-starts/{taskId}/start/', executionAvailabilitySource: 'availableActions',
})
contracts.push(Object.freeze({ currentModule: 'production-operation-start', canonicalName: '工序开工',
  route: '/planning/operation-starts', nextModule: 'production-operation-report', nextCanonicalName: '工序报工', nextRoute: '/planning/operation-reports',
  actions: Object.freeze([OPERATION_START_ACTION_CONTRACT]),
  forbiddenActions: Object.freeze(['production.task.dispatch', 'production.operation.report', 'production.operation.complete', 'production.operation.transfer']),
}))
export function resolvePceOperationStartAction(facts) {
  const registered = OPERATION_START_ACTION_CONTRACT, available = facts?.availableActions?.start
  const apiPath = facts?.selectedTask ? registered.apiPathTemplate.replace('{taskId}', String(facts.selectedTask.taskId)) : null
  if (!available || available.actionCode !== registered.actionCode || available.displayName !== registered.displayName
    || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string') {
    throw new Error('工序开工公共动作登记与服务端可用动作不一致。')
  }
  return { ...cloneAction(registered), apiPath, enabled: available.enabled, disabledReason: available.disabledReason }
}


export const OPERATION_REPORT_ACTION_CONTRACT = Object.freeze({
  key: 'report', actionId: 'production.operation.report', actionCode: 'production.operation.report',
  actionName: '提交本次报工', displayName: '提交本次报工', moduleCode: 'production-operation-report',
  actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: 'production.operation.report', requiredPermission: 'production.operation.report', serverPermission: 'production.operation.report',
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
  allowedStatuses: Object.freeze(['open']), serverValidator: 'planning.operation_report_service.report_operation',
  serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
  apiPathTemplate: '/api/planning/operation-reports/{taskId}/report/', executionAvailabilitySource: 'availableActions',
})
export const OPERATION_EXECUTION_CONFIRM_ACTION_CONTRACT = Object.freeze({
  ...OPERATION_REPORT_ACTION_CONTRACT,
  key: 'confirmExecution', actionId: 'production.operation.confirm_execution', actionCode: 'production.operation.confirm_execution',
  actionName: '登记实际经过', displayName: '登记实际经过', allowedStatuses: Object.freeze(['unconfirmed']),
  serverValidator: 'planning.operation_execution_confirmation_service.confirm_execution',
  processCode: 'MES_PRODUCTION_OPERATION', workflowNodeCode: 'PRODUCTION_OPERATION_REPORT',
  requiredResponsibility: 'RESP_PROD_OPERATION_REPORT_001',
  objectType: 'ProductionOperationExecutionConfirmation', assessmentSourceObjectType: 'ProductionWorkshopTask',
  apiPathTemplate: '/api/planning/operation-reports/{taskId}/confirm-execution/',
})
contracts.push(Object.freeze({ currentModule: 'production-operation-report', canonicalName: '工序报工',
  route: '/planning/operation-reports', nextModule: 'production-operation-completion', nextCanonicalName: '工序完工', nextRoute: '/planning/operation-completions',
  actions: Object.freeze([OPERATION_REPORT_ACTION_CONTRACT, OPERATION_EXECUTION_CONFIRM_ACTION_CONTRACT]),
  forbiddenActions: Object.freeze(['production.task.dispatch', 'production.operation.start', 'production.operation.complete', 'production.operation.transfer']),
}))
export function resolvePceOperationReportAction(facts) {
  const nonquantified = facts?.selectedTask?.executionMode === 'NON_QUANTIFIED_REQUIRED'
  const registered = nonquantified ? OPERATION_EXECUTION_CONFIRM_ACTION_CONTRACT : OPERATION_REPORT_ACTION_CONTRACT
  const available = facts?.availableActions?.[registered.key]
  const apiPath = facts?.selectedTask ? registered.apiPathTemplate.replace('{taskId}', String(facts.selectedTask.taskId)) : null
  const displayName = nonquantified && facts.selectedTask.executionConfirmation ? '已登记实际经过' : registered.displayName
  if (!available || available.actionCode !== registered.actionCode || available.displayName !== displayName
    || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string') {
    throw new Error('工序报工公共动作登记与服务端可用动作不一致。')
  }
  if (nonquantified && (['requiredPermission', 'serverValidator', 'processCode', 'workflowNodeCode', 'requiredResponsibility', 'objectType', 'assessmentSourceObjectType']
    .some(key => available[key] !== registered[key])
    || facts.availableActions.report?.enabled !== false || facts.selectedTask.executionConfirmation && available.enabled)) {
    throw new Error('无统计量实际经过动作、报工权限或防重复准入不一致。')
  }
  return { ...cloneAction(registered), displayName, apiPath, enabled: available.enabled, disabledReason: available.disabledReason }
}

export const OPERATION_COMPLETION_ACTION_CONTRACTS = Object.freeze(Object.fromEntries([
  ['request', 'production.operation.complete.request', '提交完工申请', 'unrequested'],
  ['approve', 'production.operation.complete.approve', '审核完工数据', 'pending_review'],
].map(([key, actionCode, displayName, status]) => [key, Object.freeze({
  key, actionId: actionCode, actionCode, actionName: displayName, displayName, moduleCode: 'production-operation-completion',
  actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
  permission: actionCode, requiredPermission: actionCode, serverPermission: actionCode,
  role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
  allowedStatuses: Object.freeze([status]), serverValidator: 'planning.operation_completion_service.execute_completion',
  serverEligibilityCheck: true, requiresEligibility: true, httpMethod: 'POST',
  apiPathTemplate: `/api/planning/operation-completions/{taskId}/${key}/`, executionAvailabilitySource: 'availableActions',
})])))
contracts.push(Object.freeze({ currentModule: 'production-operation-completion', canonicalName: '工序完工',
  route: '/planning/operation-completions', nextModule: OPERATION_HANDOVER_PAGE.moduleId, nextCanonicalName: OPERATION_HANDOVER_PAGE.title, nextRoute: OPERATION_HANDOVER_PAGE.route,
  actions: Object.freeze(Object.values(OPERATION_COMPLETION_ACTION_CONTRACTS)),
  forbiddenActions: Object.freeze(['production.task.dispatch', 'production.operation.start', 'production.operation.report', 'production.operation.transfer']),
}))
export const OPERATION_COMPLETION_V3_ACTION_CONTRACTS = Object.freeze(Object.fromEntries([
  ['request', 'production.operation.complete.v3.request', '提交完工申请', 'request', 'production.operation.complete.request'],
  ['approve', 'production.operation.complete.v3.approve', '审核完工数据', 'approve', 'production.operation.complete.approve'],
  ['withdrawReplace', 'production.operation.complete.withdraw_replace', '撤回待审并关联替代', 'withdraw-and-replace', 'production.operation.complete.withdraw_replace'],
].map(([key, code, label, suffix, permission]) => [key, Object.freeze({ ...OPERATION_COMPLETION_ACTION_CONTRACTS[key === 'withdrawReplace' ? 'request' : key],
  key, actionId: code, actionCode: code, actionName: label, displayName: label, permission, requiredPermission: permission, serverPermission: permission,
  allowedStatuses: Object.freeze(key === 'request' ? ['unrequested'] : ['pending_review']),
  serverValidator: 'planning.operation_completion_v3_authority.execute',
  apiPathTemplate: `/api/planning/operation-completions/{taskId}/${suffix}/` })])))
const completionContractIndex = contracts.findIndex(row => row.currentModule === 'production-operation-completion')
contracts[completionContractIndex] = Object.freeze({ ...contracts[completionContractIndex],
  actions: Object.freeze([...contracts[completionContractIndex].actions, ...Object.values(OPERATION_COMPLETION_V3_ACTION_CONTRACTS)]) })
export function resolvePceOperationCompletionAction(facts, key) {
  const registered = (key === 'withdrawReplace' || facts?.selectedTask?.completionProtocolVersion === 3 ? OPERATION_COMPLETION_V3_ACTION_CONTRACTS : OPERATION_COMPLETION_ACTION_CONTRACTS)[key],
    available = key === 'withdrawReplace' ? facts?.selectedTask?.completionV3?.availableActions?.[key] : facts?.availableActions?.[key]
  if (!registered) throw new Error('工序完工动作未注册。')
  const apiPath = facts?.selectedTask ? registered.apiPathTemplate.replace('{taskId}', String(facts.selectedTask.taskId)) : null
  if (!available || available.actionCode !== registered.actionCode || available.displayName !== registered.displayName
    || available.apiPath !== apiPath || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string') {
    throw new Error('工序完工公共动作登记与服务端可用动作不一致。')
  }
  if ((key==='withdrawReplace' || facts?.selectedTask?.completionProtocolVersion===3)
    && (available.requiredPermission!==registered.requiredPermission || available.serverValidator!==registered.serverValidator || available.httpMethod!=='POST')) {
    throw new Error('V3完工动作的正式权限、服务权威或提交方式不一致。')
  }
  return { ...cloneAction(registered), apiPath, enabled: available.enabled, disabledReason: available.disabledReason }
}

contracts.push(Object.freeze({ currentModule: OPERATION_HANDOVER_PAGE.moduleId, canonicalName: OPERATION_HANDOVER_PAGE.title,
  route: OPERATION_HANDOVER_PAGE.route, nextModule: 'routing-management', nextCanonicalName: '订单路线引用及执行安排', nextRoute: '/pde/routings',
  actions: Object.freeze(Object.values(OPERATION_HANDOVER_ACTION_CONTRACTS)),
  forbiddenActions: Object.freeze(['production.task.dispatch', 'production.operation.start', 'production.operation.report', 'production.operation.complete']),
}))

export function resolvePceOperationRangeReceiptAction(facts, releaseId) {
  const record = facts?.rangeReleases?.find(row => row.id === releaseId)
  const available = record?.receiptAction, registered = OPERATION_HANDOVER_ACTION_CONTRACTS.receive
  if (!record || !available || available.actionCode !== registered.actionCode || available.requiredPermission !== registered.requiredPermission
    || available.displayName !== registered.displayName || available.serverValidator !== registered.serverValidator
    || available.httpMethod !== 'POST' || available.apiPath !== OPERATION_RANGE_RECEIVE_API || available.requestObjectId !== record.id
    || !Number.isSafeInteger(available.sourceTaskId) || !Number.isSafeInteger(available.targetTaskId)
    || typeof available.enabled !== 'boolean' || typeof available.disabledReason !== 'string') throw new Error('当前准确来源范围接收动作尚未由服务端完整核实。')
  return { ...cloneAction(registered), key: 'range.receive', apiPath: available.apiPath, objectId: record.id,
    sourceTaskId: available.sourceTaskId, targetTaskId: available.targetTaskId,
    enabled: available.enabled, disabledReason: available.disabledReason }
}

export function resolvePceOperationHandoverAction(facts, key) {
  const registered = OPERATION_HANDOVER_ACTION_CONTRACTS[key], available = facts?.availableActions?.[key]
  if (!registered || !available || available.actionCode !== registered.actionCode
    || available.displayName !== registered.displayName || available.requiredPermission !== registered.requiredPermission
    || available.serverValidator !== registered.serverValidator || typeof available.enabled !== 'boolean'
    || typeof available.disabledReason !== 'string' || available.httpMethod !== 'POST') {
    throw new Error('工序交接公共动作登记与当前服务端动作事实不一致。')
  }
  let objectId = null
  if (registered.apiPathTemplate.includes('{objectId}')) {
    const pattern = registered.apiPathTemplate.split('{objectId}').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('([1-9]\\d*)')
    const match = typeof available.apiPath === 'string' && available.apiPath.match(new RegExp(`^${pattern}$`))
    if (!match && (available.enabled || available.apiPath !== null)) throw new Error('本次交接动作未绑定准确正式对象。')
    if (match) objectId = Number(match[1])
    const selected = facts?.[registered.objectField]
    if (selected && objectId !== null && Number(selected.id ?? selected.outputId ?? selected.handoverId) !== objectId) {
      throw new Error('本次动作对象与所选正式对象不一致。')
    }
  } else if (available.apiPath !== registered.apiPathTemplate) throw new Error('正式交接动作接口身份不一致。')
  const hashObject = facts?.[key === 'exception.submit' ? 'selectedException' : registered.objectField]
  const expectedObjectId = hashObject ? Number(hashObject.id) : null
  if (Object.hasOwn(available,'requestObjectId')) {
    if (available.requestObjectId !== expectedObjectId || objectId !== null && available.requestObjectId !== objectId) {
      throw new Error('正式交接动作的原请求对象与当前明确对象不一致。')
    }
    objectId = available.requestObjectId
  } else if (registered.objectField && !registered.apiPathTemplate.includes('{objectId}') || key === 'exception.submit' && hashObject) {
    throw new Error('服务端尚未明确本动作原请求所绑定的对象，不能提交。')
  }
  return { ...cloneAction(registered), apiPath: available.apiPath, objectId,
    role: available.role, allowedRoles: available.role, enabled: available.enabled, disabledReason: available.disabledReason }
}


// Financial execution remains forbidden for every native MES page.
for (let index = 0; index < contracts.length; index += 1) {
  const row = contracts[index]
  if (['production-workshop-task', 'production-operation-start', 'production-operation-report', 'production-operation-completion', 'production-operation-handover'].includes(row.currentModule)) {
    contracts[index] = Object.freeze({ ...row, forbiddenActions: Object.freeze([...new Set([...row.forbiddenActions, ...forbiddenExecutionActions, 'create-bank-send-task'])]) })
  }
}

contracts.push(Object.freeze({currentModule:FINISHED_GOODS_PAGE.moduleId,canonicalName:FINISHED_GOODS_PAGE.title,route:FINISHED_GOODS_PAGE.route,nextModule:FINISHED_GOODS_PAGE.moduleId,nextCanonicalName:FINISHED_GOODS_PAGE.title,nextRoute:FINISHED_GOODS_PAGE.route,terminal:true,actions:Object.freeze([...Object.values(FINISHED_GOODS_ACTIONS),FINISHED_GOODS_FORMAL_ACTIONS.receive]),forbiddenActions:Object.freeze([...forbiddenExecutionActions,'create-bank-send-task','production.task.dispatch','production.operation.start','production.operation.report'])}))
contracts.push(Object.freeze({currentModule:MES_ENTRY_PAGE.moduleId,canonicalName:MES_ENTRY_PAGE.title,route:MES_ENTRY_PAGE.route,nextModule:MES_ENTRY_PAGE.moduleId,nextCanonicalName:MES_ENTRY_PAGE.title,nextRoute:MES_ENTRY_PAGE.route,terminal:true,actions:Object.freeze([]),forbiddenActions:Object.freeze([...forbiddenExecutionActions,'create-bank-send-task','production.task.dispatch','production.operation.start','production.operation.report'])}))
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


