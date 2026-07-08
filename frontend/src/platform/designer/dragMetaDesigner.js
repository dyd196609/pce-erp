/**
 * ============================
 * Meta Runtime V9 - Drag Designer
 * ============================
 */

let canvas = {
  fields: [],
  columns: [],
  actions: [],
}

/**
 * 初始化设计器
 */
export const initDesigner = (meta) => {
  canvas = JSON.parse(JSON.stringify(meta))
  return canvas
}

/**
 * 拖拽添加字段
 */
export const dragAddField = (field) => {
  canvas.fields.push({
    id: generateId(),
    ...field,
  })
  return canvas
}

/**
 * 拖拽添加列
 */
export const dragAddColumn = (column) => {
  canvas.columns.push({
    id: generateId(),
    ...column,
  })
  return canvas
}

/**
 * 拖拽添加按钮
 */
export const dragAddAction = (action) => {
  canvas.actions.push({
    id: generateId(),
    ...action,
  })
  return canvas
}

/**
 * 删除元素
 */
export const removeItem = (type, id) => {
  canvas[type] = canvas[type].filter((i) => i.id !== id)
  return canvas
}

/**
 * 实时生成Meta JSON（核心）
 */
export const buildMeta = () => {
  return {
    layout: 'table-form',
    table: {
      columns: canvas.columns,
    },
    form: {
      fields: canvas.fields,
    },
    actions: canvas.actions,
  }
}

/**
 * 清空设计器
 */
export const resetDesigner = () => {
  canvas = { fields: [], columns: [], actions: [] }
}

/**
 * ID生成器
 */
function generateId() {
  return 'id_' + Math.random().toString(36).slice(2, 9)
}
