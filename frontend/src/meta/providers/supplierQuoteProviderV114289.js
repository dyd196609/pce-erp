import { supplierQuoteRuntimeStore } from '../runtime/supplierQuoteRuntimeStoreV114289.js'
import { resolveSupplierQuoteStatusLabel } from '../process/scm/supplierQuote/supplierQuoteStateContractV114289.js'
import { supplierQuotePreparationRuntimeAdapter } from '../runtime/supplierQuotePreparationRuntimeAdapterV1142812.js'
import { projectSupplierQuoteSimpleFields } from '../process/scm/supplierQuote/supplierQuoteSimpleModelV11428121.js'
import { resolveEnterpriseListCanaryQuery } from '../runtime/enterpriseListCanaryMode.js'

const loadFormalApi = () => import('../../api/scmStandardPageFacts.js')
const loadCanaryApi = () => import('../../api/purchaseCanary.js')

export const SUPPLIER_QUOTE_PROVIDER_VERSION = 'V1.14.2.8.18.9'

export function createSupplierQuoteProvider({ store = supplierQuoteRuntimeStore,
  preparationAdapter = supplierQuotePreparationRuntimeAdapter } = {}) {
  return Object.freeze({
    providerCode: 'SCM_SUPPLIER_QUOTE_PROVIDER',
    factSource: 'supplier_quote_runtime_store',
    load({ supplierQuoteContextNo = '', inquiryNo = '' } = {}) {
      const persistedContexts = store.listContexts().filter(item =>
        (!supplierQuoteContextNo || item.supplierQuoteContextNo === supplierQuoteContextNo)
        && (!inquiryNo || item.inquiryNo === inquiryNo))
      const bindingFacts = preparationAdapter.load({ inquiryNo })
      const persistedPreparationNos = new Set(persistedContexts.map(item => item.quotePreparationNo))
      const contexts = [...persistedContexts, ...bindingFacts.contexts.filter(item =>
        !persistedPreparationNos.has(item.quotePreparationNo)
        && (!supplierQuoteContextNo || item.supplierQuoteContextNo === supplierQuoteContextNo))]
      const allQuotes = store.listQuotes()
      const records = contexts.flatMap(context => context.materialSupplierCandidates.map(pair => {
        const quote = allQuotes.find(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo
          && item.materialCode === pair.materialCode && item.supplierCode === pair.supplierCode) || null
        const bindingFact = bindingFacts.supplierQuotes.find(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo
          && item.materialCode === pair.materialCode && item.supplierCode === pair.supplierCode) || null
        const simpleQuote = quote ? projectSupplierQuoteSimpleFields({
          quoteId: quote.quoteId || quote.quoteNo, sourceInquiryId: quote.sourceInquiryId || quote.inquiryNo,
          supplierCode: quote.supplierCode, supplierName: quote.supplierName,
          materialCode: quote.materialCode, materialName: quote.materialName, quantity: quote.quantity,
          quotePrice: quote.quotePrice ?? quote.unitPrice, remark: quote.remark || '',
        }) : null
        return Object.freeze({
          supplierQuoteContextNo: context.supplierQuoteContextNo,
          quotePreparationNo: context.quotePreparationNo,
          inquiryNo: context.inquiryNo,
          sourceRequestNo: context.sourceRequestNo,
          quoteStatus: context.quoteStatus,
          statusLabel: resolveSupplierQuoteStatusLabel(context.quoteStatus),
          materialCode: pair.materialCode,
          materialName: pair.materialName,
          quantity: pair.quantity,
          supplierCode: pair.supplierCode,
          supplierName: pair.supplierName,
          quote,
          quoteId: simpleQuote?.quoteId || bindingFact?.quoteNo || '',
          sourceInquiryId: context.inquiryNo,
          quotePrice: simpleQuote?.quotePrice || null,
          remark: simpleQuote?.remark || '',
          simpleQuote,
          runtimeContext: context,
          bindingFact,
          quoted: Boolean(quote),
        })
      }))
      return Object.freeze({
        providerCode: this.providerCode,
        factSource: this.factSource,
        contexts: Object.freeze(contexts.map(Object.freeze)),
        records: Object.freeze(records),
        contextCount: contexts.length,
        recordCount: records.length,
        quoteCount: records.filter(item => item.quoted).length,
        bindingCount: records.filter(item => item.bindingFact).length,
        preparationRecordCount: bindingFacts.quoteFactCount,
        dataAligned: bindingFacts.quoteFactCount === records.length,
        preparationFactSource: bindingFacts.adapterCode,
        businessWriteCount: 0,
        productionDataWritten: 0,
        current: contexts.at(-1) || null,
        emptyMessage: contexts.length ? '' : '暂无供应商报价准备数据。',
      })
    },
    async loadRuntime({ query = {} } = {}) {
      const canary = resolveEnterpriseListCanaryQuery(query)
      const dataMode = canary.isCanaryMode ? 'canary_acceptance' : 'production'
      const response = canary.isCanaryMode
        ? await loadCanaryApi().then(api => api.getSupplierQuotationCanaryRuntime({ canaryBatchId: canary.canaryBatchId, scenarioCode: canary.scenarioCode }))
        : await loadFormalApi().then(api => api.getScmStandardPageFacts('supplier-quotation'))
      if (!response?.success || !response.data) throw new Error(response?.error?.message || '供应商报价事实读取失败')
      const records = Object.freeze((response.data.sourceInquiryRows || []).map(row => Object.freeze({
        ...row, inquiryNo: row.sourceInquiryNo, sourceInquiryId: row.sourceInquiryId,
        quoteStatus: row.readOnly || row.quotationStatus === 'received' ? 'read_only' : 'supplier_quote_collecting',
        quoted: Boolean(row.quoted || Number(row.quotePrice) > 0),
      })))
      const contexts = Object.freeze([...new Map(records.map(row => [`${row.sourceInquiryId}:${row.supplierId}`, Object.freeze({
        sourceInquiryId: row.sourceInquiryId, inquiryNo: row.sourceInquiryNo, supplierId: row.supplierId,
        supplierName: row.supplierName, quotationId: row.quotationId, quotationNo: row.quotationNo,
        quotationStatus: row.quotationStatus,
      })])).values()])
      return Object.freeze({ providerCode: canary.isCanaryMode ? 'SupplierQuotationCanaryProvider' : 'SupplierQuotationProductionProvider',
        factSource: 'server', dataMode, contexts, records, recordCount: records.length,
        preparationRecordCount: response.data.sourceInquiryRowCount || records.length, dataAligned: true,
        canaryBatchId: response.data.canaryBatchId || '', scenarioCode: response.data.scenarioCode || '',
        sourceMapping: response.data.sourceMapping || null, businessWriteCount: 0,
        priceApprovalCreated: false, purchaseOrderCreated: false, productionUserDataWritten: false })
    },
    async saveQuotation(row, input) {
      const { saveSupplierQuotation } = await loadFormalApi()
      const response = await saveSupplierQuotation({ sourceInquiryId: row.sourceInquiryId, supplierId: row.supplierId,
        materialCode: row.materialCode, quotePrice: input.quotePrice, remark: input.remark || '', currency: row.currency || 'CNY' })
      if (!response?.success) throw new Error(response?.error?.message || '供应商报价保存失败')
      return Object.freeze(response.data)
    },
    async submitQuotation(quotationId) {
      const { submitSupplierQuotation } = await loadFormalApi()
      const response = await submitSupplierQuotation(quotationId)
      if (!response?.success) throw new Error(response?.error?.message || '供应商报价提交失败')
      return Object.freeze(response.data)
    },
  })
}

export const supplierQuoteProvider = createSupplierQuoteProvider()
