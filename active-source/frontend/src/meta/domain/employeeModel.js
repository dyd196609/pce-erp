export const employeeModel = [
  {
    id: 'emp-001',
    name: 'Demo Buyer',
    departmentId: 'procurement',
    roleId: 'procurement_manager',
  },
  {
    id: 'emp-002',
    name: 'Plant Manager',
    departmentId: 'management',
    roleId: 'manager',
  },
  {
    id: 'emp-003',
    name: 'Warehouse Lead',
    departmentId: 'warehouse',
    roleId: 'warehouse_operator',
  },
  {
    id: 'emp-004',
    name: 'Finance Analyst',
    departmentId: 'finance',
    roleId: 'viewer',
  },
]

export function getEmployeeModel() {
  return employeeModel
}

