export const ACTION_COLUMN_WIDTH_RUNTIME_CODE = 'ActionColumnWidthRuntime'
export const ACTION_COLUMN_WIDTH_RUNTIME_VERSION = 'V1.14.2.8.4.27.2.39'

const MIN_COLUMN_WIDTH = 88
const MAX_COLUMN_WIDTH = 520
const BUTTON_GAP = 8
const CELL_PADDING = 24

function visibleAction(action) {
  if (!action) return false
  if (typeof action === 'string') return true
  if (action.visible === false) return false
  if (action.show === false) return false
  if (action.hidden === true) return false
  return true
}

function actionLabel(action) {
  if (typeof action === 'string') return action
  return action?.label || action?.actionName || action?.text || action?.name || ''
}

function clampWidth(width) {
  return Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, Math.ceil(width)))
}

function buttonWidth(label = '') {
  const length = Array.from(String(label || '')).length
  if (length >= 10) return 142
  if (length >= 7) return 116
  if (length >= 5) return 88
  return Math.max(32, length * 14 + 8)
}

export function normalizeActionButtons(actions = []) {
  return (actions || []).filter(visibleAction).map((action) => ({
    ...((typeof action === 'string') ? {} : action),
    label: actionLabel(action),
  }))
}

export function getActionButtonSize(action = {}) {
  const label = actionLabel(action)
  const width = buttonWidth(label)
  if (width >= 150) return 'lg'
  if (width >= 104) return 'md'
  return 'sm'
}

export function getActionColumnWidth(actions = [], options = {}) {
  const normalized = normalizeActionButtons(actions)
  const count = normalized.length
  if (!count) return options.emptyWidth || MIN_COLUMN_WIDTH

  const baseByCount = count === 1 ? 96 : count === 2 ? 152 : 208 + (count - 3) * 56
  const contentWidth = normalized.reduce((sum, action) => sum + buttonWidth(action.label), 0)
    + Math.max(count - 1, 0) * BUTTON_GAP
    + CELL_PADDING
  return clampWidth(Math.max(baseByCount, contentWidth))
}

export function createActionColumnWidthRuntime(actions = [], options = {}) {
  const normalizedActions = normalizeActionButtons(actions)
  const actionCount = normalizedActions.length
  const width = getActionColumnWidth(normalizedActions, options)
  return Object.freeze({
    runtimeCode: ACTION_COLUMN_WIDTH_RUNTIME_CODE,
    runtimeVersion: ACTION_COLUMN_WIDTH_RUNTIME_VERSION,
    source: 'Schema Action Contract',
    actionCount,
    density: actionCount <= 1 ? 'compact' : actionCount === 2 ? 'normal' : 'expanded',
    width,
    actions: Object.freeze(normalizedActions),
  })
}

export function getActionColumnWidthForRows(rows = [], resolver, fallbackActions = []) {
  const records = rows || []
  if (!records.length) return getActionColumnWidth(fallbackActions)
  const widths = records.map((row) => getActionColumnWidth(resolver(row)))
  return clampWidth(Math.max(...widths))
}

export function getActionColumnClass(actions = []) {
  const count = normalizeActionButtons(actions).length
  if (count <= 1) return 'app-action-column-compact'
  if (count === 2) return 'app-action-column-normal'
  if (count === 3) return 'app-action-column-wide'
  return 'app-action-column-xwide'
}
