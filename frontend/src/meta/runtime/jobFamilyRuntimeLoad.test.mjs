import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'

import {
  JOB_FAMILY_LOAD_STATUS,
  loadJobFamilyOptions,
  mapJobFamilyResponse,
} from './jobFamilyRuntimeLoad.js'

const testFamily = Object.freeze({
  id: 1,
  code: 'TEST-JF-WH-001',
  name: '测试岗位族-仓储',
  isActive: true,
})

test('fresh page response maps the server JobFamily into options', () => {
  const result = mapJobFamilyResponse({
    success: true,
    data: { jobFamilies: [testFamily] },
  })
  assert.equal(result.status, JOB_FAMILY_LOAD_STATUS.LOADED)
  assert.equal(result.options.length, 1)
  assert.equal(result.options[0].code, 'TEST-JF-WH-001')
  assert.notEqual(result.options[0], testFamily)
})

test('dialog reopen performs a new read and retains the server record', async () => {
  let readCount = 0
  const readOrganizationModel = async () => {
    readCount += 1
    return { success: true, data: { jobFamilies: [{ ...testFamily }] } }
  }
  const firstOpen = await loadJobFamilyOptions(readOrganizationModel)
  const secondOpen = await loadJobFamilyOptions(readOrganizationModel)
  assert.equal(readCount, 2)
  assert.equal(firstOpen.options[0].code, 'TEST-JF-WH-001')
  assert.equal(secondOpen.options[0].code, 'TEST-JF-WH-001')
  assert.notEqual(firstOpen.options, secondOpen.options)
})

test('a valid empty server array is EMPTY_VALID', () => {
  const result = mapJobFamilyResponse({
    success: true,
    data: { jobFamilies: [] },
  })
  assert.equal(result.status, JOB_FAMILY_LOAD_STATUS.EMPTY_VALID)
  assert.deepEqual(result.options, [])
  assert.equal(result.error, '')
})

test('failed or malformed reads are READ_FAILED, never legal empty data', async () => {
  const failed = mapJobFamilyResponse({
    success: false,
    error: { message: 'server unavailable' },
  })
  const malformed = mapJobFamilyResponse({ success: true, data: {} })
  const rejected = await loadJobFamilyOptions(async () => {
    throw new Error('network unavailable')
  })
  for (const result of [failed, malformed, rejected]) {
    assert.equal(result.status, JOB_FAMILY_LOAD_STATUS.READ_FAILED)
    assert.deepEqual(result.options, [])
    assert.ok(result.error)
  }
})

test('professional management panels use server facts, formal save actions, and no browser fixture storage', async () => {
  const [familyPanel, levelPanel, foundationPage] = await Promise.all([
    readFile(new URL('../components/JobFamilyManagementPanel.vue', import.meta.url), 'utf8'),
    readFile(new URL('../components/JobLevelManagementPanel.vue', import.meta.url), 'utf8'),
    readFile(new URL('../pages/AccessControlFoundationPage.vue', import.meta.url), 'utf8'),
  ])
  assert.match(familyPanel, /SAVE_JOB_FAMILY/)
  assert.match(levelPanel, /SAVE_JOB_LEVEL/)
  assert.match(familyPanel, /facts\.positions/)
  assert.match(levelPanel, /facts\.positions/)
  assert.doesNotMatch(`${familyPanel}${levelPanel}${foundationPage}`, /localStorage|fixture|TEST-/i)
  assert.match(foundationPage, /key:'job-families'/)
  assert.match(foundationPage, /key:'job-levels'/)
  assert.match(foundationPage, /label:'岗位族'/)
  assert.match(foundationPage, /label:'岗位等级'/)
  assert.match(foundationPage, /viewFamilyPositions/)
  assert.match(foundationPage, /viewLevelPositions/)
})
