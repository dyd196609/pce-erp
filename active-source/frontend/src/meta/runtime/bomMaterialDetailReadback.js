const text = value => String(value ?? '').trim()

export function buildBomMaterialDetailReadback(detail) {
  const rows = Array.isArray(detail?.bomMaterialDetails) ? detail.bomMaterialDetails : []
  const issues = []
  const seenRequirementIds = new Set()
  let sourceRequirementCount = 0

  if (rows.length !== Number(detail?.latestMaterialCount ?? 0)) {
    issues.push('BOM物料明细数量与服务端最新版本物料数不一致。')
  }

  for (const row of rows) {
    const requirements = Array.isArray(row.sourceRequirements) ? row.sourceRequirements : []
    if (requirements.length !== Number(row.sourceRequirementCount ?? 0)) {
      issues.push(`BOMItem ${row.bomItemId ?? '-'} 的来源数量不一致。`)
    }
    for (const requirement of requirements) {
      sourceRequirementCount += 1
      if (seenRequirementIds.has(requirement.requirementId)) {
        issues.push(`Requirement ${requirement.requirementId} 被重复投影。`)
      }
      seenRequirementIds.add(requirement.requirementId)
      if (
        Number(requirement.companyId) !== Number(detail.companyId)
        || text(requirement.orderNo) !== text(detail.orderNo)
        || Number(requirement.orderLineNo) !== Number(detail.orderLineNo)
        || Number(requirement.calculationId) !== Number(detail.sourceCalculationId)
        || Number(requirement.bomItemId) !== Number(row.bomItemId)
      ) {
        issues.push(`Requirement ${requirement.requirementId ?? '-'} 超出当前BOM订单行或核算范围。`)
      }
      if (
        Number(requirement.materialId) !== Number(row.materialId)
        || text(requirement.uomCode) !== text(row.uomCode)
      ) {
        issues.push(`Requirement ${requirement.requirementId ?? '-'} 与BOMItem物料或单位不一致。`)
      }
      if (requirement.relationStatusCode !== 'LINKED') {
        issues.push(`Requirement ${requirement.requirementId ?? '-'} 未建立正式来源关系。`)
      }
    }
  }

  if (sourceRequirementCount !== Number(detail?.sourceRequirementCount ?? 0)) {
    issues.push('Requirement来源总数与服务端汇总不一致。')
  }

  return Object.freeze({
    result: issues.length ? 'FAIL_CLOSED' : 'PASS',
    rows,
    sourceRequirementCount,
    issues: Object.freeze(issues),
  })
}
