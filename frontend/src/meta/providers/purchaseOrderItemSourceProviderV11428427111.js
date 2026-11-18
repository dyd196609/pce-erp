import { getScmState } from '../scm/scmStore.js'
import { calculatePurchaseOrderQuantityV11428427112 } from
  '../domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { buildPurchaseOrderCreationContextV114284271145 } from
  '../domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js'

export const PURCHASE_ORDER_ITEM_SOURCE_PROVIDER_VERSION_V11428427111 =
  'V1.14.2.8.4.27.1.1'
export const PURCHASE_ORDER_SUPPLIER_SPLIT_PROVIDER_VERSION_V11428427114 =
  'V1.14.2.8.4.27.1.4'
export const PURCHASE_ORDER_SUPPLIER_REAL_SPLIT_PROVIDER_VERSION_V114284271143 =
  'V1.14.2.8.4.27.1.4.3'
export const PURCHASE_ORDER_DRAFT_RUNTIME_SOURCE_PROVIDER_VERSION_V1142842711431 =
  'V1.14.2.8.4.27.1.4.3.1'
export const PURCHASE_ORDER_CREATION_CONTEXT_PROVIDER_VERSION_V114284271145 =
  'V1.14.2.8.4.27.1.4.5'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))

function hydrateFromAuthoritativeFacts({ gate = {}, draft = {}, scmState = {},
  purchaseRequestFacts = [] } = {}) {
  const orders = scmState.purchaseOrders || []
  const orderItems = scmState.purchaseOrderItems || []
  const creationContext = buildPurchaseOrderCreationContextV114284271145({
    gate, draft, purchaseRequestFacts, scmState,
  })
  const inTransitStatuses = new Set(['issued', 'released', 'ordered',
    'partially_received', 'partiallyReceived', 'receiving'])
  const governedOrderIds = orders.filter(item => item.classification === 'GATE_CREATED'
    && inTransitStatuses.has(text(item.lifecycleStatus || item.status))).map(item => text(item.id))
  const items = creationContext.materialItems.map(line => {
    const hasExplicitRequestedQuantity = Object.prototype.hasOwnProperty.call(
      line, 'requestedQuantity') && Number.isFinite(Number(line.requestedQuantity))
    const requestedQuantity = hasExplicitRequestedQuantity
      ? Number(line.requestedQuantity) : 0
    const orderedQuantity = orderItems.filter(item => governedOrderIds.includes(text(item.poId))
      && text(item.materialCode) === text(line.materialCode))
      .reduce((sum, item) => sum + Math.max(Number(item.confirmedQuantity
        ?? item.quantity ?? 0) - Number(item.receivedQuantity || 0), 0), 0)
    const hydratedLine = { ...line,
      sourcePurchaseRequestIds: clone(line.sourcePurchaseRequestIds || []),
      sourcePurchaseRequestId: text(line.sourcePurchaseRequestId
        || line.sourcePurchaseRequestIds?.[0] || gate.purchaseRequestId),
      requestedQuantity,
      orderedQuantity,
      requestedDate: text(line.requestedDate),
      quantitySource: text(line.quantitySource) || 'UNKNOWN',
    }
    const quantityCalculation = calculatePurchaseOrderQuantityV11428427112(hydratedLine)
    return { ...hydratedLine,
      itemDraftStatus: quantityCalculation.itemDraftStatus,
      itemDraftStatusLabel: quantityCalculation.itemDraftStatusLabel,
      quantityConsistencyStatus: quantityCalculation.quantityConsistencyStatus,
      quantityConsistencyStatusLabel: quantityCalculation.quantityConsistencyStatusLabel,
      netDemandQuantity: quantityCalculation.netDemandQuantity,
      remainingQuantity: quantityCalculation.netDemandQuantity,
      suggestedPurchaseQuantity: quantityCalculation.suggestedPurchaseQuantity,
      suggestedQuantity: quantityCalculation.suggestedPurchaseQuantity,
      originalSuggestedQuantity: Object.prototype.hasOwnProperty.call(
        hydratedLine, 'originalSuggestedQuantity')
        && hydratedLine.originalSuggestedQuantity !== null
        && hydratedLine.originalSuggestedQuantity !== ''
        ? Number(hydratedLine.originalSuggestedQuantity)
        : quantityCalculation.suggestedPurchaseQuantity,
      availableInventoryStatus: quantityCalculation.availableInventoryStatus,
      purchasedNotReceivedStatus: quantityCalculation.purchasedNotReceivedStatus,
      quantityCalculationStatus: quantityCalculation.calculationStatus,
    }
  })
  return clone({ ...draft,
    finalCheckVersion: 'V1.14.2.8.4.27.1.4.6',
    purchaseRequestIds: creationContext.purchaseRequestIds,
    purchaseInquiryIds: creationContext.purchaseInquiryIds,
    quoteComparisonIds: creationContext.quoteComparisonIds,
    priceApprovalIds: creationContext.priceApprovalIds,
    creationContext: { ...creationContext, materialItems: items,
      supplierPurchaseDrafts: draft.supplierPurchaseDrafts || [] },
    materialItems: items })
}

