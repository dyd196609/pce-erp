const records = Object.freeze([
  ['/account-shortcuts', '快捷登录账户', '身份与访问控制'],
  ['/system-login', '账户登录', '身份与访问控制'],
  ['/customer/order-progress', '客户订单进度', '客户服务'],
  ['/analytics', '企业数据智能分析平台', '企业运营分析'],
  ['/business-trace', '企业业务追踪中心', '企业运营分析'],
  ['/process-center', '业务流程中心', '平台工作台'],
  ['/reference', '数据引用中心', 'Reference'],
  ['/foundation', '企业基础资料', 'EMD企业主数据中心'],
  ['/manufacturing/modules', 'PCE制造数字化能力地图', '产品能力架构'],
  ['/process-designer', '流程设计中心', '平台治理'],
  ['/scm', '供应链管理', '供应链管理'],
  ['/wms', '仓库管理', '仓库管理'],
  ['/qms', '质量管理', '质量管理'],
  ['/finance/p2p-validation-center', 'P2P业务数据验证与闭环中心', '财务管理'],
].map(([route, displayName, moduleName]) => Object.freeze({ route, displayName, moduleName })))

export function resolvePlatformPageIdentity(route = '') {
  return records.find(record => record.route === route) || null
}
