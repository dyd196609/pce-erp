export const PDE_WORKBENCH_RULES_VERSION = 'V1.14.2.8.4.10.3'

export const pdeWorkbenchRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-WB-001', title: '必须存在PDE工作台' }),
  Object.freeze({ ruleId: 'PDE-WB-002', title: '必须显示CRM来源' }),
  Object.freeze({ ruleId: 'PDE-WB-003', title: '禁止生成采购订单' }),
  Object.freeze({ ruleId: 'PDE-WB-004', title: 'BOM物料来自EMD' }),
  Object.freeze({ ruleId: 'PDE-WB-005', title: '工艺工作中心来自EMD' }),
  Object.freeze({ ruleId: 'PDE-WB-006', title: '返回流程中心保持PDE' }),
])

const result = (ruleId, passed, evidence) => {
  const rule = pdeWorkbenchRules.find(item => item.ruleId === ruleId)
  return Object.freeze({
    ...rule,
    status: passed === true ? 'PASS' : passed === false ? 'FAIL' : 'UNKNOWN',
    evidence,
  })
}

export function evaluatePdeWorkbenchRules({
  entries,
  relationship,
  governance,
  routeSource,
  pageSource,
  processCenterSource,
}) {
  const workbenchExists = routeSource.includes("path: 'pde/workbench'")
    && pageSource.includes('data-acceptance-id="pde-product-engineering-workbench"')
    && entries.length === 10
  const crmSourceVisible = relationship.source === 'CRM客户订单'
    && relationship.chain[0] === 'CRM客户订单'
    && entries[0]?.sourceModule === 'CRM'
    && pageSource.includes('来源：CRM')
  const purchaseOrderProtected = relationship.purchaseOrderGeneration === false
    && pageSource.includes('data-purchase-order-generation="false"')
    && !pageSource.includes('createPurchaseOrder')
  const bomFromEmd = relationship.bomMaterialOwner === 'EMD'
    && relationship.chain.includes('EMD物料')
  const routingFromEmd = relationship.routingWorkCenterOwner === 'EMD'
    && pageSource.includes('工艺工作中心所有权')
  const returnKeepsPde = governance.returnModuleCode === 'PDE'
    && processCenterSource.includes("router.push('/pde/workbench')")
    && routeSource.includes('pdeWorkbenchGovernance')
  return Object.freeze([
    result('PDE-WB-001', workbenchExists, { route: '/pde/workbench', entryCount: entries.length }),
    result('PDE-WB-002', crmSourceVisible, { source: relationship.source, firstChainNode: relationship.chain[0] }),
    result('PDE-WB-003', purchaseOrderProtected, { purchaseOrderGeneration: relationship.purchaseOrderGeneration }),
    result('PDE-WB-004', bomFromEmd, { bomMaterialOwner: relationship.bomMaterialOwner }),
    result('PDE-WB-005', routingFromEmd, { routingWorkCenterOwner: relationship.routingWorkCenterOwner }),
    result('PDE-WB-006', returnKeepsPde, { returnModuleCode: governance.returnModuleCode }),
  ])
}
