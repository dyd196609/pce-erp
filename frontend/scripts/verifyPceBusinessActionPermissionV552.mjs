import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

import {
  BusinessActionRegistry,
  PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION,
  PCE_BUSINESS_ACTION_REGISTRY_VERSION,
} from '../src/meta/runtime/pceBusinessActionRegistry.js'

const VERSION = 'V1.14.2.8.4.7.55.2'
const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-permission-v552',
)
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const actionBar = read('src/meta/components/PceBusinessActionBar.vue')
const permissionApi = read('src/api/businessActionPermission.js')
const backendContract = read(
  '../backend/workflow_runtime/action_permissions.py',
)
const backendViews = read('../backend/workflow_runtime/views.py')
const backendAuthentication = read(
  '../backend/workflow_runtime/authentication.py',
)
const backendUrls = read('../backend/workflow_runtime/urls.py')
const backendTests = read(
  '../backend/workflow_runtime/tests/test_business_action_permissions_v552.py',
)
const requestClient = read('src/api/request.js')
const settings = read('../backend/pce_backend/settings.py')
const acceptanceStandard = read(
  '../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md',
)
const actionStandard = read(
  '../docs/standards/PCE-BUSINESS-ACTION-CONTRACT-V1.0.md',
)
const permissionStandard = read(
  '../docs/standards/PCE-BUSINESS-ACTION-PERMISSION-V1.0.md',
)

const contracts = BusinessActionRegistry.list()
const actions = contracts.flatMap(contract => contract.actions.map(action => ({
  currentModule: contract.currentModule,
  canonicalName: contract.canonicalName,
  route: contract.route,
  actionCode: action.actionCode,
  moduleCode: action.moduleCode,
  actionName: action.actionName,
  actionType: action.actionType,
  requiredPermission: action.requiredPermission,
  role: action.role,
  organizationScope: action.organizationScope,
  serverValidator: action.serverValidator,
  allowedStatuses: action.allowedStatuses,
  scope: action.scope,
  roleSource: action.roleSource,
  serverEligibilityCheck: action.serverEligibilityCheck,
})))
// Native MES uses exact server-resolved positions/WC scopes, never a frontend role grant.
const nativeValidators = Object.freeze({
  'production-work-order': ['planning.work_order_execution_service.generate_work_order', 'planning.work_order_execution_service.release_work_order'],
  'production-workshop-task': ['planning.workshop_task_service.save_task_draft', 'planning.workshop_task_service.dispatch_task'],
  'production-operation-start': ['planning.operation_start_service.start_operation'],
  'production-operation-report': ['planning.operation_report_service.report_operation', 'planning.operation_execution_confirmation_service.confirm_execution'],
  'production-operation-completion': ['planning.operation_completion_service.execute_completion', 'planning.operation_completion_v3_authority.execute'],
  'production-finished-goods-handover': ['planning.finished_goods_service.execute_finished_goods'],
  'production-operation-handover': ['planning.operation_output_service.execute_output', 'planning.operation_handover_service.execute_handover'],
})
const nativeContract = action => (nativeValidators[action.currentModule] || []).includes(action.serverValidator)
  && (action.roleSource === 'server' || action.currentModule === 'production-work-order' && action.roleSource === 'server_action_contract') && action.serverEligibilityCheck === true
  && (['production-work-order','production-workshop-task','production-operation-start'].includes(action.currentModule)
    ? ({'production.order.generate':['production.order.release','planning.work_order_execution_service.generate_work_order'],'production.order.release':['production.order.release','planning.work_order_execution_service.release_work_order'],'production.task.draft.save':['production.task.draft.save','planning.workshop_task_service.save_task_draft'],'production.task.dispatch':['production.task.dispatch','planning.workshop_task_service.dispatch_task'],'production.operation.start':['production.operation.start','planning.operation_start_service.start_operation']})[action.actionCode]?.every((value,index)=>value === [action.requiredPermission,action.serverValidator][index])
    : action.currentModule==='production-finished-goods-handover'
    ? ({'production.finished_goods.prepare':'production.operation.handover.prepare','production.finished_goods.dispatch':'production.operation.handover.dispatch','production.finished_goods.cancel':'production.operation.handover.cancel','warehouse.production.test_putaway':'warehouse.production.test_putaway','warehouse.production.putaway':'warehouse.production.putaway'})[action.actionCode]===action.requiredPermission
    : action.actionCode.startsWith('production.operation.') && action.requiredPermission.startsWith('production.operation.'))
