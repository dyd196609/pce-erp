const roles = {
  admin: ['ALL'],
  manager: ['READ', 'ANALYZE', 'EXECUTE'],
  viewer: ['READ'],
}

export function checkPermission(role = 'viewer', action = 'READ') {
  const permissions = roles[role] || []

  if (permissions.includes('ALL')) return true

  return permissions.includes(action)
}

export function listRoles() {
  return Object.keys(roles)
}
