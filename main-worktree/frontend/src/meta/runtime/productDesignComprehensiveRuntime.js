export const PRODUCT_DESIGN_INPUT_FIELDS = Object.freeze([
  { inputKey: 'productCategoryId', label: '产品分类', section: '对象身份、来源与产品关联', batch: true },
  { inputKey: 'productDefinitionId', label: '正式产品定义', section: '对象身份、来源与产品关联', batch: false },
  { inputKey: 'physicalUomId', label: '实物单位', section: '数量与实物单位', batch: true },
  { inputKey: 'designUomId', label: '设计尺寸单位', section: '设计尺寸', batch: true },
  { inputKey: 'designLength', label: '设计长度', section: '设计尺寸', batch: true },
  { inputKey: 'designWidth', label: '设计宽度', section: '设计尺寸', batch: true },
  { inputKey: 'designThickness', label: '第三尺寸', section: '设计尺寸', batch: true },
  { inputKey: 'materialId', label: '物料', section: '物料', batch: true },
  { inputKey: 'processConfigurationId', label: '工艺配置', section: '工艺配置及独立油漆工艺', batch: true },
  { inputKey: 'paintProcessTypeId', label: '油漆工艺', section: '工艺配置及独立油漆工艺', batch: true },
  { inputKey: 'edgeMethodId', label: '封边方式', section: '其它现有设计内容', batch: true },
  { inputKey: 'visibleConditionCode', label: '见光条件', section: '其它现有设计内容', batch: true },
  { inputKey: 'colorVersionOptionId', label: '颜色/版号', section: '其它现有设计内容', batch: true },
  { inputKey: 'configurationNotes', label: '配置说明', section: '其它现有设计内容', batch: true },
  { inputKey: 'hardware', label: '五金要求', section: '其它现有设计内容', batch: true },
  { inputKey: 'glass', label: '玻璃要求', section: '其它现有设计内容', batch: true },
  { inputKey: 'documentReferences', label: '资料引用', section: '其它现有设计内容', batch: true },
  { inputKey: 'designNotes', label: '设计说明', section: '设计说明、修订原因和历史追溯', batch: true },
])

function currentValue(row, key) {
  const revision = row?.designRevision || {}
  const existing = row?.existingDesign || {}
  const value = field => revision[field] ?? existing[field] ?? null
  const simple = {
    productCategoryId: row?.productCategoryId ?? null,
    productDefinitionId: row?.productDefinitionId ?? null,
    physicalUomId: row?.physicalUomId ?? null,
    designLength: value('designLength'),
    designWidth: value('designWidth'),
    designThickness: value('designThickness'),
    designUomId: value('designUomId'),
    materialId: value('materialId') ?? row?.matchResults?.material?.matchedId ?? null,
    processConfigurationId: value('processConfigurationId') ?? row?.matchResults?.processConfiguration?.matchedId ?? null,
    paintProcessTypeId: value('paintProcessTypeId') ?? row?.matchResults?.paintProcess?.matchedId ?? null,
    edgeMethodId: value('edgeMethodId') ?? row?.matchResults?.edgeMethod?.matchedId ?? null,
    visibleConditionCode: value('visibleConditionCode'),
    colorVersionOptionId: value('colorVersionOptionId'),
    configurationNotes: value('configurationNotes') ?? '',
    hardware: value('hardware') ?? '',
    glass: value('glass') ?? '',
    documentReferences: value('documentReferences') ?? [],
    designNotes: value('designNotes') ?? '',
  }
  return simple[key]
}

export function summarizeProductDesignSelection(rows, fields = PRODUCT_DESIGN_INPUT_FIELDS) {
  const form = {}
  const mixedFields = []
  if (!rows.length) {
    for (const field of fields) {
      form[field.inputKey] = field.inputKey === 'documentReferences' ? [] : null
    }
    return { form, mixedFields }
  }
  for (const field of fields) {
    const values = rows.map(row => currentValue(row, field.inputKey))
    const serialized = [...new Set(values.map(value => JSON.stringify(value ?? null)))]
    if (serialized.length === 1) form[field.inputKey] = structuredClone(values[0])
    else {
      mixedFields.push(field.inputKey)
      form[field.inputKey] = Array.isArray(values[0]) ? [] : null
    }
  }
  return { form, mixedFields }
}

export function productDesignSelectionKey(rows) {
  return rows.map(row => String(row.id)).sort().join('|')
}

