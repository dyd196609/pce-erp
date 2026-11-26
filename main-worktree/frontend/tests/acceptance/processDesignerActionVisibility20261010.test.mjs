import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { resolvePageNameConsumption } from '../../src/meta/governance/pageNameConsumer.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..')
const page = readFileSync(path.join(root, 'src/meta/pages/ProcessDesignerPage.vue'), 'utf8')

test('流程设计中心操作区位于页面正常文档流并提供可观测主操作', () => {
  assert.match(page, /<header class="page-header">[\s\S]*?<\/header>\s*<section class="workflow-actions"/)
  assert.match(page, /data-acceptance-id="create-workflow-definition-button"/)
  assert.match(page, /\.workflow-actions\s*\{[^}]*position:relative[^}]*display:grid/s)
  assert.doesNotMatch(page, /\.workflow-actions\s*\{[^}]*position:(?:absolute|fixed|sticky)/s)
})

test('流程设计中心页面身份由统一BusinessNameRegistry消费', () => {
  const identity = resolvePageNameConsumption({ route: '/process-designer' })
  assert.equal(identity.result, 'PASS')
  assert.equal(identity.pageTitle, '流程设计中心')
  assert.equal(identity.moduleCode, 'SYSTEM')
})

test('无正式Catalog权限时新增入口保持可见但禁用并显示准确权限要求', () => {
  assert.match(page, /catalogAccess\.value = response\.meta\?\.status === 403 \? 'denied' : 'unavailable'/)
  assert.match(page, /:disabled="catalogAccess !== 'allowed'"/)
  assert.match(page, /system\.organization\.workflow_responsibility\.manage/)
})
