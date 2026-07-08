import { getTenant } from '../tenant/tenantManager'
import { hasPermission, canAccessData } from '../auth/permissionV12'
import { executeActionV10 } from '../runtime/metaRuntimeV10'

/**
 * ============================
 * Meta Runtime V12 Kernel
 * 商业级平台核心
 * ============================
 */

export const runPlatformV12 = async ({ meta, action, row, user }) => {
  // ======================
  // 1. 多租户隔离
  // ======================
  const tenant = getTenant()

  row.tenant_id = tenant.id

  // ======================
  // 2. 数据权限控制
  // ======================
  if (!canAccessData(row)) {
    throw new Error('No data permission')
  }

  // ======================
  // 3. 字段权限过滤
  // ======================
  if (meta?.table?.columns) {
    meta.table.columns = meta.table.columns.filter((c) => hasPermission(c.permission || ''))
  }

  // ======================
  // 4. 执行Runtime
  // ======================
  const result = await executeActionV10({
    metaId: meta.pageName,
    action,
    row,
    user,
    env: 'prod',
  })

  return result
}
