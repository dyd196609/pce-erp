import { QUOTATION_COMPARISON_STATES } from './quotationComparisonStateModel.js'

export const QUOTATION_COMPARISON_MODEL_VERSION = 'V1.14.2.8.6.2'

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'server' })

export const QUOTATION_COMPARISON = Object.freeze({
  objectCode: 'SCM_QUOTATION_COMPARISON_RUNTIME',
  objectName: '报价比较运行对象',
  businessObject: 'QuotationComparison',
  version: QUOTATION_COMPARISON_MODEL_VERSION,
  fields: Object.freeze([
    field('comparisonNo', 'string'),
    field('inquiryNo', 'string'),
    field('quotationCount', 'number'),
    field('supplierCount', 'number'),
    field('lowestPriceSupplier', 'object_reference'),
    field('highestPriceSupplier', 'object_reference'),
    field('priceVariance', 'money'),
    field('deliveryComparison', 'array'),
    field('comparisonStatus', 'status'),
  ]),
  states: QUOTATION_COMPARISON_STATES,
  purpose: 'quotation_comparison_fact_only',
  persistenceMode: 'read_only_projection',
  autoSupplierSelection: false,
  automaticCreation: false,
  advancesPriceApproval: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validateQuotationComparison(model = QUOTATION_COMPARISON) {
  const expected = ['comparisonNo', 'inquiryNo', 'quotationCount', 'supplierCount', 'lowestPriceSupplier', 'highestPriceSupplier', 'priceVariance', 'deliveryComparison', 'comparisonStatus']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = expected.every((name) => fields.has(name))
    && model.states.length === 5
    && model.persistenceMode === 'read_only_projection'
    && model.autoSupplierSelection === false
    && model.automaticCreation === false
    && model.advancesPriceApproval === false
    && model.createsPurchaseOrder === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
