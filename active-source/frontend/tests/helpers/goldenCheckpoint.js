import crypto from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'

export const CHECKPOINT_VERSION = '1.0.0'
export const FLOW_VERSION = 'V1.14.2.8.4.7.23'
export const CHECKPOINT_ROOT = path.resolve(process.cwd(), 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
export const REQUIRED_CHECKPOINT_FILES = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
  'restore-verification.json',
  'checkpoint-screenshot.png',
  'trace.zip',
]

const INTEGRITY_FILES = [
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]

function stable(value) {
  if (Array.isArray(value)) return value.map(stable)
  if (!value || typeof value !== 'object') return value
  return Object.keys(value).sort().reduce((result, key) => {
    result[key] = stable(value[key])
    return result
  }, {})
}

async function writeJson(filePath, value) {
  await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, 'utf8'))
}

function byIdOrNo(list = [], id, no, noField) {
  return list.find((item) => String(item.id) === String(id))
    || list.find((item) => String(item[noField]) === String(no))
    || null
}

function entityIds(entities) {
  return [
    entities.purchaseRequestNo,
    entities.inquiryNo,
    entities.priceApprovalNo,
    entities.purchaseOrderNo,
    entities.purchaseReceiveNo,
    entities.incomingInspectionNo,
    entities.qualifiedInboundNo,
    entities.inventoryTransactionNo,
    entities.payablePrepareNo,
    entities.payableCheckNo,
    entities.supplierSettlementNo,
  ].filter(Boolean)
}

export async function captureApplicationState(page) {
  return page.evaluate(async () => {
    const local = Object.fromEntries(Array.from({ length: localStorage.length }, (_, index) => {
      const key = localStorage.key(index)
      return [key, localStorage.getItem(key)]
    }))
    const session = Object.fromEntries(Array.from({ length: sessionStorage.length }, (_, index) => {
      const key = sessionStorage.key(index)
      return [key, sessionStorage.getItem(key)]
    }))
    const databases = typeof indexedDB?.databases === 'function'
      ? await indexedDB.databases().then((items) => items.map((item) => ({ name: item.name, version: item.version })))
      : []
    return {
      capturedAt: new Date().toISOString(),
      origin: location.origin,
      storageTypes: {
        localStorage: Object.keys(local).length > 0,
        sessionStorage: Object.keys(session).length > 0,
        indexedDB: databases.length > 0,
        piniaMemoryOnly: false,
      },
      localStorage: local,
      sessionStorage: session,
      indexedDB: databases,
      procurementStorageKeys: Object.keys(local).filter((key) => ['scm-state-v1', 'wms-state-v1', 'wms-purchase-receive-state-v1', 'qms-state-v1'].includes(key)),
      unrelatedStorageKeys: Object.keys(local).filter((key) => !['scm-state-v1', 'wms-state-v1', 'wms-purchase-receive-state-v1', 'qms-state-v1'].includes(key)),
      scmState: JSON.parse(local['scm-state-v1'] || '{}'),
      wmsState: JSON.parse(local['wms-state-v1'] || '{}'),
      purchaseReceiveState: JSON.parse(local['wms-purchase-receive-state-v1'] || '{}'),
      qmsState: JSON.parse(local['qms-state-v1'] || '{}'),
      payablePrepareState: JSON.parse(local['payable-prepare-state-v1'] || '{}'),
      payableCheckState: JSON.parse(local['payable-check-state-v1'] || '{}'),
      supplierSettlementState: JSON.parse(local['supplier-settlement-state-v1'] || '{}'),
    }
  })
}

