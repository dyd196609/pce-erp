// =========================
// 风险计算引擎（企业级稳定版）
// =========================

// 订单风险
export const calculateOrderRisk = (item) => {
  let score = 35

  if (!item.delivery_date) score += 25
  if ((item.plan_amount ?? 0) > 100000) score += 15
  if (item.status === 'pending') score += 10

  return Math.min(score, 100)
}

// 供应商风险
export const calculateSupplierRisk = (item) => {
  let score = 30

  const delay = item.delay_rate ?? item.delivery_delay_rate ?? 0

  if (delay > 0.2) score += 30
  if ((item.quality_issue_rate ?? 0) > 0.1) score += 25
  if ((item.cooperation_years ?? 0) < 1) score += 15

  return Math.min(score, 100)
}

// 风险等级
export const getRiskLevel = (s) => (s >= 80 ? 'HIGH' : s >= 60 ? 'MEDIUM' : 'LOW')

// 供应商等级
export const getSupplierLevel = (s) => (s >= 80 ? 'D' : s >= 60 ? 'C' : s >= 40 ? 'B' : 'A')

// 决策
export const getDecision = (score) => (score >= 80 ? 'REJECT' : score >= 60 ? 'REVIEW' : 'APPROVE')

// DTO构建
export const buildPurchaseOrderDTO = (item) => {
  const supplierRisk = calculateSupplierRisk(item)
  const orderRisk = calculateOrderRisk(item)

  const riskScore = Math.round((supplierRisk + orderRisk) / 2)

  return {
    order_no: item.order_no,
    supplier: item.supplier_name || item.supplier,
    buyer: item.buyer_name || item.buyer,
    order_date: item.order_date,
    delivery_date: item.delivery_date,
    plan_amount: item.plan_amount,
    status: item.status,

    supplier_risk: supplierRisk,
    order_risk: orderRisk,
    risk_score: riskScore,

    supplier_level: getSupplierLevel(supplierRisk),
    decision: getDecision(riskScore),
    risk_level: getRiskLevel(riskScore),
  }
}
