export const GOLDEN_FLOW_VERSION = 'V1.14.2.8.4.7.3'
export const GOLDEN_FLOW_PREFIX = 'E2E-GOLDEN-'
export const GOLDEN_FLOW_CASE_NO = `${GOLDEN_FLOW_PREFIX}PURCHASE-PAYMENT-001`

export const expectedGoldenFlowStages = [
  { stageId: 'procurement-request', canonicalName: '采购申请', aliases: ['采购申请'] },
  { stageId: 'purchase-inquiry', canonicalName: '采购询价', aliases: ['采购询价'] },
  { stageId: 'price-approval', canonicalName: '采购核价', aliases: ['采购核价', '核价'] },
  { stageId: 'purchase-order', canonicalName: '采购订单', aliases: ['采购订单'] },
  { stageId: 'purchase-arrival-preview', canonicalName: '采购到货预备', aliases: ['采购到货预备'] },
  { stageId: 'purchase-receive-preview', canonicalName: '采购收货预备', aliases: ['采购收货预备'] },
  { stageId: 'incoming-inspection', canonicalName: '来料检验', aliases: ['来料检验', '来料检验预备'] },
  { stageId: 'qualified-inbound', canonicalName: '合格入库', aliases: ['合格入库', '入库'] },
  { stageId: 'payable-prepare', canonicalName: '采购应付预备', aliases: ['采购应付预备'] },
  { stageId: 'payable-check', canonicalName: '采购应付核对', aliases: ['采购应付核对'] },
  { stageId: 'supplier-settlement', canonicalName: '供应商结算', aliases: ['供应商结算'] },
  { stageId: 'purchase-reconciliation', canonicalName: '采购对账', aliases: ['采购对账'] },
  { stageId: 'invoice-prepare', canonicalName: '采购发票准备', aliases: ['采购发票准备'] },
  { stageId: 'account-payable-confirm', canonicalName: '应付确认准备', aliases: ['应付确认准备'] },
  { stageId: 'payment-application', canonicalName: '付款申请准备', aliases: ['付款申请准备'] },
  { stageId: 'payment-instruction-prepare', canonicalName: '付款指令准备', aliases: ['付款指令准备'] },
  { stageId: 'payment-execution-prepare', canonicalName: '付款执行准备', aliases: ['付款执行准备'] },
  { stageId: 'account-payable-draft', canonicalName: '采购应付账款草稿', aliases: ['采购应付账款草稿'] },
  { stageId: 'supplier-payment-draft', canonicalName: '供应商付款草稿', aliases: ['供应商付款草稿'] },
  { stageId: 'payment-order-prepare', canonicalName: '正式付款单预备', aliases: ['正式付款单预备'] },
  { stageId: 'payment-order-draft', canonicalName: '正式付款单草稿', aliases: ['正式付款单草稿'] },
  { stageId: 'payment-risk-review', canonicalName: '真实付款风险评审', aliases: ['真实付款风险评审'] },
  { stageId: 'payment-execution', canonicalName: '付款执行草稿', aliases: ['付款执行草稿'] },
  { stageId: 'payment-record-review', canonicalName: '付款记录复核', aliases: ['付款记录复核'] },
  { stageId: 'payment-voucher-draft', canonicalName: '付款凭证草稿', aliases: ['付款凭证草稿'] },
  { stageId: 'payment-voucher-review', canonicalName: '付款凭证复核', aliases: ['付款凭证复核'] },
  { stageId: 'formal-payment-voucher', canonicalName: '正式付款凭证', aliases: ['正式付款凭证'] },
]

export const goldenFlowCheckpoints = [
  'request_created', 'inquiry_created', 'price_approved', 'order_created', 'order_issued', 'arrival_ready', 'receive_ready', 'received', 'quality-passed', 'payable-prepared',
  'payable-checked', 'settlement-ready', 'reconciled', 'invoice-prepared', 'payable-confirmed',
  'payment-requested', 'payment-instruction-ready', 'payment-execution-ready', 'payment-draft-ready',
  'risk-reviewed', 'payment-executed', 'payment-record-reviewed', 'voucher-reviewed', 'formal-voucher-created',
]