export function buildBusinessEntities(applicationState, sourceObjects = {}) {
  const state = applicationState.scmState || {}
  const request = byIdOrNo(state.purchaseRequests, sourceObjects.requestId, sourceObjects.requestNo, 'requestNo')
  const inquiry = byIdOrNo(state.purchaseInquiries, sourceObjects.inquiryId, sourceObjects.inquiryNo, 'inquiryNo')
  const approval = byIdOrNo(state.priceApprovals, sourceObjects.approvalId, sourceObjects.approvalNo, 'approvalNo')
  const order = byIdOrNo(state.purchaseOrders, sourceObjects.purchaseOrderId, sourceObjects.purchaseOrderNo, 'poNo')
  const requestItem = state.purchaseRequestItems?.find((item) => String(item.requestId) === String(request?.id)) || null
  const inquiryItem = state.purchaseInquiryItems?.find((item) => String(item.inquiryId) === String(inquiry?.id)) || null
  const approvalItem = state.priceApprovalItems?.find((item) => String(item.approvalId) === String(approval?.id)) || null
  const orderItem = state.purchaseOrderItems?.find((item) => String(item.poId) === String(order?.id)) || null
  const purchaseReceiveState = applicationState.purchaseReceiveState || {}
  const purchaseReceive = byIdOrNo(
    purchaseReceiveState.purchaseReceives || [],
    sourceObjects.purchaseReceiveId,
    sourceObjects.purchaseReceiveNo,
    'receiveNo',
  ) || (purchaseReceiveState.purchaseReceives || []).find((item) => (
    item.sourceType === 'scmPurchaseOrder'
    && String(item.sourceOrderId) === String(order?.id)
    && item.status !== 'cancelled'
  )) || null
  const qmsState = applicationState.qmsState || {}
  const incomingInspection = byIdOrNo(
    qmsState.incomingInspections || [],
    sourceObjects.incomingInspectionId,
    sourceObjects.incomingInspectionNo,
    'inspectionNo',
  ) || (qmsState.incomingInspections || []).find((item) => (
    String(item.sourceReceiveId) === String(purchaseReceive?.id)
    && item.status !== 'cancelled'
  )) || null
  const wmsState = applicationState.wmsState || {}
  const qualifiedInbound = byIdOrNo(
    wmsState.warehouseTasks || [],
    sourceObjects.qualifiedInboundId || sourceObjects.warehouseTaskId,
    sourceObjects.qualifiedInboundNo || sourceObjects.warehouseTaskNo,
    'taskNo',
  ) || (wmsState.warehouseTasks || []).find((item) => (
    item.businessType === 'qualifiedInboundPrepare'
    && String(item.sourceInspectionId || item.sourceId) === String(incomingInspection?.id)
    && item.status !== 'cancelled'
  )) || null
  const inventoryTransaction = byIdOrNo(
    wmsState.inventoryTransactions || [],
    sourceObjects.inventoryTransactionId,
    sourceObjects.inventoryTransactionNo,
    'transactionNo',
  ) || (wmsState.inventoryTransactions || []).find((item) => (
    String(item.sourceWarehouseTaskId || '') === String(qualifiedInbound?.id)
    && item.transactionType === 'purchaseInspectionIn'
  )) || null
  const payablePrepareState = applicationState.payablePrepareState
    || JSON.parse(applicationState.localStorage?.['payable-prepare-state-v1'] || '{}')
  const payablePrepare = byIdOrNo(
    payablePrepareState.payablePrepares || [],
    sourceObjects.payablePrepareId,
    sourceObjects.payablePrepareNo,
    'payablePrepareNo',
  ) || (payablePrepareState.payablePrepares || []).find((item) => (
    (item.sourceInventoryTransactionIds || []).some((id) => String(id) === String(inventoryTransaction?.id))
    || String(item.sourceInventoryTransactionId || '') === String(inventoryTransaction?.id)
    || (item.lines || []).some((line) => String(line.sourceInventoryTransactionId || '') === String(inventoryTransaction?.id))
  )) || null
  const payableCheckState = applicationState.payableCheckState
    || JSON.parse(applicationState.localStorage?.['payable-check-state-v1'] || '{}')
  const payableCheck = byIdOrNo(
    payableCheckState.payableChecks || [],
    sourceObjects.payableCheckId,
    sourceObjects.payableCheckNo,
    'payableCheckNo',
  ) || (payableCheckState.payableChecks || []).find((item) => (
    String(item.sourcePayablePrepareId || '') === String(payablePrepare?.id || '')
  )) || null
  const supplierSettlementState = applicationState.supplierSettlementState
    || JSON.parse(applicationState.localStorage?.['supplier-settlement-state-v1'] || '{}')
  const supplierSettlement = byIdOrNo(
    supplierSettlementState.supplierSettlements || [],
    sourceObjects.supplierSettlementId,
    sourceObjects.supplierSettlementNo,
    'settlementNo',
  ) || (supplierSettlementState.supplierSettlements || []).find((item) => (
    String(item.sourcePayableCheckId || '') === String(payableCheck?.id || '')
    || String(item.sourcePayableCheckNo || item.sourceObjectNo || '') === String(payableCheck?.payableCheckNo || '')
  )) || null
  const sourceLine = orderItem || approvalItem || inquiryItem || requestItem || {}
  const supplierSource = order || approval || sourceLine

  return {
    purchaseRequestNo: request?.requestNo || '',
    inquiryNo: inquiry?.inquiryNo || '',
    priceApprovalNo: approval?.approvalNo || '',
    purchaseOrderNo: order?.poNo || '',
    supplierId: supplierSource?.supplierId || sourceLine.suggestedSupplierId || '',
    supplierName: supplierSource?.supplierName || sourceLine.supplierName || '',
    materialCode: sourceLine.materialCode || sourceLine.materialId || '',
    materialName: sourceLine.materialName || '',
    quantity: Number(sourceLine.quantity || 0),
    unit: sourceLine.unit || '',
    requiredDate: requestItem?.requiredDate || requestItem?.expectedDeliveryDate || '',
    plannedDeliveryDate: orderItem?.planDeliveryDate || order?.planDeliveryDate || order?.plannedArrivalDate || '',
    purchaseOrderStatus: order?.status || '',
    arrivalContext: sourceObjects.arrivalContext || null,
    purchaseReceiveNo: purchaseReceive?.receiveNo || '',
    purchaseReceiveStatus: purchaseReceive?.status || '',
    receiveReadyContext: sourceObjects.receiveReadyContext || null,
    incomingInspectionNo: incomingInspection?.inspectionNo || '',
    incomingInspectionStatus: incomingInspection?.status || '',
    incomingInspectionReadyContext: sourceObjects.incomingInspectionReadyContext || null,
    qualifiedInboundId: qualifiedInbound?.id || '',
    qualifiedInboundNo: qualifiedInbound?.taskNo || '',
    qualifiedInboundStatus: qualifiedInbound?.status || '',
    qualifiedInboundReadyContext: sourceObjects.qualifiedInboundReadyContext || null,
    qualifiedInboundCompletedContext: sourceObjects.qualifiedInboundCompletedContext || null,
    inventoryTransactionId: inventoryTransaction?.id || '',
    inventoryTransactionNo: inventoryTransaction?.transactionNo || '',
    inventoryTransactionType: inventoryTransaction?.transactionType || '',
    payablePrepareId: payablePrepare?.id || '',
    payablePrepareNo: payablePrepare?.payablePrepareNo || '',
    payablePrepareStatus: payablePrepare?.payableStatus || '',
    payableQuantity: Number(payablePrepare?.totalPayableQty || 0),
    payableAmount: Number(payablePrepare?.totalPayableAmount || 0),
    payablePrepared: Boolean(payablePrepare?.id),
    payableCheckId: payableCheck?.id || '',
    payableCheckNo: payableCheck?.payableCheckNo || '',
    payableCheckStatus: payableCheck?.checkStatus || '',
    checkedAmount: Number(payableCheck?.totalCheckedAmount || 0),
    differenceAmount: Number(payableCheck?.amountDifference || 0),
    payableChecked: Boolean(payableCheck?.id && ['checked', 'matched', 'invoicePrepareReady', 'invoicePrepared'].includes(payableCheck.checkStatus)),
    payableCheckGenerated: Boolean(payableCheck?.id),
    supplierSettlementId: supplierSettlement?.id || '',
    supplierSettlementNo: supplierSettlement?.settlementNo || '',
    supplierSettlementStatus: supplierSettlement?.settlementStatus || '',
    settlementQuantity: Number(supplierSettlement?.settlementQuantity || 0),
    settlementAmount: Number(supplierSettlement?.settlementAmount || 0),
    supplierSettlementGenerated: Boolean(supplierSettlement?.id || sourceObjects.supplierSettlementGenerated),
    purchaseReconciliationGenerated: Boolean(sourceObjects.purchaseReconciliationGenerated),
    paymentGenerated: Boolean(sourceObjects.paymentGenerated),
    payablePreparedContext: sourceObjects.payablePreparedContext || null,
    internalIds: {
      purchaseRequestId: request?.id || '',
      inquiryId: inquiry?.id || '',
      priceApprovalId: approval?.id || '',
      purchaseOrderId: order?.id || '',
      purchaseReceiveId: purchaseReceive?.id || '',
      incomingInspectionId: incomingInspection?.id || '',
      qualifiedInboundId: qualifiedInbound?.id || '',
      inventoryTransactionId: inventoryTransaction?.id || '',
      payablePrepareId: payablePrepare?.id || '',
      payableCheckId: payableCheck?.id || '',
      supplierSettlementId: supplierSettlement?.id || '',
    },
    records: { request, requestItem, inquiry, inquiryItem, approval, approvalItem, order, orderItem, purchaseReceive, incomingInspection, qualifiedInbound, inventoryTransaction, payablePrepare, payableCheck, supplierSettlement },
  }
}

