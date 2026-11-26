function inferType(patch = {}) {
  const target = String(patch.target || '').toLowerCase()
  const type = String(patch.type || '').toLowerCase()

  if (target.includes('schema') || type.includes('schema')) return 'schema_change'
  if (target.includes('api') || type.includes('api')) return 'api_change'
  if (target.includes('workflow') || type.includes('workflow')) return 'workflow_change'
  return 'ui_change'
}

function classifySeverity(patch = {}) {
  if (patch.risk === 'CRITICAL') return 'critical'
  if (patch.risk === 'HIGH') return 'high'
  if (patch.risk === 'MEDIUM') return 'medium'
  return 'low'
}

export function semanticDiff(patch) {
  return {
    type: inferType(patch),
    severity: classifySeverity(patch),
  }
}
