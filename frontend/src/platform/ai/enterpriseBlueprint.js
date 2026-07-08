// ======================================
// AI Enterprise Replication System
// 企业蓝图系统
// ======================================

export const buildBlueprint = (industry) => {
  const templates = {
    factory: {
      modules: ['purchase', 'production', 'inventory'],
      bpm: ['approval', 'procurement'],
      roles: ['admin', 'manager', 'worker'],
    },

    retail: {
      modules: ['sales', 'inventory', 'crm'],
      bpm: ['order', 'delivery'],
      roles: ['admin', 'sales'],
    },
  }

  return templates[industry] || templates.factory
}
