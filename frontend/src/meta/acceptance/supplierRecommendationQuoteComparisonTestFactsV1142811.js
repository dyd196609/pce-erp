import { createQuoteComparisonModel } from '../process/scm/quoteComparison/quoteComparisonDomainModelV1142810.js'

export const SUPPLIER_RECOMMENDATION_TEST_FACT_VERSION_V1142811 = 'V1.14.2.8.18.11'

const createdAt = '2026-08-05T08:00:00.000Z'
const comparison = (quote, ranks) => createQuoteComparisonModel(quote, ranks, createdAt)

const comparisons = Object.freeze([
  comparison({ inquiryNo: 'PI-TEST-SR-001', materialCode: 'MAT-000001', materialName: '工业铝型材',
    supplierCode: 'SUP-000001', supplierName: '精工铝材供应商', quantity: 100,
    unitPrice: 86.5, deliveryDate: '2026-08-22', validityDate: '2026-09-30' },
  { priceRank: 1, deliveryRank: 2, validityStatus: 'valid' }),
  comparison({ inquiryNo: 'PI-TEST-SR-001', materialCode: 'MAT-000001', materialName: '工业铝型材',
    supplierCode: 'SUP-000002', supplierName: '华信电子材料', quantity: 100,
    unitPrice: 89.2, deliveryDate: '2026-08-20', validityDate: '2026-10-15' },
  { priceRank: 2, deliveryRank: 1, validityStatus: 'valid' }),
  comparison({ inquiryNo: 'PI-TEST-SR-001', materialCode: 'MAT-000002', materialName: '工业控制器',
    supplierCode: 'SUP-000002', supplierName: '华信电子材料', quantity: 20,
    unitPrice: 1280, deliveryDate: '2026-08-28', validityDate: '2026-10-15' },
  { priceRank: 1, deliveryRank: 1, validityStatus: 'valid' }),
  comparison({ inquiryNo: 'PI-TEST-SR-001', materialCode: 'MAT-000002', materialName: '工业控制器',
    supplierCode: 'SUP-000003', supplierName: '联创包装材料', quantity: 20,
    unitPrice: 1325, deliveryDate: '2026-08-30', validityDate: '2026-09-20' },
  { priceRank: 2, deliveryRank: 2, validityStatus: 'valid' }),
])

export const SUPPLIER_RECOMMENDATION_READ_ONLY_QUOTE_COMPARISON_FACTS_V1142811 = Object.freeze([
  Object.freeze({
    objectType: 'SupplierRecommendationDecisionPreparationContext',
    recommendationPreparationNo: 'SRDP-PI-TEST-SR-001',
    comparisonPreparationNo: 'QCP-PI-TEST-SR-001',
    sourceQuoteComparisonId: 'QCP-PI-TEST-SR-001',
    sourceInquiryNo: 'PI-TEST-SR-001',
    sourceRequestNo: 'PR-TEST-SR-001',
    comparisons,
    supplierQualificationFacts: Object.freeze([
      Object.freeze({ supplierCode: 'SUP-000001', supplierStatus: 'enabled',
        supplierCategory: 'A', qualificationStatus: 'qualified' }),
      Object.freeze({ supplierCode: 'SUP-000002', supplierStatus: 'enabled',
        supplierCategory: 'B', qualificationStatus: 'qualified' }),
      Object.freeze({ supplierCode: 'SUP-000003', supplierStatus: 'enabled',
        supplierCategory: 'A', qualificationStatus: 'qualified' }),
    ]),
    preparationStatus: 'comparison_ready',
    factScope: 'acceptance_read_only',
    readOnly: true,
    createdAt,
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeCreated: false,
    wmsCreated: false,
    mesCreated: false,
    businessWriteCount: 0,
    productionDataWritten: 0,
  }),
])
