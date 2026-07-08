// ===================================
// 全自动 CRUD 生成器（ERP核心引擎）
// ===================================

import { h } from 'vue'
import {
  ElTable,
  ElTableColumn,
  ElForm,
  ElFormItem,
  ElInput,
  ElDatePicker,
  ElSelect,
  ElTag,
} from 'element-plus'

// -------------------------------
// 生成 Table
// -------------------------------
export const generateTable = (meta) => {
  return (data) =>
    h(
      ElTable,
      { data, border: true },
      {
        default: () =>
          meta.table.columns.map((col) =>
            h(
              ElTableColumn,
              {
                prop: col.prop,
                label: col.label,
                width: col.width,
              },
              {
                default: (scope) => {
                  const value = scope.row[col.prop]

                  if (col.type === 'index') {
                    return scope.$index + 1
                  }

                  if (col.type === 'tag') {
                    const type = col.tagMap?.[value] || 'info'
                    return h(ElTag, { type }, () => value)
                  }

                  return value
                },
              }
            )
          ),
      }
    )
}

// -------------------------------
// 生成 Form（预留下一步升级）
// -------------------------------
export const generateForm = (meta) => {
  return (model) =>
    h(
      ElForm,
      { model },
      {
        default: () =>
          meta.filters.map((f) =>
            h(
              ElFormItem,
              { label: f.label },
              {
                default: () => {
                  if (f.type === 'input') {
                    return h(ElInput, {
                      modelValue: model[f.prop],
                      'onUpdate:modelValue': (val) => (model[f.prop] = val),
                    })
                  }

                  if (f.type === 'date') {
                    return h(ElDatePicker, {
                      modelValue: model[f.prop],
                      'onUpdate:modelValue': (val) => (model[f.prop] = val),
                    })
                  }

                  return null
                },
              }
            )
          ),
      }
    )
}
