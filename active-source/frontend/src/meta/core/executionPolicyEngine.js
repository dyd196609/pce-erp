export function policyDecide(risk, anomaly) {
  if (anomaly?.risky) return 'BLOCK'
  if (risk === 'HIGH') return 'REVIEW'
  if (risk === 'CRITICAL') return 'BLOCK'
  if (risk === 'LOW') return 'AUTO'
  return 'REVIEW'
}
