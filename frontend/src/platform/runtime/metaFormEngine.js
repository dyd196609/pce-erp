// =====================================
// Meta Runtime V2 - Form Engine
// 自动表单 + 自动弹窗 + 自动校验
// =====================================

import { reactive } from 'vue'

/**
 * 根据 Meta 自动生成表单模型
 */
export const createFormModel = (meta) => {
  const model = {}

  const fields = [...(meta.filters || []), ...(meta.form?.fields || [])]

  fields.forEach((f) => {
    model[f.prop] = f.default ?? ''
  })

  return reactive(model)
}

/**
 * 表单校验（基础版，可扩展）
 */
export const validateForm = (meta, model) => {
  const fields = [...(meta.form?.fields || [])]

  for (const f of fields) {
    if (f.required && !model[f.prop]) {
      return {
        valid: false,
        message: `${f.label} 不能为空`,
      }
    }
  }

  return { valid: true }
}

/**
 * 自动生成提交数据（DTO）
 */
export const buildFormDTO = (meta, model) => {
  const dto = {}

  const fields = [...(meta.form?.fields || [])]

  fields.forEach((f) => {
    dto[f.prop] = model[f.prop]
  })

  return dto
}