function relation(source, target, sourceType, targetType, sourceNoField, targetNoField) {
  if (!source || !target) return null
  const forwardMatched = String(source.targetOrderId || '') === String(target.id)
    && String(source.targetOrderNo || '') === String(target[targetNoField])
  const backwardMatched = String(target.sourceOrderId || target.sourceId || '') === String(source.id)
    && String(target.sourceOrderNo || '') === String(source[sourceNoField])
  return {
    relation: `${sourceType} -> ${targetType}`,
    sourceType,
    sourceId: source.id,
    sourceNo: source[sourceNoField],
    targetType,
    targetId: target.id,
    targetNo: target[targetNoField],
    sourceFields: ['targetModule', 'targetOrderId', 'targetOrderNo'],
    targetFields: ['sourceModule', 'sourceOrderId', 'sourceOrderNo'],
    forwardMatched,
    backwardMatched,
    bidirectionalVerified: forwardMatched && backwardMatched,
  }
}

export function buildRelationshipGraph(entities) {
  const records = entities.records || {}
  const relations = [
    relation(records.request, records.inquiry, 'purchaseRequest', 'purchaseInquiry', 'requestNo', 'inquiryNo'),
    relation(records.inquiry, records.approval, 'purchaseInquiry', 'priceApproval', 'inquiryNo', 'approvalNo'),
    relation(records.approval, records.order, 'priceApproval', 'purchaseOrder', 'approvalNo', 'poNo'),
  ].filter(Boolean)
  const downstreamRelations = []
  if (entities.arrivalContext) {
    downstreamRelations.push({
      relation: 'purchaseOrder -> purchaseArrivalPreview',
      sourceType: 'purchaseOrder',
      sourceId: records.order?.id || '',
      sourceNo: entities.purchaseOrderNo,
      targetType: 'purchaseArrivalPreview',
      targetId: entities.arrivalContext.stageId || 'purchase-arrival-preview',
      targetNo: entities.arrivalContext.purchaseOrderNo || '',
      matched: entities.arrivalContext.purchaseOrderNo === entities.purchaseOrderNo,
    })
  }
  if (records.purchaseReceive) {
    downstreamRelations.push({
      relation: 'purchaseOrder -> purchaseReceivePreview',
      sourceType: 'purchaseOrder',
      sourceId: records.order?.id || '',
      sourceNo: entities.purchaseOrderNo,
      targetType: 'purchaseReceivePreview',
      targetId: records.purchaseReceive.id,
      targetNo: records.purchaseReceive.receiveNo,
      matched: String(records.purchaseReceive.sourceOrderId) === String(records.order?.id)
        && records.purchaseReceive.sourceOrderNo === entities.purchaseOrderNo,
    })
  }
  if (records.incomingInspection) {
    downstreamRelations.push({
      relation: 'purchaseReceivePreview -> incomingInspection',
      sourceType: 'purchaseReceivePreview',
      sourceId: records.purchaseReceive?.id || '',
      sourceNo: entities.purchaseReceiveNo,
      targetType: 'incomingInspection',
      targetId: records.incomingInspection.id,
      targetNo: records.incomingInspection.inspectionNo,
      matched: String(records.incomingInspection.sourceReceiveId) === String(records.purchaseReceive?.id)
        && records.incomingInspection.sourceReceiveNo === entities.purchaseReceiveNo,
    })
  }
  if (records.qualifiedInbound) {
    downstreamRelations.push({
      relation: 'incomingInspection -> qualifiedInboundPrepare',
      sourceType: 'incomingInspection',
      sourceId: records.incomingInspection?.id || '',
      sourceNo: entities.incomingInspectionNo,
      targetType: 'qualifiedInboundPrepare',
      targetId: records.qualifiedInbound.id,
      targetNo: records.qualifiedInbound.taskNo,
      matched: String(records.qualifiedInbound.sourceInspectionId || records.qualifiedInbound.sourceId) === String(records.incomingInspection?.id)
        && records.qualifiedInbound.sourceInspectionNo === entities.incomingInspectionNo,
    })
  }
  if (records.inventoryTransaction) {
    downstreamRelations.push({
      relation: 'qualifiedInboundPrepare -> inventoryTransaction',
      sourceType: 'qualifiedInboundPrepare',
      sourceId: records.qualifiedInbound?.id || '',
      sourceNo: entities.qualifiedInboundNo,
      targetType: 'inventoryTransaction',
      targetId: records.inventoryTransaction.id,
      targetNo: records.inventoryTransaction.transactionNo,
      matched: String(records.inventoryTransaction.sourceWarehouseTaskId || '') === String(records.qualifiedInbound?.id)
        && records.inventoryTransaction.sourceWarehouseTaskNo === entities.qualifiedInboundNo,
    })
  }
  if (records.inventoryTransaction && records.payablePrepare) {
    const sourceIds = records.payablePrepare.sourceInventoryTransactionIds || []
    const lineSourceIds = (records.payablePrepare.lines || []).map((line) => line.sourceInventoryTransactionId)
    const sourceMatched = sourceIds.some((id) => String(id) === String(records.inventoryTransaction.id))
      || String(records.payablePrepare.sourceInventoryTransactionId || '') === String(records.inventoryTransaction.id)
      || lineSourceIds.some((id) => String(id) === String(records.inventoryTransaction.id))
    downstreamRelations.push({
      relation: 'inventoryTransaction -> payablePrepare',
      sourceType: 'inventoryTransaction',
      sourceId: records.inventoryTransaction.id,
      sourceNo: records.inventoryTransaction.transactionNo,
      targetType: 'payablePrepare',
      targetId: records.payablePrepare.id,
      targetNo: records.payablePrepare.payablePrepareNo,
      matched: sourceMatched
        && records.payablePrepare.sourceInventoryTransactionNo === records.inventoryTransaction.transactionNo,
      forwardLookup: 'payablePrepare.sourceInventoryTransactionId',
      reverseLookup: 'payablePrepareByInventoryTransaction',
    })
  }
  if (records.payablePrepare && records.payableCheck) {
    downstreamRelations.push({
      relation: 'payablePrepare -> payableCheck',
      sourceType: 'payablePrepare',
      sourceId: records.payablePrepare.id,
      sourceNo: records.payablePrepare.payablePrepareNo,
      targetType: 'payableCheck',
      targetId: records.payableCheck.id,
      targetNo: records.payableCheck.payableCheckNo,
      matched: String(records.payableCheck.sourcePayablePrepareId || '') === String(records.payablePrepare.id)
        && records.payableCheck.sourcePayablePrepareNo === records.payablePrepare.payablePrepareNo,
      forwardLookup: 'payableCheck.sourcePayablePrepareId',
      reverseLookup: 'payableCheckByPayablePrepare',
    })
  }
  if (records.payableCheck && records.supplierSettlement) {
    downstreamRelations.push({
      relation: 'payableCheck -> supplierSettlement',
      sourceType: 'payableCheck',
      sourceId: records.payableCheck.id,
      sourceNo: records.payableCheck.payableCheckNo,
      targetType: 'supplierSettlement',
      targetId: records.supplierSettlement.id,
      targetNo: records.supplierSettlement.settlementNo,
      matched: String(records.supplierSettlement.sourcePayableCheckId || '') === String(records.payableCheck.id)
        && records.supplierSettlement.sourcePayableCheckNo === records.payableCheck.payableCheckNo,
      forwardLookup: 'supplierSettlement.sourcePayableCheckId',
      reverseLookup: 'supplierSettlementByPayableCheck',
    })
  }
  return {
    generatedAt: new Date().toISOString(),
    relations,
    relationCount: relations.length,
    allRelationsBidirectional: relations.every((item) => item.bidirectionalVerified),
    downstreamRelations,
    downstreamRelationCount: downstreamRelations.length,
    allDownstreamRelationsMatched: downstreamRelations.every((item) => item.matched),
  }
}

