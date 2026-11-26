import { listBusinessProcessSteps } from '../process/businessProcessRegistry.js'

import { listMasterDataDefinitions } from '../master-data/masterDataRegistry.js'
import { resolveBusinessName } from '../governance/businessNameRegistry.js'
import { listScmPageIdentityDefinitions } from '../schema/scm/scmPageIdentityRegistry.js'
import { createPceAdvancedFilterSchema } from './pceAdvancedFilterContract.js'
import { FORMAL_PAYMENT_ORDER_FILTER_SCHEMA } from './formalPaymentOrderRuntime.js'
import { BANK_SEND_PREPARATION_FILTER_SCHEMA } from './bankSendPreparationRuntime.js'
import { BANK_SEND_TASK_FILTER_SCHEMA } from './bankSendTaskRuntime.js'
import { BANK_SEND_EXECUTION_GATE_FILTER_SCHEMA } from './bankSendExecutionGateRuntime.js'
import { BANK_SEND_REQUEST_FILTER_SCHEMA } from './bankSendRequestRuntime.js'
import { BANK_SEND_SIMULATION_FILTER_SCHEMA } from './bankSendSimulationRuntime.js'
import {
  AUDIT_FILTER_SCHEMA,
  ISOLATION_FILTER_SCHEMA,
} from './bankSendSimulationIsolationRuntime.js'

export const PCE_BUSINESS_MODULE_REGISTRY_VERSION = 'V1.14.2.8.4.7.52.1'

function inferFilterControlType(field = '') {
  const key = String(field)
  if (/dateRange$/i.test(key)) return 'date_range'
  if (/(dateFrom|dateTo|Date)$/i.test(key)) return 'date'
  if (/(amount|quantity)(Min|Max)$/i.test(key)) return 'number_range'
  if (/^(is|has)|generated|posted|written|confirmed|cancelled/i.test(key)) return 'boolean_select'
  if (/status|result|riskLevel|currency|stage|type$/i.test(key)) return 'select'
  if (/supplier|department|warehouse|buyer|reviewer|inspector|receiver/i.test(key)) return 'searchable_select'
  if (/No$|Code$|Name$|specification/i.test(key)) return 'searchable_select'
  return 'text'
}

function buildAdvancedFilterSchema(fields = []) {
  return createPceAdvancedFilterSchema(fields)
}

