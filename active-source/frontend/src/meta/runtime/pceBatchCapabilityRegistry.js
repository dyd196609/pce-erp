export const PCE_BATCH_CAPABILITY_REGISTRY_VERSION = 'V1.14.2.8.4.7.31'

const contracts = [
  {
    pageId: 'purchase-receive',
    canonicalName: '采购收货预备',
    route: '/wms/purchase-receives',
    pageComponent: 'src/meta/pages/PurchaseReceivePage.vue',
    tableId: 'purchase-receive-preview-main',
    sectionId: 'purchase-receive-batch-actions',
    actionIds: ['submit-purchase-receives', 'create-incoming-inspections'],
    legacyFingerprint: {
      reportedPageId: 'purchase-receive-preview',
      reportedRoute: '/wms/purchase-receive-preview',
      baselineCount: 74,
      currentCount: 71,
      classification: ['non_batch_control_overcount', 'selector_or_section_mismatch', 'intentional_standardization'],
      reason: '旧基线扫描的是共享WmsPage源码关键字总数，并非采购收货预备页面的唯一批量业务动作。',
    },
  },
  {
    pageId: 'purchase-receive-preview',
    canonicalName: '采购到货预备',
    route: '/wms/purchase-receive-preview',
    pageComponent: 'src/meta/pages/WmsPage.vue',
    tableId: 'purchase-receive-preview-main',
    sectionId: 'purchase-receive-preview-batch-actions',
    actionIds: ['create-warehouse-receive-tasks', 'create-purchase-receive-prepares'],
    includeInThreePageReport: false,
    legacyFingerprint: {
      reportedPageId: 'purchase-receive-preview',
      reportedRoute: '/wms/purchase-receive-preview',
      baselineCount: 74,
      currentCount: 71,
      classification: ['non_batch_control_overcount', 'intentional_standardization'],
      reason: '旧基线按WmsPage源码中的batch/Batch/批量文本次数统计，包含脚本、提示和样式。',
    },
  },
  {
    pageId: 'incoming-inspection',
    canonicalName: '来料检验',
    route: '/qms/incoming-inspections',
    pageComponent: 'src/meta/pages/QmsPage.vue',
    tableId: 'incoming-inspections-main',
    sectionId: 'incoming-inspection-batch-actions',
    actionIds: ['start-incoming-inspections', 'submit-incoming-inspection-results', 'create-qualified-inbound-prepares'],
    legacyFingerprint: {
      reportedPageId: 'incoming-inspection',
      reportedRoute: '/qms/incoming-inspections',
      baselineCount: 83,
      currentCount: 73,
      classification: ['non_batch_control_overcount', 'intentional_standardization'],
      reason: '旧基线把变量、函数、提示、结果面板、CSS和同一按钮的多次关键字命中全部计入。',
    },
  },
  {
    pageId: 'inventory-balances',
    canonicalName: '库存余额',
    route: '/wms/inventory-balances',
    pageComponent: 'src/meta/pages/WmsPage.vue',
    tableId: 'wms-balances-main',
    sectionId: 'wms-balances-batch-actions',
    actionIds: [],
    legacyFingerprint: {
      reportedPageId: 'inventory-balances',
      reportedRoute: '/wms/inventory-balances',
      baselineCount: 74,
      currentCount: 71,
      classification: ['selector_or_section_mismatch', 'non_batch_control_overcount'],
      reason: '库存余额运行时无批量业务动作；旧扫描器却复用了WmsPage内其他路由的全部batch文本。',
    },
  },
]

export function listPceBatchCapabilityContracts({ includeInternal = true } = {}) {
  return contracts
    .filter((item) => includeInternal || item.includeInThreePageReport !== false)
    .map((item) => ({
      ...item,
      actionIds: [...item.actionIds],
      legacyFingerprint: {
        ...item.legacyFingerprint,
        classification: [...item.legacyFingerprint.classification],
      },
    }))
}

export function getPceBatchCapabilityContract(pageId = '') {
  return listPceBatchCapabilityContracts().find((item) => item.pageId === pageId) || null
}
