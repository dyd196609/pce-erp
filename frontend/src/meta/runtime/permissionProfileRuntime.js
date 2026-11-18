import { accessControlApi } from '@/api/accessControl.js'

export const PCE_PERMISSION_PROFILE_RUNTIME_VERSION = 'PCE-ORGANIZATION-ACCESS-CORE-V1'

let cachedProfile = null

export async function loadPermissionProfile({ force = false } = {}) {
  if (!force && cachedProfile) return cachedProfile
  const response = await accessControlApi.profile()
  if (!response?.success || !response?.data?.authenticated) {
    throw new Error(response?.error?.message || '统一权限资料读取失败。')
  }
  cachedProfile = Object.freeze({ ...response.data })
  return cachedProfile
}

export function clearPermissionProfile() {
  cachedProfile = null
}

export function resolvePermissionFact(profile, actionCode) {
  const code = String(actionCode || '').trim()
  if (!code) {
    return {
      actionCode: '', visible: false, executable: false,
      disabledReason: '页面未声明业务动作编码。',
    }
  }
  if (profile?.permissionCodes?.includes('*')) {
    return { actionCode: code, visible: true, executable: true, disabledReason: '' }
  }
  return profile?.actionFacts?.[code] || {
    actionCode: code,
    visible: false,
    executable: false,
    disabledReason: '当前 Permission Profile 未授予该业务动作。',
  }
}

export async function decideBusinessAction({
  actionCode,
  organizationId = '',
  businessObject = null,
  context = null,
} = {}) {
  const response = await accessControlApi.authorize({
    actionCode,
    organizationId,
    businessObject,
    context,
  })
  if (!response?.success) {
    throw new Error(response?.error?.message || '统一授权判断读取失败。')
  }
  return response.data
}

export const PermissionProfileRuntime = Object.freeze({
  version: PCE_PERMISSION_PROFILE_RUNTIME_VERSION,
  load: loadPermissionProfile,
  clear: clearPermissionProfile,
  resolve: resolvePermissionFact,
  decide: decideBusinessAction,
})
