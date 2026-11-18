export const CRM_ORDER_PROCESS_VERSION = 'CRM-ORDER-PROCESS-V1.0'
export const CRM_ORDER_PROCESS_CODE = 'CRM_ORDER_OPERATION'

const definitions = [
  ['order-intake', '接单', 'sales-orders', '/sales/orders?entry=process-center&module=CRM&process=CRM_ORDER_OPERATION&node=order-intake', 'active', 'PASS'],
  ['product-requirement-review', '订单评审', 'crm-order-reviews', '/sales/order-reviews?entry=process-center&module=CRM&process=CRM_ORDER_OPERATION&node=product-requirement-review', 'active', 'MANUAL_REVIEW_READY'],
  ['product-design', '产品设计', 'pde-product-definitions', '/pde/product-definitions?entry=process-center&module=CRM&process=CRM_ORDER_OPERATION&node=product-design', 'active', 'PASS'],
  ['bom-definition', 'BOM', '', '', 'planned', 'AWAITING_STEP_1_VALIDATION'],
  ['routing-definition', '工艺路线', '', '', 'planned', 'AWAITING_STEP_1_VALIDATION'],
  ['engineering-document', '工程资料', '', '', 'planned', 'AWAITING_STEP_1_VALIDATION'],
  ['engineering-calculation', '工程核算', '', '', 'planned', 'AWAITING_STEP_1_VALIDATION'],
  ['manufacturing-output', '制造输出', '', '', 'planned', 'AWAITING_STEP_1_VALIDATION'],
  ['planning-input', 'MRP / 计划输入', '', '', 'frozen', 'NOT_PRODUCTION_DEPLOYED'],
]

export const CRM_ORDER_PROCESS_NODES = Object.freeze(definitions.map(
  ([nodeCode, nodeName, pageCode, pageUrl, pageStatus, acceptanceStatus], index) => Object.freeze({
    moduleCode: 'CRM', moduleName: '营销业务中心',
    processCode: CRM_ORDER_PROCESS_CODE, processName: '订单业务流程', processVersion: 'V1.0',
    nodeCode, nodeName, sequence: index + 1, pageCode, pageUrl, pageRoute: pageUrl,
    allowNewTab: Boolean(pageUrl), pageVersion: pageUrl ? 'ORDER-OPERATING-SYSTEM-V1' : '',
    pageStatus, acceptanceStatus,
    statusDescription: index === 0
      ? 'STEP 1：进入销售订单工作台，可查看开发合同与报价或保留的历史来源办理。'
      : index === 1
        ? '独立评审客户要求、报价、成本、效益、交期与履约风险；不会自动代表生产可行性通过。'
        : '必须等待上一人工验收节点通过；当前不执行。',
  })),
)

export const CRM_ORDER_PROCESS = Object.freeze({
  processCode: CRM_ORDER_PROCESS_CODE, processName: '订单业务流程',
  moduleCode: 'CRM', moduleName: '营销业务中心', version: 'V1.0', processVersion: 'V1.0',
  versionHistory: Object.freeze(['V1.0']), status: 'active', enabled: true,
  owner: '营销业务负责人', nodes: CRM_ORDER_PROCESS_NODES,
})
