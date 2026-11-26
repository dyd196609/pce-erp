import { outcome } from './pageRules.js'

const make = (id, name, evaluate) => Object.freeze({ id, name, family: 'LIST', evaluate })

export const listRules = Object.freeze([
  make('LIST-001', '搜索存在', e => outcome(e.list?.search, '标准搜索控件', '未找到搜索控件')),
  make('LIST-002', '高级筛选存在', e => outcome(e.list?.advancedFilter, '高级筛选面板', '未找到高级筛选')),
  make('LIST-003', '筛选字段存在', e => outcome(
    Number.isInteger(e.list?.filterFieldCount) ? e.list.filterFieldCount > 0 : null,
    `fieldCount=${e.list?.filterFieldCount}`,
    '高级筛选没有字段',
  )),
  make('LIST-004', '排序存在', e => outcome(e.list?.sort, '可排序表头', '未找到排序能力')),
  make('LIST-005', '导出当前结果存在', e => outcome(e.list?.export, '导出当前结果', '未找到导出能力')),
  make('LIST-006', '行选择存在', e => outcome(e.list?.selection, 'selection column', '未找到行选择')),
  make('LIST-007', '左侧冻结列完整', e => outcome(
    ['selection', 'index', 'primaryNo'].every(key => e.list?.fixedLeft?.includes(key)),
    `fixedLeft=${JSON.stringify(e.list?.fixedLeft || [])}`,
    '选择框、序号或主业务编号未左冻结',
  )),
  make('LIST-008', '操作列右冻结', e => outcome(
    e.list?.fixedRight?.includes('operation'),
    `fixedRight=${JSON.stringify(e.list?.fixedRight || [])}`,
    '操作列未右冻结',
  )),
  make('LIST-009', '中间字段可横向滚动', e => outcome(
    e.list?.horizontalScroll,
    `scrollWidth=${e.list?.scrollWidth}; clientWidth=${e.list?.clientWidth}`,
    '表格没有稳定横向滚动空间',
  )),
  make('LIST-010', '滚动后冻结位置稳定', e => outcome(
    e.list?.fixedPositionsStable,
    `maxDelta=${e.list?.fixedPositionMaxDelta}`,
    '横向滚动导致冻结列位移',
  )),
])
