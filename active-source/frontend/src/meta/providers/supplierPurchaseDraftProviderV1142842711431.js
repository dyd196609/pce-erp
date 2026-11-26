import { calculatePurchaseOrderQuantityV11428427112 } from
  '../domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { evaluateSupplierPurchaseDraftsV11428427114,
  synchronizeSupplierPurchaseDraftsV11428427114 } from
  '../domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'
import { evaluatePurchaseOrderMaterialEligibilityV114284271144 } from
  '../domain/scm/purchaseOrder/guard/purchaseOrderMaterialEligibilityGuardV114284271144.js'

export const SUPPLIER_PURCHASE_DRAFT_PROVIDER_VERSION_V1142842711431 =
  'V1.14.2.8.4.27.1.4.3.1'
export const PURCHASE_ORDER_MATERIAL_ELIGIBILITY_PROVIDER_VERSION_V114284271144 =
  'V1.14.2.8.4.27.1.4.4'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))

export function createSupplierPurchaseDraftProviderV1142842711431() {
  return freeze({
    providerCode: 'SupplierPurchaseDraftProviderV1142842711431',
    sourceObjectType: 'PurchaseOrderDraft',
    supplierObjectType: 'SupplierPurchaseDraft',
    load({ draft = {} } = {}) {
      if (draft.objectType !== 'PurchaseOrderDraft') {
        return { result: 'FAIL', factLoadStatus: 'read_failed',
          error: 'PURCHASE_ORDER_DRAFT_REQUIRED', draft: null,
          supplierPurchaseDrafts: [], materialItems: [], supplierCount: 0,
          businessWriteCount: 0, productionDataWritten: false }
      }
      const normalizedDraft = synchronizeSupplierPurchaseDraftsV11428427114(draft)
      const materialItems = normalizedDraft.materialItems || []
      const quantityCalculations = materialItems.map(calculatePurchaseOrderQuantityV11428427112)
      const materialEligibility = evaluatePurchaseOrderMaterialEligibilityV114284271144(
        materialItems)
      const eligibleDraft = synchronizeSupplierPurchaseDraftsV11428427114({
        ...normalizedDraft, materialItems: materialEligibility.eligibleItems,
      })
      const supplierEvaluation = evaluateSupplierPurchaseDraftsV11428427114(eligibleDraft)
      const recommendationEvidenceItems = materialEligibility.recommendationEvidenceItems.map(item => {
        const check = materialEligibility.checks.find(value =>
          value.lineNo === Number(item.lineNo)
            || (value.materialCode && value.materialCode === text(item.materialCode)))
        return { ...item, eligibilityResult: check?.result || 'NOT_SELECTED',
          eligibilityReason: check?.reason || '推荐证据未纳入采购草稿。' }
      })
      const supplierPurchaseDrafts = eligibleDraft.supplierPurchaseDrafts || []
      const creationContext = normalizedDraft.creationContext ? {
        ...normalizedDraft.creationContext,
        supplierPurchaseDrafts: clone(supplierPurchaseDrafts),
        materialItems: clone(materialItems),
        sourcePurchaseRequestCount:
          (normalizedDraft.creationContext.purchaseRequestIds || []).length,
      } : null
      const compositeSupplierRows = supplierPurchaseDrafts.filter(group =>
        /[、，,；;]/.test(text(group.supplierName)))
      const blockedReasons = [
        ...compositeSupplierRows.map(group =>
          `${text(group.supplierId) || '未知供应商'}：聚合供应商名称不能作为采购草稿数据源。`),
      ]
      const result = blockedReasons.length ? 'FAIL' : 'PASS'
      return {
        objectType: 'SupplierPurchaseDraftSourceFacts',
        result,
        factLoadStatus: result === 'PASS' ? 'loaded' : 'read_failed',
        sourceTrace: frozen({
          page: 'ScmPurchaseOrderCreateEntryPage',
          provider: 'SupplierPurchaseDraftProviderV1142842711431',
          runtime: 'PurchaseOrderDraft',
          domainModel: 'SupplierPurchaseDraft',
          supplierListSource: 'SupplierPurchaseDraft[]',
          itemSupplierSource: 'PurchaseOrderItem.supplierId/supplierName',
          recommendationDecisionRole: 'evidence_only',
        }),
        draft: clone({ ...normalizedDraft,
          creationContext,
          supplierPurchaseDrafts, supplierDrafts: supplierPurchaseDrafts,
          supplierCount: supplierPurchaseDrafts.length,
          purchaseMaterialItems: materialEligibility.eligibleItems,
          recommendationEvidenceItems,
          validMaterialCount: materialEligibility.validMaterialCount,
          invalidMaterialCount: materialEligibility.invalidMaterialCount,
        }),
        supplierPurchaseDrafts: clone(supplierPurchaseDrafts),
        creationContext: clone(creationContext),
        materialItems: clone(materialItems),
        quantityCalculations: frozen(quantityCalculations),
        materialEligibility: frozen(materialEligibility),
        validMaterialItems: clone(materialEligibility.eligibleItems),
        invalidMaterialItems: clone(materialEligibility.invalidItems),
        recommendationEvidenceItems: clone(recommendationEvidenceItems),
        validMaterialCount: materialEligibility.validMaterialCount,
        invalidMaterialCount: materialEligibility.invalidMaterialCount,
        supplierCount: supplierPurchaseDrafts.length,
        supplierCountSource: 'SupplierPurchaseDraft.length',
        supplierEvaluation: frozen(supplierEvaluation),
        invalidDemandItems: clone(materialEligibility.invalidItems.filter(item =>
          Number(item.requestedQuantity) === 0
            && Number(item.confirmedQuantity ?? item.quantity) > 0)),
        blockedReasons: frozen(blockedReasons),
        recommendationDecisionUsedAsDraftSource: false,
        aggregateSupplierFieldUsed: false,
        businessWriteCount: 0,
        productionDataWritten: false,
      }
    },
  })
}

export const supplierPurchaseDraftProviderV1142842711431 =
  createSupplierPurchaseDraftProviderV1142842711431()
