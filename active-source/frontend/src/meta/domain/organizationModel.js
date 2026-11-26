import { departmentModel } from './departmentModel.js'

export const organizationModel = {
  id: 'palmcloud-demo',
  name: 'PalmCloud Demo Manufacturing',
  tenantId: 'demo_company',
  type: 'manufacturing_enterprise',
  departments: departmentModel.map((department) => department.id),
}

export function getOrganizationModel() {
  return {
    ...organizationModel,
    departmentCount: organizationModel.departments.length,
  }
}

