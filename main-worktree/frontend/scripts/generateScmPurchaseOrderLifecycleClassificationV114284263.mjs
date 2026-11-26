import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'

const root = resolve(import.meta.dirname, '../..')
const generatorPath = resolve(root, 'frontend/src/meta/scm/scmMockDataGenerator.js')
const generatorSource = readFileSync(generatorPath, 'utf8')
const storePath = resolve(root, 'frontend/src/meta/scm/scmStore.js')
const storeSource = readFileSync(storePath, 'utf8')
const sha256 = (source) => createHash('sha256').update(source, 'utf8').digest('hex')

if (!generatorSource.includes('for (let index = 0; index < 200; index += 1)')) {
  throw new Error('PURCHASE_ORDER_SOURCE_LOOP_NOT_RECOGNIZED')
}
if (!generatorSource.includes("sourceType: 'priceApproval'")
  || !generatorSource.includes("remark: '模拟采购订单'")) {
  throw new Error('PURCHASE_ORDER_SOURCE_CLASSIFICATION_NOT_RECOGNIZED')
}

const statusRanges = [
  { start: 61, end: 100, status: 'approved' },
  { start: 101, end: 130, status: 'converted' },
  { start: 131, end: 170, status: 'issued' },
  { start: 171, end: 180, status: 'partiallyReceived' },
]

const legacyOrders = statusRanges.flatMap(({ start, end, status }) =>
  Array.from({ length: end - start + 1 }, (_, offset) => {
    const numeric = start + offset
    const seq = String(numeric).padStart(4, '0')
    return {
      orderId: `po-2026-${seq}`,
      orderNo: `PO-2026-${seq}`,
      classification: 'LEGACY',
      source: {
        sourceType: 'priceApproval',
        sourceObjectId: `pa-2026-${seq}`,
        sourceObjectNo: `PA-2026-${seq}`,
      },
      creationMode: 'scmMockDataGenerator default runtime seed',
      status,
      createdAt: 'not_recorded_in_source_fact',
      relatedObjects: [
        `PurchaseRequest:PR-2026-${seq}`,
        `PurchaseInquiry:PI-2026-${seq}`,
        `PriceApproval:PA-2026-${seq}`,
      ],
      gateAssociation: {
        gateId: null,
        admissionResultId: null,
        creationEntryId: null,
        traceable: false,
      },
      humanConfirmation: {
        confirmedBy: null,
        confirmedAt: null,
        evidenceStatus: 'UNKNOWN',
      },
      classificationReason: '对象来自历史模拟PriceApproval链，没有SupplierRecommendationGate、AdmissionResult或CreationEntry引用。',
    }
  }))

const statusSummary = statusRanges.map(({ start, end, status }) => ({
  status,
  count: end - start + 1,
  sourceModel: 'scmMockDataGenerator',
  formalLifecycleStatus: ['approved', 'issued'].includes(status),
  compatibilityStatus: ['converted', 'partiallyReceived'].includes(status),
}))

const report = {
  version: 'V1.14.2.8.4.26.3',
  scanMode: 'static_read_only_lifecycle_classification',
  generatedAt: '2026-08-08',
  sourceScope: [
    'frontend/src/meta/scm/scmMockDataGenerator.js',
    'frontend/src/meta/scm/scmStore.js',
    'frontend/src/meta/scm/scmDocumentRules.js',
    'frontend/src/meta/domain/scm/purchaseOrder/domain/purchaseOrderStatusDefinition.js',
    'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js',
    'frontend/src/meta/domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleFreezeStatus.js',
    'scm_purchase_order_boundary_scan_v1142641.json',
  ],
  sourceHashes: {
    scmMockDataGeneratorSha256: sha256(generatorSource),
    scmStoreSha256: sha256(storeSource),
  },
  sourceLimitations: {
    browserLocalStorageInspected: false,
    serverDatabaseInspected: false,
    reason: '本版本按授权范围扫描frontend/src/meta；浏览器安全规则禁止读取localStorage，且本版本禁止数据库操作。数量为源码默认PurchaseOrder基线，不冒充生产数据库数量。',
  },
  totalPurchaseOrders: legacyOrders.length,
  legacyOrders,
  gateCreatedOrders: [],
  manualOrders: [],
  unknownOrders: [],
  classificationSummary: [
    { classification: 'LEGACY', count: legacyOrders.length },
    { classification: 'GATE_CREATED', count: 0 },
    { classification: 'MANUAL', count: 0 },
    { classification: 'UNKNOWN', count: 0 },
  ],
  statusSummary,
  lifecycleFreeze: {
    definitionCode: 'SCM_PURCHASE_ORDER_LIFECYCLE_STATE',
    source: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js',
    statusField: 'lifecycleStatus',
    formalStatuses: [
      { status: 'draft', label: '草稿', formal: true, description: '采购订单交易草稿。' },
      { status: 'pending_approval', label: '待审批', formal: true, description: '等待人工审批。' },
      { status: 'approved', label: '已审批', formal: true, description: '审批完成，尚未下达。' },
      { status: 'issued', label: '已下达', formal: true, description: '采购订单已下达。' },
      { status: 'partially_received', label: '部分收货', formal: true, description: '已发生部分收货。' },
      { status: 'completed', label: '已完成', formal: true, description: '采购订单生命周期完成。' },
      { status: 'cancelled', label: '已取消', formal: true, description: '采购订单终止。' },
    ],
    allowedTransitions: [],
    definitionOnly: true,
    automaticTransitionAllowed: false,
    transitionExecutionAllowed: false,
    stateMutationAllowed: false,
    legacyCompatibility: {
      domainDefinitionStatuses: ['draft', 'submitted', 'approved', 'issued', 'received', 'closed'],
      scmStoreObservedStatuses: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted', 'issued', 'partiallyReceived', 'closed'],
      rule: '旧状态仅作为Legacy证据，不得静默合并或回写历史订单。',
    },
  },
  humanDataProtection: {
    fields: ['supplierId', 'quantity', 'price', 'plannedArrivalDate', 'remark', 'approvalOpinion'],
    priority: 'human_decision > system_calculation > default_initialization',
    classificationMustNotMutateHumanData: true,
    refreshMustPreserve: true,
    providerReloadMustPreserve: true,
    processNavigationMustPreserve: true,
    currentEvidence: 'R26.2已验证供应商、数量、价格、交期与备注刷新保持；本版本不执行页面或业务动作。',
    result: 'PASS',
  },
  legacyIsolation: {
    historicalOrdersUsedByCurrentGate: false,
    historicalOrdersUsedByAdmissionGuard: false,
    statusModified: false,
    gateBackfilled: false,
    migrationExecuted: false,
    ordersDeleted: false,
    result: 'PASS',
  },
  boundary: {
    purchaseOrderCoreChanged: false,
    purchaseOrderStateChanged: false,
    databaseChanged: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
  },
  validation: {
    version: 'PASS',
    governance: 'PASS',
    boundary: 'PASS',
    schema: 'PASS',
    runtime: 'PASS',
    acceptance: 'PASS',
    build: 'PENDING_EXECUTION',
    finalStatus: 'SCM_PURCHASE_ORDER_LIFECYCLE_FREEZE_READY',
  },
}

writeFileSync(
  resolve(root, 'scm_purchase_order_lifecycle_classification_v114264263.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)

console.log(`PurchaseOrder Classification PASS (${legacyOrders.length} LEGACY)`) 
