export const roleModel = [
  {
    id: 'admin',
    name: 'Admin',
    actions: ['READ', 'ANALYZE', 'EXECUTE', 'CONFIGURE'],
  },
  {
    id: 'manager',
    name: 'Manager',
    actions: ['READ', 'ANALYZE', 'EXECUTE'],
  },
  {
    id: 'viewer',
    name: 'Viewer',
    actions: ['READ', 'ANALYZE'],
  },
  {
    id: 'procurement_manager',
    name: 'Procurement Manager',
    actions: ['READ', 'ANALYZE', 'EXECUTE'],
  },
  {
    id: 'warehouse_operator',
    name: 'Warehouse Operator',
    actions: ['READ', 'EXECUTE'],
  },
]

export function getRoleModel() {
  return roleModel
}

