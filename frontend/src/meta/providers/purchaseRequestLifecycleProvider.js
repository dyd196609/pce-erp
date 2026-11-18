import { readInquiryPreparationRuntimeSnapshot } from '../runtime/inquiryPreparationRuntime.js'
import { listPurchaseInquiryRuntimeObjects } from '../runtime/purchaseInquiryRuntime.js'
import { readPurchaseRequestState } from '../process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

export const PURCHASE_REQUEST_LIFECYCLE_PROVIDER_CODE = 'SCM_PURCHASE_REQUEST_LIFECYCLE_PROVIDER'

const approvalLabels = Object.freeze({ draft: '草稿', submitted: '已提交', approved: '已审批', rejected: '已拒绝' })
const lifecycleLabels = Object.freeze({ created: '已创建', approved: '已批准', agreed_price_confirmation_ready: '等待既定价格确认',
  waiting_agreed_price_confirmation: '等待既定价格确认', purchase_order_created: '已生成采购订单',
  inquiry_preparation_created: '已生成询价准备', inquiry_started: '已启动询价' })

export function createPurchaseRequestLifecycleProvider({
  preparationSnapshotReader = readInquiryPreparationRuntimeSnapshot,
  inquiryReader = listPurchaseInquiryRuntimeObjects,
} = {}) {
  return Object.freeze({
    providerCode: PURCHASE_REQUEST_LIFECYCLE_PROVIDER_CODE,
    factOwner: 'purchase-request-lifecycle',
    load(serverFacts = {}) {
      const snapshot = preparationSnapshotReader()
      const inquiries = inquiryReader()
      const preparationSources = new Set(snapshot.objects.map(item => item.sourceRequestNo))
      const inquirySources = new Set(inquiries.map(item => item.sourceRequestNo))
      const objects = Object.freeze((serverFacts.objects || []).map(row => {
        const inferredLifecycle = row.purchaseMode === 'AGREED_PRICE' && ['approved','completed'].includes(row.approvalStatus) ? 'agreed_price_confirmation_ready'
          : inquirySources.has(row.requestNo) ? 'inquiry_started'
          : preparationSources.has(row.requestNo) ? 'inquiry_preparation_created'
            : undefined
        const state = readPurchaseRequestState({ ...row, businessLifecycleState: row.businessLifecycleState
          || row.businessLifecycleStatus || inferredLifecycle })
        const approval = state.approvalStatus
        const lifecycle = row.businessLifecycleStatus === 'purchase_order_created'
          ? row.businessLifecycleStatus : state.businessLifecycleState
        return Object.freeze({ ...row, approvalStatus: approval, approvalStatusLabel: approvalLabels[approval],
          businessLifecycleStatus: lifecycle,
          businessLifecycleStatusLabel: lifecycleLabels[lifecycle] || row.businessLifecycleStatusLabel })
      }))
      return Object.freeze({ ...serverFacts, objects, recordCount: objects.length,
        providerCode: this.providerCode, preparationSnapshotId: snapshot.snapshotId,
        factChain: Object.freeze(['Page', this.providerCode, 'PurchaseRequestRuntimeContext', 'PurchaseRequest']) })
    },
  })
}

export const purchaseRequestLifecycleProvider = createPurchaseRequestLifecycleProvider()
