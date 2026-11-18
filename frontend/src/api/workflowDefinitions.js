import request, { getAuthenticationHeaders } from './request.js'

const meta = { module: 'workflow', requiresAuthentication: true }

export function listWorkflowDefinitions() {
  return request({ method: 'GET', url: '/api/workflow/definitions/',
    headers: getAuthenticationHeaders(), meta: { ...meta, readOnly: true } })
}

export function getWorkflowDefinition(id) {
  return request({ method: 'GET', url: `/api/workflow/definitions/${id}/`,
    headers: getAuthenticationHeaders(), meta: { ...meta, readOnly: true } })
}

export function getWorkflowDefinitionNodes(id) {
  return request({ method: 'GET', url: `/api/workflow/definitions/${id}/nodes/`,
    headers: getAuthenticationHeaders(), meta: { ...meta, readOnly: true } })
}

export function getWorkflowExecutionResolution(id) {
  return request({ method: 'GET', url: `/api/workflow/definitions/${id}/execution-resolution/`,
    headers: getAuthenticationHeaders(), meta: { ...meta, readOnly: true } })
}

export function saveWorkflowDefinition(payload) {
  return request({ method: 'POST', url: '/api/workflow/definitions/',
    data: { action: 'SAVE_PROCESS_DEFINITION', payload }, headers: getAuthenticationHeaders(),
    meta: { ...meta, explicitBusinessAction: true,
      permissionCode: 'system.organization.workflow_responsibility.manage' } })
}

export function saveWorkflowNode(payload) {
  return request({ method: 'POST', url: '/api/workflow/definitions/',
    data: { action: 'SAVE_WORKFLOW_NODE', payload }, headers: getAuthenticationHeaders(),
    meta: { ...meta, explicitBusinessAction: true,
      permissionCode: 'system.organization.workflow_responsibility.manage' } })
}

export function createAtomicMinimalWorkflowTemplate(payload, idempotencyKey) {
  return request({
    method: 'POST',
    url: '/api/workflow/definitions/atomic-minimal-template/',
    data: payload,
    headers: {
      ...getAuthenticationHeaders(),
      'Idempotency-Key': idempotencyKey,
    },
    meta: {
      ...meta,
      explicitBusinessAction: true,
      permissionCode: 'system.organization.workflow_responsibility.manage',
      idempotentWrite: true,
    },
  })
}
