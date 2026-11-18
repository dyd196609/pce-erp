import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = path => fs.readFileSync(path, 'utf8')

test('routing version page exposes one controlled formal review action', () => {
  const page = read('src/meta/pages/PdeFoundationPage.vue')
  const readback = read('src/meta/pages/components/RoutingVersionReadback.vue')
  const api = read('src/api/pde.js')

  assert.match(readback, /data-acceptance-id="routing-version-formal-review"/)
  assert.match(readback, /提交正式评审通过决定/)
  assert.match(readback, /本动作不会发布版本，也不会创建生产计划/)
  assert.match(readback, /@click="submitFormalReview\(version\)"/)
  assert.match(page, /@review-version="handleReviewRoutingVersion"/)
  assert.match(page, /pde\.routing_version\.review/)
  assert.match(page, /本动作只进入已评审状态，不会发布版本/)
  assert.match(api, /routing-versions\/\$\{versionId\}\/review\//)
})

test('formal review panel consumes server preflight and authoritative readback', () => {
  const readback = read('src/meta/pages/components/RoutingVersionReadback.vue')

  assert.match(readback, /version\.reviewPreflight\.reviewAllowed/)
  assert.match(readback, /version\.reviewPreflight\.gates/)
  assert.match(readback, /version\.reviewPreflight\.reviewReadback\?\.completed/)
  assert.match(readback, /Workflow配置来源/)
  assert.match(readback, /configurationSourceLabel/)
  assert.doesNotMatch(readback, /status\s*=\s*['"]reviewed['"]/) 
})

test('canonical routing review workflow is system-owned rather than manually typed', () => {
  const designer = read('src/meta/pages/ProcessDesignerPage.vue')

  assert.match(designer, /工艺路线版本正式评审等已有系统合同的标准流程由系统目录自动生成/)
  assert.match(designer, /不应在本页手工填写技术编码/)
})

