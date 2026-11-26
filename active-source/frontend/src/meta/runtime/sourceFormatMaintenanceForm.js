/** Form serialization only. Normalization and numeric evaluation belong to the server. */
export const SOURCE_FORMAT_CONTRACT = 'PCE-SOURCE-FORMAT-MAPPING-V1'
export const WORKBOOK_BLOB_CONTRACT = 'PCE-ENGINEERING-WORKBOOK-BLOB-V1'
export const engineeringSourceTypes = Object.freeze([
  ['CUSTOMER', '客户资料'], ['SITE_MEASUREMENT', '现场测量'], ['SALES', '销售资料'],
  ['DESIGN', '设计资料'], ['ENGINEERING_INPUT', '工程录入'], ['ENGINEERING_DERIVED', '工程派生'],
  ['MASTER_DATA', '主数据'], ['RULE_PARAMETER', '规则参数'], ['AGGREGATED', '受控汇总'],
])
export const outputDomains = Object.freeze([
  ['DERIVED_FACT', '工程派生事实'], ['MATERIAL_REQUIREMENT', '材料需求结果'], ['OPERATION_REQUIREMENT', '工序需求结果'],
])
const copy = value => JSON.parse(JSON.stringify(value))
const orderedJson = value => Array.isArray(value) ? value.map(orderedJson)
  : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key,orderedJson(value[key])])) : value