export function createPurchaseOrderItemSourceProviderV11428427111({
  stateReader = getScmState,
} = {}) {
  return freeze({
    providerCode: 'PurchaseOrderItemSourceProvider',
    sourcePriority: freeze(['SupplierRecommendationGate',
      'SupplierRecommendationDecision', 'PriceApproval', 'QuoteComparison', 'PurchaseRequest']),
    hydrate({ gate = {}, draft = {}, purchaseRequestFacts = [] } = {}) {
      return hydrateFromAuthoritativeFacts({ gate, draft, scmState: stateReader(),
        purchaseRequestFacts })
    },
    load({ gate = {}, draft = {} } = {}) {
      const hydrated = hydrateFromAuthoritativeFacts({ gate, draft, scmState: stateReader() })
      const items = Array.isArray(hydrated.materialItems) ? hydrated.materialItems : []
      const supplierIds = [...new Set(items.map(item => text(item.supplierId)).filter(Boolean))]
      const requiredSourceFields = ['sourceInquiryId',
        'sourceQuoteComparisonId', 'sourcePriceApprovalId', 'sourceGateId']
      const sourceComplete = items.length > 0 && items.every(item =>
        requiredSourceFields.every(field => text(item[field]))
          && Array.isArray(item.sourcePurchaseRequestIds)
          && item.sourcePurchaseRequestIds.length > 0
          && item.quantitySource !== 'UNKNOWN'
          && (item.itemDraftStatus === 'excluded' || Number(item.requestedQuantity) > 0))
      return freeze({
        objectType: 'PurchaseOrderItemSourceFacts',
        factSource: 'SupplierRecommendationGate',
        factLoadStatus: sourceComplete ? 'loaded' : 'partial',
        sourceComplete,
        sourceTrace: frozen({
          purchaseRequestIds: hydrated.creationContext?.purchaseRequestIds || [],
          purchaseRequestId: gate.purchaseRequestId || '', inquiryId: gate.inquiryId || '',
          quoteComparisonId: gate.quoteComparisonId || '',
          priceApprovalId: gate.priceApprovalId || '', gateId: gate.gateId || '',
        }),
        items: frozen(items),
        quantityCalculations: frozen(items.map(item =>
          calculatePurchaseOrderQuantityV11428427112(item))),
        quantityFormula: '建议采购数量 = 需求数量 - 可用库存 - 已采购未入库数量',
        supplierPolicy: 'ONE_SUPPLIER_PER_PURCHASE_ORDER',
        supplierDraftPolicy: 'MULTIPLE_SUPPLIER_DRAFTS_PER_PURCHASE_ORDER_DRAFT',
        supplierSplitSupported: true,
        supplierIds: frozen(supplierIds),
        supplierSplitRequired: supplierIds.length > 1,
        supplierCountSource: 'SupplierPurchaseDraft.length',
        automaticSupplierAllocation: false,
        automaticPurchaseOrderCreation: false,
        businessWriteCount: 0,
        productionDataWritten: false,
      })
    },
  })
}

export const purchaseOrderItemSourceProviderV11428427111 =
  createPurchaseOrderItemSourceProviderV11428427111()
