import { readInquiryPreparationContextSnapshot } from './inquiryPreparationRuntime.js'
import { inquiryPreparationProvider } from '../providers/inquiryPreparationProvider.js'

export const INQUIRY_PREPARATION_PROVIDER_DIAGNOSTIC_VERSION = 'V1.14.2.8.18.3.1'

export function buildInquiryPreparationProviderDiagnostic({
  contextSnapshot = readInquiryPreparationContextSnapshot(),
  providerFacts = inquiryPreparationProvider.load(),
  pageRows = providerFacts.objects,
} = {}) {
  const sourceRequestNos = Object.freeze(contextSnapshot.objects.map(item => item.sourceRequestNo).sort())
  const providerSourceRequestNos = providerFacts.objects.map(item => item.sourceRequestNo).sort()
  const pageSourceRequestNos = (pageRows || []).map(item => item.sourceRequestNo).sort()
  const contextCount = contextSnapshot.recordCount
  const providerRecordCount = providerFacts.recordCount
  const pageConsumedCount = pageRows?.length || 0
  const consistent = contextCount === providerRecordCount && providerRecordCount === pageConsumedCount
    && sourceRequestNos.join('|') === providerSourceRequestNos.join('|')
    && providerSourceRequestNos.join('|') === pageSourceRequestNos.join('|')
  return Object.freeze({ contextCount, providerRecordCount, pageConsumedCount, sourceRequestNos,
    consistent, result: consistent ? 'PASS' : 'FAIL',
    trace: Object.freeze({ creationLocation: 'inquiryPreparationRuntime.createInquiryPreparation',
      storageLocation: contextSnapshot.storageLocation,
      providerReadLocation: 'SCM_INQUIRY_PREPARATION_PROVIDER',
      pageConsumeLocation: 'ScmPurchaseInquiryWorkbenchPage.pendingInquiryPreparations' }) })
}

