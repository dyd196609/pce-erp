import { enterpriseOperationModel } from './enterpriseOperationModel.js'
import {
  addBusinessProcess,
  getBusinessProcessByCode,
  listBusinessProcesses,
  recordBusinessProcessDesignExecution,
  setBusinessProcessEnabled,
  updateBusinessProcess,
} from '../process/businessProcessRegistry.js'

const STORAGE_KEY = 'enterprise-operation-state-v1'
const MOJIBAKE_PATTERN = /(褰撳|浼佷笟|鏁版嵁|绯荤|浠樻|閲囪|搴撳|鏉ユ|瀹℃|淇濆|杩斿|鐪熷|渚涘|鑽夌|鍩虹|妯|銆|�)/

const DISPLAY_TEXT_REPAIRS = {
  褰撳墠宀椾綅: '当前岗位',
  涓氬姟: '业务',
  绯荤粺閰嶇疆: '系统配置',
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function createDefaultState() {
  return {
    company: clone(enterpriseOperationModel.organization.company),
    departments: clone(enterpriseOperationModel.organization.departments),
    roles: clone(enterpriseOperationModel.organization.roles),
    users: clone(enterpriseOperationModel.organization.users),
    permissions: clone(enterpriseOperationModel.organization.permissions),
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
  const defaults = createDefaultState()
  const { processes: _legacyProcessCopies, ...stateWithoutLegacyProcesses } = nextState
  return {
    ...defaults,
    ...stateWithoutLegacyProcesses,
    config: {
      ...defaults.config,
      ...(nextState.config || {}),
    },
  }
}

function hasMojibake(value) {
  return typeof value === 'string' && MOJIBAKE_PATTERN.test(value)
}

function repairDisplayText(value) {
  if (!hasMojibake(value)) return value
  return DISPLAY_TEXT_REPAIRS[value] || value
}

function repairCollectionById(collection = [], defaults = [], fields = []) {
  const defaultMap = new Map(defaults.map((item) => [item.id, item]))
  return collection.map((item) => {
    const standard = defaultMap.get(item.id) || {}
    const next = { ...item }
    fields.forEach((field) => {
      if (hasMojibake(next[field])) next[field] = standard[field] || repairDisplayText(next[field])
    })
    return next
  })
}

function repairEnterpriseDisplayState(nextState) {
  const defaults = createDefaultState()
  return {
    ...nextState,
    tasks: repairCollectionById(nextState.tasks, defaults.tasks, ['title', 'process', 'owner', 'due', 'status']),
    approvals: repairCollectionById(nextState.approvals, defaults.approvals, ['title', 'applicant', 'status']),
    workflows: repairCollectionById(nextState.workflows, defaults.workflows, ['name', 'currentStep', 'progress']),
    quickActions: repairCollectionById(nextState.quickActions, defaults.quickActions, ['name']),
    departments: repairCollectionById(nextState.departments, defaults.departments, ['name', 'owner', 'processOwner']),
    roles: repairCollectionById(nextState.roles, defaults.roles, ['name', 'responsibility']),
    users: repairCollectionById(nextState.users, defaults.users, ['name', 'department', 'role']),
    permissions: repairCollectionById(nextState.permissions, defaults.permissions, ['name', 'role', 'scope']),
  }
}

function stateHasMojibake(nextState) {
  return MOJIBAKE_PATTERN.test(JSON.stringify(nextState))
}

function loadState() {
  if (typeof localStorage === 'undefined') return createDefaultState()

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return createDefaultState()
    const normalized = normalizeState(JSON.parse(raw))
    const repaired = stateHasMojibake(normalized) ? repairEnterpriseDisplayState(normalized) : normalized
    if (repaired !== normalized) localStorage.setItem(STORAGE_KEY, JSON.stringify(repaired))
    return repaired
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
  return clone({
    ...state,
    processes: listBusinessProcesses(),
  })
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
  const value = String(id || '')
  return clone(
    getBusinessProcessByCode(value)
    || listBusinessProcesses().find(process => (
      process.processName === value || process.moduleCode === value
    ))
    || null,
  )
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
  const processCode = process.processCode || process.id || createId('PROCESS')
  return addBusinessProcess({
    ...process,
    processCode,
    processName: process.processName || process.name || processCode,
    processVersion: process.processVersion || process.version || 'V1.0',
    moduleCode: process.moduleCode || String(process.category || 'SCM').toUpperCase(),
    moduleName: process.moduleName || process.categoryName || '企业业务模块',
    nodes: process.nodes || [],
  })
}

export function updateProcess(id, patch) {
  return updateBusinessProcess(String(id), {
    ...patch,
    processName: patch.processName || patch.name,
    processVersion: patch.processVersion || patch.version,
  })
}

export function deleteProcess(id) {
  return setBusinessProcessEnabled(String(id), false)
}

export function executeProcess(id, payload = {}) {
  const process = getProcessById(id)
  if (!process) return null

  recordBusinessProcessDesignExecution(process.processCode, payload)

  return addTask({
    title: `执行${process.processName}`,
    process: process.processName,
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
    processId: process?.processCode || processId,
    processName: process?.processName || '业务流程',
    name: payload.name || '新建业务单',
    type: payload.type || process?.moduleName || '业务单',
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
