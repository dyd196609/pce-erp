import { SUPPLIER_QUOTATION_LIFECYCLE } from './supplierQuotationStateModel.js'

export const SUPPLIER_QUOTATION_MODEL_VERSION = 'V1.14.2.8.6.1'

const field = (name, type, required = true) => Object.freeze({ name, type, required, factAuthority: 'server' })

export const SUPPLIER_QUOTATION = Object.freeze({
  objectCode: 'SCM_SUPPLIER_QUOTATION',
  objectName: '供应商报价',
  businessObject: 'SupplierQuotation',
  version: SUPPLIER_QUOTATION_MODEL_VERSION,
  fields: Object.freeze([
    field('quotationNo', 'string'),
    field('supplierId', 'string'),
    field('inquiryNo', 'string'),
    field('quotationStatus', 'status'),
    field('items', 'array'),
    field('price', 'money'),
    field('currency', 'currency'),
    field('deliveryDays', 'number'),
    field('validUntil', 'date', false),
  ]),
  lifecycle: SUPPLIER_QUOTATION_LIFECYCLE,
  sourceDomainObject: 'SCM_SUPPLIER_QUOTE',
  persistenceMode: 'read_only_projection',
  automaticCreation: false,
  advancesPriceApproval: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validateSupplierQuotation(model = SUPPLIER_QUOTATION) {
  const expected = ['quotationNo', 'supplierId', 'inquiryNo', 'quotationStatus', 'items', 'price', 'currency', 'deliveryDays']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = expected.every((name) => fields.has(name))
    && model.lifecycle.length === 7
    && model.persistenceMode === 'read_only_projection'
    && model.automaticCreation === false
    && model.advancesPriceApproval === false
    && model.createsPurchaseOrder === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
