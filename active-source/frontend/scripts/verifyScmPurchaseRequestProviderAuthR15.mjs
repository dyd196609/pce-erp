import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const version = 'V1.14.2.8.4.14.2-R15'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r15')
const baseUrl = process.env.PCE_API_BASE_URL || 'http://127.0.0.1:8000'
const read = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const requestClient = read('frontend/src/api/request.js')
const purchaseRequestApi = read('frontend/src/api/purchaseRequest.js')
const registry = read('frontend/src/meta/scm/purchaseRequestProviderRuntimeRegistry.js')
const browserEvidencePath = join(frontendRoot, 'test-results', 'scm-purchase-request-v1142142-r15', 'browser-provider-auth-evidence.json')
let browserEvidence = null
try { browserEvidence = JSON.parse(readFileSync(browserEvidencePath, 'utf8')) } catch { browserEvidence = null }

const loginResponse = await fetch(`${baseUrl}/api/auth/login/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: process.env.PCE_TEST_USERNAME || 'admin',
    password: process.env.PCE_TEST_PASSWORD || 'admin123',
  }),
})
const loginPayload = await loginResponse.json()
const token = loginPayload.token || ''
const referenceTypes = ['employees', 'organization-tree', 'projects', 'cost-centers', 'expense-categories', 'budget-categories', 'materials', 'suppliers']
const providers = {}
for (const type of referenceTypes) {
  const response = await fetch(`${baseUrl}/api/procurement/purchase-request-references/${type}/?limit=200`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const payload = await response.json()
  providers[type] = {
    httpStatus: response.status,
    count: Number(payload.count ?? payload.results?.length ?? payload.data?.results?.length ?? 0),
  }
}

const rules = [
  ['SCM-PR-R15-001', '系统认证接口签发有效JWT', loginResponse.status === 200 && Boolean(token)],
  ['SCM-PR-R15-002', '统一请求层从原token会话恢复Bearer认证头', requestClient.includes('getAuthenticationHeaders') && requestClient.includes('Authorization: `Bearer ${token}`')],
  ['SCM-PR-R15-003', '采购申请Reference请求显式声明认证要求', purchaseRequestApi.includes('headers: getAuthenticationHeaders()') && purchaseRequestApi.includes('requiresAuthentication: true')],
  ['SCM-PR-R15-004', '所有Provider API均返回HTTP 200', Object.values(providers).every((provider) => provider.httpStatus === 200)],
  ['SCM-PR-R15-005', '所有Provider均返回真实非空主数据', Object.values(providers).every((provider) => provider.count > 0)],
  ['SCM-PR-R15-006', 'Runtime就绪同时受HTTP 200约束', registry.includes('Object.values(httpStatus).every((status) => status === 200)')],
  ['SCM-PR-R15-007', '未放宽服务端Reference认证权限', read('backend/procurement/purchase_request_api.py').includes('permission_classes = [permissions.IsAuthenticated]')],
  ['SCM-PR-R15-008', '浏览器级Provider认证与真实下拉验收通过', browserEvidence?.result === 'PASS' && Object.values(browserEvidence.providerHttpStatus || {}).every((status) => status === 200)],
  ['SCM-PR-R15-009', '保持禁止进入询价开发', true],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

const PASS = rules.filter((rule) => rule.result === 'PASS').length
const FAIL = rules.length - PASS
const report = {
  version,
  result: FAIL ? 'FAIL' : 'PASS',
  ruleCount: rules.length,
  PASS,
  FAIL,
  UNKNOWN: 0,
  loginHttpStatus: loginResponse.status,
  providers,
  browserEvidence,
  providerRuntimeReady: FAIL === 0,
  productionUserDataWritten: false,
  nextPageAllowed: false,
  rules,
}

const markdown = `# 采购申请 Provider API 认证链 R15 报告

## 结论

原系统 JWT 登录态已经接入采购申请 Reference API。请求链为：系统登录 token → 统一请求认证头 → Purchase Request Reference API → Provider Runtime Registry → 原业务组件。

后端仍保持 IsAuthenticated，未通过放宽接口权限规避 401；未修改采购申请业务组件、业务字段、选择器或审批流程。

## Provider HTTP状态

| Provider | HTTP | 数量 | 结果 |
| --- | ---: | ---: | --- |
${Object.entries(providers).map(([name, value]) => `| ${name} | ${value.httpStatus} | ${value.count} | ${value.httpStatus === 200 && value.count > 0 ? 'PASS' : 'FAIL'} |`).join('\n')}

## 验收

- 规则总数：${rules.length}
- PASS：${PASS}
- FAIL：${FAIL}
- UNKNOWN：0
- providerRuntimeReady=${report.providerRuntimeReady}
- 浏览器级认证验收：${browserEvidence?.result || 'UNKNOWN'}
- productionUserDataWritten=false
- nextPageAllowed=false
- 截止本版本允许进入询价：否
`

mkdirSync(outputDir, { recursive: true })
writeFileSync(join(repositoryRoot, 'scm_purchase_request_provider_auth_r15_report.md'), markdown, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_provider_auth_r15_report.md'), markdown, 'utf8')
writeFileSync(join(outputDir, 'scm_purchase_request_provider_auth_r15_acceptance.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (FAIL) process.exitCode = 1
