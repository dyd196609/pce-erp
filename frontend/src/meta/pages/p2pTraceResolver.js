function hasText(value) {
  return String(value || '').trim().length > 0
}

function asList(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '').split(/[、,，;]/).map((item) => item.trim()).filter(Boolean)
}

function firstText(...values) {
  return values.find((value) => hasText(value)) || ''
}

function inventoryTransactionNos(data = {}) {
  const fromRecords = (data.inventoryTransactions || []).map((item) => item.transactionNo || item.id || item.no).filter(Boolean)
  return [
    ...asList(data.inventoryTransactionNos),
    ...asList(data.inventoryTransaction),
    ...fromRecords,
  ].filter(Boolean)
}

export function resolveP2PNodeStatus(node, data = {}) {
  const inventoryNos = inventoryTransactionNos(data)
  const warehouseEntryNo = firstText(data.warehouseEntryNo, data.warehouseEntry)
  const nodeMap = {
    purchaseOrder: {
      title: '采购订单',
      sourceNo: firstText(data.purchaseOrderNo, data.purchaseOrder?.poNo, data.purchaseOrder?.purchaseOrderNo, data.purchaseOrder?.orderNo, data.purchaseOrder),
      normalEvidence: '存在来源采购订单。',
    },
    receipt: {
      title: '收货',
      sourceNo: firstText(data.receiveNo, data.receipt?.receiveNo, data.receipt),
      normalEvidence: '存在采购收货记录。',
    },
    inspection: {
      title: '检验',
      sourceNo: firstText(data.inspectionNo, data.inspection?.inspectionNo, data.inspection),
      normalEvidence: '存在来源检验记录。',
    },
    payable: {
      title: '应付',
      sourceNo: firstText(data.payableNo, data.payable),
      normalEvidence: '存在应付来源记录。',
    },
    payment: {
      title: '付款',
      sourceNo: firstText(data.paymentVoucherNo, data.paymentVoucher),
      normalEvidence: '存在付款凭证或付款记录。',
    },
  }

  if (node === 'warehouseEntry') {
    if (hasText(warehouseEntryNo)) {
      return {
        node,
        title: '入库',
        status: 'normal',
        statusText: '正常',
        tagType: 'success',
        source: 'warehouseEntry',
        sourceNo: warehouseEntryNo,
        evidence: '存在独立入库单。',
      }
    }
    if (inventoryNos.length) {
      return {
        node,
        title: '入库',
        status: 'normal',
        statusText: '正常',
        tagType: 'success',
        source: 'inventoryTransaction',
        sourceNo: inventoryNos.join('、'),
        evidence: '存在库存流水，库存流水可代表入库完成。',
      }
    }
    return {
      node,
      title: '入库',
      status: 'abnormal',
      statusText: '异常',
      tagType: 'danger',
      source: 'missing',
      sourceNo: '',
      evidence: '未发现独立入库单，也未发现库存流水。',
    }
  }

  if (node === 'inventoryTransaction') {
    return inventoryNos.length
      ? {
          node,
          title: '库存流水',
          status: 'normal',
          statusText: '正常',
          tagType: 'success',
          source: 'inventoryTransaction',
          sourceNo: inventoryNos.join('、'),
          evidence: '存在库存流水。',
        }
      : {
          node,
          title: '库存流水',
          status: 'missing',
          statusText: '缺失',
          tagType: 'danger',
          source: 'missing',
          sourceNo: '',
          evidence: '未发现库存流水。',
        }
  }

  const config = nodeMap[node] || { title: node, sourceNo: '', normalEvidence: '存在来源记录。' }
  return hasText(config.sourceNo)
    ? {
        node,
        title: config.title,
        status: 'normal',
        statusText: '正常',
        tagType: 'success',
        source: node,
        sourceNo: config.sourceNo,
        evidence: config.normalEvidence,
      }
    : {
        node,
        title: config.title,
        status: 'missing',
        statusText: '缺失',
        tagType: 'danger',
        source: 'missing',
        sourceNo: '',
        evidence: `未发现${config.title}来源。`,
      }
}

export function resolveP2PTraceNodeStatuses(data = {}) {
  return ['purchaseOrder', 'receipt', 'inspection', 'warehouseEntry', 'inventoryTransaction', 'payable', 'payment']
    .map((node) => resolveP2PNodeStatus(node, data))
}
