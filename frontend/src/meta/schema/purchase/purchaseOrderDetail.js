const purchaseOrderDetailSchema = {
  name: 'purchaseOrderDetail',

  meta: {
    module: 'purchase_order_detail',
    title: '采购订单明细',
  },

  api: {
    module: 'purchaseOrderDetail',
  },

  ui: {
    list: {
      columns: [
        { key: 'index', type: 'index', label: '序号', sortable: false, filter: false },

        { key: 'order_no', label: '订单号', sortable: true, filter: true, filterType: 'text' },
        { key: 'material_code', label: '物料编码', sortable: true, filter: true, filterType: 'text' },
        { key: 'material_name', label: '物料名称', sortable: true, filter: true, filterType: 'fuzzy' },
        { key: 'spec', label: '规格型号', sortable: true, filter: true, filterType: 'fuzzy' },

        { key: 'plan_qty', label: '计划数量', sortable: true, filter: true, filterType: 'text' },
        { key: 'plan_price', label: '计划单价', sortable: true, filter: true, filterType: 'text' },
        { key: 'plan_amount', label: '计划金额', sortable: true, filter: true, filterType: 'text' },

        { key: 'actual_qty', label: '实际交货数量', sortable: true, filter: true, filterType: 'text' },
        { key: 'actual_price', label: '实际交货单价', sortable: true, filter: true, filterType: 'text' },
        { key: 'actual_amount', label: '实际交货金额', sortable: true, filter: true, filterType: 'text' },

        { key: 'actual_date', label: '实际到货日期', sortable: true, filter: true, filterType: 'date' },
        { key: 'expected_date', label: '期望到货日期', sortable: true, filter: true, filterType: 'date' },
      ],
      actions: [],
    },

    detail: {},
    form: {},
  },

  workflow: {},
}

export default purchaseOrderDetailSchema
