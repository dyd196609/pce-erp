import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const pageSource = await readFile(
  fileURLToPath(new URL('../pages/AccessControlFoundationPage.vue', import.meta.url)),
  'utf8',
)
const acceptanceRegistrySource = await readFile(
  fileURLToPath(new URL('./pcePageAcceptanceRegistry.js', import.meta.url)),
  'utf8',
)
const platformIdentitySource = await readFile(
  fileURLToPath(new URL('../governance/platformPageIdentityRegistry.js', import.meta.url)),
  'utf8',
)
const authApiSource = await readFile(
  fileURLToPath(new URL('../../api/auth.js', import.meta.url)),
  'utf8',
)
const userStoreSource = await readFile(
  fileURLToPath(new URL('../../stores/counter.js', import.meta.url)),
  'utf8',
)

assert.match(pageSource, /passwordChangeRequested:false/)
assert.match(pageSource, /v-if="editorForm\.id" label="重置密码"/)
assert.match(pageSource, /<template v-if="editorForm\.id&&editorForm\.passwordChangeRequested">/)
assert.match(pageSource, /新账户将建立为“待设置初始密码”；本次不写入密码/)
assert.match(pageSource, /v-model="editorForm\.passwordConfirm"/)
assert.match(pageSource, /v-model="editorForm\.reason"/)
assert.match(pageSource, /普通资料、角色和范围修改不会改变密码/)
assert.match(pageSource, /key:'review-grants'/)
assert.match(pageSource, /双重门禁：系统角色权限与当前评审对象授权必须同时有效/)
assert.match(pageSource, /SET_REVIEW_PARTICIPANT_GRANT/)
assert.match(pageSource, /requiredPermissionCodes/)
assert.match(pageSource, /filterType:'select'/)
assert.match(acceptanceRegistrySource, /\['system-login', '账户登录', '\/system-login', 'SystemLogin', 'src\/views\/Login\.vue'/)
assert.match(platformIdentitySource, /\['\/system-login', '账户登录', '身份与访问控制'\]/)
assert.match(authApiSource, /axios\.post\('\/api\/auth\/logout\/'/)
assert.match(userStoreSource, /await terminateEnterpriseSession\(\)/)

console.log('accountCredentialGovernance: 16 assertions passed')
