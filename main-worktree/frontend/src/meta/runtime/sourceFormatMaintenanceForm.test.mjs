import assert from 'node:assert/strict'
import { test } from 'node:test'
import { eligibleFormatRules, newFormatMapping, parseObject, ruleDraftFromSpecification,
  sourcePayloadFromDraft, specificationFromRuleDraft, supportsStructuredRule, tokensFromText, validateSourceFormatPreview,
  explicitTraceConditions, WORKBOOK_BLOB_CONTRACT, newWorkbookMappingSheet, validateWorkbookUpload, validateWorkbookCatalog,
  workbookContextKey } from './sourceFormatMaintenanceForm.js'

const hash = 'a'.repeat(64)
const rule = { id: 51, company_id: 8, status: 'released', version: 'V2', specificationHash: hash,
  specification: { sourceFormatMapping: newFormatMapping() } }

test('mapping rule options require same company, released status and server-provided hash', () => {
  assert.deepEqual(eligibleFormatRules([rule, { ...rule, id:52,company_id:9 }, { ...rule,id:53,status:'draft' },
    { ...rule,id:54,specificationHash:undefined }], 8), [rule])
  assert.deepEqual(eligibleFormatRules([rule], null), [])
})
test('source draft retains original raw text and server identity without inventing normalized values', () => {
  const original = { sourceContext:{ product:'A' },normalization:{ stale:true },canonicalInputs:{ forged:'99' } }
  const rawText = '量\n1,234.500\n—'
  const payload = sourcePayloadFromDraft({ rule,rawText,rowIndex:'1' }, original)
  assert.equal(payload.rawContent, rawText)
  assert.deepEqual(payload.sourceFormatReference, { ruleId:51,ruleVersion:'V2',specificationHash:hash })
  assert.equal(payload.sourceFormatRow, 1)
  assert.deepEqual(payload.sourceContext, original.sourceContext)
  assert.equal('normalization' in payload, false)
  assert.equal('canonicalInputs' in payload, false)
  assert.equal(original.normalization.stale, true)
})
test('JSON rows preserve original decimal lexemes and reject wrong shape and ambiguous row indices', () => {
  const jsonRule = { ...rule,specification:{ sourceFormatMapping:{ ...newFormatMapping(),format:'JSON_ROWS' } } }
  const rawText = '[{"量":0.1234567890123456789012345678901234567890}, {"量":null}, {"量":"0"}]'
  assert.equal(sourcePayloadFromDraft({ rule:jsonRule,rawText,rowIndex:'' }).rawContent, rawText)
  assert.equal(typeof sourcePayloadFromDraft({ rule:jsonRule,rawText,rowIndex:'' }).rawContent, 'string')
  assert.throws(() => sourcePayloadFromDraft({ rule:jsonRule,rawText:'{}',rowIndex:'' }), /对象数组/)
  assert.throws(() => sourcePayloadFromDraft({ rule,rawText:'a\n1',rowIndex:'-1' }), /非负整数/)
  assert.throws(() => sourcePayloadFromDraft({ rule:{ ...rule,specificationHash:'' },rawText:'a\n1' }), /服务端规范指纹/)
})
test('zero and blank tokens remain explicit, including empty text and space-only source tokens', () => {
  assert.deepEqual(tokensFromText('0\n无\n0', false), ['0','无'])
  assert.deepEqual(tokensFromText('—\n ', true), ['', '—', ' '])
  const field = newFormatMapping().fields[0]
  assert.deepEqual(field.zeroTokens, [])
  assert.deepEqual(field.blankTokens, [])
  assert.equal(field.blankPolicy, 'ERROR')
  assert.equal(field.unit, null)
  assert.equal(field.unitDimension, 'dimensionless')
  assert.equal(newFormatMapping({ unit:'m2',unitDimension:'area' }).fields[0].unit, 'm2')
})
test('single-input business form creates a full rule contract without evaluating arithmetic', () => {
  const draft = ruleDraftFromSpecification({})
  Object.assign(draft, { inputName:'gross_length',sourceType:'SITE_MEASUREMENT',sourceField:'',expression:'gross_length / 2',
    inputUnit:'m',inputDimension:'length',outputUnit:'m',outputDimension:'length',evidence:'已批准的现场计量标准' })
  const spec = specificationFromRuleDraft(draft, { code:'CUT-LENGTH',version:'V1' })
  assert.deepEqual(spec.rulePackage, { code:'CUT-LENGTH',version:'V1' })
  assert.equal(spec.inputs[0].sourceType, 'SITE_MEASUREMENT')
  assert.equal(spec.expression, 'gross_length / 2')
  assert.equal(spec.outputs[0].resultDomain, 'DERIVED_FACT')
  assert.equal(spec.sourceEvidence.reference, '已批准的现场计量标准')
  assert.equal('evaluatedOutput' in spec, false)
  assert.deepEqual(spec.dependencies, [])
})
test('editing supported drafts preserves original provenance and optional mapping; complex contracts stay technical', () => {
  const original = specificationFromRuleDraft(ruleDraftFromSpecification({}), { code:'A',version:'V1' })
  Object.assign(original, { sourceEvidence:{ reference:'原依据',auditReference:'KEEP' },sourceFormatMapping:newFormatMapping(),priority:5 })
  const draft = ruleDraftFromSpecification(original)
  draft.scale = 4
  const spec = specificationFromRuleDraft(draft, { code:'A',version:'V1' }, original)
  assert.equal(spec.sourceEvidence.auditReference, 'KEEP')
  assert.deepEqual(spec.sourceFormatMapping, original.sourceFormatMapping)
  assert.equal(spec.priority, 5)
  assert.equal(spec.outputScale, 4)
  assert.equal(supportsStructuredRule({ ...original,inputs:[...original.inputs,...original.inputs] }), false)
  assert.equal(supportsStructuredRule({ ...original,manufacturing:{ modeId:1 } }), false)
  assert.equal(supportsStructuredRule({ ...original,factExtension:{ strategy:'SCOPE_SUM' } }), false)
})
test('invalid technical JSON and precision cannot become a silently altered rule', () => {
  assert.throws(() => parseObject('[]'), /对象/)
  assert.throws(() => parseObject('{'), SyntaxError)
  const draft = { ...ruleDraftFromSpecification({}),precision:4,scale:5 }
  assert.throws(() => specificationFromRuleDraft(draft, { code:'A',version:'V1' }), /精度/)
})
test('native preview must match submitted reference, raw source and complete server projections', () => {
  const submitted = sourcePayloadFromDraft({ rule,rawText:'量\n0',rowIndex:'0' })
  const normalization = { rawContentHash:'b'.repeat(64),rowCount:1,selectedRow:0 }
  const canonicalInputs = { amount:{ value:'0',valueType:'decimal',unit:'m2' } }
  const result = { factSource:'server',businessWriteCount:0,auditWriteCount:0,normalization,canonicalInputs,
    normalizedPayload:{ ...submitted,normalization,canonicalInputs } }
  assert.equal(validateSourceFormatPreview(result, submitted), result)
  assert.throws(() => validateSourceFormatPreview({ ...result,normalizedPayload:{ ...result.normalizedPayload,rawContent:'量\n999' } }, submitted), /原文/)
  assert.throws(() => validateSourceFormatPreview({ ...result,canonicalInputs:{ amount:{ value:'5' } } }, submitted), /快照/)
  assert.throws(() => validateSourceFormatPreview({ ...result,businessWriteCount:1 }, submitted), /不一致/)
})
test('explicit source selectors preserve typed scalar intent without coercing text or null to zero', () => {
  assert.deepEqual(explicitTraceConditions([
    { key:'AreaType',valueType:'string',value:'VISIBLE_AREA' }, { key:'Pass',valueType:'boolean',value:'false' },
    { key:'Revision',valueType:'integer',value:'2' }, { key:'Missing',valueType:'null',value:'' },
    { key:'TextZero',valueType:'string',value:'0' },
  ]), { AreaType:'VISIBLE_AREA',Pass:false,Revision:2,Missing:null,TextZero:'0' })
  assert.throws(() => explicitTraceConditions([]), /至少/)
  assert.throws(() => explicitTraceConditions([{ key:'x',valueType:'integer',value:'0.5' }]), /整数/)
  assert.throws(() => explicitTraceConditions([{ key:'x',valueType:'integer',value:'9007199254740993' }]), /整数/)
  assert.throws(() => explicitTraceConditions([{ key:'x',valueType:'string',value:'' }, { key:'x',valueType:'null' }]), /重复/)
  assert.throws(() => explicitTraceConditions([{ key:'x\ny',valueType:'string',value:'' }]), /控制字符/)
})

