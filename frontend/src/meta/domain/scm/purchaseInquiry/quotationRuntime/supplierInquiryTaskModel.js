import { SUPPLIER_QUOTATION_LIFECYCLE } from './supplierQuotationStateModel.js'

export const SUPPLIER_INQUIRY_TASK_MODEL_VERSION = 'V1.14.2.8.6.1'

const field = (name, type, required = true) => Object.freeze({ name, type, required, factAuthority: 'server' })

export const SUPPLIER_INQUIRY_TASK = Object.freeze({
  objectCode: 'SCM_SUPPLIER_INQUIRY_TASK',
  objectName: '供应商询价任务',
  businessObject: 'SupplierInquiryTask',
  version: SUPPLIER_INQUIRY_TASK_MODEL_VERSION,
  fields: Object.freeze([
    field('inquiryNo', 'string'),
    field('supplierId', 'string'),
    field('sendStatus', 'status'),
    field('responseDeadline', 'datetime'),
    field('quotationStatus', 'status'),
  ]),
  lifecycle: SUPPLIER_QUOTATION_LIFECYCLE,
  persistenceMode: 'read_only_projection',
  automaticQuotationCreation: false,
  supplierApiEnabled: false,
  productionDataWritten: false,
})

export function validateSupplierInquiryTask(model = SUPPLIER_INQUIRY_TASK) {
  const expected = ['inquiryNo', 'supplierId', 'sendStatus', 'responseDeadline', 'quotationStatus']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = expected.every((name) => fields.has(name))
    && model.persistenceMode === 'read_only_projection'
    && model.automaticQuotationCreation === false
    && model.supplierApiEnabled === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