const fieldConfigByStepId = {
  'procurement-request': {
    canonicalModuleId: 'purchase-request',
    pageComponent: 'src/meta/pages/ScmPurchaseRequestPage.vue',
    searchableFields: ['requestNo', 'requesterId', 'requestDepartment', 'demandDepartment', 'status'],
    advancedFilterFields: ['requestNo', 'requesterId', 'requestDepartment', 'demandDepartment', 'status'],
    primaryBusinessNoField: 'requestNo',
    operationMode: 'workflow',
  },
  'purchase-inquiry': {
    pageComponent: 'src/meta/pages/ScmPage.vue',
    searchableFields: ['inquiryNo', 'sourceOrderNo', 'buyerId', 'status'],
    advancedFilterFields: ['inquiryNo', 'sourceOrderNo', 'buyerId', 'status'],
    primaryBusinessNoField: 'inquiryNo',
    operationMode: 'workflow',
  },
  'price-approval': {
    pageComponent: 'src/meta/pages/ScmPage.vue',
    searchableFields: ['approvalNo', 'sourceOrderNo', 'rootRequestNo', 'buyerId', 'status'],
    advancedFilterFields: ['approvalNo', 'sourceOrderNo', 'rootRequestNo', 'buyerId', 'status'],
    primaryBusinessNoField: 'approvalNo',
    operationMode: 'workflow',
  },
  'purchase-order': {
    pageComponent: 'src/meta/pages/ScmPage.vue',
    searchableFields: ['poNo', 'sourceOrderNo', 'rootRequestNo', 'supplierId', 'status'],
    advancedFilterFields: ['poNo', 'sourceOrderNo', 'rootRequestNo', 'supplierId', 'status'],
    primaryBusinessNoField: 'objectNo',
    operationMode: 'workflow',
  },
  'purchase-arrival-preview': {
    canonicalName: '采购到货预备',
    showInTopModuleNavigation: false,
    showInProcessCenter: false,
    pageComponent: 'src/meta/pages/WmsPage.vue',
    searchableFields: ['poNo', 'purchaseOrderNo', 'sourcePurchaseOrderNo', 'rootRequestNo', 'supplierName', 'materialCode', 'materialName', 'warehouseName', 'statusText'],
    advancedFilterFields: ['poNo', 'purchaseOrderNo', 'rootRequestNo', 'supplierName', 'warehouseName', 'receiverName', 'status', 'plannedDateRange'],
    primaryBusinessNoField: 'poNo',
    operationMode: 'workflow',
    advancedFilterSchema: [
      { key: 'poNo', label: '采购订单号', filterControlType: 'searchable_select' },
      { key: 'rootRequestNo', label: '原始请购单号', filterControlType: 'searchable_select' },
      { key: 'requestDepartment', label: '请购部门', filterControlType: 'searchable_select' },
      { key: 'demandDepartment', label: '需求部门', filterControlType: 'searchable_select' },
      { key: 'materialNames', label: '物料名称', filterControlType: 'searchable_select' },
      { key: 'specifications', label: '规格型号', filterControlType: 'searchable_select' },
      { key: 'deliveryUrgency', label: '交期紧急程度', filterControlType: 'select' },
      { key: 'status', label: '状态', filterControlType: 'select' },
      { key: 'purchaseType', label: '采购类型', filterControlType: 'select' },
      { key: 'hasReceiveTask', label: '是否已生成仓库收货任务', filterControlType: 'boolean_select' },
      { key: 'plannedArrivalDate', label: '计划到货日期', filterControlType: 'date_range' },
    ],
  },
  'purchase-receive-preview': {
    pageComponent: 'src/meta/pages/PurchaseReceivePage.vue',
    searchableFields: ['receiveNo', 'sourceOrderNo', 'rootRequestNo', 'supplierName', 'statusText'],
    advancedFilterFields: ['receiveNo', 'sourceOrderNo', 'rootRequestNo', 'supplierName', 'status'],
    primaryBusinessNoField: 'receiveNo',
    operationMode: 'workflow',
  },
  'incoming-inspection': {
    pageComponent: 'src/meta/pages/QmsPage.vue',
    searchableFields: ['inspectionNo', 'iqcNo', 'sourceReceiveNo', 'sourcePurchaseOrderNo', 'rootRequestNo', 'supplierName', 'warehouseName', 'inspectorName', 'statusText'],
    advancedFilterFields: ['inspectionNo', 'sourcePurchaseOrderNo', 'sourceReceiveNo', 'rootRequestNo', 'supplierName', 'warehouseName', 'inspectorName', 'status', 'warehouseStatus', 'plannedDateRange', 'actualDateRange'],
    primaryBusinessNoField: 'inspectionNo',
    operationMode: 'workflow',
  },
  'payable-prepare': {
    pageComponent: 'src/meta/pages/PayablePreparePage.vue',
    searchableFields: ['sourceInventoryTransactionNo', 'payablePrepareNo', 'sourcePurchaseOrderNo', 'sourceReceiveNo', 'sourceInspectionNo', 'sourceWarehouseTaskNo', 'supplierName', 'materialCode', 'materialName', 'payableStatus', 'downstreamObjectNo'],
    advancedFilterFields: ['sourceInventoryTransactionNo', 'payablePrepareNo', 'sourcePurchaseOrderNo', 'supplierName', 'payableStatus', 'flowWritebackStatus'],
    primaryBusinessNoField: 'payablePrepareNo',
    operationMode: 'workflow',
  },
  'payable-check': {
    pageComponent: 'src/meta/pages/PayableCheckPage.vue',
    searchableFields: ['primaryBusinessNo', 'payableCheckNo', 'sourcePayablePrepareNo', 'supplierName', 'sourcePurchaseOrderNo', 'checkStatus', 'downstreamObjectNo'],
    advancedFilterFields: ['payableCheckNo', 'sourcePayablePrepareNo', 'supplierName', 'sourcePurchaseOrderNo', 'checkStatus', 'downstreamStatus', 'flowWritebackStatus', 'checkedDateFrom', 'checkedDateTo'],
    primaryBusinessNoField: 'primaryBusinessNo',
    operationMode: 'workflow',
  },
  'supplier-settlement': {
    pageComponent: 'src/meta/pages/SupplierSettlementPage.vue',
    searchableFields: ['settlementNo', 'sourcePayableCheckNo', 'sourceObjectNo', 'supplierName', 'purchaseOrderNo', 'reconciliationStatus', 'settlementStatus', 'nextStepReadiness'],
    advancedFilterFields: ['settlementNo', 'sourcePayableCheckNo', 'supplierName', 'purchaseOrderNo', 'reconciliationStatus', 'settlementStatus', 'nextStepReadiness'],
    primaryBusinessNoField: 'settlementNo',
    operationMode: 'workflow',
  },
  'purchase-reconciliation': {
    pageComponent: 'src/meta/pages/PurchaseReconciliationPage.vue',
    searchableFields: ['reconciliationNo', 'sourceSettlementNo', 'sourcePayableCheckNo', 'supplierName', 'purchaseOrderNo', 'statusText'],
    advancedFilterFields: ['reconciliationNo', 'sourceSettlementNo', 'reconciliationStatus', 'supplierName', 'purchaseOrderNo'],
    primaryBusinessNoField: 'reconciliationNo',
    operationMode: 'readonly',
  },
  'invoice-prepare': {
    pageComponent: 'src/meta/pages/InvoicePreparePage.vue',
    searchableFields: ['prepareNo', 'sourcePurchaseReconciliationNo', 'supplierName', 'status', 'invoiceDataStatus', 'transactionId'],
    advancedFilterFields: ['prepareNo', 'sourcePurchaseReconciliationNo', 'supplierName', 'status', 'invoiceDataStatus', 'transactionId'],
    primaryBusinessNoField: 'prepareNo',
    operationMode: 'workflow',
  },
  'account-payable-draft': {
    pageComponent: 'src/meta/pages/AccountPayableDraftPage.vue',
    searchableFields: ['draftNo', 'sourcePurchaseInvoicePrepareNo', 'supplierName', 'invoiceNumber', 'status'],
    advancedFilterFields: ['draftNo', 'sourcePurchaseInvoicePrepareNo', 'supplierName', 'status'],
    primaryBusinessNoField: 'draftNo',
    operationMode: 'workflow',
  },
  'account-payable-confirm': {
    pageComponent: 'src/meta/pages/AccountPayableConfirmPage.vue',
    searchableFields: ['prepareNo', 'sourceDraftNo', 'scenarioCode', 'supplierName', 'accountingPeriod', 'paymentTermsCode', 'validationStatus', 'status'],
    advancedFilterFields: ['prepareNo', 'sourceDraftNo', 'supplierName', 'status', 'scenarioCode', 'accountingPeriod', 'paymentTermsCode', 'validationStatus', 'currency'],
    primaryBusinessNoField: 'prepareNo',
    operationMode: 'workflow',
  },
  'payment-application': {
    pageComponent: 'src/meta/pages/PaymentApplicationPage.vue',
    searchableFields: ['prepareNo', 'sourcePayableConfirmationPrepareNo', 'sourceApDraftNo', 'supplierName', 'status', 'paymentDataStatus', 'validationStatus', 'scenarioCode'],
    advancedFilterFields: ['prepareNo', 'sourcePayableConfirmationPrepareNo', 'sourceApDraftNo', 'supplierName', 'status', 'paymentDataStatus', 'validationStatus', 'currency', 'scenarioCode'],
    primaryBusinessNoField: 'prepareNo',
    operationMode: 'workflow',
  },
  'payment-request': {
    pageComponent: 'src/meta/pages/PaymentRequestPage.vue',
    searchableFields: ['requestNo', 'sourcePaymentRequestPrepareNo', 'supplierName', 'status', 'approvalStatus'],
    advancedFilterFields: ['requestNo', 'sourcePaymentRequestPrepareNo', 'supplierName', 'status', 'approvalStatus', 'currency'],
    primaryBusinessNoField: 'requestNo',
    operationMode: 'workflow',
  },
  'payment-instruction-prepare': {
    pageComponent: 'src/meta/pages/PaymentInstructionPreparePage.vue',
    searchableFields: ['prepareNo', 'sourcePaymentRequestNo', 'supplierName', 'status', 'validationStatus', 'paymentRouteId'],
    advancedFilterFields: ['prepareNo', 'sourcePaymentRequestNo', 'supplierName', 'status', 'validationStatus', 'currency', 'dateRange'],
    primaryBusinessNoField: 'prepareNo',
    operationMode: 'workflow',
  },
  'payment-order-prepare': {
    pageComponent: 'src/meta/pages/PaymentOrderPreparePage.vue',
    searchableFields: ['prepareNo', 'sourcePaymentInstructionPrepareNo', 'supplierName', 'status', 'validationStatus', 'signingPolicyId'],
    advancedFilterFields: ['prepareNo', 'sourcePaymentInstructionPrepareNo', 'supplierName', 'status', 'validationStatus', 'currency'],
    primaryBusinessNoField: 'prepareNo',
    operationMode: 'workflow',
  },
  'payment-order-draft': {
    pageComponent: 'src/meta/pages/PaymentOrderDraftPage.vue',
    searchableFields: ['draftNo', 'sourcePaymentOrderPrepareNo', 'sourcePaymentRequestNo', 'supplierName', 'keyword'],
    advancedFilterFields: [
      'status', 'reviewStatus', 'reviewResultCode', 'nextStepReadiness',
      'supplierName', 'legalEntityName', 'ledgerBookId', 'currency',
      'amountMin', 'amountMax', 'executionDateFrom', 'executionDateTo',
      'payerBankAccountMasked', 'payeeBankAccountMasked', 'paymentRouteId',
      'bankInterfaceProfileId', 'signingPolicyId', 'authorizationRouteId',
      'fundsSufficient', 'signingCapabilityStatus', 'credentialStatus',
      'segregationValid', 'scenarioType', 'scenarioCode',
    ],
    primaryBusinessNoField: 'draftNo',
    operationMode: 'workflow',
  },
  'payment-risk-review': {
    pageComponent: 'src/meta/pages/PaymentExecutionRiskReviewPage.vue',
    searchableFields: ['reviewNo', 'sourcePaymentOrderDraftNo', 'supplierName', 'status'],
    advancedFilterFields: ['reviewNo', 'sourcePaymentOrderDraftNo', 'supplierName', 'status'],
    primaryBusinessNoField: 'reviewNo',
    operationMode: 'readonly',
  },
  'formal-payment-order': {
    pageComponent: 'src/meta/pages/FormalPaymentOrderPage.vue',
    searchableFields: ['orderNo', 'sourceRiskReviewNo', 'supplierName', 'legalEntity', 'ledgerBook', 'status'],
    advancedFilterFields: [
      'orderNo', 'sourceRiskReviewNo', 'supplierName', 'legalEntity',
      'ledgerBook', 'currency', 'status', 'amountMin', 'amountMax',
      'executionDateFrom', 'executionDateTo',
    ],
    advancedFilterSchema: FORMAL_PAYMENT_ORDER_FILTER_SCHEMA,
    primaryBusinessNoField: 'orderNo',
    operationMode: 'readonly',
  },
  'bank-send-preparation': {
    pageComponent: 'src/meta/pages/BankSendPreparationPage.vue',
    searchableFields: [
      'prepareNo', 'sourceFormalPaymentOrderNo', 'supplierName',
      'legalEntityId', 'currency', 'status',
    ],
    advancedFilterFields: [
      'prepareNo', 'sourceFormalPaymentOrderNo', 'supplierName',
      'legalEntityId', 'currency', 'status', 'previewStatus',
      'executionDateFrom', 'executionDateTo',
    ],
    advancedFilterSchema: BANK_SEND_PREPARATION_FILTER_SCHEMA,
    primaryBusinessNoField: 'prepareNo',
    operationMode: 'workflow',
  },
  'bank-send-task': {
    pageComponent: 'src/meta/pages/BankSendTaskPage.vue',
    searchableFields: [
      'taskNo', 'sourcePreparationNo', 'sourceFormalPaymentOrderNo',
      'supplierName', 'legalEntityId', 'currency', 'status',
    ],
    advancedFilterFields: [
      'taskNo', 'sourcePreparationNo', 'status', 'supplierName',
      'legalEntityId', 'currency', 'executionDateFrom', 'executionDateTo',
    ],
    advancedFilterSchema: BANK_SEND_TASK_FILTER_SCHEMA,
    primaryBusinessNoField: 'taskNo',
    operationMode: 'workflow',
  },
  'bank-send-execution-gate': {
    pageComponent: 'src/meta/pages/BankSendExecutionGatePage.vue',
    searchableFields: [
      'gateNo', 'bankSendTaskNo', 'formalPaymentOrderNo', 'status',
    ],
    advancedFilterFields: [
      'gateNo', 'bankSendTaskNo', 'formalPaymentOrderNo', 'status',
    ],
    advancedFilterSchema: BANK_SEND_EXECUTION_GATE_FILTER_SCHEMA,
    primaryBusinessNoField: 'gateNo',
    operationMode: 'workflow',
  },
  'bank-send-request': {
    pageComponent: 'src/meta/pages/BankSendRequestPage.vue',
    searchableFields: [
      'requestNo', 'bankSendExecutionGateNo', 'bankSendTaskNo',
      'formalPaymentOrderNo', 'status',
    ],
    advancedFilterFields: [
      'requestNo', 'bankSendExecutionGateNo', 'bankSendTaskNo', 'status',
    ],
    advancedFilterSchema: BANK_SEND_REQUEST_FILTER_SCHEMA,
    primaryBusinessNoField: 'requestNo',
    operationMode: 'workflow',
  },
  'bank-send-simulation': {
    pageComponent: 'src/meta/pages/BankSendSimulationPage.vue',
    searchableFields: [
      'simulationNo', 'bankSendRequestNo', 'status',
    ],
    advancedFilterFields: [
      'simulationNo', 'bankSendRequestNo', 'status',
    ],
    advancedFilterSchema: BANK_SEND_SIMULATION_FILTER_SCHEMA,
    primaryBusinessNoField: 'simulationNo',
    operationMode: 'workflow',
  },
  'bank-send-simulation-audit': {
    pageComponent: 'src/meta/pages/BankSendSimulationAuditPage.vue',
    searchableFields: ['auditNo', 'simulationNo', 'auditType', 'operator'],
    advancedFilterFields: ['auditNo', 'simulationNo', 'auditType', 'operator'],
    advancedFilterSchema: AUDIT_FILTER_SCHEMA,
    primaryBusinessNoField: 'auditNo',
    operationMode: 'readonly',
  },
  'bank-send-isolation-gate': {
    pageComponent: 'src/meta/pages/BankSendIsolationGatePage.vue',
    searchableFields: ['gateNo', 'status', 'tenantId', 'batchId'],
    advancedFilterFields: ['gateNo', 'status', 'tenantId', 'batchId'],
    advancedFilterSchema: ISOLATION_FILTER_SCHEMA,
    primaryBusinessNoField: 'gateNo',
    operationMode: 'readonly',
  },
  'bank-send-chain-trace': {
    pageComponent: 'src/meta/pages/BankSendChainTracePage.vue',
    searchableFields: ['traceNo', 'formalPaymentOrderNo', 'bankSendRequestNo', 'simulationNo'],
    advancedFilterFields: ['traceNo', 'formalPaymentOrderNo', 'bankSendRequestNo', 'simulationNo'],
    primaryBusinessNoField: 'traceNo',
    operationMode: 'readonly',
  },
  'bank-send-final-approval': {
    pageComponent: 'src/meta/pages/BankSendFinalApprovalPage.vue',
    searchableFields: ['approvalNo', 'traceNo', 'requestNo', 'status'],
    advancedFilterFields: ['approvalNo', 'traceNo', 'requestNo', 'status'],
    primaryBusinessNoField: 'approvalNo',
    operationMode: 'workflow',
  },
  'bank-send-dual-isolation-check': {
    pageComponent: 'src/meta/pages/BankSendDualIsolationCheckPage.vue',
    searchableFields: ['checkNo', 'traceNo', 'approvalNo', 'result'],
    advancedFilterFields: ['checkNo', 'traceNo', 'approvalNo', 'result'],
    primaryBusinessNoField: 'checkNo',
    operationMode: 'readonly',
  },
  'bank-send-production-release-review': {
    pageComponent: 'src/meta/pages/BankSendProductionReleaseReviewPage.vue',
    searchableFields: ['reviewNo', 'traceNo', 'approvalNo', 'status'],
    advancedFilterFields: ['reviewNo', 'traceNo', 'approvalNo', 'status'],
    primaryBusinessNoField: 'reviewNo',
    operationMode: 'workflow',
  },
  'bank-send-execution-framework-review': {
    pageComponent: 'src/meta/pages/BankSendExecutionFrameworkReviewPage.vue',
    searchableFields: ['frameworkNo', 'sourceReviewNo', 'environment', 'status'],
    advancedFilterFields: ['frameworkNo', 'sourceReviewNo', 'environment', 'status'],
    primaryBusinessNoField: 'frameworkNo',
    operationMode: 'readonly',
  },
  'bank-connector-adapter-review': {
    pageComponent: 'src/meta/pages/BankConnectorAdapterReviewPage.vue',
    searchableFields: ['interfaceName', 'environment', 'status', 'callMode'],
    advancedFilterFields: ['interfaceName', 'environment', 'status'],
    primaryBusinessNoField: 'interfaceName',
    operationMode: 'readonly',
  },
  'payment-execution-prepare': {
    pageComponent: 'src/meta/pages/PaymentExecutionPreparePage.vue',
    searchableFields: ['paymentExecutionPrepareNo', 'sourcePaymentOrderPrepareNo', 'sourcePaymentApplicationNo', 'sourcePayableConfirmNo', 'supplierName', 'purchaseOrderNo', 'invoiceNo', 'paymentExecutionPrepareStatus', 'paymentExecutionStatus'],
    advancedFilterFields: ['paymentExecutionPrepareNo', 'sourcePaymentOrderPrepareNo', 'sourcePaymentApplicationNo', 'sourcePayableConfirmNo', 'supplierName', 'purchaseOrderNo', 'invoiceNo', 'paymentExecutionPrepareStatus', 'paymentExecutionStatus', 'dateRange'],
    primaryBusinessNoField: 'paymentExecutionPrepareNo',
    operationMode: 'workflow',
  },
  'payment-execution': {
    pageComponent: 'src/meta/pages/PaymentExecutionPage.vue',
    searchableFields: ['paymentExecutionNo', 'sourcePaymentExecutionPrepareNo', 'supplierName', 'paymentExecutionStatus'],
    advancedFilterFields: ['paymentExecutionNo', 'sourcePaymentExecutionPrepareNo', 'supplierName', 'paymentExecutionStatus'],
    primaryBusinessNoField: 'paymentExecutionNo',
    operationMode: 'workflow',
  },
  'payment-voucher-draft': {
    pageComponent: 'src/meta/pages/PaymentVoucherDraftPage.vue',
    searchableFields: ['voucherDraftNo', 'sourcePaymentExecutionNo', 'supplierName', 'voucherDraftStatus'],
    advancedFilterFields: ['voucherDraftNo', 'sourcePaymentExecutionNo', 'supplierName', 'voucherDraftStatus'],
    primaryBusinessNoField: 'voucherDraftNo',
    operationMode: 'workflow',
  },
  'payment-voucher-review': {
    pageComponent: 'src/meta/pages/PaymentVoucherReviewPage.vue',
    searchableFields: ['voucherReviewNo', 'sourcePaymentVoucherDraftNo', 'supplierName', 'voucherReviewStatus'],
    advancedFilterFields: ['voucherReviewNo', 'sourcePaymentVoucherDraftNo', 'supplierName', 'voucherReviewStatus'],
    primaryBusinessNoField: 'voucherReviewNo',
    operationMode: 'workflow',
  },
  'payment-record-review': {
    pageComponent: 'src/meta/pages/PaymentRecordReviewPage.vue',
    searchableFields: ['paymentRecordReviewNo', 'sourcePaymentVoucherReviewNo', 'supplierName', 'recordReviewStatus'],
    advancedFilterFields: ['paymentRecordReviewNo', 'sourcePaymentVoucherReviewNo', 'supplierName', 'recordReviewStatus'],
    primaryBusinessNoField: 'paymentRecordReviewNo',
    operationMode: 'workflow',
  },
  'formal-payment-voucher': {
    pageComponent: 'src/meta/pages/FormalPaymentVoucherPage.vue',
    searchableFields: ['formalVoucherNo', 'sourcePaymentRecordReviewNo', 'supplierName', 'formalVoucherStatus'],
    advancedFilterFields: ['formalVoucherNo', 'sourcePaymentRecordReviewNo', 'supplierName', 'formalVoucherStatus'],
    primaryBusinessNoField: 'formalVoucherNo',
    operationMode: 'readonly',
  },
}

