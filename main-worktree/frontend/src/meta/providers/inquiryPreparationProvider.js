import { readInquiryPreparationContextSnapshot } from '../runtime/inquiryPreparationRuntime.js'

export const INQUIRY_PREPARATION_PROVIDER_VERSION = 'V1.14.2.8.18.3'

const numberValue = value => Number(value || 0)
const freezeList = values => Object.freeze(values.map(value => Object.freeze(value)))

export function mapInquiryPreparationWorkbenchRow(object = {}) {
  const inquiryLines = freezeList(Array.isArray(object.materialLines) ? object.materialLines
    : Array.isArray(object.inquiryLines) ? object.inquiryLines : [])
  const supplierCandidates = freezeList(Array.isArray(object.supplierCandidates) ? object.supplierCandidates : [])
  return Object.freeze({
    inquiryPreparationNo: String(object.inquiryPreparationNo || ''),
    objectType: object.objectType || 'InquiryPreparationContext',
    contextContractCode: object.contextContractCode || 'SCM_INQUIRY_PREPARATION_CONTEXT',
    sourceRequestNo: String(object.sourceRequestNo || ''),
    sourceRequestDate: String(object.sourceRequestDate || ''),
    requester: String(object.requester || ''),
    requestDepartment: String(object.requestDepartment || ''),
    purchaseDepartment: String(object.purchaseDepartment || ''),
    inquiryLines,
    materialLineCount: inquiryLines.length,
    materialQuantity: inquiryLines.reduce((sum, line) => sum + numberValue(line.quantity), 0),
    requiredDate: object.requiredDate || inquiryLines.map(line => line.requiredDate).filter(Boolean).sort()[0] || '',
    supplierCandidates,
    supplierCandidateCount: supplierCandidates.length,
    preparationStatus: object.preparationStatus || (object.status === 'prepared' ? 'ready_for_inquiry' : 'created'),
    status: object.preparationStatus === 'ready_for_inquiry' || object.status === 'prepared' ? 'prepared' : 'blocked',
    statusLabel: object.preparationStatus === 'ready_for_inquiry' || object.status === 'prepared' ? '询价准备就绪' : '询价准备异常',
    sourceTrace: object.sourceTrace || null,
    inquiryCreated: false,
    quotationCreated: false,
    supplierSent: false,
    priceApprovalCreated: false,
    purchaseOrderCreated: false,
  })
}

export function createInquiryPreparationProvider({ snapshotReader = readInquiryPreparationContextSnapshot } = {}) {
  return Object.freeze({
    providerCode: 'SCM_INQUIRY_PREPARATION_PROVIDER',
    version: INQUIRY_PREPARATION_PROVIDER_VERSION,
    factOwner: 'inquiry-preparation',
    sourceObject: 'InquiryPreparationContext',
    targetView: 'PurchaseInquiryWorkbench',
    load(query = {}) {
      const snapshot = snapshotReader()
      const objects = freezeList(snapshot.objects.map(mapInquiryPreparationWorkbenchRow))
      const selected = objects.find(item => item.inquiryPreparationNo === query.inquiryPreparationNo)
        || objects.find(item => item.sourceRequestNo === query.sourceRequestNo) || objects.at(-1) || null
      return Object.freeze({ providerCode: this.providerCode, version: this.version,
        factSource: 'inquiry_preparation_context_runtime', storageLocation: snapshot.storageLocation,
        snapshotId: snapshot.snapshotId, runtimeRevision: snapshot.revision,
        recordCount: objects.length, objects, selected,
        protections: Object.freeze({ inquiryCreated: false, quotationCreated: false, supplierSent: false,
          priceApprovalCreated: false, purchaseOrderCreated: false, productionDataWritten: false, database: 'UNCHANGED' }) })
    },
  })
}

export const inquiryPreparationProvider = createInquiryPreparationProvider()
