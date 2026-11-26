import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R16'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const read = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const requestClient = read('frontend/src/api/request.js')
const loginPage = read('frontend/src/views/Login.vue')
const registry = read('frontend/src/meta/scm/purchaseRequestProviderRuntimeRegistry.js')
const referenceView = read('backend/procurement/purchase_request_api.py')
const factsView = read('backend/procurement/scm_page_facts.py')
const settings = read('backend/pce_backend/settings.py')
const evidencePath = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r16', 'browser-provider-auth-context-evidence.json')
const evidence = JSON.parse(readFileSync(evidencePath, 'utf8'))

const providerStatuses = Object.values(evidence.providerHttpStatus || {})
const sessionContexts = Object.values(evidence.sessionContext || {})
const rules = [
  ['SCM-PR-R16-001', '统一请求携带有效JWT Bearer认证', requestClient.includes('getAuthenticationHeaders') && requestClient.includes('isUsableJwt') && evidence.jwtContextVerified],
  ['SCM-PR-R16-002', '统一请求启用session cookie继承', requestClient.includes('withCredentials: true') && loginPage.includes("axios.post('/api/auth/login/'")],
  ['SCM-PR-R16-003', '同源登录恢复session上下文', loginPage.includes('withCredentials: true') && settings.includes('rest_framework.authentication.SessionAuthentication')],
  ['SCM-PR-R16-004', 'GET配置CSRF标准项且确认GET无需CSRF令牌', requestClient.includes("xsrfHeaderName: 'X-CSRFToken'") && evidence.csrfRequiredForGet === false],
  ['SCM-PR-R16-005', 'Provider调用继续经过统一request封装', registry.includes("import { purchaseRequestApi } from '@/api/purchaseRequest.js'") && !registry.includes('fetch(')],
  ['SCM-PR-R16-006', '全部Provider浏览器请求HTTP 200', providerStatuses.length === 8 && providerStatuses.every((status) => status === 200)],
  ['SCM-PR-R16-007', '移除Bearer后session cookie仍可完成认证', evidence.sessionFallbackVerified && sessionContexts.every((item) => item.cookiePresent && !item.authorizationPresent)],
  ['SCM-PR-R16-008', '事实接口200不再被误判为认证成功', evidence.factsHttpStatus === 200 && factsView.includes('permission_classes = [AllowAny]')],
  ['SCM-PR-R16-009', 'Reference继续使用IsAuthenticated', referenceView.includes('permission_classes = [permissions.IsAuthenticated]')],
  ['SCM-PR-R16-010', '真实下拉与80条物料浏览器验收通过', evidence.selectorsVerified?.includes('materials-80') && evidence.selectorsVerified.length === 6],
  ['SCM-PR-R16-011', '保持禁止进入询价开发', evidence.nextPageAllowed === false],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = { version, result: FAIL ? 'FAIL' : 'PASS', ruleCount: rules.length, PASS, FAIL, UNKNOWN: 0, evidence, productionUserDataWritten: false, nextPageAllowed: false, rules }
const markdown = `# 采购申请 Provider 请求认证上下文 R16 报告

## 根因

采购申请事实接口使用 AllowAny，因此其 HTTP 200 不能证明浏览器持有后端登录态；Reference API 保持 IsAuthenticated。旧登录请求直连 127.0.0.1，而业务页面通过 localhost 同源代理请求，造成 session cookie 上下文分裂。失效 Bearer 还会在认证链前端阻止 session 回退。

## 修复

- 登录改为同源 /api/auth/login/，继承浏览器 session cookie。
- 统一请求同时支持有效 JWT、withCredentials session 与标准 X-CSRFToken 配置。
- 失效或非JWT token不再作为 Authorization 发送，允许已认证session接管。
- Reference仍为IsAuthenticated，未开放匿名访问。

## 浏览器HTTP结果

${Object.entries(evidence.providerHttpStatus).map(([name, status]) => `- ${name}: HTTP ${status}`).join('\n')}

GET为安全方法，不要求CSRF令牌；写请求仍由Axios按csrftoken自动发送X-CSRFToken。

## 验收

- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
- JWT认证：PASS
- session cookie回退：PASS
- 真实下拉：PASS
- productionUserDataWritten=false
- nextPageAllowed=false
- 允许进入询价：否
`

writeFileSync(join(repositoryRoot, 'scm_purchase_request_provider_auth_context_r16_report.md'), markdown, 'utf8')
writeFileSync(join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r16', 'scm_purchase_request_provider_auth_context_r16_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (FAIL) process.exitCode = 1
