export const reviewScopes = [
  {
    key: 'ERP',
    label: 'ERP Core Data Layer',
    domains: ['organization', 'department', 'role', 'employee'],
    responsibility: 'master data and enterprise control',
  },
  {
    key: 'MES',
    label: 'MES Execution System',
    domains: ['productionExecution', 'workOrder', 'qualityInspection'],
    responsibility: 'shop-floor execution and traceability',
  },
  {
    key: 'SCM',
    label: 'SCM Supply Chain',
    domains: ['material', 'purchaseOrder', 'supplier'],
    responsibility: 'supply chain planning and purchase execution',
  },
  {
    key: 'WMS',
    label: 'WMS Warehouse',
    domains: ['inventory', 'warehouse', 'stockMovement'],
    responsibility: 'inventory control and warehouse movement',
  },
  {
    key: 'CRM',
    label: 'CRM Customer System',
    domains: ['customer', 'customerProfit', 'salesOrder'],
    responsibility: 'customer relationship and revenue context',
  },
  {
    key: 'BI',
    label: 'BI Analytics System',
    domains: ['analytics', 'profitAnalysis', 'dashboard'],
    responsibility: 'analytics and decision reporting',
  },
  {
    key: 'ProfitOS',
    label: 'ProfitOS Decision Layer',
    domains: ['cockpit', 'decisionKernel', 'profitEngine', 'agentRuntime'],
    responsibility: 'profit-driven decision and enterprise cockpit',
  },
]

export function getReviewScopes() {
  return reviewScopes
}

export function mapDomainToScope(domain) {
  return reviewScopes.find((scope) => scope.domains.includes(domain)) || {
    key: 'UNKNOWN',
    label: 'Unknown Scope',
    domains: [],
    responsibility: 'unmapped domain',
  }
}

export function getScopeByKey(key) {
  return reviewScopes.find((scope) => scope.key === key)
}