async function calculateIntegrityHash(directory) {
  const hash = crypto.createHash('sha256')
  for (const fileName of INTEGRITY_FILES) {
    hash.update(fileName)
    hash.update(await fs.readFile(path.join(directory, fileName)))
  }
  return hash.digest('hex')
}

export async function checkpointImmutableHashes(checkpointId) {
  const directory = path.join(CHECKPOINT_ROOT, checkpointId)
  const fileNames = [
    'manifest.json',
    'storage-state.json',
    'application-state.json',
    'business-entities.json',
    'relationship-graph.json',
  ]
  const hashes = {}
  for (const fileName of fileNames) {
    const hash = crypto.createHash('sha256')
    hash.update(await fs.readFile(path.join(directory, fileName)))
    hashes[fileName] = hash.digest('hex')
  }
  return hashes
}

export async function resetCheckpointRoot() {
  await fs.mkdir(CHECKPOINT_ROOT, { recursive: true })
  const entries = await fs.readdir(CHECKPOINT_ROOT, { withFileTypes: true })
  await Promise.all(entries
    .filter((entry) => entry.name !== '.staging')
    .map((entry) => fs.rm(path.join(CHECKPOINT_ROOT, entry.name), { recursive: true, force: true })))
}

export async function saveCheckpoint({ context, page, checkpointId, sourceObjects, baseUrl, nextStageId, sourceCheckpointId = '', tracePath }) {
  const directory = path.join(CHECKPOINT_ROOT, checkpointId)
  await fs.rm(directory, { recursive: true, force: true })
  await fs.mkdir(directory, { recursive: true })
  const storageStatePath = path.join(directory, 'storage-state.json')
  await context.storageState({ path: storageStatePath, indexedDB: true })
  const applicationState = await captureApplicationState(page)
  const entities = buildBusinessEntities(applicationState, sourceObjects)
  const graph = buildRelationshipGraph(entities)
  await writeJson(path.join(directory, 'application-state.json'), applicationState)
  await writeJson(path.join(directory, 'business-entities.json'), entities)
  await writeJson(path.join(directory, 'relationship-graph.json'), graph)
  await writeJson(path.join(directory, 'restore-verification.json'), {
    checkpointId,
    status: 'pending',
    verifiedAt: '',
    verificationProcess: '',
  })
  await page.screenshot({ path: path.join(directory, 'checkpoint-screenshot.png'), fullPage: true })
  if (tracePath && tracePath !== path.join(directory, 'trace.zip')) {
    await fs.copyFile(tracePath, path.join(directory, 'trace.zip'))
  }
  const integrityHash = await calculateIntegrityHash(directory)
  const manifest = {
    checkpointVersion: CHECKPOINT_VERSION,
    flowVersion: FLOW_VERSION,
    checkpointId,
    createdAt: new Date().toISOString(),
    applicationVersion: FLOW_VERSION,
    baseUrl,
    origin: applicationState.origin,
    storageTypes: applicationState.storageTypes,
    storageKeys: Object.keys(applicationState.localStorage),
    entityIds: entityIds(entities),
    sourceCheckpointId,
    nextStageId,
    integrityFiles: INTEGRITY_FILES,
    integrityHash,
    restorable: false,
    userProfileOpened: false,
    userBusinessDataModified: false,
  }
  await writeJson(path.join(directory, 'manifest.json'), manifest)
  return { directory, manifest, entities, graph }
}

