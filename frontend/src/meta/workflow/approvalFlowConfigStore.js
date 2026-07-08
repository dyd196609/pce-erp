const STORAGE_KEY = 'approval-flow-config-state-v1'

const MODULES = [
  { moduleName: 'purchaseRequest', moduleLabel: '采购申请', defaultStepCount: 3 },
  { moduleName: 'purchaseInquiry', moduleLabel: '采购询价', defaultStepCount: 2 },
  { moduleName: 'priceApproval', moduleLabel: '核价单', defaultStepCount: 3 },
  { moduleName: 'purchaseOrder', moduleLabel: '采购订单', defaultStepCount: 3 },
]

const STEP_POOL = [
  { stepKey: 'review', stepLabel: '审核', role: '审核员' },
  { stepKey: 'recheck', stepLabel: '复核', role: '复核员' },
  { stepKey: 'approve', stepLabel: '审批', role: '审批员' },
]

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function buildSteps(count = 3) {
  const selected = count === 1 ? [STEP_POOL[2]] : count === 2 ? [STEP_POOL[0], STEP_POOL[2]] : STEP_POOL
  return selected.map((step, index) => ({
    id: createId('approval-step'),
    ...step,
    required: true,
    order: index + 1,
  }))
}

function defaultState() {
  const stamp = nowText()
  return {
    approvalFlowConfigs: MODULES.map((module) => ({
      id: createId('approval-flow'),
      moduleName: module.moduleName,
      moduleLabel: module.moduleLabel,
      enabled: true,
      steps: buildSteps(module.defaultStepCount),
      createdAt: stamp,
      updatedAt: stamp,
    })),
  }
}

function normalizeState(raw = {}) {
  const base = defaultState()
  const configs = MODULES.map((module) => {
    const existing = (raw.approvalFlowConfigs || []).find((item) => item.moduleName === module.moduleName)
    return existing ? {
      ...existing,
      moduleLabel: existing.moduleLabel || module.moduleLabel,
      enabled: existing.enabled !== false,
      steps: existing.steps?.length ? existing.steps : buildSteps(module.defaultStepCount),
    } : base.approvalFlowConfigs.find((item) => item.moduleName === module.moduleName)
  })
  return { approvalFlowConfigs: configs }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : defaultState()
  } catch (error) {
    console.warn('[APPROVAL FLOW CONFIG] fallback to default state', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function getApprovalFlowState() {
  return clone(state)
}

export function listApprovalFlowConfigs() {
  return clone(state.approvalFlowConfigs)
}

export function getApprovalFlowConfig(moduleName) {
  return clone(state.approvalFlowConfigs.find((item) => item.moduleName === moduleName))
}

export function saveApprovalFlowConfig(moduleName, patch = {}) {
  const current = state.approvalFlowConfigs.find((item) => item.moduleName === moduleName)
  if (!current) return null
  Object.assign(current, {
    ...patch,
    steps: patch.stepCount ? buildSteps(Number(patch.stepCount)) : patch.steps || current.steps,
    updatedAt: nowText(),
  })
  persist()
  return clone(current)
}

export function getEnabledApprovalSteps(moduleName) {
  const config = state.approvalFlowConfigs.find((item) => item.moduleName === moduleName)
  if (!config || config.enabled === false) return buildSteps(1)
  return clone((config.steps || []).filter((step) => step.required !== false).sort((a, b) => a.order - b.order))
}

export function getApprovalStepCount(moduleName) {
  return getEnabledApprovalSteps(moduleName).length || 1
}

export function getNextApprovalStatus(moduleName, currentStatus) {
  const count = getApprovalStepCount(moduleName)
  if (currentStatus === 'draft' || currentStatus === 'rejected') return 'submitted'
  if (currentStatus === 'submitted') return count === 1 ? 'approved' : 'reviewed'
  if (currentStatus === 'reviewed') return count === 2 ? 'approved' : 'rechecked'
  if (currentStatus === 'rechecked') return 'approved'
  return currentStatus
}
