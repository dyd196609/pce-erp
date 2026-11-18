import { createInquiryPreparationProvider } from '../../providers/inquiryPreparationProvider.js'

const fixture = Object.freeze({ inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008',
  requestDepartment: '采购部', purchaseDepartment: '计划物控部', status: 'prepared',
  inquiryLines: Object.freeze([{ materialCode: 'MT068', materialName: '扩展坞', quantity: 14, requiredDate: '2026-08-09' },
    { materialCode: 'MT026', materialName: '胶水', quantity: 500, requiredDate: '2026-08-10' }]),
  supplierCandidates: Object.freeze([{ supplierId: 'SUP001', supplierName: '华为技术有限公司' }]) })

export const PURCHASE_INQUIRY_PREPARATION_PROVIDER_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_PREPARATION_PROVIDER', version: 'V1.14.2.8.7.10',
  status: 'SCM_PURCHASE_INQUIRY_PREPARATION_PROVIDER_READY', route: '/scm/purchase-inquiry',
  providerCode: 'SCM_INQUIRY_PREPARATION_PROVIDER', sourceObject: 'InquiryPreparationObject',
  formalInquiryCreated: false, quotationCreated: false, supplierSent: false,
  priceApprovalCreated: false, purchaseOrderCreated: false,
  gates: Object.freeze(['Provider', 'Schema', 'Page', 'Router', 'Acceptance', 'Build']),
})

export function validatePurchaseInquiryPreparationProviderAcceptance() {
  const facts = createInquiryPreparationProvider({ reader: () => [fixture] }).load({ sourceRequestNo: 'PR202608020008' })
  const valid = facts.providerCode === 'SCM_INQUIRY_PREPARATION_PROVIDER' && facts.recordCount === 1
    && facts.selected?.sourceRequestNo === 'PR202608020008' && facts.selected?.materialLineCount === 2
    && facts.selected?.materialQuantity === 514 && facts.selected?.supplierCandidateCount === 1
    && facts.selected?.statusLabel === '询价准备完成'
    && Object.values(facts.protections).every(value => value === false || value === 'UNCHANGED')
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', facts })
}
