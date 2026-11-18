import request from './request.js'


export const PCE_BUSINESS_ACTION_PERMISSION_VERSION =
  'PCE-BUSINESS-ACTION-PERMISSION-V1.0'

function unwrap(response) {
  return response?.data ?? response ?? {}
}

export async function listBusinessActionPermissions({
  moduleCode,
  objectIds = [],
  selectionCount = objectIds.length,
  legalEntityId = '',
}) {
  return unwrap(await request({
    method: 'GET',
    url: '/api/workflow/action-permissions/',
    params: {
      moduleCode,
      objectIds: objectIds.join(','),
      selectionCount,
      legalEntityId,
    },
    meta: { module: 'workflow-action-permissions' },
  }))
}

export async function validateBusinessActionPermission({
  actionCode,
  moduleCode,
  objectIds = [],
  selectionCount = objectIds.length,
  legalEntityId = '',
}) {
  return unwrap(await request({
    method: 'POST',
    url: '/api/workflow/action-permissions/validate',
    data: {
      actionCode,
      moduleCode,
      objectIds,
      selectionCount,
      legalEntityId,
    },
    meta: { module: 'workflow-action-permissions' },
  }))
}

export async function getBusinessActionPermissionContract() {
  return unwrap(await request({
    method: 'GET',
    url: '/api/workflow/action-permissions/contract',
    meta: { module: 'workflow-action-permissions' },
  }))
}
