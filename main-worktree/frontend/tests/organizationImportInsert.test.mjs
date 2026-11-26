import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const page = await readFile(new URL('../src/meta/pages/AccessControlFoundationPage.vue', import.meta.url), 'utf8')
const component = await readFile(new URL('../src/meta/components/LatestBaseDataImportToolbarExtension.vue', import.meta.url), 'utf8')
const api = await readFile(new URL('../src/api/accessControl.js', import.meta.url), 'utf8')

test('department position and employee tabs share the governed import toolbar', () => {
  assert.match(page, /organizationImportTabs=\['departments','positions','employees'\]/)
  assert.match(page, /#toolbar-extension/)
  assert.match(page, /provider="organization"/)
  assert.match(page, /:xlsx-only="true"/)
  assert.doesNotMatch(page, /organizationImportTabs=.*users/)
})

test('shared component provides template preview explicit confirmation and readback refresh', () => {
  assert.match(component, />下载导入模板</)
  assert.match(component, /'导入数据'/)
  assert.match(component, /previewOrganizationImport/)
  assert.match(component, /commitOrganizationImport/)
  assert.match(component, /ElMessageBox\.confirm/)
  assert.match(component, /emit\('import-committed'/)
})

test('organization import api has separate template preview and commit endpoints', () => {
  assert.match(api, /organizationImportTemplate\(entity\)/)
  assert.match(api, /previewOrganizationImport\(entity, file\)/)
  assert.match(api, /commitOrganizationImport\(entity, file, previewFingerprint, idempotencyKey, previewActorBinding\)/)
  assert.match(api, /confirmed', 'true'/)
})
