export const buildPurchaseOrderTableVM = (dto) => {
  return {
    ...dto,

    // UI专用字段（和业务解耦）
    riskTagType:
      dto.risk_level === 'HIGH' ? 'danger' : dto.risk_level === 'MEDIUM' ? 'warning' : 'success',

    decisionLabel:
      dto.decision === 'APPROVE' ? '通过' : dto.decision === 'REVIEW' ? '待审' : '拒绝',

    supplierLevelColor:
      dto.supplier_level === 'A'
        ? 'success'
        : dto.supplier_level === 'B'
          ? 'info'
          : dto.supplier_level === 'C'
            ? 'warning'
            : 'danger',
  }
}