const processModules = listBusinessProcessSteps().map((step, index) => {
  const fieldConfig = fieldConfigByStepId[step.stepId] || {}
  return {
    moduleId: fieldConfig.canonicalModuleId || step.moduleId || step.stepId,
    canonicalName: fieldConfig.canonicalName || step.pageTitle || step.stepName,
    route: step.routePath,
    pageComponent: fieldConfig.pageComponent || '',
    processOrder: (index + 1) * 10,
    processCenterOrder: (index + 1) * 10,
    showInTopModuleNavigation: fieldConfig.showInTopModuleNavigation ?? true,
    showInProcessCenter: fieldConfig.showInProcessCenter ?? true,
    pageType: 'business_list',
    searchableFields: fieldConfig.searchableFields || [],
    advancedFilterFields: fieldConfig.advancedFilterFields || [],
    advancedFilterSchema: createPceAdvancedFilterSchema(
      fieldConfig.advancedFilterSchema || fieldConfig.advancedFilterFields || [],
    ),
    primaryBusinessNoField: fieldConfig.primaryBusinessNoField || '',
    operationMode: fieldConfig.operationMode || 'workflow',
    quickSearchVisibleByDefault: true,
    operationRequired: true,
    horizontalScrollMode: 'element_plus_native',
    exportSelectedEnabled: true,
    exportCurrentResultEnabled: true,
    moduleCode: step.moduleCode,
    moduleName: step.moduleName,
  }
})