export function reconcileProductDesignTargets(currentRows, requestedIds) {
  const requested = new Set((requestedIds || []).map(String))
  const current = new Set((currentRows || []).map(row => String(row.id)))
  return {
    add: (requestedIds || []).filter(id => !current.has(String(id))),
    remove: currentRows.filter(row => !requested.has(String(row.id))),
  }
}

export function resolveProductDesignTargets(rows, requestedIds) {
  const currentById = new Map((rows || []).map(row => [String(row.id), row]))
  const orderedIds = [...new Set((requestedIds || []).map(String))]
  const targets = []
  const missingIds = []
  for (const id of orderedIds) {
    const row = currentById.get(id)
    if (row) targets.push(row)
    else missingIds.push(id)
  }
  return { targets, missingIds }
}

export function appendProductDesignTargetIds(currentIds, rangeIds) {
  const result = []
  const seen = new Set()
  for (const id of [...(currentIds || []), ...(rangeIds || [])]) {
    const key = String(id)
    if (!key || seen.has(key)) continue
    seen.add(key)
    result.push(id)
  }
  return result
}

export function assertCompleteProductDesignRangeSource(rows, { expectedRecordCount, orderNo } = {}) {
  const expected = Number(expectedRecordCount)
  if (!Number.isInteger(expected) || expected < 0 || expected !== (rows || []).length) {
    const error = new Error(`范围事实不完整：服务端声明 ${expectedRecordCount ?? '未知'} 项，当前只取得 ${(rows || []).length} 项。`)
    error.code = 'PRODUCT_DESIGN_RANGE_SOURCE_INCOMPLETE'
    throw error
  }
  const ids = new Set()
  for (const row of rows || []) {
    const id = String(row?.id ?? '')
    if (!id || ids.has(id)) {
      const error = new Error('范围事实包含缺失或重复的 ProductDesignItem 稳定ID。')
      error.code = 'PRODUCT_DESIGN_RANGE_ID_INVALID'
      throw error
    }
    if (orderNo && String(row?.orderNo || '') !== String(orderNo)) {
      const error = new Error(`范围事实混入其它订单设计项：${row?.itemNo || id}。`)
      error.code = 'PRODUCT_DESIGN_RANGE_ORDER_MISMATCH'
      throw error
    }
    ids.add(id)
  }
  return true
}

export function filterProductDesignRange(rows, { productCategoryId = '', designGroup = '' } = {}) {
  return (rows || []).filter(row => (
    (!productCategoryId || String(row?.productCategoryId || '') === String(productCategoryId))
    && (!designGroup || String(row?.designGroup || '') === String(designGroup))
  ))
}

export function createProductDesignRangeSnapshot({ rows, selectedRows, productCategoryId = '', designGroup = '', orderNo = '' }) {
  const rangeRows = filterProductDesignRange(rows, { productCategoryId, designGroup })
  const selectedIds = (selectedRows || []).map(row => row.id)
  const rangeIds = rangeRows.map(row => row.id)
  const rangeSet = new Set(rangeIds.map(String))
  const selectedSet = new Set(selectedIds.map(String))
  const finalIds = appendProductDesignTargetIds(selectedIds, rangeIds)
  return Object.freeze({
    orderNo,
    productCategoryId,
    designGroup,
    targetIds: Object.freeze([...rangeIds]),
    baseSelectedIds: Object.freeze([...selectedIds]),
    finalIds: Object.freeze([...finalIds]),
    matchedCount: rangeIds.length,
    alreadySelectedCount: rangeIds.filter(id => selectedSet.has(String(id))).length,
    newCount: rangeIds.filter(id => !selectedSet.has(String(id))).length,
    selectedOutsideCount: selectedIds.filter(id => !rangeSet.has(String(id))).length,
    finalCount: finalIds.length,
    targets: Object.freeze(rangeRows.map(row => Object.freeze({
      id: row.id,
      itemNo: row.itemNo,
      productName: row.productName,
      installationPosition: row.installationPosition || row.spaceLabel || '',
      sourcePosition: row.sourcePosition || row.listValues?.sourcePosition || '',
      version: row.version,
    }))),
  })
}

export function assertProductDesignFieldContract(fieldContract) {
  const contractInputs = new Set(fieldContract.map(field => field.inputKey).filter(Boolean))
  for (const field of PRODUCT_DESIGN_INPUT_FIELDS) {
    if (!contractInputs.has(field.inputKey)) {
      throw new Error(`产品设计统一字段契约缺少 ${field.inputKey}`)
    }
  }
  return true
}
