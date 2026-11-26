export const BASE_DATA_ROW_SELECTION_CONTRACT = 'PCE-BASE-DATA-ROW-SELECTION-V1.0'

function identity(row, rowKey = 'id') {
  return typeof rowKey === 'function' ? rowKey(row) : row?.[rowKey]
}

function sameRow(left, right, rowKey) {
  const leftIdentity = identity(left, rowKey)
  const rightIdentity = identity(right, rowKey)
  if (leftIdentity !== undefined && rightIdentity !== undefined) {
    return String(leftIdentity) === String(rightIdentity)
  }
  return left === right
}

export function applySingleRowSelection(current = [], row, selected, rowKey = 'id') {
  const withoutRow = current.filter(item => !sameRow(item, row, rowKey))
  return selected ? [...withoutRow, row] : withoutRow
}

export function applyHeaderSelection(current = [], visibleRows = [], selected, rowKey = 'id') {
  const outsideVisibleScope = current.filter(item => !visibleRows.some(row => sameRow(item, row, rowKey)))
  return selected ? [...outsideVisibleScope, ...visibleRows] : outsideVisibleScope
}

export function selectionContains(selection = [], row, rowKey = 'id') {
  return selection.some(item => sameRow(item, row, rowKey))
}
