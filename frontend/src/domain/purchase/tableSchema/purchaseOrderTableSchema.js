// ===============================
// 采购订单 - 动态表格配置
// ERP级核心：字段驱动UI
// ===============================

export const purchaseOrderTableSchema = [
  {
    prop: 'index',
    label: '序号',
    width: 60,
    type: 'index',
  },

  {
    prop: 'order_no',
    label: '采购订单号',
  },

  {
    prop: 'supplier',
    label: '供应商',
  },

  {
    prop: 'buyer',
    label: '采购员',
  },

  {
    prop: 'order_date',
    label: '下单日期',
  },

  {
    prop: 'delivery_date',
    label: '交货日期',
  },

  {
    prop: 'plan_amount',
    label: '计划金额',
  },

  {
    prop: 'risk_score',
    label: '风险评分',
    type: 'tag',
    tagMap: {
      HIGH: 'danger',
      MEDIUM: 'warning',
      LOW: 'success',
    },
  },

  {
    prop: 'supplier_level',
    label: '供应商等级',
    type: 'tag',
  },

  {
    prop: 'decision',
    label: '采购决策',
    type: 'tag',
    tagMap: {
      APPROVE: 'success',
      REVIEW: 'warning',
      REJECT: 'danger',
    },
  },

  {
    prop: 'risk_level',
    label: '风险等级',
    type: 'tag',
    tagMap: {
      HIGH: 'danger',
      MEDIUM: 'warning',
      LOW: 'success',
    },
  },
]
