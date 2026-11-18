export const BUSINESS_DEPENDENCY_REGISTRY_VERSION = 'V1.14.2.8.4.10'

export const scmSupplierSettlementDependency = Object.freeze({
  moduleCode: 'SCM',
  processCode: 'supplier_settlement',
  processBaselineCode: 'SCM_SUPPLIER_SETTLEMENT_PROCESS',
  status: 'baseline_ready',
  baselineCheckpoint: 'pce_scm_supplier_settlement_final_ready',
  dependsOn: Object.freeze([
    'EMD_SUPPLIER_MASTER',
    'EMD_MATERIAL_MASTER',
    'EMD_ORGANIZATION',
  ]),
  provides: Object.freeze([
    'supplier_settlement_result',
    'supplier_performance_data',
    'buyer_performance_data',
  ]),
  protectedObjects: Object.freeze([
    'Supplier',
    'Material',
    'PurchaseOrder',
    'Settlement',
  ]),
  downstreamConsumers: Object.freeze([
    Object.freeze({ moduleCode: 'PDE', integrationMode: 'dependency_reference', mayModifyProcessNodes: false }),
    Object.freeze({ moduleCode: 'MRP', integrationMode: 'api_reference', mayCopyBusinessLogic: false }),
    Object.freeze({ moduleCode: 'MPS', integrationMode: 'api_reference', mayCopyBusinessLogic: false }),
    Object.freeze({ moduleCode: 'APS', integrationMode: 'api_reference', mayCopyBusinessLogic: false }),
    Object.freeze({ moduleCode: 'MES', integrationMode: 'api_reference', mayCopyBusinessLogic: false }),
    Object.freeze({ moduleCode: 'WMS', integrationMode: 'api_reference', mayCopyBusinessLogic: false }),
  ]),
})

export const pdeFoundationDependency = Object.freeze({
  moduleCode: 'PDE',
  processCode: 'product_development_engineering',
  status: 'active',
  protectsBaseline: 'pce_scm_supplier_settlement_final_ready',
  dependsOn: Object.freeze([
    'EMD_MATERIAL_MASTER',
    'EMD_ORGANIZATION',
    'EMD_WORK_CENTER',
  ]),
  provides: Object.freeze([
    'BOM',
    'ROUTING',
    'PRODUCT_DEFINITION',
    'ENGINEERING_DOCUMENT',
    'MRP_INPUT_BASIS',
  ]),
  integrationRules: Object.freeze({
    materialCodeOwnership: 'EMD',
    scmIntegrationMode: 'dependency_reference',
    mayModifyScmBusinessLogic: false,
  }),
})

export function listBusinessDependencies() {
  return [{
    ...scmSupplierSettlementDependency,
    dependsOn: [...scmSupplierSettlementDependency.dependsOn],
    provides: [...scmSupplierSettlementDependency.provides],
    protectedObjects: [...scmSupplierSettlementDependency.protectedObjects],
    downstreamConsumers: scmSupplierSettlementDependency.downstreamConsumers
      .map(consumer => ({ ...consumer })),
  }, {
    ...pdeFoundationDependency,
    dependsOn: [...pdeFoundationDependency.dependsOn],
    provides: [...pdeFoundationDependency.provides],
    integrationRules: { ...pdeFoundationDependency.integrationRules },
  }]
}
