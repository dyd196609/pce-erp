import { createRouter, createWebHashHistory } from 'vue-router'
import { resolveSchema } from '@/meta/core/schemaResolver'
import { buildModuleHub } from '@/meta/platform/moduleHub'
import { h, onMounted, ref, shallowRef } from 'vue'

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
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'organization' },
      },
      {
        path: 'organization/department/:id',
        name: 'OrganizationDepartmentAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'organization/role/:id',
        name: 'OrganizationRoleAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'organization/user/:id',
        name: 'OrganizationUserAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'organization/permission/:id',
        name: 'OrganizationPermissionAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'process-center',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'process-center' },
      },
      {
        path: 'process-center/process/:id',
        name: 'ProcessDetail',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'process-center/process/:id/create',
        name: 'ProcessCreate',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'process-center/process/:id/edit',
        name: 'ProcessEdit',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'process-center/process/:id/execute',
        name: 'ProcessExecute',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
      },
      {
        path: 'work-center',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
        props: { view: 'work-center' },
      },
      {
        path: 'work-center/task/:id',
        name: 'WorkTaskAction',
        component: () => import('@/meta/pages/EnterpriseOSPage.vue'),
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
        component: () => import('@/meta/pages/ApprovalFlowConfigPage.vue'),
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
        path: 'manufacturing/module/:moduleId',
        component: () => import('@/meta/pages/ManufacturingOSPage.vue'),
      },
      {
        path: 'foundation',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/business-partners',
        component: () => import('@/meta/pages/BusinessPartnerPage.vue'),
      },
      {
        path: 'foundation/suppliers',
        component: () => import('@/meta/pages/BusinessPartnerPage.vue'),
      },
      {
        path: 'foundation/dealers',
        component: () => import('@/meta/pages/BusinessPartnerPage.vue'),
      },
      {
        path: 'foundation/company-bank-accounts',
        component: () => import('@/meta/pages/BusinessPartnerPage.vue'),
      },
      {
        path: 'foundation/review-check',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/import-records',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/pfm/employees',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/pfm/employee/create',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/pfm/employee/:id',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/pfm/skills',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/pfm/certificates',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/pfm/shifts',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/materials',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/material/create',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/material/:id',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/customers',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/customer/create',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/customer/:id',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/suppliers',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/supplier/create',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/supplier/:id',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/work-centers',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/warehouses',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/supplier-material-prices',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/material-suppliers',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/product-categories',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/manufacturing/processes',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/manufacturing/routings',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/manufacturing/routing/:id',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/manufacturing/equipment',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/sample-data',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/data-dictionaries',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/coding-rules',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/erp/system-parameters',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/security/permissions',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/security/role-permissions',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/security/user-roles',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/logs/operation',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/warnings/rules',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/warnings/records',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'foundation/warnings/subscribers',
        component: () => import('@/meta/pages/ManufacturingFoundationPage.vue'),
      },
      {
        path: 'reference',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'reference/master-data',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'reference/organization',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'reference/warehouse',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'reference/production',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'reference/warning',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'reference/check',
        component: () => import('@/meta/pages/ManufacturingReferencePage.vue'),
      },
      {
        path: 'scm',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-requests',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-request/create',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-request/:id',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-inquiries',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-inquiry/create',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-inquiry/:id',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/price-approvals',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/price-approval/create',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/price-approval/:id',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-orders',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-order/create',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'scm/purchase-order/:id',
        component: () => import('@/meta/pages/ScmPage.vue'),
      },
      {
        path: 'wms',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/inventory-balances',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/inventory-balance/:id',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/inventory-transactions',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/inventory-transaction/:id',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/warehouse-tasks',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/warehouse-task/:id',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/stock-warnings',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/purchase-receive-preview',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/purchase-receive-preview/:id',
        component: () => import('@/meta/pages/WmsPage.vue'),
      },
      {
        path: 'wms/purchase-receives',
        component: () => import('@/meta/pages/PurchaseReceivePage.vue'),
      },
      {
        path: 'wms/purchase-receive/:id',
        component: () => import('@/meta/pages/PurchaseReceivePage.vue'),
      },
      {
        path: 'qms',
        component: () => import('@/meta/pages/QmsPage.vue'),
      },
      {
        path: 'qms/incoming-inspections',
        component: () => import('@/meta/pages/QmsPage.vue'),
      },
      {
        path: 'qms/incoming-inspection/:id',
        component: () => import('@/meta/pages/QmsPage.vue'),
      },
      {
        path: 'finance/payable-prepares',
        component: () => import('@/meta/pages/PayablePreparePage.vue'),
      },
      {
        path: 'finance/payable-prepare/:id',
        component: () => import('@/meta/pages/PayablePreparePage.vue'),
      },
      {
        path: 'finance/payable-checks',
        component: () => import('@/meta/pages/PayableCheckPage.vue'),
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
        path: 'finance/invoice-prepare/:id',
        component: () => import('@/meta/pages/InvoicePreparePage.vue'),
      },
      {
        path: 'finance/ap-drafts',
        component: () => import('@/meta/pages/AccountPayableDraftPage.vue'),
      },
      {
        path: 'finance/ap-draft/:id',
        component: () => import('@/meta/pages/AccountPayableDraftPage.vue'),
      },
      {
        path: 'finance/payment-drafts',
        component: () => import('@/meta/pages/SupplierPaymentDraftPage.vue'),
      },
      {
        path: 'finance/payment-draft/:id',
        component: () => import('@/meta/pages/SupplierPaymentDraftPage.vue'),
      },
      {
        path: 'finance/payment-prepares',
        component: () => import('@/meta/pages/PaymentOrderPreparePage.vue'),
      },
      {
        path: 'finance/payment-prepare/:id',
        component: () => import('@/meta/pages/PaymentOrderPreparePage.vue'),
      },
      {
        path: 'finance/payment-order-drafts',
        component: () => import('@/meta/pages/PaymentOrderDraftPage.vue'),
      },
      {
        path: 'finance/payment-order-draft/:id',
        component: () => import('@/meta/pages/PaymentOrderDraftPage.vue'),
      },
      {
        path: 'finance/payment-risk-reviews',
        component: () => import('@/meta/pages/PaymentExecutionRiskReviewPage.vue'),
      },
      {
        path: 'finance/payment-risk-review/:id',
        component: () => import('@/meta/pages/PaymentExecutionRiskReviewPage.vue'),
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

export default router
