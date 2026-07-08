/**
 * ============================
 * Meta Snapshot V11（生产级）
 * ============================
 */

const snapshots = new Map()

/**
 * 创建快照（发布）
 */
export const createSnapshot = (metaId, meta) => {
  const snapshot = {
    id: generateId(),
    metaId,
    meta: JSON.parse(JSON.stringify(meta)),
    createdAt: Date.now(),
    status: 'PUBLISHED',
  }

  snapshots.set(snapshot.id, snapshot)

  return snapshot
}

/**
 * 回滚快照
 */
export const rollbackSnapshot = (snapshotId) => {
  return snapshots.get(snapshotId)
}

/**
 * 获取所有快照
 */
export const getSnapshots = (metaId) => {
  return Array.from(snapshots.values()).filter((s) => s.metaId === metaId)
}

/**
 * 生成ID
 */
function generateId() {
  return 'snap_' + Math.random().toString(36).slice(2, 10)
}
