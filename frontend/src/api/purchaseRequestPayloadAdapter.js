const headerIdFields = Object.freeze([
  'requesterEmployeeId', 'departmentId', 'usageDepartmentId', 'purchaseDepartmentId',
  'projectId', 'costCenterId', 'expenseCategoryId', 'budgetCategoryId',
])

function normalizedId(value, { nullable = false } = {}) {
  if ((value === '' || value === null || value === undefined) && nullable) return null
  const result = Number(value)
  return Number.isInteger(result) && result > 0 ? result : value
}

export function adaptPurchaseRequestPayload(data = {}) {
  const payload = { ...data }
  for (const field of headerIdFields) payload[field] = normalizedId(data[field])
  payload.items = (Array.isArray(data.items) ? data.items : []).map((item) => ({
    materialId: normalizedId(item.materialId), quantity: String(item.quantity ?? ''),
    requiredDate: item.requiredDate || null, demandReason: String(item.demandReason || ''),
    suggestedSupplierId: normalizedId(item.suggestedSupplierId, { nullable: true }),
    substituteMaterialId: normalizedId(item.substituteMaterialId, { nullable: true }),
    technicalRequirements: String(item.technicalRequirements || ''),
    brandRequirements: String(item.brandRequirements || ''),
    substituteRequirement: String(item.substituteRequirement || ''),
    purchaseRemark: String(item.purchaseRemark || ''), remark: String(item.remark || ''),
  }))
  return payload
}
