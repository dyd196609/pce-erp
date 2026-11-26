import { createRouter, createWebHashHistory } from 'vue-router'
import { resolveSchema } from '@/meta/core/schemaResolver'
import { buildModuleHub } from '@/meta/platform/moduleHub'
import { defineAsyncComponent, h, onMounted, ref, shallowRef } from 'vue'
import { applyPageDocumentTitle } from '@/meta/runtime/pageTitleManager'
import BusinessOperationPageShell from '@/meta/components/BusinessOperationPageShell.vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import { createMasterDataPageGovernance } from '@/meta/master-data/masterDataRegistry.js'
import { findPdePageDefinition, pdeOrderEngineeringCalculationGovernance } from '@/meta/pages/pdePageDefinitions.js'
import { foundationCanonicalRouteDefinitions, getFoundationCanonicalModule, resolveFoundationPageState, serializeFoundationMode } from '@/meta/master-data/foundationEntryUnificationRegistry.js'
import { hasUsableServerAuthentication } from '@/meta/runtime/latestBaseDataProviderState.js'
import { exchangeTabAuthenticationHandoff } from '@/api/auth.js'
import { rememberTabIdentity, setTabAuthToken } from '@/meta/runtime/tabAuthenticationContext.js'

const canonicalFoundationLocation = (moduleId, mode = 'view') => {
  const identity = getFoundationCanonicalModule(moduleId)
  if (!identity) throw new Error(`PAGE IDENTITY MISMATCH: router module ${moduleId} is not registered`)
  const view = serializeFoundationMode(mode)
  return view ? { name: identity.routeName, query: { view } } : { name: identity.routeName }
}

