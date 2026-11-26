const approvalActions = new Set(['APPROVE', 'POST', 'CLOSE_DEAL', 'DELIVER'])
const roleApprovals = {
  admin: ['APPROVE', 'POST', 'CLOSE_DEAL', 'DELIVER'],
  manager: ['APPROVE', 'POST', 'CLOSE_DEAL'],
  viewer: [],
}

export function applyBusinessRules(module, action, context = {}) {
  const role = context.role || context.user?.role || 'admin'
  const amount = Number(
    context.record?.price * context.record?.quantity
      || context.record?.opportunityValue
      || context.record?.balance
      || context.record?.cost
      || 0
  )
  const requiresApproval = approvalActions.has(action)
  const roleAllowed = !requiresApproval || (roleApprovals[role] || []).includes(action)
  const autoApproved = requiresApproval && roleAllowed && amount < 50000

  return {
    module,
    action,
    role,
    requiresApproval,
    roleAllowed,
    autoApproved,
    rejected: requiresApproval && !roleAllowed,
    reason: roleAllowed ? 'APPROVAL_RULE_PASSED' : 'ROLE_APPROVAL_DENIED',
  }
}
