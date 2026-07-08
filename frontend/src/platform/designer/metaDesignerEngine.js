/**
 * ============================
 * Meta Designer Engine V8
 * ============================
 */

/**
 * 设计模式状态
 */
let designMode = false

export const enableDesignMode = () => {
  designMode = true
}

export const disableDesignMode = () => {
  designMode = false
}

export const isDesignMode = () => designMode

/**
 * 动态修改 Meta（核心）
 */
export const updateMeta = (meta, patch) => {
  return {
    ...meta,
    ...patch,

    table: {
      ...meta.table,
      ...patch.table,
    },

    form: {
      ...meta.form,
      ...patch.form,
    },

    actions: patch.actions || meta.actions || [],
  }
}

/**
 * 添加字段（表单设计器）
 */
export const addField = (meta, field) => {
  return {
    ...meta,
    form: {
      ...meta.form,
      fields: [...(meta.form?.fields || []), field],
    },
  }
}

/**
 * 删除字段
 */
export const removeField = (meta, fieldKey) => {
  return {
    ...meta,
    form: {
      ...meta.form,
      fields: (meta.form?.fields || []).filter((f) => f.prop !== fieldKey),
    },
  }
}

/**
 * 修改列
 */
export const updateColumn = (meta, prop, patch) => {
  const columns = meta.table?.columns || []

  return {
    ...meta,
    table: {
      ...meta.table,
      columns: columns.map((col) => (col.prop === prop ? { ...col, ...patch } : col)),
    },
  }
}

/**
 * 添加Action
 */
export const addAction = (meta, action) => {
  return {
    ...meta,
    actions: [...(meta.actions || []), action],
  }
}
