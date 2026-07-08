import { getTenant } from '../saas/tenantSaaSManager'
import { checkQuota } from '../saas/billingSystem'
import { checkLicense } from '../license/licenseManager'
import { runPlatformV12 } from './metaKernelV12'

/**
 * ============================
 * Meta Runtime V13 Kernel
 * 商业闭环终极核心
 * ============================
 */

export const runPlatformV13 = async (payload) => {
  const tenant = getTenant(payload.tenantId)

  // ======================
  // 1. License检查
  // ======================
  if (!checkLicense()) {
    throw new Error('License invalid')
  }

  // ======================
  // 2. 额度检查
  // ======================
  if (!checkQuota(tenant)) {
    throw new Error('Quota exceeded')
  }

  // ======================
  // 3. SaaS执行
  // ======================
  const result = await runPlatformV12(payload)

  // ======================
  // 4. 计费增加
  // ======================
  tenant.usage = (tenant.usage || 0) + 1

  return result
}
