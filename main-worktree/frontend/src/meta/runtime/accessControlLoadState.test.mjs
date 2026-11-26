import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import {
  ACCESS_CONTROL_LOAD_STATE,
  classifyAccessControlFailure,
  loadStateMessage,
} from './accessControlLoadState.js'

assert.equal(classifyAccessControlFailure({
  factLoadFacts: { httpStatus: 500, errorCode: 'OperationalError', apiUrl: '/api/access-control/foundation/' },
}).state, ACCESS_CONTROL_LOAD_STATE.READ_FAILED)
assert.equal(classifyAccessControlFailure({ meta: { status: 403 }, error: { code: 'ACCESS_CONTROL_ADMIN_REQUIRED' } }).state, ACCESS_CONTROL_LOAD_STATE.PERMISSION_DENIED)
assert.equal(classifyAccessControlFailure({ meta: { status: 401 }, error: { code: 'not_authenticated' } }).state, ACCESS_CONTROL_LOAD_STATE.AUTH_EXPIRED)
assert.match(loadStateMessage(ACCESS_CONTROL_LOAD_STATE.READ_FAILED), /未知值/)

const pageSource = await readFile(
  fileURLToPath(new URL('../pages/AccessControlFoundationPage.vue', import.meta.url)),
  'utf8',
)
const stateSource = await readFile(
  fileURLToPath(new URL('./accessControlLoadState.js', import.meta.url)),
  'utf8',
)
assert.match(pageSource, /v-if="!factsReadable"/)
assert.match(pageSource, /— \/ —/)
assert.match(stateSource, /列表不会显示“暂无数据”/)
assert.doesNotMatch(pageSource, /activeOperatingCompanyCount\|\|0/)

console.log('accessControlLoadState: 8 assertions passed')
