export const PCE_BASIC_OPERATION_TAXONOMY_VERSION = 'V1.14.2.8.4.6'

export const pceBasicOperationDefectTaxonomy = [
  {
    category: 'operation_column_floating',
    subcategory: 'right_operation_column',
    keywords: ['operation floating', 'overlay normal column', 'payment-fixed-action-column', '操作列漂浮', '覆盖普通列'],
    description: '操作列脱离当前业务表格网格或覆盖普通业务列，必须回到同一 table 内的右侧固定列。',
  },
  {
    category: 'operation_column_jitter',
    subcategory: 'scroll_coordinate_stability',
    keywords: ['operation jitter', 'operation x delta', 'horizontal scroll jitter', '操作列抖动'],
    description: '横向滚动过程中操作列 x 坐标变化超过 1px，通常由重复偏移计算或错误滚动祖先导致。',
  },
  {
    category: 'operation_column_not_at_right_edge',
    subcategory: 'right_edge_alignment',
    keywords: ['operation right edge', 'scroll viewport right', '右边界', '最右侧'],
    description: '操作列右边界与表格可视滚动容器右边界误差超过 1px。',
  },
  {
    category: 'operation_column_wrong_scroll_ancestor',
    subcategory: 'sticky_scroll_container',
    keywords: ['wrong scroll ancestor', 'sticky reference', 'BusinessTableScrollContainer', 'sticky 参照容器'],
    description: '操作列 sticky 参照容器与真实横向滚动拥有者不一致。',
  },
  {
    category: 'required_list_controls_missing',
    subcategory: 'standard_toolbar_controls',
    keywords: ['StandardListToolbar', 'quick search', 'advanced filter', 'export current result', '清除排序'],
    description: '列表页面缺少快速查找、高级筛选、清空筛选、清除排序或导出当前结果。',
  },
  {
    category: 'list_fixed_columns_missing',
    subcategory: 'left_right_fixed_columns',
    keywords: ['selection column', 'index column', 'primary business no', 'operation fixed right', '固定列缺失'],
    description: '业务列表缺少左侧多选框、序号、主业务编号冻结列或右侧操作冻结列。',
  },
  {
    category: 'list_horizontal_scroll_missing',
    subcategory: 'native_scroll_owner',
    keywords: ['horizontal scroll missing', 'scroll owner', 'scrollWidth', '横向滚动条缺失'],
    description: '宽业务表格存在横向溢出但没有单一、可操作、可到达最右侧的横向滚动条。',
  },
  {
    category: 'module_name_consistency',
    subcategory: 'canonical_name_surface',
    keywords: ['canonicalName', 'document.title', 'route meta title', 'h1', '内部主题', '模块名称', '简称', '旧名称'],
    description: '流程中心名称、浏览器标签、路由标题、页面主标题或内部主题标题与标准模块全名不一致。',
  },
  {
    category: 'list_toolbar_missing',
    subcategory: 'standard_list_toolbar',
    keywords: ['fuzzy search', 'advanced filter', 'clear filter', 'clear sort', 'export current result', '模糊查找', '高级筛选', '清空筛选', '清除排序', '导出当前结果'],
    description: '业务列表缺少标准工具栏控件，或控件存在但未接入真实筛选、排序、导出结果。',
  },
  {
    category: 'toolbar_table_separation',
    subcategory: 'toolbar_table_distance',
    keywords: ['toolbar distance', 'advanced filter distance', '工具栏距离', '筛选距表格', '开发验收信息插入'],
    description: '工具栏、高级筛选和数据表格之间被大块说明、诊断或开发验收内容隔开。',
  },
  {
    category: 'row_operation_missing',
    subcategory: 'fixed_operation_column',
    keywords: ['operation column', 'fixed right', 'row action', '操作列', '右侧固定', '查看来源', '进入下一步'],
    description: '业务记录列表缺少右侧固定操作列，或操作列没有真实可达动作。',
  },
  {
    category: 'horizontal_scroll_missing',
    subcategory: 'single_scroll_owner',
    keywords: ['horizontal scroll', 'scrollWidth', 'clientWidth', '横向滚动', '最右侧', '最后一列'],
    description: '宽业务表格存在横向溢出但缺少单一可用横向滚动，或无法到达最右侧。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'table_toolbar',
    keywords: ['fuzzy search', 'advanced filter', 'clear sort', 'export current result', 'toolbar adjacent', '模糊查找', '高级筛选', '清空筛选', '清除排序', '导出当前结果', '工具栏'],
    description: '列表缺少标准搜索筛选工具栏，或工具栏与表格被开发验收内容隔开。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'page_layout',
    keywords: ['acceptance panel', 'business operation area', 'layout distance', '验收信息', '业务操作区', '表格距离', '页面布局'],
    description: '开发验收内容占据正式业务操作区，或搜索、筛选、表格布局不连续。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'sidebar_navigation',
    keywords: ['sidebar', 'collapse menu', 'expand menu', 'main menu', '主菜单', '收起主菜单', '展开主菜单', '侧边栏'],
    description: '主菜单固定、收起、展开、当前高亮或内容遮挡问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'selection',
    keywords: ['selection', 'checkbox', 'selected', 'indeterminate', '全选', '半选', '选择列'],
    description: '选择列、多选、全选、半选、选中数量或选择状态稳定性问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'table_scroll',
    keywords: ['scroll', 'scrollbar', 'horizontal', 'overflow', '横向滚动', '右边界'],
    description: '表格横向滚动、双滚动、滚动到达右边界或页面溢出问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'fixed_column',
    keywords: ['fixed', 'sticky', 'coordinate', 'left column', 'right column', '固定列', '坐标'],
    description: '选择列、序号列、主业务编号列或操作列冻结与坐标稳定问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'navigation',
    keywords: ['route', 'navigation', 'url', '跳转', '页面不可达'],
    description: '页面入口、路由跳转和用户可达性问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'primary_action',
    keywords: ['button', 'disabled', 'click', 'primary action', '按钮', '主操作'],
    description: '主操作按钮可见、可点击、禁用原因或错误触发问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'sort_filter_pagination',
    keywords: ['sort', 'filter', 'pagination', '排序', '筛选', '分页'],
    description: '排序、筛选、分页和结果稳定性问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'form_operation',
    keywords: ['form', 'input', 'select', '表单', '输入', '下拉'],
    description: '表单输入、选择器和编辑入口问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'visibility_and_overflow',
    keywords: ['visible', 'covered', 'overflow', 'hidden', '遮挡', '不可见', '溢出'],
    description: '元素不可见、遮挡、裁切、换行错位或内容溢出问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'feedback',
    keywords: ['message', 'toast', 'reason', 'warning', '提示', '原因'],
    description: '操作反馈、禁用原因、提示或警告文案问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'business_display',
    keywords: ['source=', 'target=', '.js', 'raw', 'status code', '中文', '乱码', '技术值'],
    description: '业务中文显示、技术值泄露、乱码或字段缺失问题。',
  },
  {
    category: 'basic_page_operation',
    subcategory: 'accessibility',
    keywords: ['aria', 'role', 'keyboard', 'focus', '可访问', '键盘'],
    description: '可访问性、键盘焦点和语义角色问题。',
  },
  {
    category: 'workflow_navigation',
    subcategory: 'process_route_reachability',
    keywords: ['supplier-settlement', 'workflow', 'process route', 'next step', '供应商结算', '采购对账', '流程导航', '下一步入口'],
    description: '流程中心、模块导航或当前页面无法到达当前步骤或后续步骤的问题。',
  },
  {
    category: 'action_reachability',
    subcategory: 'current_step_action',
    keywords: ['execute payable check', 'primary action', 'disabled action', 'batch result', '执行应付核对', '批量完成', '主动作不可达', '按钮不可达'],
    description: '当前步骤主动作、批量动作、来源查看或下一步动作不可见、不可点或缺少原因的问题。',
  },
  {
    category: 'baseline_coverage',
    subcategory: 'baseline_registration',
    keywords: ['baselineCoverageRate', 'unregisteredBaselinePageCount', 'runtimeUntestedPageCount', 'baseline coverage', '未登记基线', '覆盖率不足', '运行时未覆盖'],
    description: '页面基础基线登记、合法例外、非法例外和运行时覆盖不足的问题。',
  },
  {
    category: 'selected_record_context_mismatch',
    subcategory: 'toolbar_action_selection_context',
    keywords: ['selected row', 'selection context', '已选记录', '下一步对象'],
    description: '工具栏流程动作使用的业务对象与用户当前唯一选中记录不一致。',
  },
  {
    category: 'action_uses_hardcoded_record',
    subcategory: 'hardcoded_business_context',
    keywords: ['hardcoded record', 'sample no', '固定单号', '样例编号'],
    description: '流程动作使用固定样例单号，而不是当前行或当前唯一选中记录。',
  },
  {
    category: 'action_uses_first_row_fallback',
    subcategory: 'implicit_first_row_context',
    keywords: ['rows[0]', 'first row fallback', '默认第一条'],
    description: '没有有效选择时，流程动作错误回退到第一条或上一次记录。',
  },
  {
    category: 'export_scope_mismatch',
    subcategory: 'selected_or_current_result',
    keywords: ['selected export', 'current result export', '导出已选记录', '导出当前结果'],
    description: '导出按钮文案与实际导出的已选记录或当前筛选排序结果范围不一致。',
  },
  {
    category: 'export_all_sheets_unexpected',
    subcategory: 'single_business_sheet',
    keywords: ['all sheets', 'multiple sheets', '全部工作表', '多余工作表'],
    description: '列表导出未经用户指定生成多个工作表或附带其他范围数据。',
  },
  {
    category: 'canonical_name_english_fallback',
    subcategory: 'route_segment_title_fallback',
    keywords: ['Inventory Balances', 'route segment title', '英文路径兜底', '库存余额'],
    description: '中文业务页面未登记唯一名称时，使用英文路径段自动生成页面名称。',
  },
]

export function listPceBasicOperationDefectTaxonomy() {
  return pceBasicOperationDefectTaxonomy.map((item) => ({ ...item }))
}