const supplementalModules = [
  ...listScmPageIdentityDefinitions()
    .filter((definition) => definition.pageCode === 'purchase-request'
      || definition.pageCode === 'purchase-order-create'
      || definition.pageCode.startsWith('purchase-inquiry'))
    .map((definition) => ({
      moduleId: definition.pageCode,
      canonicalName: definition.pageName,
      route: definition.route,
      pageComponent: ({
        'purchase-request': 'src/meta/pages/ScmPurchaseRequestPage.vue',
        'purchase-order-create': 'src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue',
        'purchase-inquiry': 'src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue',
        'purchase-inquiry-detail': 'src/meta/pages/ScmPurchaseInquiryDetailPage.vue',
        'purchase-inquiry-edit': 'src/meta/pages/ScmPurchaseInquiryEditPage.vue',
        'purchase-inquiry-acceptance': 'src/meta/pages/ScmPurchaseInquiryAcceptancePage.vue',
      })[definition.pageCode] || 'src/meta/pages/ScmPage.vue',
      processOrder: processModules.length * 10 + 1,
      processCenterOrder: processModules.length * 10 + 1,
      showInTopModuleNavigation: false,
      showInProcessCenter: false,
      pageType: definition.pageType,
      searchableFields: (definition.pageCode === 'purchase-request'
        ? fieldConfigByStepId['procurement-request']
        : fieldConfigByStepId[definition.pageCode])?.searchableFields || [],
      advancedFilterFields: (definition.pageCode === 'purchase-request'
        ? fieldConfigByStepId['procurement-request']
        : fieldConfigByStepId[definition.pageCode])?.advancedFilterFields || [],
      advancedFilterSchema: buildAdvancedFilterSchema((definition.pageCode === 'purchase-request'
        ? fieldConfigByStepId['procurement-request']
        : fieldConfigByStepId[definition.pageCode])?.advancedFilterFields || []),
      primaryBusinessNoField: (definition.pageCode === 'purchase-request'
        ? fieldConfigByStepId['procurement-request']
        : fieldConfigByStepId[definition.pageCode])?.primaryBusinessNoField || 'poNo',
      operationMode: (definition.pageCode === 'purchase-request'
        ? fieldConfigByStepId['procurement-request']
        : fieldConfigByStepId[definition.pageCode])?.operationMode || 'source_governed_create',
      moduleCode: definition.moduleCode,
      moduleName: '供应链管理',
      tableId: definition.tableId,
      schema: definition.schema,
    })),
  ...listMasterDataDefinitions().map((definition, index) => ({
    moduleId: definition.pageCode,
    canonicalName: definition.title,
    route: definition.pageUrl,
    pageComponent: 'src/meta/pages/EnterpriseMasterDataPage.vue',
    processOrder: (processModules.length + 10 + index) * 10,
    processCenterOrder: (processModules.length + 10 + index) * 10,
    showInTopModuleNavigation: false,
    showInProcessCenter: true,
    pageType: 'business_list',
    searchableFields: definition.searchFields,
    advancedFilterFields: definition.filterSchema.map(field => field.field),
    advancedFilterSchema: definition.filterSchema.map(field => ({
      key: field.field,
      field: field.field,
      label: field.label,
      filterControlType: field.filterType === 'daterange'
        ? 'date_range'
        : field.filterType === 'numberRange' ? 'number_range' : field.filterType,
      options: field.options,
    })),
    primaryBusinessNoField: definition.primaryField,
    operationMode: 'readonly',
    moduleCode: 'EMD',
    moduleName: '企业主数据中心',
  })),
  ...[
    ['supplier-reconciliation', '供应商对账', '/scm/supplier-reconciliations', ['reconciliationNo', 'supplierName', 'period', 'statusCode'], 'reconciliationNo'],
    ['supplier-performance', '供应商绩效', '/scm/supplier-performance', ['supplierName', 'period'], 'supplierName'],
    ['buyer-performance', '采购员绩效', '/scm/buyer-performance', ['buyerName', 'period'], 'buyerName'],
    ['supplier-reconciliation-differences', '供应商对账差异分析', '/scm/supplier-reconciliation-differences', ['supplierName', 'differenceType', 'responsibilityType', 'statusCode', 'occurredAt'], 'differenceNo'],
    ['supplier-reconciliation-confirmations', '供应商协同确认', '/scm/supplier-reconciliation-confirmations', ['supplierName', 'supplierResponse', 'statusCode', 'confirmedAt'], 'confirmationNo'],
    ['buyer-exception-analysis', '采购异常责任分析', '/scm/buyer-exception-analysis', ['buyerName', 'period'], 'buyerName'],
    ['supplier-payment-status', '供应商付款状态记录', '/scm/supplier-payment-status', ['paymentRequestNo', 'supplierName', 'paymentStatus', 'operator'], 'paymentRequestNo'],
    ['supplier-settlement-completion', '供应商结算完成确认', '/scm/supplier-settlement-completions', ['supplierName', 'reconciliationNo', 'paymentRequestNo', 'completionStatus'], 'settlementNo'],
  ].map(([moduleId, canonicalName, route, fields, primaryBusinessNoField], index) => ({
    moduleId, canonicalName, route,
    pageComponent: moduleId.includes('differences') || moduleId.includes('confirmations') || moduleId === 'buyer-exception-analysis'
      ? 'src/meta/pages/SupplierReconciliationV82Page.vue'
      : 'src/meta/pages/SupplierPerformanceBasePage.vue',
    processOrder: (processModules.length + 20 + index) * 10,
    processCenterOrder: (processModules.length + 20 + index) * 10,
    showInTopModuleNavigation: true, showInProcessCenter: true,
    pageType: 'business_list', searchableFields: fields, advancedFilterFields: fields,
    advancedFilterSchema: buildAdvancedFilterSchema(fields),
    primaryBusinessNoField, operationMode: 'readonly',
    moduleCode: 'SCM', moduleName: '供应链管理',
  })),
  {
    moduleId: 'inventory-balances',
    route: '/wms/inventory-balances',
    pageComponent: 'src/meta/pages/WmsPage.vue',
    processOrder: (processModules.length + 1) * 10,
    processCenterOrder: (processModules.length + 1) * 10,
    showInTopModuleNavigation: true,
    showInProcessCenter: true,
    pageType: 'business_list',
    searchableFields: ['materialCode', 'materialName', 'warehouseName', 'locationName', 'batchNo', 'status'],
    advancedFilterFields: ['materialCode', 'materialName', 'specification', 'unit', 'warehouseName', 'locationName', 'batchNo', 'qualityStatus', 'quantity', 'availableQuantity', 'lockedQuantity', 'safetyStock', 'maxStock', 'sourceInspectionNo', 'sourceReceiveNo', 'sourcePurchaseOrderNo', 'rootRequestNo', 'status', 'lastTransactionAt'],
    advancedFilterSchema: [
      ...['materialCode', 'materialName', 'specification', 'unit', 'warehouseName', 'locationName', 'batchNo', 'sourceInspectionNo', 'sourceReceiveNo', 'sourcePurchaseOrderNo', 'rootRequestNo'].map((field) => ({ field, key: field, label: field, filterControlType: 'searchable_select', optionSource: 'current_result_distinct_values', clearable: true, searchable: true })),
      ...['qualityStatus', 'status'].map((field) => ({ field, key: field, label: field, filterControlType: 'select', optionSource: 'current_result_distinct_values', clearable: true, searchable: false })),
      ...['quantity', 'availableQuantity', 'lockedQuantity', 'safetyStock', 'maxStock'].map((field) => ({ field, key: field, label: field, filterControlType: 'number_range', optionSource: 'current_result_values', clearable: true, searchable: false, filterSpan: 2 })),
      { field: 'lastTransactionAt', key: 'lastTransactionAt', label: 'lastTransactionAt', filterControlType: 'date_range', optionSource: 'current_result_values', clearable: true, searchable: false, filterSpan: 2 },
    ],
    primaryBusinessNoField: 'materialCode',
    operationMode: 'workflow',
    moduleCode: 'WMS',
    moduleName: '仓库管理',
  },
  {
    moduleId: 'supplier-payment-draft',
    canonicalName: '供应商付款草稿',
    route: '/finance/payment-drafts',
    pageComponent: 'src/meta/pages/SupplierPaymentDraftPage.vue',
    processOrder: (processModules.length + 2) * 10,
    processCenterOrder: (processModules.length + 2) * 10,
    showInTopModuleNavigation: true,
    showInProcessCenter: true,
    pageType: 'business_list',
    searchableFields: ['paymentDraftNo', 'sourceApDraftNo', 'supplierName', 'sourcePurchaseOrderNo', 'paymentDraftStatus'],
    advancedFilterFields: ['paymentDraftNo', 'sourceApDraftNo', 'supplierName', 'sourcePurchaseOrderNo', 'paymentDraftStatus'],
    advancedFilterSchema: buildAdvancedFilterSchema(['paymentDraftNo', 'sourceApDraftNo', 'supplierName', 'sourcePurchaseOrderNo', 'paymentDraftStatus']),
    primaryBusinessNoField: 'paymentDraftNo',
    operationMode: 'workflow',
    moduleCode: 'FIN',
    moduleName: '璐㈠姟绠＄悊',
  },
]