export async function saveStagedCheckpoint({ context, page, checkpointId, runId, sourceObjects, baseUrl, nextStageId, sourceCheckpointId = '' }) {
  if (!runId) throw new Error('staged checkpoint requires an explicit runId')
  const directory = path.join(CHECKPOINT_ROOT, '.staging', `${checkpointId}-${runId}`)
  await fs.rm(directory, { recursive: true, force: true })
  await fs.mkdir(directory, { recursive: true })
  await context.storageState({ path: path.join(directory, 'storage-state.json'), indexedDB: true })
  const applicationState = await captureApplicationState(page)
  const entities = buildBusinessEntities(applicationState, sourceObjects)
  const graph = buildRelationshipGraph(entities)
  await writeJson(path.join(directory, 'application-state.json'), applicationState)
  await writeJson(path.join(directory, 'business-entities.json'), entities)
  await writeJson(path.join(directory, 'relationship-graph.json'), graph)
  await writeJson(path.join(directory, 'restore-verification.json'), {
    checkpointId,
    status: 'pending',
    verifiedAt: '',
    verificationProcess: '',
  })
  await page.screenshot({ path: path.join(directory, 'checkpoint-screenshot.png'), fullPage: true })
  await writeJson(path.join(directory, 'staging-metadata.json'), {
    checkpointVersion: CHECKPOINT_VERSION,
    flowVersion: FLOW_VERSION,
    checkpointId,
    runId,
    createdAt: new Date().toISOString(),
    baseUrl,
    origin: applicationState.origin,
    storageTypes: applicationState.storageTypes,
    storageKeys: Object.keys(applicationState.localStorage),
    entityIds: entityIds(entities),
    sourceCheckpointId,
    nextStageId,
    userProfileOpened: false,
    userBusinessDataModified: false,
  })
  return { directory, entities, graph }
}

