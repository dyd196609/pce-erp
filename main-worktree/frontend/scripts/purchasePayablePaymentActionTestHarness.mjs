export function installMemoryLocalStorage() {
  const bucket = new Map()
  globalThis.localStorage = {
    getItem(key) {
      return bucket.has(key) ? bucket.get(key) : null
    },
    setItem(key, value) {
      bucket.set(key, String(value))
    },
    removeItem(key) {
      bucket.delete(key)
    },
    clear() {
      bucket.clear()
    },
  }
}

export async function loadActionModules() {
  const wms = await import('../src/meta/wms/wmsStore.js')
  const payablePrepare = await import('../src/meta/finance/payablePrepareStore.js')
  const payableCheck = await import('../src/meta/finance/payableCheckStore.js')
  const supplierSettlement = await import('../src/meta/scm/supplierSettlementStore.js')
  const invoicePrepare = await import('../src/meta/finance/invoicePrepareStore.js')
  const apDraft = await import('../src/meta/finance/accountPayableDraftStore.js')
  const apConfirm = await import('../src/meta/finance/accountPayableConfirmStore.js')
  const paymentApplication = await import('../src/meta/finance/paymentApplicationStore.js')
  const flowLink = await import('../src/meta/process/businessFlowLinkStore.js')
  const flowAudit = await import('../src/meta/process/businessFlowActionAuditStore.js')
  const executor = await import('../src/meta/process/businessFlowActionExecutor.js')
  const registry = await import('../src/meta/process/purchasePayablePaymentActionRegistry.js')
  const transition = await import('../src/meta/process/businessFlowTransitionGuard.js')
  return {
    wms,
    payablePrepare,
    payableCheck,
    supplierSettlement,
    invoicePrepare,
    apDraft,
    apConfirm,
    paymentApplication,
    flowLink,
    flowAudit,
    executor,
    registry,
    transition,
  }
}

export function resetActionStores(modules) {
  modules.wms.saveWmsState({
    inventoryBalances: [],
    inventoryTransactions: [],
    warehouseTasks: [],
    stockWarnings: [],
  })
  modules.payablePrepare.savePayablePrepareState({ payablePrepares: [] })
  modules.payableCheck.savePayableCheckState({ payableChecks: [] })
  modules.supplierSettlement.saveSupplierSettlementState({ supplierSettlements: [] })
  modules.invoicePrepare.saveInvoicePrepareState({ invoicePrepares: [] })
  modules.apDraft.saveAccountPayableDraftState({ accountPayableDrafts: [] })
  modules.apConfirm.saveAccountPayableConfirmState({ accountPayableConfirms: [] })
  modules.paymentApplication.savePaymentApplicationState({ paymentApplications: [] })
  modules.flowLink.saveBusinessFlowLinkState({ links: [] })
  modules.flowAudit.saveBusinessFlowActionAuditState({ audits: [] })
}

