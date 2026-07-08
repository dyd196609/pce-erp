import { h } from 'vue'
import { ElForm, ElFormItem, ElInput, ElDatePicker, ElSelect, ElOption } from 'element-plus'

// ================================
// 自动表单生成器（ERP核心）
// ================================

export const generateForm = (meta) => {
  return (model) =>
    h(
      ElForm,
      { model, labelWidth: '100px' },
      {
        default: () =>
          meta.filters.map((f) =>
            h(
              ElFormItem,
              { label: f.label, prop: f.prop },
              {
                default: () => {
                  // 输入框
                  if (f.type === 'input') {
                    return h(ElInput, {
                      modelValue: model[f.prop],
                      placeholder: f.label,
                      'onUpdate:modelValue': (val) => (model[f.prop] = val),
                    })
                  }

                  // 日期
                  if (f.type === 'date') {
                    return h(ElDatePicker, {
                      modelValue: model[f.prop],
                      type: 'date',
                      placeholder: f.label,
                      'onUpdate:modelValue': (val) => (model[f.prop] = val),
                    })
                  }

                  // 下拉
                  if (f.type === 'select') {
                    return h(
                      ElSelect,
                      {
                        modelValue: model[f.prop],
                        placeholder: f.label,
                        'onUpdate:modelValue': (val) => (model[f.prop] = val),
                      },
                      () =>
                        (f.options || []).map((opt) =>
                          h(ElOption, {
                            label: opt.label,
                            value: opt.value,
                          })
                        )
                    )
                  }

                  return null
                },
              }
            )
          ),
      }
    )
}