export async function finalizeStagedCheckpoint({ checkpointId, runId, tracePath }) {
  const stagingDirectory = path.join(CHECKPOINT_ROOT, '.staging', `${checkpointId}-${runId}`)
  const finalDirectory = path.join(CHECKPOINT_ROOT, checkpointId)
  const metadata = await readJson(path.join(stagingDirectory, 'staging-metadata.json'))
  if (metadata.checkpointId !== checkpointId || metadata.runId !== runId) throw new Error('staged checkpoint identity mismatch')
  const traceStat = await fs.stat(tracePath)
  if (!traceStat.isFile() || traceStat.size <= 0) throw new Error('current runner trace is missing or empty')
  await fs.copyFile(tracePath, path.join(stagingDirectory, 'trace.zip'))
  const integrityHash = await calculateIntegrityHash(stagingDirectory)
  await writeJson(path.join(stagingDirectory, 'manifest.json'), {
    checkpointVersion: metadata.checkpointVersion,
    flowVersion: metadata.flowVersion,
    checkpointId,
    createdAt: metadata.createdAt,
    applicationVersion: metadata.flowVersion,
    baseUrl: metadata.baseUrl,
    origin: metadata.origin,
    storageTypes: metadata.storageTypes,
    storageKeys: metadata.storageKeys,
    entityIds: metadata.entityIds,
    sourceCheckpointId: metadata.sourceCheckpointId,
    nextStageId: metadata.nextStageId,
    integrityFiles: INTEGRITY_FILES,
    integrityHash,
    restorable: true,
    runnerTraceRunId: runId,
    runnerTraceSource: path.resolve(tracePath),
    userProfileOpened: false,
    userBusinessDataModified: false,
  })
  await fs.rm(path.join(stagingDirectory, 'staging-metadata.json'))
  for (const fileName of REQUIRED_CHECKPOINT_FILES) await fs.access(path.join(stagingDirectory, fileName))
  try {
    await fs.access(finalDirectory)
    throw new Error(`final checkpoint already exists: ${finalDirectory}`)
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error
  }
  await fs.rename(stagingDirectory, finalDirectory)
  return verifyCheckpointIntegrity(checkpointId, { expectedOrigin: metadata.origin })
}