export function seedForAction(modules, actionCode) {
  resetActionStores(modules)
  if (actionCode === 'CREATE_PAYABLE_PREPARE') {
    modules.wms.saveWmsState({
      inventoryBalances: [],
      inventoryTransactions: [{
        id: 'txn-test-001',
        transactionNo: 'TXNTEST001',
        transactionType: 'purchaseInspectionIn',
        transactionDate: '2026-07-13',
        materialId: 'mat-001',
        materialCode: 'MAT001',
        materialName: '测试物料',
        warehouseId: 'wh-001',
        locationId: 'loc-001',
        quantity: 10,
        beforeQuantity: 0,
        afterQuantity: 10,
        qualityStatus: 'qualified',
        sourceModule: 'qms',
        sourcePurchaseOrderNo: 'POTEST001',
        sourceReceiveNo: 'PRVTEST001',
        sourceInspectionNo: 'IQCTEST001',
        supplierId: 'sup-001',
        supplierName: '测试供应商',
      }],
      warehouseTasks: [],
      stockWarnings: [],
    })
    return
  }

  modules.payablePrepare.savePayablePrepareState({
    payablePrepares: [{
      id: 'pp-test-001',
      payablePrepareNo: 'PPTEST001',
      sourceInventoryTransactionIds: ['txn-test-001'],
      sourcePurchaseOrderNo: 'POTEST001',
      sourceReceiveNo: 'PRVTEST001',
      sourceInspectionNo: 'IQCTEST001',
      supplierId: 'sup-001',
      supplierName: '测试供应商',
      payableStatus: 'payableReady',
      totalPayableQty: 10,
      totalPayableAmount: 1000,
      totalPlanAmount: 1000,
      lines: [{
        id: 'ppl-test-001',
        materialId: 'mat-001',
        materialCode: 'MAT001',
        materialName: '测试物料',
        payableQty: 10,
        payablePrice: 100,
        payableAmount: 1000,
      }],
    }],
  })
  if (actionCode === 'COMPLETE_PAYABLE_CHECK') return

  modules.payableCheck.savePayableCheckState({
    payableChecks: [{
      id: 'pc-test-001',
      payableCheckNo: 'PCTEST001',
      sourcePayablePrepareId: 'pp-test-001',
      sourcePayablePrepareNo: 'PPTEST001',
      sourcePurchaseOrderNo: 'POTEST001',
      sourceReceiveNo: 'PRVTEST001',
      sourceInspectionNo: 'IQCTEST001',
      supplierId: 'sup-001',
      supplierName: '测试供应商',
      checkStatus: 'checked',
      totalPayableQty: 10,
      totalPayableAmount: 1000,
      totalCheckedQty: 10,
      totalCheckedAmount: 1000,
      amountDifference: 0,
      quantityDifference: 0,
      differenceStatus: 'none',
      lines: [],
    }],
  })
  if (actionCode === 'CREATE_SUPPLIER_SETTLEMENT') return

  modules.supplierSettlement.saveSupplierSettlementState({
    supplierSettlements: [{
      id: 'set-test-001',
      settlementNo: 'SETTEST001',
      supplierId: 'sup-001',
      supplierName: '测试供应商',
      purchaseOrderNo: 'POTEST001',
      receiveNo: 'PRVTEST001',
      inspectionNo: 'IQCTEST001',
      inventoryTransactionNos: ['TXNTEST001'],
      payablePrepareNos: ['PPTEST001'],
      purchaseAmount: 1000,
      inventoryAmount: 1000,
      payablePrepareAmount: 1000,
      settlementAmount: 1000,
      differenceAmount: 0,
      reconciliationStatus: 'matched',
      settlementStatus: 'reconciled',
      differenceType: 'none',
      differenceConfirmStatus: 'not_required',
      reconciliationConfirmStatus: 'confirmed',
      nextStepReadiness: 'ready_for_invoice_prepare',
    }],
  })
  if (actionCode === 'CREATE_PURCHASE_INVOICE_PREPARE') return

  modules.invoicePrepare.saveInvoicePrepareState({
    invoicePrepares: [{
      id: 'ip-test-001',
      invoicePrepareNo: 'IPTEST001',
      sourceSettlementId: 'set-test-001',
      sourceSettlementNo: 'SETTEST001',
      supplierId: 'sup-001',
      supplierName: '测试供应商',
      purchaseOrderNo: 'POTEST001',
      sourcePurchaseOrderNo: 'POTEST001',
      settlementAmount: 1000,
      totalInvoiceAmount: 1000,
      invoiceAmount: 884.96,
      taxAmount: 115.04,
      invoicePrepareStatus: 'payableReady',
      invoiceStatus: 'checked',
      invoiceNo: 'INVTEST001',
      invoiceDate: '2026-07-13',
      lines: [],
    }],
  })
  if (actionCode === 'CREATE_ACCOUNT_PAYABLE_DRAFT') return

  modules.apDraft.saveAccountPayableDraftState({
    accountPayableDrafts: [{
      id: 'apd-test-001',
      apDraftNo: 'APDTEST001',
      sourceInvoicePrepareId: 'ip-test-001',
      sourceInvoicePrepareNo: 'IPTEST001',
      supplierId: 'sup-001',
      supplierName: '测试供应商',
      sourcePurchaseOrderNo: 'POTEST001',
      invoiceNo: 'INVTEST001',
      invoiceDate: '2026-07-13',
      apStatus: 'draft',
      totalInvoiceAmount: 1000,
      totalPayableAmount: 1000,
      unpaidAmount: 1000,
      lines: [],
    }],
  })
  if (actionCode === 'CONFIRM_ACCOUNT_PAYABLE') return

  modules.apConfirm.saveAccountPayableConfirmState({
    accountPayableConfirms: [{
      id: 'apc-test-001',
      payableConfirmNo: 'APCTEST001',
      sourceInvoicePrepareId: 'ip-test-001',
      sourceInvoicePrepareNo: 'IPTEST001',
      sourceSettlementNo: 'SETTEST001',
      supplierId: 'sup-001',
      supplierName: '测试供应商',
      purchaseOrderNo: 'POTEST001',
      invoiceNo: 'INVTEST001',
      invoiceDate: '2026-07-13',
      invoiceAmount: 884.96,
      taxAmount: 115.04,
      totalInvoiceAmount: 1000,
      payableAmount: 1000,
      confirmedPayableAmount: 1000,
      payableStatus: 'confirmed_pending_payment',
      payableConfirmStatus: 'confirmed',
      invoiceCheckStatus: 'checked',
      paymentPlanStatus: 'not_started',
      writeOffStatus: 'not_written_off',
      ledgerStatus: 'not_written_ledger',
      postingStatus: 'not_posted',
    }],
  })
}

export async function executeSeededAction(modules, actionCode) {
  seedForAction(modules, actionCode)
  return modules.executor.executeBusinessFlowAction(actionCode)
}