const canonicalFoundationRouteRecord = (moduleId) => {
  const identity = getFoundationCanonicalModule(moduleId)
  if (!identity) throw new Error(`PAGE IDENTITY MISMATCH: router module ${moduleId} is not registered`)
  return Object.freeze({
    path: identity.routePath.replace(/^\//, ''),
    name: identity.routeName,
    meta: Object.freeze({ pageCode: identity.pageKey, moduleCode: 'EMD', canonicalModuleId: identity.moduleId, businessObject: identity.displayName, formalModel: identity.dataSource, componentKey: identity.component, dataAdapter: identity.api }),
  })
}

function wrapSchemaPage(routePath) {
  return {
    name: 'SchemaPage',

    setup() {
      const Page = shallowRef(null)
      const loading = ref(true)
      const error = ref(null)

      const init = async () => {
        try {
          Page.value = await resolveSchema({
            path: routePath,
          })
        } catch (e) {
          error.value = e
          console.error('[SCHEMA PAGE ERROR]', e)
        } finally {
          loading.value = false
        }
      }

      onMounted(init)

      return () => {
        if (error.value) {
          return h('div', { class: 'schema-page-error' }, error.value?.message || 'SCHEMA ERROR')
        }

        if (loading.value || !Page.value) {
          return h('div', { class: 'schema-page-loading' }, 'LOADING...')
        }

        return h(Page.value)
      }
    },
  }
}

function wrapBusinessOperationPage(pageStepId, loader) {
  const InnerPage = defineAsyncComponent(loader)
  const WrappedPage = {
    name: `BusinessOperationPage_${pageStepId.replace(/-/g, '_')}`,
    setup() {
      return () =>
        h(PceListPageShell, { moduleId: pageStepId }, {
          default: () => h(BusinessOperationPageShell, { pageStepId }, {
            'business-operation': () => h(InnerPage, { embeddedInCommonShell: true }),
          }),
        })
    },
  }
  WrappedPage.__pceComponentFile = String(loader).match(/(?:@\/|\/src\/)(meta\/pages\/[A-Za-z0-9_.-]+\.vue)/)?.[1] || ''
  return WrappedPage
}

function wrapPceListPage(moduleId, loader, { pageOwnsCanary = false } = {}) {
  const InnerPage = defineAsyncComponent(loader)
  const WrappedPage = {
    name: `PceListPage_${moduleId.replace(/-/g, '_')}`,
    setup() {
      return () =>
        h(PceListPageShell, { moduleId, pageOwnsCanary }, {
          default: () => h(InnerPage),
        })
    },
  }
  WrappedPage.__pceComponentFile = String(loader).match(/(?:@\/|\/src\/)(meta\/pages\/[A-Za-z0-9_.-]+\.vue)/)?.[1] || ''
  return WrappedPage
}

function wrapMasterDataPage(entityCode) {
  const governance = createMasterDataPageGovernance(entityCode)
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/EnterpriseMasterDataPage.vue'))
  return {
    name: `EnterpriseMasterData_${entityCode}`,
    setup() {
      return () => h(PceListPageShell, {
        moduleId: governance.pageCode,
        governance,
      }, {
        default: () => h(InnerPage, { entityCode }),
      })
    },
  }
}

function wrapPdeGovernedPage(pageKind) {
  const definition = findPdePageDefinition(pageKind)
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/PdeFoundationPage.vue'))
  return {
    name: `PdeGovernedPage_${pageKind}`,
    setup() {
      return () => h(PceListPageShell, {
        moduleId: definition.pageCode,
        governance: definition.governance,
      }, {
        default: () => h(InnerPage, { pageKind }),
      })
    },
  }
}

function wrapPdeOrderEngineeringCalculationPage() {
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/PdeOrderEngineeringCalculationPage.vue'))
  return {
    name: 'PdeOrderEngineeringCalculation',
    setup() {
      return () => h(PceListPageShell, {
        moduleId: pdeOrderEngineeringCalculationGovernance.pageCode,
        governance: pdeOrderEngineeringCalculationGovernance,
        compactEmployeeView: true,
      }, {
        default: () => h(InnerPage),
      })
    },
  }
}

function wrapPdeProductVersionManagementPage() {
  const definition = findPdePageDefinition('productVersions')
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/PdeProductVersionManagementPage.vue'))
  return {
    name: 'PdeProductVersionManagement',
    setup() {
      return () => h(PceListPageShell, {
        moduleId: definition.pageCode,
        governance: definition.governance,
      }, {
        default: () => h(InnerPage),
      })
    },
  }
}

function wrapCrossFunctionalReviewPage(moduleId, governance = null) {
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/CrossFunctionalReviewPage.vue'))
  return {
    name: `CrossFunctionalReviewPage_${moduleId.replace(/-/g, '_')}`,
    setup() {
      const orderNo = ref('')
      return () => {
        const crm = moduleId === 'crm-order-reviews'
        const next = governance?.navigation?.next
        const pageGovernance = crm ? {
          ...governance,
          navigation: {
            ...governance.navigation,
            next: {
              ...next,
              pageUrl: orderNo.value ? `${next.pageUrl}?orderNo=${encodeURIComponent(orderNo.value)}` : '',
            },
          },
        } : governance
        return h(PceListPageShell, { moduleId, governance: pageGovernance }, {
          default: () => h(InnerPage, crm ? {
            onReviewOrderContext: value => { orderNo.value = value },
          } : undefined),
        })
      }
    },
  }
}

const supplierGovernance = Object.freeze({
  reconciliation: {
    version: 'V1.14.2.8.4.8.1.2', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'supplier-reconciliation',
    purpose: '供应商采购业务对账确认。',
    allowed: ['√ 查看来源', '√ 查看状态', '√ 查看评价基础数据'],
    forbidden: ['× 直接付款', '× 银行发送', '× 资金扣减', '× 总账处理'],
    flowSteps: ['采购订单', '收货', '质量检验', '入库', '供应商对账', '应付确认', '付款申请'],
    currentFlowStep: '供应商对账', navigation: { previous: '入库', next: '应付确认' },
  },
  supplier: {
    version: 'V1.14.2.8.4.8.1.2', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'supplier-performance',
    purpose: '供应商采购履约与结算评价基础数据分析。',
    allowed: ['√ 查看来源', '√ 查看状态', '√ 查看评价基础数据'],
    forbidden: ['× 直接付款', '× 银行发送', '× 资金扣减', '× 总账处理'],
    flowSteps: ['采购订单', '交付', '质量', '价格', '服务', '综合评分'],
    currentFlowStep: '综合评分', navigation: { previous: '服务', next: '绩效结果应用' },
  },
  buyer: {
    version: 'V1.14.2.8.4.8.1.2', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'buyer-performance',
    purpose: '采购员交期、成本、异常处理和流程执行评价。',
    allowed: ['√ 查看来源', '√ 查看状态', '√ 查看评价基础数据'],
    forbidden: ['× 直接付款', '× 银行发送', '× 资金扣减', '× 总账处理'],
    flowSteps: ['采购需求', '采购订单', '供应商管理', '交付跟踪', '异常处理', '绩效评价'],
    currentFlowStep: '绩效评价', navigation: { previous: '异常处理', next: '绩效结果应用' },
  },
})

function wrapSupplierGovernedPage(kind) {
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/SupplierPerformanceBasePage.vue'))
  return {
    name: `SupplierGovernedPage_${kind}`,
    setup() {
      return () => h(PceListPageShell, {
        moduleId: supplierGovernance[kind].pageCode,
        governance: supplierGovernance[kind],
      }, { default: () => h(InnerPage, { kind }) })
    },
  }
}

const supplierV82Governance = Object.freeze({
  difference: {
    version: 'V1.14.2.8.4.8.2', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'supplier-reconciliation-differences',
    purpose: '分析采购、收货、质量、入库之间差异。',
    allowed: ['√ 查看差异', '√ 查看来源', '√ 查看责任'],
    forbidden: ['× 付款', '× 银行发送', '× 财务处理'],
    flowSteps: ['采购订单', '收货', '质量检验', '入库', '供应商对账', '差异分析', '供应商确认'],
    currentFlowStep: '差异分析', navigation: { previous: '供应商对账', next: '供应商确认' },
  },
  confirmation: {
    version: 'V1.14.2.8.4.8.2', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'supplier-reconciliation-confirmations',
    purpose: '供应商确认差异处理结果并保留协同记录。',
    allowed: ['√ 查看确认', '√ 查看差异来源', '√ 查看处理结果'],
    forbidden: ['× 付款', '× 银行发送', '× 财务处理'],
    flowSteps: ['供应商对账', '差异分析', '供应商沟通', '供应商确认', '内部复核', '协同完成'],
    currentFlowStep: '供应商确认', navigation: { previous: '差异分析', next: '内部复核' },
  },
  buyerException: {
    version: 'V1.14.2.8.4.8.2', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'buyer-exception-analysis',
    purpose: '分析采购员负责订单、差异和供应商问题，不用于处罚。',
    allowed: ['√ 查看采购责任', '√ 查看差异统计', '√ 查看管理评分'],
    forbidden: ['× 处罚执行', '× 付款', '× 财务处理'],
    flowSteps: ['采购订单', '供应商履约', '差异识别', '责任分析', '管理评价'],
    currentFlowStep: '责任分析', navigation: { previous: '差异识别', next: '管理评价' },
  },
})

function wrapSupplierV82Page(kind) {
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/SupplierReconciliationV82Page.vue'))
  return {
    name: `SupplierV82Page_${kind}`,
    setup() {
      const governance = supplierV82Governance[kind]
      return () => h(PceListPageShell, {
        moduleId: governance.pageCode,
        governance,
      }, { default: () => h(InnerPage, { kind }) })
    },
  }
}

const supplierV83Governance = Object.freeze({
  payable: {
    version: 'V1.14.2.8.4.8.3.1.1', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'supplier-payable-confirmation',
    purpose: '依据已完成对账、已关闭差异与供应商确认结果形成应付业务确认。',
    allowed: ['✓ 查看应付确认', '✓ 查看来源对象', '✓ 查看状态历史'],
    forbidden: ['× 付款执行', '× 银行发送', '× 资金扣减', '× 总账处理'],
    flowSteps: ['供应商对账', '差异关闭', '供应商确认', '应付确认', '付款申请'],
    currentFlowStep: '应付确认', navigation: { previous: '供应商确认', next: '付款申请' },
  },
  request: {
    version: 'V1.14.2.8.4.8.3.1.1', frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM', pageCode: 'supplier-payment-request',
    purpose: '基于已确认应付金额形成付款申请记录，不代表付款执行。',
    allowed: ['✓ 查看付款申请', '✓ 查看应付依据', '✓ 查看状态历史'],
    forbidden: ['× 付款执行', '× 银行发送', '× 资金扣减', '× 生成银行流水'],
    flowSteps: ['供应商对账', '差异关闭', '供应商确认', '应付确认', '付款申请'],
    currentFlowStep: '付款申请', navigation: { previous: '应付确认', next: '后续付款审批链' },
  },
})

function wrapSupplierV83Page(kind) {
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/SupplierPayableV83Page.vue'))
  return {
    name: `SupplierV83Page_${kind}`,
    setup() {
      const governance = supplierV83Governance[kind]
      return () => h(PceListPageShell, {
        moduleId: governance.pageCode,
        governance,
      }, { default: () => h(InnerPage, { kind }) })
    },
  }
}

const supplierV84Governance = Object.freeze({
  paymentStatus: {
    version: 'V1.14.2.8.4.8.4',
    frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM',
    pageCode: 'supplier-payment-status',
    purpose: '记录供应商付款业务状态，不执行付款。',
    allowed: ['✓ 查看付款状态', '✓ 查看状态历史', '✓ 记录结算完成'],
    forbidden: ['× 付款执行', '× 银行发送', '× 资金扣减', '× 财务处理'],
    flowSteps: ['付款申请', '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效'],
    currentFlowStep: '付款状态记录',
    navigation: { previous: '付款申请', next: '供应商结算完成' },
  },
  completion: {
    version: 'V1.14.2.8.4.8.4',
    frameworkVersion: 'PCE Enterprise Page V2',
    businessModule: 'SCM',
    pageCode: 'supplier-settlement-completion',
    purpose: '确认供应商结算闭环，并提供绩效更新来源。',
    allowed: ['✓ 查看结算状态', '✓ 查看绩效来源', '✓ 确认结算完成'],
    forbidden: ['× 付款执行', '× 银行发送', '× 资金扣减', '× 财务处理'],
    flowSteps: ['付款申请', '付款状态记录', '供应商结算完成', '供应商绩效', '采购员绩效'],
    currentFlowStep: '供应商结算完成',
    navigation: { previous: '付款状态记录', next: '供应商绩效' },
  },
})

function wrapSupplierV84Page(kind) {
  const InnerPage = defineAsyncComponent(() => import('@/meta/pages/SupplierSettlementV84Page.vue'))
  return {
    name: `SupplierV84Page_${kind}`,
    setup() {
      const governance = supplierV84Governance[kind]
      return () => h(PceListPageShell, {
        moduleId: governance.pageCode,
        governance,
      }, { default: () => h(InnerPage, { kind }) })
    },
  }
}

const moduleHub = buildModuleHub()
const knownModulePaths = new Set((moduleHub.menu || []).map((item) => item.path))
function resolveListFallback(path = '') {
  const normalized = String(path || '').split('?')[0]
  const matches = Array.from(knownModulePaths)
    .filter((modulePath) => normalized === modulePath || normalized.startsWith(`${modulePath}/`))
    .sort((a, b) => b.length - a.length)

  return matches[0] || '/process-center'
}

const moduleRoutes = Array.from(
  new Map((moduleHub.routes || []).map((entry) => [entry.path, entry])).values()
).map((entry) => ({
  path: entry.path.replace(/^\//, ''),
  component: wrapSchemaPage(entry.path),
}))

const routes = [
  {
    path: '/account-shortcuts',
    name: 'AccountShortcuts',
    component: () => import('@/meta/pages/AccountShortcutsPage.vue'),
  },
  {
    path: '/system-login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/login',
    component: () => import('@/meta/pages/LoginPage.vue'),
  },
  {
    path: '/onboarding',
    component: () => import('@/meta/pages/OnboardingPage.vue'),
  },
  {
    path: '/pricing',
    component: () => import('@/meta/pages/PricingPage.vue'),
  },
  {
    path: '/',
    component: () => import('@/meta/shell/ProfitCockpit.vue'),
    children: [
      {
        path: '',
        redirect: '/process-center',
      },
      {
        path: 'dashboard',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'dashboard' },
      },
      {
        path: 'organization',
        component: wrapPceListPage('erp-access-control', () => import('@/meta/pages/AccessControlFoundationPage.vue')),
      },
      {
        path: 'organization-directory',
        component: wrapPceListPage('organization-directory-v1', () => import('@/meta/pages/OrganizationDirectoryPage.vue')),
      },
      {
        path: 'organization-model',
        component: wrapPceListPage('enterprise-organization-model-v1', () => import('@/meta/pages/EnterpriseOrganizationModelPage.vue')),
      },
      {
        path: 'organization-model/departments',
        component: wrapPceListPage('enterprise-department-model-v1', () => import('@/meta/pages/EnterpriseDepartmentModelPage.vue')),
      },
      {
        path: 'organization-model/positions',
        component: wrapPceListPage('enterprise-position-model-v1', () => import('@/meta/pages/EnterprisePositionModelPage.vue')),
      },
      {
        path: 'organization/master-data-executor-preview',
        name: 'MasterDataExecutorPreview',
        meta: { pageCode: 'master-data-executor-preview', moduleCode: 'SYSTEM', businessObject: 'MasterDataExecutorDecision', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/MasterDataExecutorPreviewPage.vue'),
      },
      {
        path: 'organization/departments',
        redirect: '/organization?tab=departments',
      },
      {
        path: 'organization/positions',
        redirect: '/organization?tab=positions',
      },
      {
        path: 'organization/employees',
        redirect: '/organization?tab=employees',
      },
      {
        path: 'organization/users',
        redirect: '/organization?tab=users',
      },
      {
        path: 'organization/roles',
        redirect: '/organization?tab=roles',
      },
      {
        path: 'organization/permissions',
        redirect: '/organization?tab=permissions',
      },
      {
        path: 'organization/department/:id',
        name: 'OrganizationDepartmentAction',
        redirect: '/organization?tab=departments',
      },
      {
        path: 'organization/role/:id',
        name: 'OrganizationRoleAction',
        redirect: '/organization?tab=roles',
      },
      {
        path: 'organization/user/:id',
        name: 'OrganizationUserAction',
        redirect: '/organization?tab=users',
      },
      {
        path: 'organization/permission/:id',
        name: 'OrganizationPermissionAction',
        redirect: '/organization?tab=permissions',
      },
      {
        path: 'process-center',
        component: () => import('@/meta/pages/ProcessCenterRoutePage.vue'),
        props: { view: 'process-center' },
        meta: { runtimeCode: 'ProcessCenterRuntime',
          runtimeModelType: 'ProcessCenterRuntimeModel' },
      },
      {
        path: 'process-center/process/:id',
        redirect: to => `/process-designer/process/${to.params.id}`,
      },
      {
        path: 'process-center/process/:id/create',
        redirect: '/process-designer/process/new',
      },
      {
        path: 'process-center/process/:id/edit',
        redirect: to => `/process-designer/process/${to.params.id}/edit`,
      },
      {
        path: 'process-center/process/:id/execute',
        redirect: to => `/process-designer/process/${to.params.id}/execute`,
      },
      {
        path: 'process-designer',
        name: 'ProcessDesigner',
        component: () => import('@/meta/pages/ProcessDesignerPage.vue'),
      },
      {
        path: 'process-designer/process/new',
        name: 'ProcessDesignerCreate',
        component: () => import('@/meta/pages/ProcessDesignerPage.vue'),
      },
      {
        path: 'process-designer/process/:id',
        name: 'ProcessDesignerDetail',
        component: () => import('@/meta/pages/ProcessDesignerPage.vue'),
      },
      {
        path: 'process-designer/process/:id/edit',
        name: 'ProcessDesignerEdit',
        component: () => import('@/meta/pages/ProcessDesignerPage.vue'),
      },
      {
        path: 'process-designer/process/:id/execute',
        name: 'ProcessDesignerExecute',
        component: () => import('@/meta/pages/ProcessDesignerPage.vue'),
      },
      {
        path: 'work-center',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'work-center' },
      },
      {
        path: 'work-center/task/:id',
        name: 'WorkTaskAction',
        redirect: '/organization?tab=permissions',
      },
      {
        path: 'work-center/approval/:id',
        name: 'ApprovalAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'work-center/execution/:id',
        name: 'ExecutionAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'analytics',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'analytics' },
      },
      {
        path: 'admin',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'admin' },
      },
      {
        path: 'admin/config/:key',
        name: 'AdminConfig',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'admin/role-permission',
        name: 'AdminRolePermission',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'admin/process-template',
        name: 'AdminProcessTemplate',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'admin/tenant-setting',
        name: 'AdminTenantSetting',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'admin/approval-flow-config',
        name: 'ApprovalFlowConfig',
        meta: {
          pageCode: 'approval-flow-config',
          moduleCode: 'SCM', businessObject: 'ApprovalConfiguration' },
        component: wrapPceListPage('approval-flow-config', () => import('@/meta/pages/ApprovalFlowConfigPage.vue')),
      },
      {
        path: 'manufacturing',
        redirect: '/manufacturing/modules',
      },
      {
        path: 'manufacturing/modules',
        component: () => import('@/meta/pages/ManufacturingOSPage.vue'),
      },
      {
        path: 'manufacturing/plan',
        component: () => import('@/meta/pages/ManufacturingOSPage.vue'),
      },
      {
        path: 'planning/requirements',
        name: 'PlanningRequirements',
        meta: { pageCode: 'planning-requirements', moduleCode: 'PLAN', businessObject: 'PlanningRequirement' },
        component: wrapPceListPage('planning-requirements', () => import('@/meta/pages/PlanningCenterPage.vue')),
      },
      {
        path: 'planning/production-batch-foundation',
        name: 'ProductionBatchFoundationPreview',
        meta: { pageCode: 'production-batch-foundation-preview', moduleCode: 'PLAN', businessObject: 'ProductionBatch', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/ProductionBatchFoundationPreviewPage.vue'),
      },
      {
        path: 'sales/orders',
        name: 'SalesOrders',
        meta: { pageCode: 'sales-orders', moduleCode: 'SALES', businessObject: 'SalesOrder', requiresServerAuthentication: true },
        component: wrapPceListPage('sales-orders', () => import('@/meta/pages/SalesOrderPage.vue')),
      },
      {
        path: 'sales/order-reviews',
        name: 'CrmOrderReviews',
        meta: { pageCode: 'crm-order-reviews', moduleCode: 'CRM', businessObject: 'CrmOrderReview', reviewType: 'CRM_ORDER_REVIEW', requiresServerAuthentication: true },
        component: wrapCrossFunctionalReviewPage('crm-order-reviews', {
          version: 'CRM-ORDER-REVIEW-V1.0', frameworkVersion: 'PCE Enterprise Page V2',
          businessModule: 'CRM', pageName: '订单评审', pageCode: 'crm-order-reviews',
          purpose: '判断能否接单，以及按什么商业条件接单。',
          allowed: ['✓ 查看订单与工程依据', '✓ 记录商务评审意见与待补条件'],
          forbidden: ['× 自动批准生产可行性', '× 自动建立正式订单', '× 绕过业务资格'],
          flowSteps: ['接单', '订单评审', '产品设计'], currentFlowStep: '订单评审',
          navigation: {
            previous: { label: '接单', pageCode: 'sales-orders', pageUrl: '/sales/orders' },
            current: { label: '订单评审', pageCode: 'crm-order-reviews', pageUrl: '/sales/order-reviews' },
            next: { label: '产品设计', pageCode: 'pde-product-definitions', pageUrl: '/pde/product-definitions' },
          },
          returnModuleCode: 'CRM', positioning: '营销业务中心订单业务流程',
        }),
      },
      {
        path: 'manufacturing/module/:moduleId',
        component: () => import('@/meta/pages/ManufacturingOSPage.vue'),
      },
      {
        path: 'pde/workbench',
        name: 'PdeProductEngineeringWorkbenchLegacyRedirect',
        redirect: to => ({
          path: '/process-center',
          query: { ...to.query, module: 'PDE' },
          hash: to.hash,
        }),
      },
      {
        path: 'pde/engineering-calculations',
        name: 'PdeOrderEngineeringCalculation',
        meta: { pageCode: 'pde-order-engineering-calculation', moduleCode: 'PDE', businessObject: 'EngineeringCalculationRecord', requiresServerAuthentication: true },
        component: wrapPdeOrderEngineeringCalculationPage(),
      },
      {
        path: 'pde/product-requirements',
        name: 'PdeProductRequirements',
        meta: { pageCode: 'pde-product-requirements', moduleCode: 'PDE', businessObject: 'PdeProductRequirements', requiresServerAuthentication: true },
        component: wrapPdeGovernedPage('requirements'),
      },
      {
        path: 'pde/product-requirement-reviews',
        name: 'PdeProductRequirementReviews',
        meta: { pageCode: 'pde-product-requirement-reviews', moduleCode: 'PDE', businessObject: 'PdeProductionFeasibilityReview', reviewType: 'PDE_PRODUCTION_FEASIBILITY', requiresServerAuthentication: true },
        component: wrapCrossFunctionalReviewPage('pde-product-requirement-reviews', findPdePageDefinition('requirementReviews').governance),
      },
      {
        path: 'pde/product-definitions',
        name: 'PdeProductDefinitions',
        meta: { pageCode: 'pde-product-definitions', moduleCode: 'PDE', businessObject: 'OrderLineProductDesignDraft', requiresServerAuthentication: true },
        component: () => import('@/meta/pages/PdeProductDesignPage.vue'),
      },
      {
        path: 'pde/product-boms',
        name: 'PdeProductBoms',
        component: wrapPdeGovernedPage('boms'),
      },
      {
        path: 'pde/routings',
        name: 'PdeRoutings',
        meta: { pageCode: 'pde-routings', moduleCode: 'PDE', businessObject: 'PdeRoutings', requiresServerAuthentication: true },
        component: wrapPdeGovernedPage('routings'),
      },
      {
        path: 'pde/engineering-documents',
        name: 'PdeEngineeringDocuments',
        meta: { pageCode: 'pde-engineering-documents', moduleCode: 'PDE', businessObject: 'PdeEngineeringDocuments', requiresServerAuthentication: true },
        component: wrapPdeGovernedPage('engineeringDocuments'),
      },
      {
        path: 'pde/product-versions',
        name: 'PdeProductVersions',
        meta: { pageCode: 'pde-product-versions', moduleCode: 'PDE', businessObject: 'OrderEngineeringBaseline / ProductVersion', requiresServerAuthentication: true },
        component: wrapPdeProductVersionManagementPage(),
      },
      {
        path: 'pde/bom-versions',
        name: 'PdeBomVersions',
        component: wrapPdeGovernedPage('bomVersions'),
      },
      {
        path: 'pde/routing-versions',
        name: 'PdeRoutingVersions',
        component: wrapPdeGovernedPage('routingVersions'),
      },
      {
        path: 'pde/engineering-changes',
        name: 'PdeEngineeringChanges',
        component: wrapPdeGovernedPage('engineeringChanges'),
      },
      {
        path: 'pde/trial-production-validations',
        name: 'PdeTrialProductionValidations',
        component: wrapPdeGovernedPage('trialProductionValidations'),
      },
      {
        path: 'pde/mass-production-introductions',
        name: 'PdeMassProductionIntroductions',
        component: wrapPdeGovernedPage('massProductionIntroductions'),
      },
      {
        path: 'pde/engineering-readiness',
        name: 'PdeEngineeringReadiness',
        meta: { pageCode: 'pde-engineering-readiness', moduleCode: 'PDE', businessObject: 'PdeEngineeringReadiness', requiresServerAuthentication: true },
        component: wrapPdeGovernedPage('engineeringReadiness'),
      },
      {
        path: 'pde/manufacturing-outputs',
        name: 'PdeManufacturingOutputs',
        component: wrapPdeGovernedPage('manufacturingOutputs'),
      },
      {
        path: 'pde/manufacturing-admissions',
        name: 'PdeManufacturingAdmissions',
        meta: { pageCode: 'pde-manufacturing-admissions', moduleCode: 'PDE', businessObject: 'SalesOrderManufacturingAdmission', requiresServerAuthentication: true },
        component: wrapPdeGovernedPage('manufacturingAdmissions'),
      },
      {
        path: 'pde/mrp-input-preparation',
        name: 'PdeMrpInputPreparation',
        meta: { pageCode: 'pde-mrp-input-preparation', moduleCode: 'PDE', businessObject: 'PdeMrpInputSource', requiresServerAuthentication: true },
        component: wrapPdeGovernedPage('mrpInputPreparation'),
      },
      {
        path: 'master-data/organizations',
        name: 'MasterDataOrganizations',
        component: wrapMasterDataPage('organizations'),
      },
      {
        ...canonicalFoundationRouteRecord('customer'),
        component: wrapMasterDataPage('customers'),
      },
      {
        ...canonicalFoundationRouteRecord('supplier'),
        component: wrapMasterDataPage('suppliers'),
      },
      {
        path: 'master-data/materials',
        name: 'MasterDataMaterials',
        redirect: canonicalFoundationLocation('material'),
      },
      {
        path: 'master-data/boms',
        name: 'MasterDataBoms',
        redirect: canonicalFoundationLocation('bom'),
      },
      {
        path: 'master-data/routings',
        name: 'MasterDataRoutings',
        redirect: canonicalFoundationLocation('routing'),
      },
      {
        path: 'master-data/warehouses',
        name: 'MasterDataWarehouses',
        redirect: canonicalFoundationLocation('warehouse'),
      },
      {
        path: 'foundation',
        component: () => import('@/meta/pages/EnterpriseFoundationUnifiedPage.vue'),
      },
      {
        path: 'foundation/import-preview',
        name: 'FoundationManufacturingImportPreview',
        meta: { pageCode: 'foundation-manufacturing-import-preview', moduleCode: 'PDE', businessObject: 'FoundationImportPreview', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/FoundationManufacturingImportPreviewPage.vue'),
      },
      {
        path: 'foundation/manual-acceptance-center',
        name: 'BaseDataManualAcceptanceCenter',
        meta: { pageCode: 'base-data-manual-acceptance-center', moduleCode: 'EMD', businessObject: 'BaseDataReadiness', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/BaseDataManualAcceptanceCenterPage.vue'),
      },
      {
        path: 'foundation/base-data-comparison/:entity',
        name: 'BaseDataComparisonPreview',
        meta: { pageCode: 'base-data-comparison-preview', moduleCode: 'EMD', businessObject: 'BaseDataComparison', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/BaseDataComparisonPreviewPage.vue'),
        props: route => ({ entity: String(route.params.entity || 'customers') }),
      },
      {
        path: 'foundation/group2-material-targeted-revalidation',
        name: 'Group2MaterialTargetedRevalidation',
        meta: { pageCode: 'group2-material-targeted-revalidation', moduleCode: 'EMD', businessObject: 'Group2MaterialTargetedRevalidation', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/Group2ComparisonPreviewPage.vue'),
        props: { entity: 'materials' },
      },
      {
        path: 'foundation/group2-comparison/:entity',
        name: 'Group2ComparisonPreview',
        meta: { pageCode: 'group2-comparison-preview', moduleCode: 'EMD', businessObject: 'Group2Comparison', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/Group2ComparisonPreviewPage.vue'),
        props: route => ({ entity: String(route.params.entity || 'materials') }),
      },
      {
        path: 'foundation/group3-acceptance/:entity',
        name: 'Group3ManufacturingEngineeringAcceptance',
        meta: { pageCode: 'group3-manufacturing-engineering-acceptance', moduleCode: 'PDE', businessObject: 'ManufacturingEngineeringAcceptance', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/Group3ManufacturingEngineeringAcceptancePage.vue'),
        props: route => ({ entity: String(route.params.entity || 'operations') }),
      },
      {
        path: 'foundation/group3a-operation-targeted-revalidation',
        name: 'Group3AOperationTargetedRevalidation',
        redirect: canonicalFoundationLocation('operation', 'acceptance'),
      },
      {
        path: 'foundation/validated-fact-formalization',
        name: 'ValidatedFactFormalization',
        meta: { pageCode: 'validated-fact-formalization', moduleCode: 'EMD', businessObject: 'ValidatedBaseData', pageType: 'VALIDATION_PAGE' },
        component: () => import('@/meta/pages/ValidatedFactFormalizationPage.vue'),
      },
      ...foundationCanonicalRouteDefinitions.map(definition => ({
        path: definition.path,
        name: definition.name,
        meta: definition.meta,
        component: () => import('@/meta/components/ProductionFoundationMaintenance.vue'),
        props: { initialEntity: definition.entityKey },
      })),
      {
        path: 'foundation/master-data/:entity',
        name: 'EnterpriseFoundationFormalMaintenance',
        redirect: route => {
          const match = foundationCanonicalRouteDefinitions.find(item => item.entityKey === String(route.params.entity || ''))
          return match ? { name: match.name, query: route.query } : { path: '/foundation', query: { identityError: 'unknown-module' } }
        },
      },
      {
        path: 'foundation/business-partners',
        redirect: canonicalFoundationLocation('supplier'),
      },
      {
        path: 'foundation/suppliers',
        redirect: canonicalFoundationLocation('supplier'),
      },
      {
        path: 'foundation/dealers',
        redirect: canonicalFoundationLocation('customer'),
      },
      {
        path: 'foundation/company-bank-accounts',
        redirect: '/reference/master-data',
      },
      {
        path: 'foundation/review-check',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/import-records',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/pfm/employees',
        redirect: '/organization?tab=employees',
      },
      {
        path: 'foundation/pfm/employee/create',
        redirect: '/organization?tab=employees',
      },
      {
        path: 'foundation/pfm/employee/:id',
        redirect: '/organization?tab=employees',
      },
      {
        path: 'foundation/pfm/skills',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/pfm/certificates',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/pfm/shifts',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/erp/materials',
        redirect: canonicalFoundationLocation('material'),
      },
      {
        path: 'foundation/erp/material/create',
        redirect: canonicalFoundationLocation('material'),
      },
      {
        path: 'foundation/erp/material/:id',
        redirect: canonicalFoundationLocation('material'),
      },
      {
        path: 'foundation/erp/customers',
        redirect: canonicalFoundationLocation('customer'),
      },
      {
        path: 'foundation/erp/customer/create',
        redirect: canonicalFoundationLocation('customer'),
      },
      {
        path: 'foundation/erp/customer/:id',
        redirect: canonicalFoundationLocation('customer'),
      },
      {
        path: 'foundation/erp/suppliers',
        redirect: canonicalFoundationLocation('supplier'),
      },
      {
        path: 'foundation/erp/supplier/create',
        redirect: canonicalFoundationLocation('supplier'),
      },
      {
        path: 'foundation/erp/supplier/:id',
        redirect: canonicalFoundationLocation('supplier'),
      },
      {
        path: 'foundation/erp/work-centers',
        redirect: canonicalFoundationLocation('work-center'),
      },
      {
        path: 'foundation/erp/warehouses',
        redirect: canonicalFoundationLocation('warehouse'),
      },
      {
        path: 'foundation/erp/supplier-material-prices',
        component: () => import('@/meta/pages/FoundationServerRuntimeOperatorPage.vue'),
        props: { runtimeKind: 'price' },
      },
      {
        path: 'pde/a1-foundation',
        name: 'PdeProductionFoundationA1',
        meta: { pageCode: 'pce-production-a1', moduleCode: 'PDE', businessObject: 'ProductionFoundationA1' },
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'pde/wave2-manufacturing-foundation',
        name: 'PdeManufacturingStructureWave2',
        meta: { pageCode: 'pce-foundation-wave2', moduleCode: 'PDE', businessObject: 'ManufacturingStructureWave2' },
        component: () => import('@/meta/pages/ManufacturingStructureWave2Page.vue'),
      },
      {
        path: 'foundation/erp/supplier-price-facts',
        component: wrapPceListPage(
          'foundation-supplier-price-facts',
          () => import('@/meta/pages/SupplierPriceFactPage.vue'),
        ),
      },
      {
        path: 'foundation/erp/supplier-price-analysis',
        component: wrapPceListPage(
          'foundation-supplier-price-analysis',
          () => import('@/meta/pages/SupplierPriceAnalysisPage.vue'),
        ),
      },
      {
        path: 'foundation/erp/material-suppliers',
        component: () => import('@/meta/pages/FoundationServerRuntimeOperatorPage.vue'),
        props: { runtimeKind: 'relation' },
      },
      {
        path: 'foundation/erp/product-categories',
        redirect: canonicalFoundationLocation('product-category'),
      },
      {
        path: 'foundation/manufacturing/processes',
        redirect: canonicalFoundationLocation('operation'),
      },
      {
        path: 'foundation/manufacturing/routings',
        redirect: canonicalFoundationLocation('routing'),
      },
      {
        path: 'foundation/manufacturing/routing/:id',
        redirect: canonicalFoundationLocation('routing'),
      },
      {
        path: 'foundation/manufacturing/equipment',
        redirect: canonicalFoundationLocation('equipment'),
      },
      {
        path: 'foundation/sample-data',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/erp/data-dictionaries',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/erp/coding-rules',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/erp/system-parameters',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/security/permissions',
        redirect: '/organization?tab=permissions',
      },
      {
        path: 'foundation/security/role-permissions',
        redirect: '/organization?tab=roles',
      },
      {
        path: 'foundation/security/user-roles',
        redirect: '/organization?tab=users',
      },
      {
        path: 'foundation/logs/operation',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/warnings/rules',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/warnings/records',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/warnings/subscribers',
        redirect: route => ({ path: '/foundation/legacy-diagnostic', query: { from: route.fullPath } }),
      },
      {
        path: 'foundation/legacy-diagnostic',
        name: 'FoundationLegacyReadOnlyDiagnostic',
        component: () => import('@/meta/pages/LegacyFoundationDiagnosticPage.vue'),
      },
      {
        path: 'reference',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'reference/master-data',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'reference/organization',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'reference/warehouse',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'reference/production',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'reference/warning',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'reference/check',
        component: () => import('@/meta/pages/ProductionFoundationA1Page.vue'),
      },
      {
        path: 'demo/reference',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
        meta: { demoOnly: true, excludedFromFormalGate: true },
      },
      {
        path: 'scm',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-requests',
        name: 'ScmPurchaseRequests',
        redirect: '/scm/purchase-request',
      },
      {
        path: 'scm/purchase-request',
        name: 'ScmPurchaseRequestCanonical',
        meta: { pageCode: 'purchase-request', moduleCode: 'SCM',
          businessObject: 'PurchaseRequest', tableId: 'purchase_request', schema: 'PurchaseRequestSchema' },
        component: wrapPceListPage('purchase-request', () => import('@/meta/pages/ScmPurchaseRequestPage.vue')),
      },
      {
        path: 'scm/purchase-request/create',
        name: 'ScmPurchaseRequestCreate',
        meta: { pageCode: 'purchase-request', moduleCode: 'SCM',
          businessObject: 'PurchaseRequest', tableId: 'purchase_request', schema: 'PurchaseRequestSchema' },
        component: wrapPceListPage('purchase-request', () => import('@/meta/pages/ScmPurchaseRequestPage.vue')),
      },
      {
        path: 'scm/purchase-request/:id',
        name: 'ScmPurchaseRequestDetail',
        meta: { pageCode: 'purchase-request', moduleCode: 'SCM',
          businessObject: 'PurchaseRequest', tableId: 'purchase_request', schema: 'PurchaseRequestSchema' },
        component: wrapPceListPage('purchase-request', () => import('@/meta/pages/ScmPurchaseRequestPage.vue')),
      },
      {
        path: 'scm/purchase-inquiries',
        name: 'ScmPurchaseInquiries',
        redirect: '/scm/purchase-inquiry',
      },
      {
        path: 'scm/purchase-approvals',
        name: 'ScmPurchaseApprovals',
        meta: {
          pageCode: 'purchase-approval',
          moduleCode: 'SCM', businessObject: 'PurchaseRequestApproval',
          previousModule: 'purchase-request', currentModule: 'purchase-approval', nextModule: 'inquiry-preparation' },
        component: wrapPceListPage('purchase-approval', () => import('@/meta/pages/PurchaseApprovalExecutionPage.vue')),
      },
      {
        path: 'scm/inquiry-preparations',
        name: 'ScmInquiryPreparations',
        meta: { pageCode: 'inquiry-preparation',
          moduleCode: 'SCM', businessObject: 'InquiryPreparationContext',
          previousModule: 'purchase-approval', currentModule: 'inquiry-preparation', nextModule: 'purchase-inquiry' },
        component: wrapPceListPage('inquiry-preparation', () => import('@/meta/pages/ScmInquiryPreparationPage.vue')),
      },
      {
        path: 'scm/purchase-inquiry',
        name: 'ScmPurchaseInquiryCanonical',
        meta: { pageCode: 'purchase-inquiry', moduleCode: 'SCM', businessObject: 'PurchaseInquiry',
          previousModule: 'inquiry-preparation', currentModule: 'purchase-inquiry', nextModule: 'supplier-quote',
          tableId: 'purchase_inquiry', schema: 'PurchaseInquirySchema', runtimeVersion: 'V1.14.2.8.18.7' },
        component: wrapPceListPage('purchase-inquiry', () => import('@/meta/pages/ScmPurchaseInquiryNodePage.vue'), { pageOwnsCanary: true }),
      },
      {
        path: 'scm/purchase-inquiry/create',
        name: 'ScmPurchaseInquiryCreate',
        redirect: '/scm/purchase-inquiry',
      },
      {
        path: 'scm/purchase-inquiry/detail/:inquiryNo',
        name: 'ScmPurchaseInquiryDetail',
        meta: { pageCode: 'purchase-inquiry-detail', moduleCode: 'SCM', businessObject: 'PurchaseInquiry' },
        component: () => import('@/meta/pages/ScmPurchaseInquiryDetailPage.vue'),
      },
      {
        path: 'scm/purchase-inquiry/edit/:inquiryNo',
        name: 'ScmPurchaseInquiryEdit',
        meta: { pageCode: 'purchase-inquiry-edit', moduleCode: 'SCM', businessObject: 'PurchaseInquiry' },
        component: () => import('@/meta/pages/ScmPurchaseInquiryEditPage.vue'),
      },
      {
        path: 'scm/purchase-inquiry/acceptance/:inquiryNo',
        name: 'ScmPurchaseInquiryAcceptance',
        meta: { pageCode: 'purchase-inquiry-acceptance', moduleCode: 'SCM', businessObject: 'PurchaseInquiry' },
        component: () => import('@/meta/pages/ScmPurchaseInquiryAcceptancePage.vue'),
      },
      {
        path: 'scm/purchase-inquiry/:id',
        redirect: to => `/scm/purchase-inquiry/detail/${to.params.id}`,
      },
      {
        path: 'scm/supplier-quotation',
        name: 'ScmSupplierQuoteWorkbench',
        meta: {
          pageCode: 'supplier-quote-workbench', moduleCode: 'SCM', businessObject: 'SupplierQuotation', pageOwnsCanary: true,
          previousModule: 'price-approval-preparation', currentModule: 'supplier-quote',
          nextModule: 'quote-comparison-preparation' },
        component: wrapPceListPage('supplier-quote-workbench', () => import('@/meta/pages/ScmSupplierQuoteWorkbenchPage.vue'), { pageOwnsCanary: true }),
      },
      {
        path: 'scm/supplier-quotes',
        redirect: '/scm/supplier-quotation',
      },
      {
        path: 'scm/purchase-request/agreed-price',
        name: 'ScmAgreedPricePurchaseFoundation',
        meta: { pageCode: 'agreed-price-purchase-foundation', moduleCode: 'SCM',
          businessObject: 'PurchaseRequest', tableId: 'supplier_material_price', schema: 'PurchaseRequestSchema' },
        component: () => import('@/meta/pages/ScmAgreedPricePurchaseFoundationPage.vue'),
      },
      {
        path: 'scm/purchase-request/:id/agreed-price-confirmation',
        name: 'ScmAgreedPricePurchaseConfirmation',
        meta: { pageCode: 'agreed-price-purchase-confirmation', moduleCode: 'SCM',
          businessObject: 'PurchaseRequest', schema: 'PurchaseOrderSchema' },
        component: () => import('@/meta/pages/ScmAgreedPricePurchaseConfirmationPage.vue'),
      },
      {
        path: 'scm/supplier-quote',
        redirect: '/scm/supplier-quotation',
      },
      {
        path: 'scm/quote-comparisons',
        name: 'ScmQuoteComparisonWorkbench',
        meta: {
          pageCode: 'quote-comparison-workbench', moduleCode: 'SCM', businessObject: 'QuoteComparison',
          previousModule: 'supplier-quote', currentModule: 'quote-comparison',
          nextModule: 'supplier-recommendation-decision-preparation' },
        component: wrapPceListPage('quote-comparison-workbench', () => import('@/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'), { pageOwnsCanary: true }),
      },
      {
        path: 'scm/quote-comparison',
        redirect: '/scm/quote-comparisons',
      },
      {
        path: 'scm/supplier-recommendation',
        name: 'ScmSupplierRecommendation',
        meta: { pageCode: 'supplier-recommendation',
          moduleCode: 'SCM', businessObject: 'SupplierRecommendationDecisionBatch',
          previousModule: 'quote-comparison', currentModule: 'supplier-recommendation', nextModule: 'purchase-order-gate' },
        component: wrapPceListPage('supplier-recommendation', () => import('@/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')),
      },
      {
        path: 'scm/supplier-recommendations',
        redirect: '/scm/supplier-recommendation',
      },
      {
        path: 'scm/purchase-order-gate',
        name: 'ScmPurchaseOrderGate',
        meta: { pageCode: 'purchase-order-gate',
          moduleCode: 'SCM', businessObject: 'PurchaseOrderCreationGateDecision',
          previousModule: 'supplier-recommendation', currentModule: 'purchase-order-gate', nextModule: 'purchase-order' },
        component: wrapPceListPage('purchase-order-gate', () => import('@/meta/pages/ScmPurchaseOrderGatePage.vue')),
      },
      {
        path: 'scm/price-approvals',
        name: 'ScmPriceApprovals',
        redirect: '/scm/price-approval',
      },
      {
        path: 'scm/price-approval',
        name: 'ScmPriceApprovalCanonical',
        meta: { pageCode: 'price-approval', moduleCode: 'SCM',
          businessObject: 'PriceApprovalPreparation', tableId: 'price_approval_preparation', schema: 'PriceApprovalPreparationSchema' },
        component: wrapPceListPage('price-approval', () => import('@/meta/pages/ScmPriceApprovalRuntimePage.vue')),
      },
      {
        path: 'scm/price-review-assistant',
        component: wrapPceListPage(
          'price-review-assistant',
          () => import('@/meta/pages/PurchasePriceReviewAssistantPage.vue'),
        ),
      },
      {
        path: 'scm/price-approval/create',
        name: 'ScmPriceApprovalCreate',
        redirect: '/scm/price-approval',
      },
      {
        path: 'scm/price-approval/:id',
        name: 'ScmPriceApprovalDetail',
        redirect: '/scm/price-approval',
      },
      {
        path: 'scm/purchase-orders',
        name: 'ScmPurchaseOrders',
        redirect: '/scm/purchase-order',
      },
      {
        path: 'scm/purchase-order',
        name: 'ScmPurchaseOrderCanonical',
        meta: { pageCode: 'purchase-order', moduleCode: 'SCM', tableId: 'purchase_order', schema: 'PurchaseOrderSchema' },
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-order/create',
        name: 'ScmPurchaseOrderCreate',
        meta: { pageCode: 'purchase-order-create', moduleCode: 'SCM', tableId: 'purchase_order', schema: 'PurchaseOrderSchema' },
        component: () => import('@/meta/pages/ScmPurchaseOrderCreateEntryPage.vue'),
      },
      {
        path: 'scm/purchase-order/:id',
        name: 'ScmPurchaseOrderDetail',
        meta: { pageCode: 'purchase-order-detail', moduleCode: 'SCM', tableId: 'purchase_order', schema: 'PurchaseOrderSchema' },
        component: () => import('@/meta/pages/PurchaseOrderDetailPage.vue'),
      },
      {
        path: 'scm/supplier-settlements',
        name: 'ScmSupplierSettlements',
        meta: { },
        component: wrapBusinessOperationPage('supplier-settlement', () => import('@/meta/pages/SupplierSettlementPage.vue')),
      },
      {
        path: 'scm/purchase-reconciliations',
        name: 'ScmPurchaseReconciliations',
        meta: { },
        component: wrapBusinessOperationPage('purchase-reconciliation', () => import('@/meta/pages/PurchaseReconciliationPage.vue')),
      },
      {
        path: 'scm/supplier-reconciliations',
        name: 'ScmSupplierReconciliations',
        meta: { },
        component: wrapSupplierGovernedPage('reconciliation'),
      },
      {
        path: 'scm/buyer-performance',
        name: 'ScmBuyerPerformance',
        meta: { },
        component: wrapSupplierGovernedPage('buyer'),
      },
      {
        path: 'scm/supplier-performance',
        name: 'ScmSupplierPerformance',
        meta: { },
        component: wrapSupplierGovernedPage('supplier'),
      },
      {
        path: 'scm/supplier-reconciliation-differences',
        name: 'ScmSupplierReconciliationDifferences',
        meta: { },
        component: wrapSupplierV82Page('difference'),
      },
      {
        path: 'scm/supplier-reconciliation-confirmations',
        name: 'ScmSupplierReconciliationConfirmations',
        meta: { },
        component: wrapSupplierV82Page('confirmation'),
      },
      {
        path: 'scm/buyer-exception-analysis',
        name: 'ScmBuyerExceptionAnalysis',
        meta: { },
        component: wrapSupplierV82Page('buyerException'),
      },
      {
        path: 'scm/supplier-payable-confirmations',
        name: 'ScmSupplierPayableConfirmations',
        meta: { },
        component: wrapSupplierV83Page('payable'),
      },
      {
        path: 'scm/supplier-payment-requests',
        name: 'ScmSupplierPaymentRequests',
        meta: { },
        component: wrapSupplierV83Page('request'),
      },
      {
        path: 'scm/supplier-payment-status',
        name: 'ScmSupplierPaymentStatus',
        meta: { },
        component: wrapSupplierV84Page('paymentStatus'),
      },
      {
        path: 'scm/supplier-settlement-completions',
        name: 'ScmSupplierSettlementCompletions',
        meta: { },
        component: wrapSupplierV84Page('completion'),
      },
      {
        path: 'wms',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/inventory-balances',
        name: 'WmsInventoryBalances',
        meta: { },
        component: wrapPceListPage('inventory-balances', () => import('@/meta/pages/FormalExecutionPage.vue')),
      },
      {
        path: 'wms/inventory-balance/:id',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/inventory-transactions',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/inventory-transaction/:id',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/warehouse-tasks',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/warehouse-task/:id',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/stock-warnings',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/purchase-receive-preview',
        name: 'WmsPurchaseReceivePreview',
        meta: { },
        component: wrapPceListPage('purchase-receive-preview', () => import('@/meta/pages/PurchaseReceivePage.vue')),
      },
      {
        path: 'wms/purchase-receive-preview/:id',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'wms/purchase-receives',
        name: 'WmsPurchaseReceives',
        meta: { },
        component: () => import('@/meta/pages/PurchaseReceivePage.vue'),
      },
      {
        path: 'wms/purchase-receive/:id',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'qms',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'qms/incoming-inspections',
        name: 'QmsIncomingInspections',
        meta: { },
        component: wrapPceListPage('incoming-inspection', () => import('@/meta/pages/QmsPage.vue')),
      },
      {
        path: 'qms/incoming-inspection/:id',
        component: () => import('@/meta/pages/FormalExecutionPage.vue'),
      },
      {
        path: 'demo/wms',
        component: () => import('@/meta/pages/WmsPage.vue'),
        meta: { demoOnly: true, excludedFromFormalGate: true },
      },
      {
        path: 'demo/qms',
        component: () => import('@/meta/pages/QmsPage.vue'),
        meta: { demoOnly: true, excludedFromFormalGate: true },
      },
      {
        path: 'finance/payable-prepares',
        name: 'FinancePayablePrepares',
        meta: { },
        component: wrapBusinessOperationPage('payable-prepare', () => import('@/meta/pages/PayablePreparePage.vue')),
      },
      {
        path: 'finance/payable-prepare/:id',
        component: () => import('@/meta/pages/PayablePreparePage.vue'),
      },
      {
        path: 'finance/payable-checks',
        name: 'FinancePayableChecks',
        meta: { },
        component: wrapBusinessOperationPage('payable-check', () => import('@/meta/pages/PayableCheckPage.vue')),
      },
      {
        path: 'finance/payable-check/:id',
        component: () => import('@/meta/pages/PayableCheckPage.vue'),
      },
      {
        path: 'finance/invoice-prepares',
        component: () => import('@/meta/pages/InvoicePreparePage.vue'),
      },
      {
        path: 'finance/purchase-invoice-prepares',
        name: 'FinancePurchaseInvoicePrepares',
        meta: { },
        component: wrapBusinessOperationPage('invoice-prepare', () => import('@/meta/pages/InvoicePreparePage.vue')),
      },
      {
        path: 'finance/invoice-prepare/:id',
        component: () => import('@/meta/pages/InvoicePreparePage.vue'),
      },
      {
        path: 'finance/ap-drafts',
        name: 'FinanceAccountPayableDrafts',
        meta: { },
        component: wrapBusinessOperationPage('account-payable-draft', () => import('@/meta/pages/AccountPayableDraftPage.vue')),
      },
      {
        path: 'finance/ap-draft/:id',
        component: () => import('@/meta/pages/AccountPayableDraftPage.vue'),
      },
      {
        path: 'finance/account-payable-confirms',
        name: 'FinanceAccountPayableConfirms',
        meta: { },
        component: wrapBusinessOperationPage('account-payable-confirm', () => import('@/meta/pages/AccountPayableConfirmPage.vue')),
      },
      {
        path: 'finance/account-payable-confirm/:id',
        component: () => import('@/meta/pages/AccountPayableConfirmPage.vue'),
      },
      {
        path: 'finance/payment-applications',
        name: 'FinancePaymentApplications',
        meta: { },
        component: wrapBusinessOperationPage('payment-application', () => import('@/meta/pages/PaymentApplicationPage.vue')),
      },
      {
        path: 'finance/payment-application/:id',
        component: () => import('@/meta/pages/PaymentApplicationPage.vue'),
      },
      {
        path: 'finance/payment-requests',
        name: 'FinancePaymentRequests',
        meta: { },
        component: wrapBusinessOperationPage('payment-request', () => import('@/meta/pages/PaymentRequestPage.vue')),
      },
      {
        path: 'finance/payment-request/:id',
        component: () => import('@/meta/pages/PaymentRequestPage.vue'),
      },
      {
        path: 'finance/payment-order-prepares',
        name: 'FinancePaymentOrderPrepares',
        meta: { },
        component: wrapBusinessOperationPage('payment-instruction-prepare', () => import('@/meta/pages/PaymentInstructionPreparePage.vue')),
      },
      {
        path: 'finance/payment-order-prepare/:id',
        component: () => import('@/meta/pages/PaymentInstructionPreparePage.vue'),
      },
      {
        path: 'finance/payment-execution-prepares',
        name: 'FinancePaymentExecutionPrepares',
        meta: { },
        component: wrapBusinessOperationPage('payment-execution-prepare', () => import('@/meta/pages/PaymentExecutionPreparePage.vue')),
      },
      {
        path: 'finance/payment-execution-prepare/:id',
        component: () => import('@/meta/pages/PaymentExecutionPreparePage.vue'),
      },
      {
        path: 'finance/payment-voucher-prepare-preview/:paymentExecutionPrepareNo',
        component: () => import('@/meta/pages/PaymentVoucherPreparePreviewPage.vue'),
      },
      {
        path: 'finance/bank-flow-import-validation-preview/:paymentExecutionPrepareNo',
        component: () => import('@/meta/pages/BankFlowImportValidationPreviewPage.vue'),
      },
      {
        path: 'finance/bank-flow-import-validation-preview',
        component: () => import('@/meta/pages/BankFlowImportValidationPreviewPage.vue'),
      },
      {
        path: 'finance/bank-account-master-design',
        component: () => import('@/meta/pages/BankAccountMasterDesignPage.vue'),
      },
      {
        path: 'finance/settlement-boundary-overview',
        component: () => import('@/meta/pages/SettlementBoundaryOverviewPage.vue'),
      },
      {
        path: 'finance/payment-drafts',
        name: 'FinanceSupplierPaymentDrafts',
        meta: { },
        component: wrapPceListPage('supplier-payment-draft', () => import('@/meta/pages/SupplierPaymentDraftPage.vue')),
      },
      {
        path: 'finance/payment-draft/:id',
        component: () => import('@/meta/pages/SupplierPaymentDraftPage.vue'),
      },
      {
        path: 'finance/payment-prepares',
        name: 'FinancePaymentPrepares',
        meta: { },
        component: wrapBusinessOperationPage('payment-order-prepare', () => import('@/meta/pages/PaymentOrderPreparePage.vue')),
      },
      {
        path: 'finance/payment-prepare/:id',
        component: () => import('@/meta/pages/PaymentOrderPreparePage.vue'),
      },
      {
        path: 'finance/payment-order-drafts',
        name: 'FinancePaymentOrderDrafts',
        meta: { },
        component: wrapBusinessOperationPage('payment-order-draft', () => import('@/meta/pages/PaymentOrderDraftPage.vue')),
      },
      {
        path: 'finance/payment-order-draft/:id',
        component: () => import('@/meta/pages/PaymentOrderDraftPage.vue'),
      },
      {
        path: 'finance/payment-risk-reviews',
        name: 'FinancePaymentRiskReviews',
        meta: { },
        component: wrapBusinessOperationPage('payment-risk-review', () => import('@/meta/pages/PaymentExecutionRiskReviewPage.vue')),
      },
      {
        path: 'finance/payment-risk-review/:id',
        component: () => import('@/meta/pages/PaymentExecutionRiskReviewPage.vue'),
      },
      {
        path: 'finance/formal-payment-orders',
        name: 'FinanceFormalPaymentOrders',
        meta: { },
        component: wrapBusinessOperationPage('formal-payment-order', () => import('@/meta/pages/FormalPaymentOrderPage.vue')),
      },
      {
        path: 'finance/formal-payment-order/:id',
        component: () => import('@/meta/pages/FormalPaymentOrderPage.vue'),
      },
      {
        path: 'finance/bank-send-prepares',
        name: 'FinanceBankSendPrepares',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-preparation', () => import('@/meta/pages/BankSendPreparationPage.vue')),
      },
      {
        path: 'finance/bank-send-prepare/:id',
        component: () => import('@/meta/pages/BankSendPreparationPage.vue'),
      },
      {
        path: 'finance/bank-send-tasks',
        name: 'FinanceBankSendTasks',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-task', () => import('@/meta/pages/BankSendTaskPage.vue')),
      },
      {
        path: 'finance/bank-send-task/:id',
        component: () => import('@/meta/pages/BankSendTaskPage.vue'),
      },
      {
        path: 'finance/bank-send-execution-gates',
        name: 'FinanceBankSendExecutionGates',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-execution-gate', () => import('@/meta/pages/BankSendExecutionGatePage.vue')),
      },
      {
        path: 'finance/bank-send-execution-gate/:id',
        component: () => import('@/meta/pages/BankSendExecutionGatePage.vue'),
      },
      {
        path: 'finance/bank-send-requests',
        name: 'FinanceBankSendRequests',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-request', () => import('@/meta/pages/BankSendRequestPage.vue')),
      },
      {
        path: 'finance/bank-send-request/:id',
        component: () => import('@/meta/pages/BankSendRequestPage.vue'),
      },
      {
        path: 'finance/bank-send-simulations',
        name: 'FinanceBankSendSimulations',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-simulation', () => import('@/meta/pages/BankSendSimulationPage.vue')),
      },
      {
        path: 'finance/bank-send-simulation-audits',
        name: 'FinanceBankSendSimulationAudits',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-simulation-audit', () => import('@/meta/pages/BankSendSimulationAuditPage.vue')),
      },
      {
        path: 'finance/bank-send-isolation-gates',
        name: 'FinanceBankSendIsolationGates',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-isolation-gate', () => import('@/meta/pages/BankSendIsolationGatePage.vue')),
      },
      {
        path: 'finance/bank-send-chain-traces',
        name: 'FinanceBankSendChainTraces',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-chain-trace', () => import('@/meta/pages/BankSendChainTracePage.vue')),
      },
      {
        path: 'finance/bank-send-final-approvals',
        name: 'FinanceBankSendFinalApprovals',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-final-approval', () => import('@/meta/pages/BankSendFinalApprovalPage.vue')),
      },
      {
        path: 'finance/bank-send-dual-isolation-checks',
        name: 'FinanceBankSendDualIsolationChecks',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-dual-isolation-check', () => import('@/meta/pages/BankSendDualIsolationCheckPage.vue')),
      },
      {
        path: 'finance/bank-send-production-release-reviews',
        name: 'FinanceBankSendProductionReleaseReviews',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-production-release-review', () => import('@/meta/pages/BankSendProductionReleaseReviewPage.vue')),
      },
      {
        path: 'finance/bank-send-execution-framework-reviews',
        name: 'FinanceBankSendExecutionFrameworkReviews',
        meta: { },
        component: wrapBusinessOperationPage('bank-send-execution-framework-review', () => import('@/meta/pages/BankSendExecutionFrameworkReviewPage.vue')),
      },
      {
        path: 'finance/bank-connector-adapter-reviews',
        name: 'FinanceBankConnectorAdapterReviews',
        meta: { },
        component: wrapBusinessOperationPage('bank-connector-adapter-review', () => import('@/meta/pages/BankConnectorAdapterReviewPage.vue')),
      },
      {
        path: 'finance/payment-executions',
        name: 'FinancePaymentExecutions',
        meta: { },
        component: wrapBusinessOperationPage('payment-execution', () => import('@/meta/pages/PaymentExecutionPage.vue')),
      },
      {
        path: 'finance/payment-execution/:id',
        component: () => import('@/meta/pages/PaymentExecutionPage.vue'),
      },
      {
        path: 'finance/payment-record-reviews',
        name: 'FinancePaymentRecordReviews',
        meta: { },
        component: wrapBusinessOperationPage('payment-record-review', () => import('@/meta/pages/PaymentRecordReviewPage.vue')),
      },
      {
        path: 'finance/payment-record-review/:id',
        component: () => import('@/meta/pages/PaymentRecordReviewPage.vue'),
      },
      {
        path: 'finance/payment-voucher-drafts',
        name: 'FinancePaymentVoucherDrafts',
        meta: { },
        component: wrapBusinessOperationPage('payment-voucher-draft', () => import('@/meta/pages/PaymentVoucherDraftPage.vue')),
      },
      {
        path: 'finance/payment-voucher-draft/:id',
        component: () => import('@/meta/pages/PaymentVoucherDraftPage.vue'),
      },
      {
        path: 'finance/payment-voucher-reviews',
        name: 'FinancePaymentVoucherReviews',
        meta: { },
        component: wrapBusinessOperationPage('payment-voucher-review', () => import('@/meta/pages/PaymentVoucherReviewPage.vue')),
      },
      {
        path: 'finance/payment-voucher-review/:id',
        component: () => import('@/meta/pages/PaymentVoucherReviewPage.vue'),
      },
      {
        path: 'finance/formal-payment-vouchers',
        name: 'FinanceFormalPaymentVouchers',
        meta: { },
        component: wrapBusinessOperationPage('formal-payment-voucher', () => import('@/meta/pages/FormalPaymentVoucherPage.vue')),
      },
      {
        path: 'finance/formal-payment-voucher/:id',
        component: () => import('@/meta/pages/FormalPaymentVoucherPage.vue'),
      },
      {
        path: 'finance/p2p-validation-center',
        component: () => import('@/meta/pages/FormalP2PTracePage.vue'),
      },
      {
        path: 'finance/p2p-business-trace-center',
        component: () => import('@/meta/pages/FormalP2PTracePage.vue'),
      },
      {
        path: 'business-trace',
        component: () => import('@/meta/pages/FormalP2PTracePage.vue'),
      },
      {
        path: 'demo/p2p-validation-center',
        component: () => import('@/meta/pages/P2PValidationCenterPage.vue'),
        meta: { demoOnly: true, excludedFromFormalGate: true },
      },
      {
        path: 'demo/p2p-business-trace-center',
        component: () => import('@/meta/pages/P2PBusinessTraceCenterPage.vue'),
        meta: { demoOnly: true, excludedFromFormalGate: true },
      },
      {
        path: 'demo/business-trace',
        component: () => import('@/meta/pages/BusinessTraceCenterPage.vue'),
        meta: { demoOnly: true, excludedFromFormalGate: true },
      },
      {
        path: 'finance/p2p-trace/:id',
        component: () => import('@/meta/pages/P2PTracePage.vue'),
      },
      {
        path: 'crm/:pathMatch(.*)*',
        redirect: '/process-center',
      },
      {
        path: 'scm/:pathMatch(.*)*',
        redirect: '/process-center',
      },
      {
        path: 'finance/:pathMatch(.*)*',
        redirect: '/process-center',
      },
      {
        path: 'inventory/:pathMatch(.*)*',
        redirect: '/process-center',
      },
      {
        path: 'control-tower',
        component: () => import('@/meta/pages/ControlTower.vue'),
      },
      ...moduleRoutes,
      {
        path: 'agents',
        component: () => import('@/meta/pages/CockpitModulePlaceholder.vue'),
        props: {
          title: 'Agents',
          layer: 'ProfitOS Agent Core',
          owner: 'ProfitOS',
        },
      },
      {
        path: 'profit-analysis',
        component: () => import('@/meta/pages/CockpitModulePlaceholder.vue'),
        props: {
          title: 'Profit Analysis',
          layer: 'ProfitOS Decision Layer',
          owner: 'ProfitOS',
        },
      },
      {
        path: 'system-health',
        component: () => import('@/meta/pages/CockpitModulePlaceholder.vue'),
        props: {
          title: 'System Health',
          layer: 'Cockpit Observability',
          owner: 'ProfitOS',
        },
      },
      {
        path: ':module/:pathMatch(.*)*',
        redirect: (to) => resolveListFallback(to.path),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeResolve(async (to) => {
  const handoffCode = Array.isArray(to.query?.authHandoff)
    ? to.query.authHandoff[0]
    : to.query?.authHandoff
  if (handoffCode) {
    const cleanQuery = { ...to.query }
    delete cleanQuery.authHandoff
    const targetPath = router.resolve({ path: to.path, query: cleanQuery, hash: to.hash }).fullPath
    try {
      const payload = await exchangeTabAuthenticationHandoff(handoffCode, targetPath)
      setTabAuthToken(payload.token)
      rememberTabIdentity(payload.user)
      return { path: to.path, query: cleanQuery, hash: to.hash, replace: true }
    } catch {
      return { path: '/system-login', query: { redirect: targetPath, reason: 'tab-authentication-handoff-failed' } }
    }
  }
  if (to.meta?.canonicalModuleId || to.meta?.requiresServerAuthentication) {
    if (!hasUsableServerAuthentication()) {
      return { path: '/system-login', query: { redirect: to.fullPath, reason: 'formal-server-context-required' } }
    }
    if (to.meta?.canonicalModuleId) resolveFoundationPageState(to)
  }
  return true
})

// Read-only runtime inventory for full-route UI acceptance. It exposes route
// metadata only and never navigates, mutates business state, or writes storage.
if (import.meta.env.DEV && typeof window !== 'undefined') {
  window.__PCE_RUNTIME_ROUTE_MANIFEST__ = router.getRoutes().map((route) => ({
    path: route.path,
    name: route.name ? String(route.name) : '',
    redirect: Boolean(route.redirect),
    componentSource: String(route.components?.default?.__pceComponentFile || route.components?.default || ''),
  }))
}

router.afterEach((to) => {
  applyPageDocumentTitle(to)
})

if (typeof window !== 'undefined') {
  const refreshIdentityTitle = () => applyPageDocumentTitle(router.currentRoute.value)
  window.addEventListener('pce:authentication-changed', refreshIdentityTitle)
}

export default router