const blob = () => ({ contractVersion:WORKBOOK_BLOB_CONTRACT,storageKey:`${'b'.repeat(64)}.xlsx`,sha256:'b'.repeat(64),bytes:2345,originalName:'新来源.xlsx' })
const sourceContext = () => ({ objectSourceRecordId:87,baselineId:93,baselineSnapshotHash:'c'.repeat(64),label:'服务端已确认对象范围' })
const workbookRule = () => ({ ...rule,specification:{ sourceFormatMapping:{ contractVersion:'PCE-SOURCE-FORMAT-MAPPING-V1',format:'XLSX_ADAPTER',adapterContract:'APPROVED-TEST',sheets:[] } } })
function workbookPreview(submitted) {
  const canonicalInputs = { SLOT:{ value:null,valueType:'decimal',unit:'m',adapterSlot:'SLOT',sourceCell:'AB12',sourceSheet:'当前表',headerCell:'AB9',headerValue:'正式表头' } }
  const normalization = { format:'XLSX_ADAPTER',rowCount:1,selectedRow:0,rawContentHash:submitted.rawContent.sha256,
    sourceFormatReference:submitted.sourceFormatReference,sourceScope:{ ...submitted.sourceContext,objectCount:1,statusLabel:'正式范围已核对' },rows:[{ rowNumber:0,canonicalInputs }] }
  return { factSource:'server',businessWriteCount:0,auditWriteCount:0,normalization,canonicalInputs,normalizedPayload:{ ...submitted,normalization,canonicalInputs } }
}
test('XLSX source serializes only exact uploaded file, mapping reference and server baseline identity', () => {
  const file = blob(), context = sourceContext()
  const payload = sourcePayloadFromDraft({ rule:workbookRule(),rawText:'never parsed as workbook',rowIndex:'',workbookBlob:file,sourceContext:context }, { normalization:{ stale:true },canonicalInputs:{ wrong:'99' },metadata:'preserved' })
  assert.deepEqual(payload.rawContent,file)
  assert.notEqual(payload.rawContent,file)
  assert.deepEqual(payload.sourceContext,{ objectSourceRecordId:87,baselineId:93,baselineSnapshotHash:'c'.repeat(64) })
  assert.equal(payload.metadata,'preserved')
  assert.equal('canonicalInputs' in payload,false)
  assert.equal('normalization' in payload,false)
  assert.equal('sourceFormatRow' in payload,false)
  assert.equal(workbookContextKey(context),JSON.stringify([87,93,'c'.repeat(64)]))
  assert.deepEqual(newWorkbookMappingSheet(),{ sheetName:'',sourceRows:[],fields:[] })
})
test('XLSX draft cannot use an arbitrary file path, fake file hash, zero bytes or missing baseline proof', () => {
  const draft = { rule:workbookRule(),workbookBlob:blob(),sourceContext:sourceContext() }
  for (const bad of [{ ...blob(),storageKey:'../source.xlsx' },{ ...blob(),sha256:'wrong' },{ ...blob(),bytes:0 }]) {
    assert.throws(() => sourcePayloadFromDraft({ ...draft,workbookBlob:bad }),/服务端存储身份/)
  }
  for (const bad of [undefined,{ ...sourceContext(),baselineSnapshotHash:'' },{ ...sourceContext(),baselineId:0 }]) {
    assert.throws(() => sourcePayloadFromDraft({ ...draft,sourceContext:bad }),/已确认对象及基线/)
  }
})
test('XLSX native preview binds file bytes, full source scope, mapping and unchanged normalized payload', () => {
  const submitted = sourcePayloadFromDraft({ rule:workbookRule(),workbookBlob:blob(),sourceContext:sourceContext() })
  const result = workbookPreview(submitted)
  assert.equal(validateSourceFormatPreview(result,submitted),result)
  assert.equal(result.canonicalInputs.SLOT.value,null)
  assert.equal(result.canonicalInputs.SLOT.adapterSlot,'SLOT')
  assert.equal(result.canonicalInputs.SLOT.sourceCell,'AB12')
  for (const change of [
    value => { value.normalizedPayload.sourceContext.baselineId = 94 },
    value => { value.normalization.sourceScope.objectSourceRecordId = 88 },
    value => { value.normalization.rawContentHash = 'd'.repeat(64) },
    value => { value.normalization.sourceFormatReference.ruleVersion = 'different' },
    value => { value.normalization.rows = [] },
  ]) {
    const changed = JSON.parse(JSON.stringify(result));change(changed)
    assert.throws(() => validateSourceFormatPreview(changed,submitted),/不一致/)
  }
})
test('structured JSON identity ignores object key order while preserving array order, exact types and raw text', () => {
  const submitted = sourcePayloadFromDraft({ rule:workbookRule(),workbookBlob:{ ...blob(),storageKey:`8/${blob().sha256}.xlsx` },sourceContext:sourceContext() })
  const result = workbookPreview(submitted)
  const sort = value => Array.isArray(value) ? value.map(sort) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).sort(([a],[b]) => a.localeCompare(b)).map(([key,item]) => [key,sort(item)])) : value
  assert.equal(validateSourceFormatPreview(sort(result),submitted).factSource,'server')
  const changed = sort(result);changed.normalizedPayload.rawContent.bytes=String(submitted.rawContent.bytes)
  assert.throws(() => validateSourceFormatPreview(changed,submitted),/不一致/)
  const csv = sourcePayloadFromDraft({ rule,rawText:'量\n0' }),preview = { factSource:'server',businessWriteCount:0,auditWriteCount:0,normalization:{ rawContentHash:'a'.repeat(64) },canonicalInputs:{ list:[0,null] } }
  preview.normalizedPayload={ ...csv,normalization:preview.normalization,canonicalInputs:{ list:[null,0] } }
  assert.throws(() => validateSourceFormatPreview(preview,csv),/不一致/)
})
test('upload proves file storage only and never implies a registered or confirmed business source', () => {
  const result = { factSource:'server',blob:blob(),sourceFileStored:true,businessWriteCount:0,auditWriteCount:0 }
  assert.deepEqual(validateWorkbookUpload(result),blob())
  for (const change of [{ businessWriteCount:1 },{ auditWriteCount:1 },{ sourceFileStored:false },{ factSource:'client' }]) {
    assert.throws(() => validateWorkbookUpload({ ...result,...change }),/未返回/)
  }
  const namespaced={ ...result,blob:{ ...blob(),storageKey:`8/${blob().sha256}.xlsx` } }
  assert.equal(validateWorkbookUpload(namespaced,8),namespaced.blob)
  assert.throws(() => validateWorkbookUpload(namespaced,9),/服务端存储身份/)
  for (const storageKey of [`../${blob().sha256}.xlsx`,`8/../${blob().sha256}.xlsx`,`/8/${blob().sha256}.xlsx`,`8/extra/${blob().sha256}.xlsx`]) {
    assert.throws(() => validateWorkbookUpload({ ...result,blob:{ ...blob(),storageKey } },8),/服务端存储身份/)
  }
})
test('workbook catalog keeps exact server order and distinguishes no candidates from read failure', () => {
  const result = { factSource:'server',businessWriteCount:0,workbookSources:[{ id:9 },{ id:4 }],sourceContexts:[sourceContext()],sourceIntakeAllowed:false,sourceIntakeStatusLabel:'仅承接核算方法来源' }
  assert.equal(validateWorkbookCatalog(result),result)
  assert.deepEqual(result.workbookSources.map(row => row.id),[9,4])
  assert.equal(result.sourceIntakeAllowed,false)
  assert.deepEqual(validateWorkbookCatalog({ ...result,workbookSources:[],sourceContexts:[] }).workbookSources,[])
  for (const changed of [{ ...result,sourceContexts:undefined },{ ...result,businessWriteCount:1 },{ ...result,sourceContexts:[{ ...sourceContext(),baselineSnapshotHash:'' }] }]) {
    assert.throws(() => validateWorkbookCatalog(changed),/资格未知/)
  }
})