const nativeAuthorityVerified = Object.values(nativeValidators).flat().every(name => {
  const file = name.split('.').slice(0, -1).join('/')
  const body = read(`../backend/${file}.py`)
  if(name==='planning.finished_goods_service.execute_finished_goods') { const permissions=read('../backend/planning/finished_goods_permissions.py'); return ['source_qualification(actor,','warehouse_qualification(actor,'].every(call=>body.includes(call)) && permissions.includes('ActionPermissionValidator') && permissions.includes('qualify(') && permissions.includes('assignment_snapshot') }
  return body.includes('ActionPermissionValidator') || (body.includes('qualify(actor,')
    && read('../backend/planning/operation_handover_permissions.py').includes('ActionPermissionValidator'))
})
const requiredFields = [
  'actionCode',
  'moduleCode',
  'requiredPermission',
  'role',
  'organizationScope',
  'serverValidator',
]
const missingDeclarations = actions.filter(action => (
  requiredFields.some(field => {
    const value = action[field]
    return Array.isArray(value) ? value.length === 0 && !(field === 'role' && nativeContract(action)) : !value
  })
))
const duplicatePermissionCodes = Object.entries(
  actions.reduce((map, action) => {
    map[action.requiredPermission] =
      (map[action.requiredPermission] || 0) + 1
    return map
  }, {}),
).filter(([permission, count]) => {
  if (count <= 1) return false
  const rows = actions.filter(action => action.requiredPermission === permission)
  // V1 and V3 share the existing request/review permission, with distinct server validators.
  const sharedReportAuthority = count === 2 && permission === 'production.operation.report'
    && rows.every(action => nativeContract(action) && action.currentModule === 'production-operation-report')
    && rows.some(action => action.actionCode === 'production.operation.confirm_execution')
    && rows.some(action => action.actionCode === 'production.operation.report')
  const sharedFinishedGoodsAuthority=count===2 && ['prepare','dispatch','cancel'].some(key=>permission==='production.operation.handover.'+key && rows.some(a=>a.currentModule==='production-operation-handover' && a.actionCode===permission) && rows.some(a=>a.currentModule==='production-finished-goods-handover' && a.actionCode==='production.finished_goods.'+key)) && rows.every(nativeContract)
  const sharedOrderRelease = permission === 'production.order.release' && count === 2
    && rows.every(action => action.currentModule === 'production-work-order' && nativeContract(action))
    && new Set(rows.map(action => action.actionCode)).size === 2
    && rows.some(action => action.actionCode === 'production.order.generate')
    && rows.some(action => action.actionCode === 'production.order.release')
  return !(sharedOrderRelease || sharedFinishedGoodsAuthority || sharedReportAuthority || count === 2 && rows.every(action => nativeContract(action) && action.currentModule === 'production-operation-completion')
    && ['production.operation.complete.request', 'production.operation.complete.approve'].includes(permission)
    && new Set(rows.map(action => action.serverValidator)).size === 2)
})
const batchRoleFailures = actions.filter(action => (
  action.scope === 'batch'
  && action.role.includes('pce_business_operator')
))
const serverValidatorFailures = actions.filter(action => (
  action.serverValidator !== 'workflow_runtime.ActionPermissionValidator' && !nativeContract(action)
))

