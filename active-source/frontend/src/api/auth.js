import axios from 'axios'
import { getTabAuthToken } from '../meta/runtime/tabAuthenticationContext.js'

export async function authenticateEnterprise({ username, password }) {
  const response = await axios.post('/api/auth/login/', { username, password }, {
    withCredentials: true,
    withXSRFToken: true,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
  })
  const payload = response.data || {}
  if (!payload.token || !payload.user) {
    throw new Error(payload.error || '后端认证未返回有效JWT和用户上下文')
  }
  return payload
}

export async function terminateEnterpriseSession() {
  const response = await axios.post('/api/auth/logout/', {}, {
    withCredentials: true,
    withXSRFToken: true,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
  })
  return response.data || { success: true }
}

export async function issueTabAuthenticationHandoff(targetPath) {
  const token = getTabAuthToken()
  if (!token) throw new Error('当前标签页没有可用的服务端登录身份')
  const response = await axios.post('/api/auth/tab-handoff/issue/', { targetPath }, {
    headers: { Authorization: `Bearer ${token}` },
    withCredentials: true,
  })
  return response.data || {}
}

export async function exchangeTabAuthenticationHandoff(handoffCode, targetPath) {
  const response = await axios.post('/api/auth/tab-handoff/exchange/', {
    handoffCode, targetPath,
  }, { withCredentials: true })
  return response.data || {}
}
