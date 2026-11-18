import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { setImmediate as waitImmediate } from 'node:timers'

import {
  EngineeringDocumentReleaseSubmissionError,
  submitEngineeringDocumentVersionRelease,
} from '../../src/meta/pages/engineeringDocumentVersionReleaseSubmission.js'

const VERSION_ID = 1

function committedResponse() {
  return {
    success: true,
    data: {
      result: {
        engineeringDocumentVersion: {
          engineeringDocumentVersionId: VERSION_ID,
          status: 'released',
        },
        businessStateTransition: {
          id: 201,
          fromState: 'reviewed',
          toState: 'released',
        },
        auditId: 202,
        writeRequestId: 203,
        manufacturingReleaseExecuted: false,
      },
    },
    error: null,
    meta: { status: 200 },
  }
}

function committedReadback() {
  return {
    engineeringDocumentVersionId: VERSION_ID,
    documentVersionStatusLabel: '已发布',
    documentReleasePreflight: {
      releaseReadback: {
        completed: true,
        businessStateTransitionId: 201,
        writeRequestId: 203,
        manufacturingReleaseExecuted: false,
      },
    },
  }
}

function options(overrides = {}) {
  return {
    versionId: VERSION_ID,
    confirmSubmission: async () => true,
    requestRelease: async () => committedResponse(),
    refreshFacts: async () => {},
    getFormalReadback: () => committedReadback(),
    ...overrides,
  }
}

test('工程资料版本发布只在事务证据与正式回读一致后成功', async () => {
  let refreshCount = 0
  const result = await submitEngineeringDocumentVersionRelease(options({
    refreshFacts: async () => { refreshCount += 1 },
  }))
  assert.equal(result.result.engineeringDocumentVersion.status, 'released')
  assert.equal(result.readback.completed, true)
  assert.equal(refreshCount, 1)
})

for (const [status, code, category] of [
  [200, 'BUSINESS_REJECTED', '工程资料版本正式发布未成功'],
  [400, 'INVALID_INPUT', '输入或发布准入未通过'],
  [401, 'NOT_AUTHENTICATED', '登录认证已失效'],
  [403, 'PERMISSION_DENIED', '工程资料版本发布权限被拒绝'],
  [409, 'STATE_CONFLICT', '业务状态或幂等冲突'],
  [500, 'SERVER_ERROR', '服务端发布事务处理失败'],
]) {
  test(`发布HTTP ${status} / success=false保留准确错误`, async () => {
    await assert.rejects(
      submitEngineeringDocumentVersionRelease(options({
        requestRelease: async () => ({
          success: false,
          data: null,
          error: { code, message: `${status}发布拒绝` },
          meta: { status },
        }),
      })),
      error => {
        assert.ok(error instanceof EngineeringDocumentReleaseSubmissionError)
        assert.equal(error.code, code)
        assert.match(error.userMessage, new RegExp(category))
        return true
      },
    )
  })
}

test('成功响应但正式回读不一致时不得宣称发布完成', async () => {
  await assert.rejects(
    submitEngineeringDocumentVersionRelease(options({
      getFormalReadback: () => ({
        ...committedReadback(),
        documentVersionStatusLabel: '已评审',
      }),
    })),
    error => error.code === 'ENGINEERING_DOCUMENT_RELEASE_READBACK_MISMATCH',
  )
})

test('发布确认取消不发送请求', async () => {
  let requestCount = 0
  await assert.rejects(
    submitEngineeringDocumentVersionRelease(options({
      confirmSubmission: async () => { throw 'cancel' },
      requestRelease: async () => { requestCount += 1 },
    })),
    error => error === 'cancel',
  )
  assert.equal(requestCount, 0)
})

test('发布在途锁阻止重复点击', async () => {
  let submitting = false
  let requestCount = 0
  let releaseRequest
  const barrier = new Promise(resolve => { releaseRequest = resolve })
  const shared = {
    isSubmitting: () => submitting,
    setSubmitting: value => { submitting = value },
  }
  const first = submitEngineeringDocumentVersionRelease(options({
    ...shared,
    requestRelease: async () => {
      requestCount += 1
      await barrier
      return committedResponse()
    },
  }))
  await new Promise(resolve => waitImmediate(resolve))
  const duplicate = await submitEngineeringDocumentVersionRelease(options(shared))
  assert.equal(duplicate.duplicateSuppressed, true)
  assert.equal(requestCount, 1)
  releaseRequest()
  await first
  assert.equal(submitting, false)
})

test('原页面明确区分评审、工程资料版本发布和制造发布', () => {
  const page = fs.readFileSync(new URL('../../src/meta/pages/PdeFoundationPage.vue', import.meta.url), 'utf8')
  const component = fs.readFileSync(new URL('../../src/meta/pages/components/EngineeringDocumentReleaseReadback.vue', import.meta.url), 'utf8')
  const api = fs.readFileSync(new URL('../../src/api/pde.js', import.meta.url), 'utf8')
  assert.match(component, /FORMAL REVIEW COMPLETED/)
  assert.match(component, /engineering-document-version-release-admission/)
  assert.match(component, /READY_FOR_HUMAN_DOCUMENT_RELEASE/)
  assert.match(component, /制造发布.*独立后续动作/)
  assert.match(page, /submitEngineeringDocumentVersionRelease/)
  assert.match(page, /production\.engineering\.document\.release/)
  assert.match(page, /不会创建或推进制造发布记录/)
  assert.match(api, /engineering-document-versions\/\$\{versionId\}\/release\//)
})
