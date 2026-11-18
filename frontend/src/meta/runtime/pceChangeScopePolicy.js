export const PCE_CHANGE_SCOPE_POLICY_VERSION = 'V1.14.2.8.3.1'

export const PCE_CHANGE_SCOPE_TYPES = {
  CANONICAL_NAME_ONLY_WITH_REGRESSION_RESTORE: 'canonical_name_only_with_regression_restore',
}

export const pceChangeScopePolicies = {
  [PCE_CHANGE_SCOPE_TYPES.CANONICAL_NAME_ONLY_WITH_REGRESSION_RESTORE]: {
    version: PCE_CHANGE_SCOPE_POLICY_VERSION,
    scopeName: '名称整改与功能回退恢复',
    allowedChangeAreas: [
      '模块标准名称注册',
      '名称解析服务',
      '路由标题元数据',
      '页面标题最小绑定',
      '回退页面能力恢复',
      '变更范围门禁脚本',
      '页面能力指纹脚本',
      '自动化验收脚本',
      '开发备案文档',
    ],
    forbiddenChangeAreas: [
      '新增页面壳迁移',
      '新增表格壳迁移',
      '新增滚动组件',
      '新增筛选框架',
      '新增业务动作',
      '新增业务 Store',
      '新增流程状态',
      '新增数据模型',
      '修改业务状态机',
      '写入正式业务数据',
      '写入用户 localStorage',
    ],
    invariantMetrics: [
      'tableCount',
      'tableColumnCount',
      'fuzzySearchCount',
      'advancedFilterToggleCount',
      'advancedFilterFieldCount',
      'operationColumnCount',
      'rowOperationCount',
      'horizontalScrollOwnerCount',
      'fixedLeftColumnCount',
      'fixedRightColumnCount',
      'paginationCount',
      'batchActionCount',
      'exportCurrentResultCount',
    ],
    allowedFilePatterns: [
      'frontend/src/meta/runtime/pceBusinessModuleRegistry.js',
      'frontend/src/meta/runtime/pceCanonicalNameService.js',
      'frontend/src/meta/runtime/pageTitleManager.js',
      'frontend/src/meta/runtime/pceChangeScopePolicy.js',
      'frontend/src/meta/runtime/pceDefectRegressionRegistry.js',
      'frontend/src/meta/pages/*.vue',
      'frontend/src/router/index.js',
      'frontend/scripts/*.mjs',
      'frontend/scripts/Test-PcePurchasePaymentFlow.ps1',
      'frontend/tests/**/*.spec.js',
      'frontend/package.json',
      'docs/*.md',
    ],
    protectedFilePatterns: [
      'frontend/src/meta/scm/*Store.js',
      'frontend/src/meta/wms/*Store.js',
      'frontend/src/meta/qms/*Store.js',
      'frontend/src/meta/finance/*Store.js',
    ],
  },
}

export function resolvePceChangeScopePolicy(
  scopeType = PCE_CHANGE_SCOPE_TYPES.CANONICAL_NAME_ONLY_WITH_REGRESSION_RESTORE,
) {
  return pceChangeScopePolicies[scopeType] || pceChangeScopePolicies[PCE_CHANGE_SCOPE_TYPES.CANONICAL_NAME_ONLY_WITH_REGRESSION_RESTORE]
}
