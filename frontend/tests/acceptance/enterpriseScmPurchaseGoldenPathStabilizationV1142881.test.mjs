import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createApprovalContract,
  createApprovalInstance,
  executeApprovalAction,
  writeApprovalResultToBusinessObject,
} from '../../src/meta/workflow/approvalRuntime.js'
import { resolveScmPageIdentity } from '../../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { resolvePurchaseInquiryBusinessState } from '../../src/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import {
  createSupplierBusinessDisplay,
  resolveSupplierCategoryLabel,
  resolveSupplierSourceLabel,
  resolveSupplierStatusLabel,
} from '../../src/meta/process/scm/purchaseInquiry/businessStatusDisplayMapping.js'

test('CASE-SCM-010 registers the approval configuration page identity', () => {
  const identity = resolveScmPageIdentity('/admin/approval-flow-config')
  assert.deepEqual(
    {
      pageCode: identity.pageCode,
      pageName: identity.pageName,
      route: identity.route,
      moduleCode: identity.moduleCode,
      businessObject: identity.businessObject,
    },
    {
      pageCode: 'approval-flow-config',
      pageName: '审批规则配置',
      route: '/admin/approval-flow-config',
      moduleCode: 'SCM',
      businessObject: 'ApprovalConfiguration',
    },
  )
})

for (const gateCount of [1, 2, 3]) {
  test(`CASE-SCM-011 completes an idempotent ${gateCount}-gate approval lifecycle`, () => {
    const contract = createApprovalContract('purchaseRequest', gateCount)
    let instance = createApprovalInstance({
      contract,
      businessObjectId: `PR-APPROVAL-${gateCount}`,
      submittedBy: 'requester-001',
      submittedAt: '2026-08-04T08:00:00.000Z',
    })

    for (let level = 1; level <= gateCount; level += 1) {
      const result = executeApprovalAction(instance, contract, {
        action: 'APPROVE',
        actorId: `approver-${level}`,
        actorRole: contract.gates[level - 1].approverRole,
        at: `2026-08-04T0${8 + level}:00:00.000Z`,
      })
      assert.equal(result.idempotent, false)
      instance = result.instance
    }

    assert.equal(instance.status, 'completed')
    assert.equal(instance.approvalStatus, 'approved')
    assert.equal(instance.approvalResult.code, 'approved')
    assert.equal(instance.approvalHistory.length, gateCount + 1)

    const duplicateApproval = executeApprovalAction(instance, contract, {
      action: 'APPROVE',
      actorId: 'duplicate-approver',
    })
    assert.equal(duplicateApproval.idempotent, true)
    assert.deepEqual(duplicateApproval.instance, instance)

    const firstWriteback = writeApprovalResultToBusinessObject(instance, {
      requestNo: `PR-APPROVAL-${gateCount}`,
      approvalStatus: 'submitted',
      businessLifecycleState: 'submitted',
    })
    assert.equal(firstWriteback.written, true)
    assert.equal(firstWriteback.object.approvalStatus, 'approved')
    assert.equal(firstWriteback.object.businessLifecycleState, 'approved')

    const duplicateWriteback = writeApprovalResultToBusinessObject(instance, firstWriteback.object)
    assert.equal(duplicateWriteback.written, false)
    assert.equal(duplicateWriteback.idempotent, true)
    assert.equal(duplicateWriteback.object.approvalWritebackKeys.length, 1)
  })
}

test('CASE-SCM-012 maps runtime state to one display state and next action', () => {
  const state = resolvePurchaseInquiryBusinessState({
    statusCode: 'draft',
    statusLabel: '草稿',
    runtimeState: 'quote_preparation_ready',
  })
  assert.equal(state.processStatusLabel, '已进入供应商报价准备')
  assert.equal(state.nextAction, '进入供应商报价准备')
  assert.notEqual(state.nextAction, '编辑询价')
})

test('CASE-SCM-013 exposes business labels while retaining codes in the model', () => {
  assert.equal(resolveSupplierStatusLabel('active'), '有效')
  assert.equal(resolveSupplierCategoryLabel('unclassified'), '未分类')
  assert.equal(resolveSupplierSourceLabel('supplier_master'), '供应商主数据')
  assert.deepEqual(
    createSupplierBusinessDisplay({
      supplierStatus: 'active',
      supplierCategory: 'unclassified',
      source: 'supplier_master',
    }),
    {
      supplierStatusLabel: '有效',
      supplierCategoryLabel: '未分类',
      sourceLabel: '供应商主数据',
    },
  )
})
