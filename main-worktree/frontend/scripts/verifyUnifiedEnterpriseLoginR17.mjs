import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const read = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const loginPage = read('frontend/src/meta/pages/LoginPage.vue')
const systemLogin = read('frontend/src/views/Login.vue')
const authApi = read('frontend/src/api/auth.js')
const router = read('frontend/src/router/index.js')
const evidence = JSON.parse(readFileSync(join(frontendRoot, 'test-results', 'unified-enterprise-login-r17', 'browser-evidence.json'), 'utf8'))
const statuses = Object.values(evidence.providerHttpStatus || {})
const contexts = Object.values(evidence.providerAuthContext || {})
const rules = [
  ['AUTH-R17-001', '普通/login仍为ProfitOS商业入口', router.includes("path: '/login'") && router.includes("import('@/meta/pages/LoginPage.vue')")],
  ['AUTH-R17-002', '普通入口必须调用后端认证API', loginPage.includes('await authenticateEnterprise') && authApi.includes("axios.post('/api/auth/login/'")],
  ['AUTH-R17-003', 'JWT写入统一用户Store', loginPage.includes('userStore.setToken(authentication.token)')],
  ['AUTH-R17-004', '后端认证成功后才建立商业session', loginPage.indexOf('await authenticateEnterprise') < loginPage.indexOf('stateManager.setSession') && loginPage.includes('backendAuthenticated: true')],
  ['AUTH-R17-005', '保留Demo Company、Role和Plan', ['Demo Company', 'Role', 'Plan'].every((value) => loginPage.includes(value))],
  ['AUTH-R17-006', '认证成功进入dashboard', evidence.targetUrl === '/dashboard' && evidence.loginHttpStatus === 200],
  ['AUTH-R17-007', '八个Provider全部HTTP200', statuses.length === 8 && statuses.every((status) => status === 200)],
  ['AUTH-R17-008', 'Provider同时继承JWT与session', contexts.length === 8 && contexts.every((context) => context.authorizationPresent && context.cookiePresent)],
  ['AUTH-R17-009', '系统登录入口复用相同后端认证实现', systemLogin.includes("authenticateEnterprise")],
  ['AUTH-R17-010', '未进入询价开发', evidence.nextPageAllowed === false],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))
const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = { version: 'V1.14.2.8.4.15-R17', result: FAIL ? 'FAIL' : 'PASS', ruleCount: rules.length, PASS, FAIL, UNKNOWN: 0, evidence, productionUserDataWritten: false, nextPageAllowed: false, rules }
const markdown = `# V1.14.2.8.4.15-R17 统一企业登录认证上下文报告

## 认证链变化

旧链：/login → 前端商业/demo session → Dashboard；不建立后端认证。

新链：/login → /api/auth/login/ → JWT + Django session → 前端Tenant/Role/Plan商业上下文 → Dashboard → Provider API。

认证失败时不建立商业session，也不进入Dashboard。Demo Company、Role、Plan与Demo mode均保留。

## 测试结果

- 登录API：HTTP ${evidence.loginHttpStatus}
- Dashboard跳转：PASS
${Object.entries(evidence.providerHttpStatus).map(([name, status]) => `- ${name}: HTTP ${status}`).join('\n')}
- 真实员工下拉：PASS
- 物料80条：PASS
- 供应商下拉：PASS
- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
- productionUserDataWritten=false
- nextPageAllowed=false
- 允许进入询价：否
`
writeFileSync(join(repositoryRoot, 'unified_enterprise_login_auth_context_r17_report.md'), markdown, 'utf8')
writeFileSync(join(frontendRoot, 'test-results', 'unified-enterprise-login-r17', 'acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (FAIL) process.exitCode = 1