export async function markCheckpointRestored(checkpointId, verification, directoryOverride = '') {
  const directory = directoryOverride || path.join(CHECKPOINT_ROOT, checkpointId)
  const verificationDirectory = path.join(directory, 'verification')
  await fs.mkdir(verificationDirectory, { recursive: true })
  const restoreTime = new Date().toISOString()
  const restoreVerification = {
    checkpointId,
    status: 'passed',
    restoreTime,
    verifiedAt: restoreTime,
    processId: verification.processId || process.pid,
    browserContextId: verification.browserContextId || '',
    result: verification.result || 'passed',
    errors: verification.errors || [],
    verifiedEntities: verification.verifiedEntities || {},
    ...verification,
  }
  const historyPath = path.join(verificationDirectory, 'restore-history.json')
  let history = []
  try {
    history = await readJson(historyPath)
    if (!Array.isArray(history)) history = []
  } catch {
    history = []
  }
  history.push(restoreVerification)
  await writeJson(historyPath, history)
  const resultFileName = `restore-result-${restoreTime.replace(/[:.]/g, '-')}.json`
  await writeJson(path.join(verificationDirectory, resultFileName), restoreVerification)
  return restoreVerification
}

async function hasPassedRestoreVerification(directory) {
  try {
    const history = await readJson(path.join(directory, 'verification', 'restore-history.json'))
    if (Array.isArray(history) && history.some((item) => item.status === 'passed' || item.result === 'passed')) return true
  } catch {
    // Legacy checkpoints may only carry the immutable manifest flag.
  }
  return false
}

