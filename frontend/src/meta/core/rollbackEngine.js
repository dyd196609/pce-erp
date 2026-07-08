export function generateRollback(diff) {
  return {
    rollbackPlan: (diff?.removed || []).map((target) => ({
      action: 'RESTORE',
      target,
    })),
  }
}