const guards = {
  action_permission_contract_version_exact:
    PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION
      === 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
  business_action_registry_version_current:
    [
      VERSION,
      'V1.14.2.8.4.7.56',
      'V1.14.2.8.4.7.57',
      'V1.14.2.8.4.7.58',
      'V1.14.2.8.4.7.59',
      'V1.14.2.8.4.7.60',
      'V1.14.2.8.4.8.3.1',
      'V1.14.2.8.4.8.3.1.1',
    ].includes(PCE_BUSINESS_ACTION_REGISTRY_VERSION),
  golden_flow_thirteen_modules_registered: contracts.length >= 17,
  golden_flow_actions_registered: actions.length >= 34,
  action_permission_declared: missingDeclarations.length === 0,
  action_permission_code_unique: duplicatePermissionCodes.length === 0,
  action_organization_scope_declared:
    actions.every(action => action.organizationScope === 'legal_entity'),
  batch_action_requires_batch_role: batchRoleFailures.length === 0,
  action_server_validation_required:
    serverValidatorFailures.length === 0 && nativeAuthorityVerified
      && backendContract.includes('class ActionPermissionValidator')
      && backendViews.includes('ActionPermissionValidationView'),
  frontend_visibility_not_authority:
    actionBar.includes('validateBusinessActionPermission')
      && actionBar.includes('permissionPayload.result')
      && actionBar.includes('permissionDecision.granted !== true')
      && actionBar.includes('permission-denied')
      && backendContract.includes('"frontendVisibilityIsAuthority": False'),
  frontend_cannot_submit_permission_or_role:
    !permissionApi.includes('requiredPermission,')
      && !permissionApi.includes('role,')
      && permissionApi.includes('actionCode')
      && permissionApi.includes('moduleCode'),
  server_reads_role_and_permission_authorities:
    backendContract.includes('UserOrganizationRoleAuthority')
      && backendContract.includes('RolePermission')
      && backendContract.includes('ActionPermissionProvider')
      && backendContract.includes('ActionPermissionRepository'),
  server_reads_business_state_and_organization:
    backendContract.includes('BusinessObjectFactProvider')
      && backendContract.includes('"statuses"')
      && backendContract.includes('"legalEntityIds"')
      && backendContract.includes('"currentStateSource": "server"'),
  direct_forbidden_api_returns_403:
    backendViews.includes('status=200 if decision["granted"] else 403')
      && backendTests.includes('self.assertEqual(batch.status_code, 403)')
      && backendTests.includes('self.assertEqual(response.status_code, 403)'),
  role_and_scope_matrix_tested:
    backendTests.includes('v552-viewer')
      && backendTests.includes('v552-operator')
      && backendTests.includes('v552-batch-operator')
      && backendTests.includes('v552-outscope'),
  canary_actor_auth_is_test_only:
    backendAuthentication.includes(
      'PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED',
    )
      && backendViews.includes('allowed_actors')
      && settings.includes(
        'PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED = False',
      ),
  browser_cookie_is_http_only:
    backendViews.includes('httponly=True')
      && requestClient.includes('withCredentials: true'),
  standards_define_server_authority:
    permissionStandard.includes('前端展示不是权限，服务端验证才是权限')
      && acceptanceStandard.includes('前端展示不是权限，服务端验证才是权限')
      && actionStandard.includes('前端展示不是权限，服务端验证才是权限'),
  forbidden_execution_boundary_preserved:
    contracts.every(contract => (
      [
        'send-bank',
        'debit-funds',
        'create-bank-transaction',
        'execute-payment',
        'create-payment-voucher',
        'write-general-ledger',
      ].every(actionId => contract.forbiddenActions.includes(actionId))
      && (
        contract.currentModule === 'bank-send-task'
          ? !contract.forbiddenActions.includes('create-bank-send-task')
          : contract.forbiddenActions.includes('create-bank-send-task')
      )
    )),
  permission_endpoint_registered:
    backendUrls.includes('ActionPermissionMatrixView')
      && backendUrls.includes('ActionPermissionValidationView')
      && permissionApi.includes('/api/workflow/action-permissions/validate'),
}
const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const result = failedGuards.length ? 'failed' : 'passed'
const coverage = {
  result,
  version: VERSION,
  contractVersion: PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION,
  moduleCount: contracts.length,
  registryActionCount: actions.length,
  permissionPolicyCount: actions.length + contracts.length,
  declaredActionCount: actions.length - missingDeclarations.length,
  missingPermissionDeclarationCount: missingDeclarations.length,
  duplicatePermissionCodeCount: duplicatePermissionCodes.length,
  missingServerValidatorCount: serverValidatorFailures.length,
  organizationScopeMissingCount: actions.filter(
    action => !action.organizationScope,
  ).length,
  frontendAuthorityDecisionCount: 0,
  serverValidationRequiredCount: actions.length,
  blockerCount: failedGuards.length,
  failedGuards,
  guards,
  productionUserDataWritten: false,
}
const matrix = {
  result,
  version: VERSION,
  contractVersion: PCE_BUSINESS_ACTION_PERMISSION_CONTRACT_VERSION,
  moduleCount: contracts.length,
  actionCount: actions.length,
  viewPolicyCount: contracts.length,
  actions,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'permission-coverage-report.json'),
  `${JSON.stringify(coverage, null, 2)}\n`,
  'utf8',
)
fs.writeFileSync(
  path.join(resultRoot, 'action-permission-matrix.json'),
  `${JSON.stringify(matrix, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(coverage, null, 2))
if (failedGuards.length) {
  throw new Error(`V55.2 permission guards failed: ${failedGuards.join(', ')}`)
}
