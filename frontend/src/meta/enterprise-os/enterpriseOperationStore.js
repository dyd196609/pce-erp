import { enterpriseOperationModel, processGroups } from './enterpriseOperationModel.js'

const STORAGE_KEY = 'enterprise-operation-state-v1'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function createDefaultProcesses() {
  return processGroups.flatMap((group) => (
    enterpriseOperationModel.processCenter[group.key] || []
  ).map((process) => ({
    ...process,
    category: group.key,
    categoryName: group.title,
    enabled: process.enabled !== false,
  })))
}

function createDefaultState() {
  return {
    company: clone(enterpriseOperationModel.organization.company),
    departments: clone(enterpriseOperationModel.organization.departments),
    roles: clone(enterpriseOperationModel.organization.roles),
    users: clone(enterpriseOperationModel.organization.users),
    permissions: clone(enterpriseOperationModel.organization.permissions),
    processes: createDefaultProcesses(),
    tasks: [
      ...enterpriseOperationModel.workCenter.pendingTasks.map((task) => ({ ...task, type: 'pending' })),
      ...enterpriseOperationModel.workCenter.executionTasks.map((task) => ({ ...task, type: 'execution' })),
    ],
    approvals: clone(enterpriseOperationModel.workCenter.approvals),
    workflows: clone(enterpriseOperationModel.workCenter.workflows),
    quickActions: enterpriseOperationModel.workCenter.quickActions.map((name, index) => ({
      id: `quick-${index + 1}`,
      name,
    })),
    businessRecords: [],
    config: {
      enterpriseOSMode: 'ON',
      moduleUI: 'DISABLED',
      processUI: 'ACTIVE',
      organizationUI: 'ACTIVE',
      defaultEntry: '/process-center',
      rolePermissionMode: 'ROLE_BASED',
    },
  }
}

function normalizeState(nextState = {}) {
  return {
    ...createDefaultState(),
    ...nextState,
    config: {
      ...createDefaultState().config,
      ...(nextState.config || {}),
    },
  }
}

function loadState() {
  if (typeof localStorage === 'undefined') return createDefaultState()

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : createDefaultState()
  } catch (error) {
    return createDefaultState()
  }
}

let state = loadState()

function persist() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }
}

function upsert(collection, item) {
  const id = item.id || createId(collection)
  state[collection] = [...(state[collection] || []), { ...item, id }]
  persist()
  return id
}

function update(collection, id, patch) {
  state[collection] = (state[collection] || []).map((item, index) => (
    matchesId(item, index, id) ? { ...item, ...patch } : item
  ))
  persist()
}

function remove(collection, id) {
  state[collection] = (state[collection] || []).filter((item, index) => !matchesId(item, index, id))
  persist()
}

function matchesId(item, index, id) {
  const value = String(id || '')
  return String(item.id) === value || String(index + 1) === value
}

function findById(collection, id, matcher) {
  const value = String(id || '')
  return clone((state[collection] || []).find((item, index) => (
    matchesId(item, index, value) || matcher?.(item, value)
  )) || null)
}

export function getEnterpriseOperationState() {
  return clone(state)
}

export function getTaskById(id) {
  return findById('tasks', id, (item, value) => item.type === 'pending' && String(item.id) === value)
}

export function getApprovalById(id) {
  return findById('approvals', id)
}

export function getExecutionTaskById(id) {
  return findById('tasks', id, (item, value) => item.type === 'execution' && String(item.id) === value)
}

export function getProcessById(id) {
  return findById('processes', id, (item, value) => (
    item.category === value || item.key === value || item.name === value
  ))
}

export function getDepartmentById(id) {
  return findById('departments', id)
}

export function getRoleById(id) {
  return findById('roles', id)
}

export function getUserById(id) {
  return findById('users', id)
}

export function getPermissionById(id) {
  return findById('permissions', id)
}

export function addDepartment(department) {
  return upsert('departments', department)
}

export function updateDepartment(id, patch) {
  update('departments', id, patch)
}

export function deleteDepartment(id) {
  remove('departments', id)
}

export function addRole(role) {
  return upsert('roles', role)
}

export function updateRole(id, patch) {
  update('roles', id, patch)
}

export function deleteRole(id) {
  remove('roles', id)
}

export function addUser(user) {
  return upsert('users', user)
}

export function updateUser(id, patch) {
  update('users', id, patch)
}

export function deleteUser(id) {
  remove('users', id)
}

export function addPermission(permission) {
  return upsert('permissions', permission)
}

export function updatePermission(id, patch) {
  update('permissions', id, patch)
}

export function deletePermission(id) {
  remove('permissions', id)
}

export function addProcess(process) {
  return upsert('processes', {
    enabled: true,
    pending: 0,
    status: '待处理',
    ...process,
  })
}

export function updateProcess(id, patch) {
  update('processes', id, patch)
}

export function deleteProcess(id) {
  remove('processes', id)
}

export function executeProcess(id, payload = {}) {
  const process = getProcessById(id)
  if (!process) return null

  updateProcess(process.id, {
    status: '执行中',
    executionAction: payload.action || '确认执行',
    executionResult: payload.result || '已确认执行',
    pending: Math.max(0, Number(process.pending || 0) - 1),
  })

  return addTask({
    title: `执行${process.name}`,
    process: process.name,
    owner: process.owner,
    status: '执行中',
    type: 'execution',
    result: payload.result || '',
  })
}

export function createBusinessRecord(processId, payload = {}) {
  const process = getProcessById(processId)
  const record = {
    id: createId('business-record'),
    processId: process?.id || processId,
    processName: process?.name || '业务流程',
    name: payload.name || '新建业务单',
    type: payload.type || process?.categoryName || '业务单',
    owner: payload.owner || process?.owner || '负责人',
    planDate: payload.planDate || '',
    remark: payload.remark || '',
    status: '已创建',
    createdAt: new Date().toISOString(),
  }

  state.businessRecords = [...(state.businessRecords || []), record]
  persist()
  return record.id
}

export function addTask(task) {
  return upsert('tasks', {
    type: 'pending',
    due: '今天',
    status: '待处理',
    ...task,
  })
}

export function updateTask(id, patch) {
  update('tasks', id, patch)
}

export function approveTask(id, opinion = '') {
  updateTask(id, { status: '已审批', opinion })
}

export function rejectTask(id, opinion = '') {
  updateTask(id, { status: '已驳回', opinion })
}

export function completeTask(id, result = '') {
  updateTask(id, { status: '已完成', result, completed: true })
}

export function addApproval(approval) {
  return upsert('approvals', approval)
}

export function updateApproval(id, patch) {
  update('approvals', id, patch)
}

export function deleteApproval(id) {
  remove('approvals', id)
}

export function updateCompany(patch) {
  state.company = { ...state.company, ...patch }
  persist()
}

export function updateConfig(patch) {
  state.config = { ...state.config, ...patch }
  persist()
}

export function resetEnterpriseOperationState() {
  state = createDefaultState()
  persist()
}