const consolidatedModules = [...processModules]
for (const supplemental of supplementalModules) {
  const index = consolidatedModules.findIndex(module => module.moduleId === supplemental.moduleId)
  if (index < 0) {
    consolidatedModules.push(supplemental)
    continue
  }
  const processModule = consolidatedModules[index]
  // A shared page code may govern two real route surfaces (for example the
  // purchase-inquiry list and workbench). Preserve both route contracts while
  // still collapsing exact duplicate registrations.
  if (processModule.route !== supplemental.route) {
    consolidatedModules.push(supplemental)
    continue
  }
  consolidatedModules[index] = {
    ...processModule,
    ...supplemental,
    processOrder: processModule.processOrder,
    processCenterOrder: processModule.processCenterOrder,
    showInTopModuleNavigation: processModule.showInTopModuleNavigation,
    showInProcessCenter: processModule.showInProcessCenter,
  }
}

export const pceBusinessModules = consolidatedModules
  .map((module) => {
    const governedName = resolveBusinessName({ pageCode: module.moduleId })
    return governedName ? {
      ...module,
      canonicalName: governedName.pageName,
      route: governedName.route,
      businessObject: governedName.businessObject,
      nameSource: 'BusinessNameRegistry',
    } : module
  })
  .sort((left, right) => left.processOrder - right.processOrder || left.moduleId.localeCompare(right.moduleId))

