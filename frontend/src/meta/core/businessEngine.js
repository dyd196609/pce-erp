// ================================
// V3.9 BUSINESS ENGINE
// ================================

export function evaluateBusiness(schema, row) {
  return {
    orderAchieved: evaluateOrderAchieved(row),
    statusLabel: mapStatus(row),
    progressLabel: mapProgress(row),
  }
}

// ----------------
// 1. 订单达成逻辑
// ----------------
function evaluateOrderAchieved(row) {
  const planQty = Number(row.plan_quantity || 0)
  const actualQty = Number(row.actual_quantity || 0)

  const planDate = new Date(row.plan_delivery_date || 0)
  const actualDate = new Date(row.actual_delivery_date || 0)

  const qtyOk = actualQty >= planQty
  const timeOk = actualDate <= planDate

  return qtyOk && timeOk
}

// ----------------
// 2. 状态映射（中文→业务层）
// ----------------
function mapStatus(row) {
  const map = {
    draft: '草案',
    submitted: '提报',
    approved: '审核通过',
    reviewed: '复核',
    audited: '审计',
    closed: '关闭',
  }

  return map[row.status] || row.status
}

// ----------------
// 3. 进度映射
// ----------------
function mapProgress(row) {
  const map = {
    not_started: '未开始',
    arriving: '到货中',
    arrived: '已到货',
    inspected: '已检验',
    warehoused: '已入库',
  }

  return map[row.progress_status] || row.progress_status
}

// ----------------
// 4. 操作按钮生成器（核心）
// ----------------
export function generateActions(schema, row) {
  const actions = []

  const biz = evaluateBusiness(schema, row)

  // 查看详情（永远存在）
  actions.push({ name: 'detail', label: '详情' })

  // 编辑：草案/提报可编辑
  if (['draft', 'submitted'].includes(row.status)) {
    actions.push({ name: 'edit', label: '编辑' })
  }

  // 删除：只有草案
  if (row.status === 'draft') {
    actions.push({ name: 'delete', label: '删除' })
  }

  // 完成订单
  if (biz.orderAchieved) {
    actions.push({ name: 'complete', label: '完成订单' })
  }

  return actions
}
