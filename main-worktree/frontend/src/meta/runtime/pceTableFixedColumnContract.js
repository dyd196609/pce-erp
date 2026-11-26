export const PCE_TABLE_FIXED_COLUMN_CONTRACT_VERSION = 'V1.14.2.8.4.4'

export const pceFixedColumnWidths = {
  selection: 48,
  index: 64,
}

export const pceFixedColumnRoles = {
  selection: {
    role: 'selection',
    selectors: [
      '.business-table-selection-column',
      '.payment-fixed-selection-column',
      '.el-table-column--selection',
      '.el-table__cell:has(.el-checkbox)',
    ],
    shiftDirection: 'left',
  },
  index: {
    role: 'index',
    selectors: [
      '.pce-fixed-index-column',
      '.payment-fixed-index-column',
    ],
    shiftDirection: 'left',
  },
  primaryNo: {
    role: 'primary-no',
    selectors: [
      '.pce-fixed-primary-no-column',
      '.payment-fixed-no-column',
    ],
    shiftDirection: 'left',
  },
  operation: {
    role: 'operation',
    selectors: [
      '.payment-fixed-action-column',
    ],
    shiftDirection: 'right',
  },
}

export const pceFixedColumnCssVariables = {
  selectionWidth: '--pce-selection-column-width',
  indexWidth: '--pce-index-column-width',
  primaryLeft: '--pce-primary-column-left',
  leftPinOffset: '--pce-left-column-pin-offset',
}

export function resolvePcePrimaryColumnLeft() {
  return pceFixedColumnWidths.selection + pceFixedColumnWidths.index
}

export function listPceFixedColumnRoleContracts() {
  return Object.values(pceFixedColumnRoles).map((item) => ({
    ...item,
    selectors: [...item.selectors],
  }))
}