export function listPceBusinessModules() {
  return pceBusinessModules.map((item) => ({
    ...item,
    searchableFields: [...item.searchableFields],
    advancedFilterFields: [...item.advancedFilterFields],
    advancedFilterSchema: (item.advancedFilterSchema || []).map((field) => ({ ...field })),
  }))
}

export function listPceProcessNavigationModules() {
  return listPceBusinessModules().filter((item) => item.showInTopModuleNavigation && item.showInProcessCenter)
}

export function findPceBusinessModuleByRoute(routePath = '') {
  const normalized = String(routePath || '').split('?')[0]
  const matchesTemplate = (template = '') => {
    const expected = String(template).split('/').filter(Boolean)
    const actual = normalized.split('/').filter(Boolean)
    return expected.length === actual.length && expected.every((segment, index) =>
      segment.startsWith(':') || segment === actual[index])
  }
  const exact = pceBusinessModules
    .filter((item) => normalized === item.route || matchesTemplate(item.route))
    .sort((left, right) => right.route.length - left.route.length)[0]
  if (exact) return exact
  return pceBusinessModules
    .filter((item) => normalized.startsWith(`${item.route}/`))
    .sort((left, right) => right.route.length - left.route.length)[0] || null
}

export function findPceBusinessModuleById(moduleId = '') {
  return pceBusinessModules.find((item) => item.moduleId === moduleId) || null
}

export function findPceBusinessModuleByComponent(pageComponent = '') {
  return pceBusinessModules.find((item) => item.pageComponent === pageComponent) || null
}

export function resolvePceCanonicalName(routeOrModuleId = '') {
  const value = String(routeOrModuleId || '')
  return (value.startsWith('/') ? findPceBusinessModuleByRoute(value) : findPceBusinessModuleById(value))?.canonicalName || ''
}

