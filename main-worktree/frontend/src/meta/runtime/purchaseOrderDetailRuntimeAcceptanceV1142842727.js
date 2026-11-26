export const PURCHASE_ORDER_DETAIL_RUNTIME_ACCEPTANCE_VERSION_V1142842727 =
  'V1.14.2.8.4.27.2.7'

export function evaluatePurchaseOrderDetailRuntimeV1142842727({
  urlOpened = false, pageTitleVisible = false, classificationVisible = false,
  numberCardsVisible = false, basicInformationVisible = false,
  sourceRelationsVisible = false, materialWideTableVisible = false,
  lifecycleVisible = false, operationButtonsVisible = false,
  oldRendererUsed = true, oldLayoutPresent = true, newLayoutActive = false,
  printClassificationChanged = false, printPreviewUpdated = false,
  refreshRequested = false, providerReloaded = false, stateUpdated = false,
  uiTimestampUpdated = false, routeStable = false, businessObjectStable = false,
  businessWriteCount = 0,
} = {}) {
  const checks = Object.freeze({
    urlOpened, pageTitleVisible, classificationVisible, numberCardsVisible,
    basicInformationVisible, sourceRelationsVisible, materialWideTableVisible,
    lifecycleVisible, operationButtonsVisible,
    pageMigration: !oldRendererUsed && !oldLayoutPresent && newLayoutActive,
    printOutputClassification: printClassificationChanged && printPreviewUpdated,
    refreshRuntime: refreshRequested && providerReloaded && stateUpdated
      && uiTimestampUpdated && routeStable && businessObjectStable,
    zeroBusinessWrite: Number(businessWriteCount) === 0,
  })
  return Object.freeze({
    version: PURCHASE_ORDER_DETAIL_RUNTIME_ACCEPTANCE_VERSION_V1142842727,
    rules: Object.freeze(['PURCHASE-ORDER-DETAIL-RUNTIME-002', 'PAGE-MIGRATION-002']),
    checks, businessWriteCount: Number(businessWriteCount) || 0,
    result: Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL',
  })
}
