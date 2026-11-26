const mockRows = {
  inventory: [
    { id: 501, item_code: 'MAT-501', item_name: 'Bearing', stock_qty: 320, warehouse: 'Main', workflow_state: 'DRAFT' },
    { id: 502, item_code: 'MAT-502', item_name: 'Motor', stock_qty: 86, warehouse: 'Line A', workflow_state: 'ACTIVE' },
    { id: 503, item_code: 'MAT-503', item_name: 'Control Board', stock_qty: 44, warehouse: 'Electronics', workflow_state: 'ACTIVE' },
  ],
  finance: [
    { id: 601, voucher_no: 'FIN-0601', customer: 'Demo Customer', amount: 12800, cash_status: 'Healthy', workflow_state: 'DRAFT' },
    { id: 602, voucher_no: 'FIN-0602', customer: 'Retail Account', amount: 7600, cash_status: 'Watch', workflow_state: 'ACTIVE' },
    { id: 603, voucher_no: 'FIN-0603', customer: 'Enterprise Buyer', amount: 32600, cash_status: 'Healthy', workflow_state: 'CLOSED' },
  ],
  crm: [
    { id: 701, customer_code: 'CUS-701', customer_name: 'North Star', owner: 'Sales A', ltv: 46000, workflow_state: 'DRAFT' },
    { id: 702, customer_code: 'CUS-702', customer_name: 'East Works', owner: 'Sales B', ltv: 32000, workflow_state: 'ACTIVE' },
    { id: 703, customer_code: 'CUS-703', customer_name: 'Blue Ridge', owner: 'Sales C', ltv: 58000, workflow_state: 'CLOSED' },
  ],
  scm: [
    { id: 801, supplier_code: 'SUP-801', supplier_name: 'Prime Supply', delivery_score: 94, risk_level: 'LOW', workflow_state: 'DRAFT' },
    { id: 802, supplier_code: 'SUP-802', supplier_name: 'Rapid Parts', delivery_score: 78, risk_level: 'MEDIUM', workflow_state: 'ACTIVE' },
    { id: 803, supplier_code: 'SUP-803', supplier_name: 'Stable Metals', delivery_score: 88, risk_level: 'LOW', workflow_state: 'CLOSED' },
  ],
  purchaseOrder: [
    {
      id: 412,
      po_no: 'PO-2026-0412',
      apply_dept: 'Production',
      request_dept: 'Assembly',
      buyer: 'Demo Buyer',
      amount: 1000,
      plan_arrival_date: '2026-07-08',
      actual_arrival_date: '2026-07-07',
      actual_amount: 940,
      urgency: 'High',
      status: 'Achieved',
      progress: 'Received',
      workflow_state: 'DRAFT',
    },
    {
      id: 413,
      po_no: 'PO-2026-0413',
      apply_dept: 'Engineering',
      request_dept: 'Prototype',
      buyer: 'Demo Buyer',
      amount: 2200,
      plan_arrival_date: '2026-07-12',
      actual_arrival_date: '',
      actual_amount: 0,
      urgency: 'Medium',
      status: 'Pending',
      progress: 'Submitted',
      workflow_state: 'SUBMITTED',
    },
  ],
  purchaseOrderDetail: [
    {
      id: 412,
      order_no: 'PO-2026-0412',
      material_code: 'MAT-DEMO-001',
      material_name: 'Demo Material',
      spec: 'Standard',
      plan_qty: 100,
      plan_price: 10,
      plan_amount: 1000,
      actual_qty: 94,
      actual_price: 10,
      actual_amount: 940,
      actual_date: '2026-07-07',
      expected_date: '2026-07-08',
      workflow_state: 'DRAFT',
    },
  ],
}

function normalizeModule(module = '') {
  const normalized = String(module || '').trim()
  const aliases = {
    purchase: 'purchaseOrder',
    orders: 'purchaseOrder',
    purchaseOrders: 'purchaseOrder',
    purchaseOrderDetail: 'purchaseOrderDetail',
  }

  return aliases[normalized] || normalized
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

export function getMockData(module, action = 'list', params = {}) {
  const moduleKey = normalizeModule(module)
  const rows = mockRows[moduleKey]

  if (!rows) return null

  if (action === 'detail') {
    const id = params.id || params.pk || params.recordId
    return clone(rows.find((row) => String(row.id) === String(id)) || rows[0] || null)
  }

  if (['create', 'update', 'delete', 'execute', 'run'].includes(action)) {
    return {
      success: true,
      module: moduleKey,
      action,
      mutation: params.payload || params.data || {},
      affected: action === 'delete' ? 1 : 0,
    }
  }

  return clone(rows)
}

export function listMockModules() {
  return Object.keys(mockRows)
}
