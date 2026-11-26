import assert from 'node:assert/strict'
import test from 'node:test'
import { setImmediate as waitImmediate } from 'node:timers'

import {
  EngineeringDocumentReviewSubmissionError,
  submitEngineeringDocumentVersionReview,
} from '../../src/meta/pages/engineeringDocumentVersionReviewSubmission.js'

const VERSION_ID = 1

function committedResponse() {
  return {
    success: true,
    data: {
      result: {
        engineeringDocumentVersion: {
          engineeringDocumentVersionId: VERSION_ID,
          status: 'reviewed',
        },
        workflow: {
          instanceId: 91,
          statusCode: 'approved',
          decisionId: 93,
        },
        businessStateTransition: {
          id: 94,
          fromState: 'draft',
          toState: 'reviewed',
          workflowInstanceId: 91,
        },
        auditId: 95,
        writeRequestId: 96,
      },
    },
    error: null,
    meta: { status: 200 },
  }
}

function committedReadback() {
  return {
    engineeringDocumentVersionId: VERSION_ID,
    documentVersionStatusLabel: '已评审',
    reviewPreflight: {
      reviewReadback: {
        completed: true,
        projectionState: 'workflow_approved',
        projectionConsistent: true,
        workflowInstanceId: 91,
        decisionId: 93,
        businessStateTransitionId: 94,
      },
    },
  }
}

function failureResponse(status, code, message) {
  return {
    success: false,
    data: null,
    error: { code, message },
    meta: { status },
    factLoadFacts: { httpStatus: status, errorCode: code, errorMessage: message },
  }
}

function submissionOptions(overrides = {}) {
  return {
    versionId: VERSION_ID,
    confirmSubmission: async () => true,
    requestReview: async () => committedResponse(),
    refreshFacts: async () => {},
    getFormalReadback: () => committedReadback(),
    ...overrides,
  }
}

test('HTTP 200 success=true只在事务证据与刷新回读一致后成功', async () => {
  let refreshCount = 0
  const result = await submitEngineeringDocumentVersionReview(submissionOptions({
    refreshFacts: async () => { refreshCount += 1 },
  }))

  assert.equal(result.duplicateSuppressed, false)
  assert.equal(result.result.engineeringDocumentVersion.status, 'reviewed')
  assert.equal(result.readback.completed, true)
  assert.equal(refreshCount, 1)
})

for (const [status, code, category] of [
  [200, 'BUSINESS_REJECTED', '工程资料版本正式评审未成功'],
  [400, 'INVALID_INPUT', '输入或业务校验未通过'],
  [401, 'NOT_AUTHENTICATED', '登录认证已失效'],
  [403, 'PERMISSION_DENIED', '正式评审权限被拒绝'],
  [409, 'STATE_CONFLICT', '业务状态或幂等冲突'],
  [500, 'SERVER_ERROR', '服务端事务处理失败'],
]) {
  test(`HTTP ${status} / success=false显示准确错误且不刷新`, async () => {
    let refreshCount = 0
    const reviewReason = '符合要求，评审通过'
    await assert.rejects(
      submitEngineeringDocumentVersionReview(submissionOptions({
        requestReview: async () => failureResponse(status, code, `${status}专项拒绝`),
        refreshFacts: async () => { refreshCount += 1 },
      })),
      error => {
        assert.ok(error instanceof EngineeringDocumentReviewSubmissionError)
        assert.equal(error.code, code)
        assert.equal(error.httpStatus, status)
        assert.match(error.userMessage, new RegExp(category))
        assert.match(error.userMessage, new RegExp(code))
        assert.match(error.userMessage, new RegExp(`${status}专项拒绝`))
        return true
      },
    )
    assert.equal(refreshCount, 0)
    assert.equal(reviewReason, '符合要求，评审通过')
  })
}

test('网络异常明确标识请求未发送且不宣称成功', async () => {
  await assert.rejects(
    submitEngineeringDocumentVersionReview(submissionOptions({
      requestReview: async () => {
        const error = new Error('连接被中断')
        error.code = 'ERR_NETWORK'
        throw error
      },
    })),
    error => {
      assert.equal(error.code, 'ERR_NETWORK')
      assert.equal(error.httpStatus, 0)
      assert.match(error.userMessage, /请求未发送或网络中断/)
      return true
    },
  )
})

test('确认弹窗取消不发送评审请求', async () => {
  let requestCount = 0
  await assert.rejects(
    submitEngineeringDocumentVersionReview(submissionOptions({
      confirmSubmission: async () => { throw 'cancel' },
      requestReview: async () => { requestCount += 1 },
    })),
    error => error === 'cancel',
  )
  assert.equal(requestCount, 0)
})

test('服务端返回成功但正式回读不一致时拒绝宣称评审完成', async () => {
  await assert.rejects(
    submitEngineeringDocumentVersionReview(submissionOptions({
      getFormalReadback: () => ({
        ...committedReadback(),
        documentVersionStatusLabel: '草稿',
      }),
    })),
    error => error.code === 'ENGINEERING_DOCUMENT_REVIEW_READBACK_MISMATCH',
  )
})

test('在途提交锁阻止重复点击发起第二个请求', async () => {
  let submitting = false
  let requestCount = 0
  let releaseRequest
  const requestBarrier = new Promise(resolve => { releaseRequest = resolve })
  const shared = {
    isSubmitting: () => submitting,
    setSubmitting: value => { submitting = value },
  }
  const first = submitEngineeringDocumentVersionReview(submissionOptions({
    ...shared,
    requestReview: async () => {
      requestCount += 1
      await requestBarrier
      return committedResponse()
    },
  }))
  await new Promise(resolve => waitImmediate(resolve))
  const duplicate = await submitEngineeringDocumentVersionReview(submissionOptions(shared))
  assert.equal(duplicate.duplicateSuppressed, true)
  assert.equal(requestCount, 1)
  releaseRequest()
  await first
  assert.equal(submitting, false)
})

test('原页面提交处理使用专用编排、错误明细与服务端回读', async () => {
  const fs = await import('node:fs')
  const pageUrl = new URL('../../src/meta/pages/PdeFoundationPage.vue', import.meta.url)
  const componentUrl = new URL('../../src/meta/pages/components/EngineeringDocumentReleaseReadback.vue', import.meta.url)
  const page = fs.readFileSync(pageUrl, 'utf8')
  const component = fs.readFileSync(componentUrl, 'utf8')
  assert.match(page, /submitEngineeringDocumentVersionReview/)
  assert.match(page, /getFormalReadback:/)
  assert.match(page, /error\?\.userMessage/)
  assert.match(component, /:loading="props\.reviewSubmitting"/)
  assert.doesNotMatch(component, /reviewReason\.value\s*=\s*['"]/)
})
