export const departmentModel = [
  {
    id: 'production',
    name: 'Production',
    module: 'MES',
  },
  {
    id: 'assembly',
    name: 'Assembly',
    module: 'MES',
  },
  {
    id: 'procurement',
    name: 'Procurement',
    module: 'SCM',
  },
  {
    id: 'warehouse',
    name: 'Warehouse',
    module: 'WMS',
  },
  {
    id: 'finance',
    name: 'Finance',
    module: 'ERP',
  },
  {
    id: 'management',
    name: 'Management',
    module: 'ProfitOS',
  },
]

export function getDepartmentModel() {
  return departmentModel
}