export async function verifyCheckpointIntegrity(checkpointId, { expectedOrigin = '', requireRestorable = true } = {}) {
  const directory = path.join(CHECKPOINT_ROOT, checkpointId)
  const missingFiles = []
  for (const fileName of REQUIRED_CHECKPOINT_FILES) {
    try {
      await fs.access(path.join(directory, fileName))
    } catch {
      missingFiles.push(fileName)
    }
  }
  if (missingFiles.length) throw new Error(`检查点缺少文件：${missingFiles.join(', ')}`)
  const manifest = await readJson(path.join(directory, 'manifest.json'))
  if (manifest.checkpointVersion !== CHECKPOINT_VERSION) throw new Error(`不支持的检查点版本：${manifest.checkpointVersion}`)
  if (manifest.checkpointId !== checkpointId) throw new Error(`检查点编号不匹配：${manifest.checkpointId}`)
  if (expectedOrigin && manifest.origin !== expectedOrigin) throw new Error(`检查点 origin 不匹配：${manifest.origin} !== ${expectedOrigin}`)
  if (!manifest.entityIds?.length) throw new Error('检查点 entityIds 为空')
  if (!manifest.nextStageId) throw new Error('检查点 nextStageId 为空')
  if (requireRestorable && manifest.restorable !== true && !(await hasPassedRestoreVerification(directory))) {
    throw new Error('检查点尚未通过恢复验证')
  }
  const actualHash = await calculateIntegrityHash(directory)
  if (actualHash !== manifest.integrityHash) throw new Error(`检查点完整性 hash 不匹配：${actualHash}`)
  const entities = await readJson(path.join(directory, 'business-entities.json'))
  const graph = await readJson(path.join(directory, 'relationship-graph.json'))
  return { directory, manifest, entities, graph, actualHash, missingFiles }
}

export function checkpointPath(checkpointId, fileName = '') {
  return path.join(CHECKPOINT_ROOT, checkpointId, fileName)
}