const sameJson = (left, right) => JSON.stringify(orderedJson(left)) === JSON.stringify(orderedJson(right))
export function parseObject(value) {
  const result = typeof value === 'string' ? JSON.parse(value || '{}') : value || {}
  if (!result || Array.isArray(result) || typeof result !== 'object') throw new Error('正式定义必须是对象。')
  return result
}
export function tokensFromText(text, includeEmpty = false) {
  return [...new Set([...(includeEmpty ? [''] : []), ...String(text || '').split(/\r?\n/).filter(value => value !== '')])]
}
export function newMappingField(input = {}) {
  return { rawField: '', canonicalName: input.canonicalName || '', sourceType: input.sourceType || 'ENGINEERING_INPUT',
    valueType: input.valueType || 'decimal', unit: input.unit || null, unitDimension: input.unitDimension || 'dimensionless',
    zeroTokens: [], blankTokens: [], blankPolicy: 'ERROR' }
}
export function newFormatMapping(input = {}) {
  return { contractVersion: SOURCE_FORMAT_CONTRACT, format: 'CSV', delimiter: ',', decimalSeparator: '.',
    thousandsSeparator: '', fields: [newMappingField(input)] }
}
export function newWorkbookMappingSheet() {
  return { sheetName: '', sourceRows: [], fields: [] }
}
export function workbookContextKey(context) {
  return context ? JSON.stringify([context.objectSourceRecordId, context.baselineId, context.baselineSnapshotHash]) : ''
}
export function validateWorkbookBlob(blob, companyId = null) {
  const key = /^(?:([1-9]\d*)\/)?([a-f0-9]{64}\.xlsx)$/i.exec(blob?.storageKey || '')
  if (!blob || blob.contractVersion !== WORKBOOK_BLOB_CONTRACT || !/^[a-f0-9]{64}$/i.test(blob.sha256 || '')
    || !key || key[2] !== `${blob.sha256}.xlsx` || (key[1] && companyId != null && key[1] !== String(companyId))
    || !Number.isSafeInteger(blob.bytes) || blob.bytes <= 0
    || typeof blob.originalName !== 'string' || !blob.originalName) throw new Error('工作簿文件引用缺少准确的服务端存储身份、指纹或长度。')
  return blob
}
export function validateWorkbookUpload(result, companyId = null) {
  if (result?.factSource !== 'server' || result.businessWriteCount !== 0 || result.auditWriteCount !== 0
    || result.sourceFileStored !== true) throw new Error('工作簿上传未返回服务端文件存储证明；尚未登记正式来源。')
  return validateWorkbookBlob(result.blob, companyId)
}
export function sourceFormatResponse(response) {
  if (response?.success === false) throw new Error(response.error?.message || response.factLoadFacts?.errorMessage || response.message || '原生来源读取失败，当前结果未知。')
  return response?.data ?? response
}
export function validateWorkbookCatalog(result) {
  if (result?.factSource !== 'server' || result.businessWriteCount !== 0 || !Array.isArray(result.workbookSources)
    || !Array.isArray(result.sourceContexts) || result.workbookSources.some(row => !Number.isSafeInteger(row.id) || row.id <= 0)
    || result.sourceContexts.some(row => !Number.isSafeInteger(row.objectSourceRecordId) || row.objectSourceRecordId <= 0
      || !Number.isSafeInteger(row.baselineId) || row.baselineId <= 0 || !/^[a-f0-9]{64}$/i.test(row.baselineSnapshotHash || '')
      || typeof row.label !== 'string' || !row.label)) throw new Error('工作簿来源或已确认对象范围目录不完整，当前选择资格未知。')
  return result
}
export function supportsStructuredRule(spec) {
  return !Object.keys(spec).length || (spec.inputs?.length === 1 && spec.outputs?.length === 1
    && typeof spec.expression === 'string' && !spec.factExtension && !spec.manufacturing
    && typeof spec.inputs[0].unitDimension !== 'object' && typeof spec.outputs[0].unitDimension !== 'object')
}
export function ruleDraftFromSpecification(spec) {
  const input = spec.inputs?.[0] || {}, output = spec.outputs?.[0] || {}
  return { inputName: input.canonicalName || 'source_quantity', sourceType: input.sourceType || 'ENGINEERING_INPUT',
    inputType: input.valueType || 'decimal', inputUnit: input.unit || '', inputDimension: input.unitDimension || 'dimensionless',
    sourceField: input.sourceCanonicalField || '', expression: spec.expression || input.canonicalName || 'source_quantity',
    outputName: output.canonicalName || 'result_quantity', outputType: output.valueType || 'decimal',
    outputUnit: output.unit || '', outputDimension: output.unitDimension || 'dimensionless',
    resultDomain: output.resultDomain || 'DERIVED_FACT', precision: spec.decimalPrecision ?? 28,
    scale: spec.outputScale ?? 6, rounding: spec.roundingMode || 'ROUND_HALF_UP',
    evidence: spec.sourceEvidence?.reference || '', scope: spec.applicability?.scope || 'order_engineering' }
}
export function specificationFromRuleDraft(draft, metadata, original = {}) {
  const precision = Number(draft.precision), scale = Number(draft.scale)
  if (!Number.isInteger(precision) || precision < 1 || precision > 50
    || !Number.isInteger(scale) || scale < 0 || scale > precision) throw new Error('精度须为1—50整数，输出小数位须在0至精度之间。')
  const input = { ...(original.inputs?.[0] || {}), canonicalName: draft.inputName, sourceType: draft.sourceType,
    valueType: draft.inputType, unit: draft.inputUnit || null, unitDimension: draft.inputDimension, required: true,
    unitRequired: Boolean(draft.inputUnit) }
  if (draft.sourceField) input.sourceCanonicalField = draft.sourceField
  else delete input.sourceCanonicalField
  return { ...copy(original), rulePackage: { ...(original.rulePackage || {}), code: metadata.code, version: metadata.version },
    expression: draft.expression, inputs: [input], outputs: [{ ...(original.outputs?.[0] || {}), canonicalName: draft.outputName,
      resultDomain: draft.resultDomain, valueType: draft.outputType, unit: draft.outputUnit || null, unitDimension: draft.outputDimension }],
    dependencies: original.dependencies || [], decimalPrecision: precision, outputScale: scale, roundingMode: draft.rounding,
    applicability: { ...(original.applicability || {}), scope: draft.scope },
    sourceEvidence: { ...(original.sourceEvidence || {}), reference: draft.evidence } }
}
export function eligibleFormatRules(rows, companyId) {
  if (!Number.isInteger(Number(companyId)) || Number(companyId) <= 0) return []
  return (rows || []).filter(row => Number(row.company_id) === Number(companyId) && row.status === 'released'
    && row.specification?.sourceFormatMapping?.contractVersion === SOURCE_FORMAT_CONTRACT
    && /^[a-f0-9]{64}$/i.test(row.specificationHash || '') && Number.isInteger(row.id) && row.id > 0)
}
export function sourcePayloadFromDraft({ rule, rawText, rowIndex, workbookBlob, sourceContext }, original = {}) {
  if (!rule || !/^[a-f0-9]{64}$/i.test(rule.specificationHash || '')) throw new Error('请选择当前公司已发布且带服务端规范指纹的格式规则。')
  const mapping = rule.specification?.sourceFormatMapping
  if (!mapping || !['CSV', 'JSON_ROWS', 'XLSX_ADAPTER'].includes(mapping.format)) throw new Error('来源格式规则不受支持。')
  const payload = copy(original)
  delete payload.normalization
  delete payload.canonicalInputs
  payload.sourceFormatReference = { ruleId: rule.id, ruleVersion: rule.version, specificationHash: rule.specificationHash }
  if (mapping.format === 'XLSX_ADAPTER') {
    if (!sourceContext || !Number.isSafeInteger(sourceContext.objectSourceRecordId) || sourceContext.objectSourceRecordId <= 0
      || !Number.isSafeInteger(sourceContext.baselineId) || sourceContext.baselineId <= 0
      || !/^[a-f0-9]{64}$/i.test(sourceContext.baselineSnapshotHash || '')) throw new Error('请选择服务端提供的已确认对象及基线范围。')
    payload.rawContent = copy(validateWorkbookBlob(workbookBlob, rule.company_id))
    payload.sourceContext = { objectSourceRecordId:sourceContext.objectSourceRecordId,baselineId:sourceContext.baselineId,
      baselineSnapshotHash:sourceContext.baselineSnapshotHash }
  } else {
    if (mapping.format === 'JSON_ROWS' && !Array.isArray(JSON.parse(rawText))) throw new Error('JSON行格式须填写对象数组。')
    // Validate shape only; preserve JSON number lexemes for server Decimal parsing.
    payload.rawContent = rawText
  }
  if (rowIndex !== '' && rowIndex !== null && rowIndex !== undefined) {
    if (!/^\d+$/.test(String(rowIndex))) throw new Error('来源行索引须为从0开始的非负整数。')
    payload.sourceFormatRow = Number(rowIndex)
  } else delete payload.sourceFormatRow
  return payload
}
export function validateSourceFormatPreview(result, submitted) {
  const normalized = result?.normalizedPayload
  if (result?.factSource !== 'server' || result.businessWriteCount !== 0 || result.auditWriteCount !== 0
    || !result.normalization || !result.canonicalInputs || !normalized
    || !/^[a-f0-9]{64}$/i.test(result.normalization.rawContentHash || '')
    || !sameJson(normalized.sourceFormatReference, submitted.sourceFormatReference)
    || !sameJson(normalized.rawContent, submitted.rawContent)
    || (submitted.rawContent?.contractVersion === WORKBOOK_BLOB_CONTRACT
      && (!sameJson(normalized.sourceContext, submitted.sourceContext)
        || result.normalization.rawContentHash !== submitted.rawContent.sha256
        || result.normalization.format !== 'XLSX_ADAPTER' || !result.normalization.sourceScope
        || !Array.isArray(result.normalization.rows)
        || !sameJson(result.normalization.sourceFormatReference, submitted.sourceFormatReference)
        || result.normalization.sourceScope.objectSourceRecordId !== submitted.sourceContext.objectSourceRecordId
        || result.normalization.sourceScope.baselineId !== submitted.sourceContext.baselineId
        || result.normalization.sourceScope.baselineSnapshotHash !== submitted.sourceContext.baselineSnapshotHash
        || !Number.isSafeInteger(result.normalization.rowCount) || result.normalization.rowCount <= 0
        || result.normalization.rows.length !== result.normalization.rowCount))
    || normalized.sourceFormatRow !== submitted.sourceFormatRow
    || !sameJson(normalized.normalization, result.normalization)
    || !sameJson(normalized.canonicalInputs, result.canonicalInputs)) {
    throw new Error('原生格式预览响应与本次准确规则、原文或规范化快照不一致。')
  }
  return result
}
export function explicitTraceConditions(rows) {
  if (!Array.isArray(rows) || !rows.length) throw new Error('显式来源条件至少需要一项。')
  const keys = new Set()
  return Object.fromEntries(rows.map(row => {
    const key = String(row.key || '').trim()
    if (!key || /[\u0000-\u001f\u007f]/.test(key) || keys.has(key)) throw new Error('来源条件字段须非空、无控制字符且不得重复。')
    keys.add(key)
    let value
    if (row.valueType === 'string') value = String(row.value ?? '')
    else if (row.valueType === 'integer') {
      if (!/^[+-]?\d+$/.test(String(row.value)) || !Number.isSafeInteger(Number(row.value))) throw new Error('整数条件须填写可精确表达的整数。')
      value = Number(row.value)
    } else if (row.valueType === 'boolean') {
      if (!['true', 'false'].includes(String(row.value))) throw new Error('布尔条件须明确选择是或否。')
      value = String(row.value) === 'true'
    } else if (row.valueType === 'null') value = null
    else throw new Error('来源条件只支持文本、整数、布尔或空值。')
    return [key, value]
  }))
}
