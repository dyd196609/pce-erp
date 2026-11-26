export const BUSINESS_DISPLAY_VALUE_FORMATTER_VERSION = 'V1.14.2.7.1'

const statusTextMap = {
  completed: '已完成',
  already_completed_reused: '已存在且已复用',
  existing_target_complete: '已发现目标记录，关联证据完整（existing_target_complete）',
  existing_target_incomplete: '已发现目标记录，处理证据不完整（existing_target_incomplete）',
  existing_target_conflict: '已发现目标关联冲突（existing_target_conflict）',
  target_evidence_read_failed: '目标证据读取失败，当前结果不可确认（target_evidence_read_failed）',
  target_not_found: '尚未发现目标记录（target_not_found）',
  blocked_conflict: '数据冲突，禁止继续',
  failed: '执行失败',
  not_executed: '未执行',
  draft: '草稿',
  pending: '待处理',
  checked: '已核对',
  confirmed: '已确认',
  reconciled: '已对账',
  written_back: '已回写',
  linked: '已关联',
  active: '已关联',
  reused: '已复用',
  read_failed: '读取失败',
}

const evidenceStatusTextMap = {
  not_found: '未发现目标对象',
  complete: '完整',
  incomplete: '不完整',
  conflict: '冲突',
  read_failed: '读取失败',
}

function isBlank(value) {
  return value === null || value === undefined || String(value).trim() === ''
}

function formatBoolean(value, fallback = '否') {
  if (value === true) return '是'
  if (value === false) return '否'
  if (isBlank(value)) return fallback || '未执行'
  return value ? '是' : '否'
}

function formatIdentifier(value, fallback = '尚未生成') {
  return isBlank(value) ? fallback : String(value).trim()
}

function formatReason(value, fallback = '当前无阻断原因。') {
  if (Array.isArray(value)) {
    const reasons = value.map((item) => String(item || '').trim()).filter(Boolean)
    return reasons.length ? reasons.join('；') : fallback
  }
  return isBlank(value) ? fallback : String(value).trim()
}

function formatStatus(value, fallback = '未执行') {
  if (isBlank(value)) return fallback
  return statusTextMap[value] || String(value).trim()
}

function formatEvidenceStatus(value, fallback = '未发现目标对象') {
  if (isBlank(value)) return fallback
  return evidenceStatusTextMap[value] || String(value).trim()
}

export function formatBusinessDisplayValue(value, options = {}) {
  const { displayType = 'text', fallback } = options
  if (displayType === 'boolean') return formatBoolean(value, fallback)
  if (displayType === 'identifier') return formatIdentifier(value, fallback)
  if (displayType === 'reason') return formatReason(value, fallback)
  if (displayType === 'status') return formatStatus(value, fallback)
  if (displayType === 'evidenceStatus') return formatEvidenceStatus(value, fallback)
  if (Array.isArray(value)) return value.length ? value.join('；') : (fallback || '-')
  return isBlank(value) ? (fallback || '-') : String(value).trim()
}

export function getBusinessEvidenceStatusText(value) {
  return formatEvidenceStatus(value)
}

export function formatBusinessNo(value, fallback = '尚未生成') {
  return formatIdentifier(value, fallback)
}

export function formatBusinessStatus(value, fallback = '未执行') {
  return formatStatus(value, fallback)
}




