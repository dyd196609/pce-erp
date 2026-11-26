import { outcome } from './pageRules.js'

const make = (id, name, evaluate) => Object.freeze({ id, name, family: 'FILTER', evaluate })

export const filterRules = Object.freeze([
  make('LIST-FILTER-001', '筛选字段声明类型', e => outcome(
    e.filter?.fields?.every(field => Boolean(field.filterType)),
    `fields=${e.filter?.fields?.length ?? 0}`,
    '存在未声明 filterType 的字段',
  )),
  make('LIST-FILTER-002', '下拉字段具有选项来源', e => outcome(
    e.filter?.fields?.filter(field => field.filterType === 'select')
      .every(field => (field.optionCount ?? 0) > 0 || Boolean(field.optionsProvider)),
    'select options/optionsProvider',
    'select 字段缺少 options 或受治理选项提供者',
  )),
  make('LIST-FILTER-003', '下拉字段渲染下拉控件', e => outcome(
    e.filter?.fields?.filter(field => field.filterType === 'select')
      .every(field => field.actualControl === 'select'),
    'select → select',
    'select 字段未显示下拉控件',
  )),
  make('LIST-FILTER-004', '日期字段渲染日期控件', e => outcome(
    e.filter?.fields?.filter(field => ['date', 'daterange'].includes(field.filterType))
      .every(field => field.actualControl === field.filterType),
    'date/daterange → date control',
    '日期字段未显示对应日期控件',
  )),
  make('LIST-FILTER-005', '高级筛选未全部退化为文本', e => outcome(
    e.filter?.fields?.some(field => field.actualControl !== 'text'),
    'typed controls present',
    '高级筛选全部退化为文本输入',
  )),
  make('LIST-FILTER-006', '筛选参数正确传递 API', e => outcome(
    e.filter?.apiParamsCorrect,
    JSON.stringify(e.filter?.apiParams || {}),
    '筛选条件未按 Schema 映射到 API 参数',
  )),
])
