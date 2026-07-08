/**
 * ============================
 * Meta Runtime V14 - AI ERP Generator
 * ============================
 */

export const generateERP = async (prompt) => {
  // 模拟AI理解业务
  const model = analyzeBusiness(prompt)

  // 生成Meta
  const meta = generateMeta(model)

  // 生成BPM
  const workflow = generateWorkflow(model)

  // 生成权限
  const permission = generatePermission(model)

  return {
    meta,
    workflow,
    permission,
  }
}

/**
 * 业务理解（模拟AI）
 */
function analyzeBusiness(prompt) {
  if (prompt.includes('采购')) {
    return 'purchase_system'
  }

  if (prompt.includes('工厂')) {
    return 'factory_system'
  }

  return 'generic_system'
}

/**
 * 自动生成Meta
 */
function generateMeta(model) {
  if (model === 'purchase_system') {
    return {
      pageName: 'purchase',
      table: {
        columns: [
          { prop: 'order_no', label: '订单号' },
          { prop: 'supplier', label: '供应商' },
        ],
      },
      form: {
        fields: [
          { prop: 'order_no', label: '订单号' },
          { prop: 'supplier', label: '供应商' },
        ],
      },
    }
  }

  return {}
}

/**
 * 自动生成BPM
 */
function generateWorkflow(model) {
  return {
    enabled: true,
    states: ['DRAFT', 'APPROVE', 'DONE'],
  }
}

/**
 * 自动生成权限
 */
function generatePermission(model) {
  return {
    role: ['admin', 'user'],
  }
}
