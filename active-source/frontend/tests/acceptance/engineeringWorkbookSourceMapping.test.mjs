import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import * as Vue from 'vue'
import * as SSR from 'vue/server-renderer'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as forms from '../../src/meta/runtime/sourceFormatMaintenanceForm.js'

// Synthetic UI fixtures exercise the actual component functions and templates; no business service is invoked.
const plain = value => JSON.parse(JSON.stringify(value))
const sourceFile = name => fs.readFileSync(new URL(`../../src/meta/${name}`, import.meta.url), 'utf8')
function parsed(name) {
  const source = sourceFile(name), descriptor = parse(source).descriptor
  return { source, descriptor, compiled:compileScript(descriptor,{ id:name }) }
}
function behavior(name, functions, variables = []) {
  const { descriptor, compiled } = parsed(name)
  return compiled.scriptSetupAst.filter(node => node.type === 'FunctionDeclaration' && functions.includes(node.id.name)
    || node.type === 'VariableDeclaration' && node.declarations.some(item => variables.includes(item.id.name)))
    .map(node => descriptor.scriptSetup.content.slice(node.start,node.end)).join('\n')
}
function deferred() { let resolve,reject; const promise = new Promise((done,fail) => { resolve=done;reject=fail }); return { promise,resolve,reject } }
const blob = () => ({ contractVersion:forms.WORKBOOK_BLOB_CONTRACT,storageKey:`1/${'a'.repeat(64)}.xlsx`,sha256:'a'.repeat(64),bytes:3456,originalName:'当前来源.xlsx' })
const context = () => ({ objectSourceRecordId:71,baselineId:81,baselineSnapshotHash:'b'.repeat(64),label:'已确认的当前对象范围' })
const rule = () => ({ id:51,company_id:1,status:'released',rule_name:'工作簿正式映射',version:'V2',specificationHash:'c'.repeat(64),specification:{ sourceFormatMapping:{ contractVersion:forms.SOURCE_FORMAT_CONTRACT,format:'XLSX_ADAPTER',adapterContract:'APPROVED-SYNTHETIC',sheets:[] } } })
function previewResult(submitted) {
  const canonicalInputs = { LENGTH:{ value:'0',unit:'m',valueType:'decimal',adapterSlot:'LENGTH',sourceSheet:'正式工作表',sourceCell:'BC12',headerCell:'BC9',headerValue:'当前长度' },UNKNOWN:{ value:null,unit:'m',valueType:'decimal' } }
  const normalization = { format:'XLSX_ADAPTER',rawContentHash:submitted.rawContent.sha256,rowCount:1,selectedRow:0,sourceFormatReference:submitted.sourceFormatReference,
    sourceScope:{ ...submitted.sourceContext,objectCount:1,statusLabel:'正式范围一致' },rows:[{ canonicalInputs }] }
  return { factSource:'server',businessWriteCount:0,auditWriteCount:0,normalization,canonicalInputs,normalizedPayload:{ ...submitted,canonicalInputs,normalization } }
}
const inputFunctions = ['payload','updateDraft','uploadWorkbook','preview']
const inputComputed = ['availableRules','selectedRule','isWorkbook','selectedContext','identity','currentPreview']
function inputHarness(options = {}) {
  const props = Vue.reactive({ companyId:1,rules:[rule()],workbookContexts:[context()],rulesError:'',workbookContextsError:'',readonly:false })
  const events = [], calls = []
  const state = { props,mapped:Vue.ref(true),selectedRuleId:Vue.ref('51'),rawText:Vue.ref(''),rowIndex:Vue.ref(''),workbookBlob:Vue.ref(blob()),selectedContextKey:Vue.ref(forms.workbookContextKey(context())),
    error:Vue.ref(''),busy:Vue.ref(false),previewResult:Vue.ref(null),draftValid:Vue.ref(false) }
  const dependencies = { ...Vue,...forms,...state,emit:(...event) => events.push(plain(event)),pdeApi:{
    async previewSourceFormat(payload) { calls.push(['preview',plain(payload)]);return options.preview ? options.preview(payload) : previewResult(payload) },
    async uploadSourceWorkbook(file) { calls.push(['upload',file.name]);return options.upload ? options.upload(file) : { factSource:'server',sourceFileStored:true,businessWriteCount:0,auditWriteCount:0,blob:blob() } },
  } }
  const methods = vm.runInNewContext(`let base={}, emitted=null, requestId=0; ${behavior('components/EngineeringSourceFormatInput.vue',inputFunctions,inputComputed)}; ({ ${[...inputFunctions,...inputComputed].join(',')} })`,dependencies)
  return { ...state,methods,calls,events }
}

test('workbook API uses the original source maintenance and batch endpoints with exact intent', () => {
  const requests = []
  class Multipart { constructor() { this.items=[] } append(...entry) { this.items.push(entry) } }
  const source = fs.readFileSync(new URL('../../src/api/pde.js',import.meta.url),'utf8')
  const api = vm.runInNewContext(`${source.replace(/^import .*$/m,'').replace('export const pdeApi','const pdeApi')}; pdeApi`,{ request:value => { requests.push(value);return value },FormData:Multipart })
  const file = { name:'chosen.xlsx' }
  api.uploadSourceWorkbook(file)
  assert.deepEqual(plain(requests[0].data.items),[['action','upload-workbook'],['file',file]])
  assert.equal(requests[0].url,'/api/pde/a1-foundation/engineering-source-records/')
  api.calculationBatchCatalog({ action:'workbookSources' })
  api.calculationBatchCatalog({ workbookSourceRecordId:12 })
  api.calculateSourceBatch(['sheet:12'],{ workbookSourceRecordId:12 })
  api.engineeringDesignCalculationContext(9,{ includeWorkloadSummary:false,workbookSourceRecordId:12 })
  api.formalEngineeringContinuation('ORDER',{ workbookSourceRecordId:12 })
  assert.deepEqual(plain(requests[1].params),{ action:'workbookSources' })
  assert.equal(requests[2].params.workbookSourceRecordId,12)
  assert.deepEqual(plain(requests[3].data),{ sourceKeys:['sheet:12'],workbookSourceRecordId:12 })
  assert.equal(requests[4].params.workbookSourceRecordId,12)
  assert.equal(requests[5].params.workbookSourceRecordId,12)
  api.engineeringDesignCalculationContext('',{ workbookSourceRecordId:'' })
  assert.equal(Object.hasOwn(requests[6].params,'workbookSourceRecordId'),false)
})

test('source component publishes exact native preview and preserves zero, null, slot and actual coordinate', async () => {
  const f = inputHarness();f.methods.updateDraft();await f.methods.preview()
  assert.equal(f.methods.currentPreview.value.canonicalInputs.LENGTH.value,'0')
  assert.equal(f.methods.currentPreview.value.canonicalInputs.UNKNOWN.value,null)
  assert.equal(f.methods.currentPreview.value.canonicalInputs.LENGTH.adapterSlot,'LENGTH')
  assert.equal(f.methods.currentPreview.value.canonicalInputs.LENGTH.sourceCell,'BC12')
  assert.equal(f.events.at(-1)[0],'validity');assert.equal(f.events.at(-1)[1],true)
  assert.deepEqual(f.calls.map(row => row[0]),['preview'])
})
test('changing a source selection while preview is pending discards the previous response', async () => {
  const pending = deferred();let submitted
  const f = inputHarness({ preview:payload => { submitted=payload;return pending.promise } })
  f.methods.updateDraft();const reading=f.methods.preview()
  f.rowIndex.value='1';f.methods.updateDraft();pending.resolve(previewResult(submitted));await reading
  assert.equal(f.methods.currentPreview.value,null)
  assert.equal(f.events.some(event => event[0] === 'validity' && event[1] === true),false)
  assert.equal(f.busy.value,false)
})
test('upload stores only a blob reference and never calls source save, confirm or numeric evaluation', async () => {
  const f=inputHarness();f.workbookBlob.value=null
  await f.methods.uploadWorkbook({ target:{ files:[{ name:'chosen.xlsx' }],value:'selected' } })
  assert.deepEqual(f.calls,[['upload','chosen.xlsx']])
  assert.equal(f.methods.currentPreview.value,null)
  assert.equal(f.events.some(event => event[0] === 'validity' && event[1] === true),false)
  assert.deepEqual(plain(f.methods.payload().rawContent),blob())
})
test('company or baseline changes cannot admit an old upload response or an unlisted scope', async () => {
  const pending=deferred(),f=inputHarness({ upload:() => pending.promise })
  f.workbookBlob.value=null
  const uploading=f.methods.uploadWorkbook({ target:{ files:[{ name:'chosen.xlsx' }],value:'selected' } })
  f.props.companyId=2;f.methods.updateDraft()
  pending.resolve({ factSource:'server',sourceFileStored:true,businessWriteCount:0,auditWriteCount:0,blob:blob() });await uploading
  assert.equal(f.workbookBlob.value,null)
  const g=inputHarness();g.props.workbookContexts=[];g.methods.updateDraft()
  assert.equal(g.draftValid.value,false);assert.match(g.error.value,/正式范围|已确认对象/)
})
test('native source failure reasons remain visible and never become an empty valid preview or stored file', async () => {
  const nativeFailure={ success:false,data:null,error:{ code:'WORKBOOK_SCOPE_MISMATCH',message:'原生校验：工作簿与已确认对象范围不一致' } }
  const f=inputHarness({ preview:() => nativeFailure });f.methods.updateDraft();await f.methods.preview()
  assert.equal(f.methods.currentPreview.value,null);assert.equal(f.error.value,nativeFailure.error.message)
  const g=inputHarness({ upload:() => nativeFailure });await g.methods.uploadWorkbook({ target:{ files:[{ name:'wrong.xlsx' }],value:'selected' } })
  assert.equal(g.workbookBlob.value,null);assert.equal(g.error.value,nativeFailure.error.message)
  assert.equal(g.events.some(event => event[0] === 'validity' && event[1] === true),false)
})

function mappingHarness() {
  const props=Vue.reactive({ modelValue:forms.newFormatMapping() })
  const functions=['update','changeFormat','updateSheet','updateSheetRows','addSheet','removeSheet','updateField','addField','removeField']
  const code=behavior('components/SourceFormatMappingEditor.vue',functions,['isWorkbook','editorFields'])
  const methods=vm.runInNewContext(`${code}; ({ ${[...functions,'editorFields'].join(',')} })`,{ ...Vue,...forms,props,emit:(_,value) => { props.modelValue=value } })
  return { props,methods }
}
test('mapping maintenance updates exact sheet and field paths without a column-name business branch', () => {
  const f=mappingHarness();f.methods.changeFormat('XLSX_ADAPTER');f.methods.updateSheet(0,'sheetName','甲表');f.methods.updateSheetRows(0,'12,13')
  f.methods.addField(0);f.methods.addSheet();f.methods.updateSheet(1,'sheetName','乙表');f.methods.addField(1)
  f.methods.updateField(1,'canonicalName','STABLE_SLOT');f.methods.updateField(1,'rawField','BC');f.methods.updateField(1,'headerCell','BC9');f.methods.updateField(1,'headerValue','真实表头')
  f.methods.updateField(1,'baselinePath','source.rawValue.length');f.methods.updateField(1,'designOverrideField','designLength');f.methods.updateField(1,'identity',true)
  assert.deepEqual(plain(f.props.modelValue.sheets[0].sourceRows),[12,13])
  assert.equal(f.props.modelValue.sheets[0].fields[0].canonicalName,'')
  assert.equal(f.props.modelValue.sheets[1].fields[0].rawField,'BC')
  assert.equal(f.props.modelValue.sheets[1].fields[0].identity,true)
  f.methods.updateSheetRows(1,'-1,not-a-row')
  assert.deepEqual(plain(f.props.modelValue.sheets[1].sourceRows),['-1','not-a-row'])
  f.methods.removeField(0);assert.equal(f.props.modelValue.sheets[0].fields.length,0)
})

function batchHarness(options = {}) {
  const props=Vue.reactive({ nonProduction:true,workbookSourceRecordId:'12' }),calls=[]
  const state={ props,catalog:Vue.ref(null),result:Vue.ref(null),phase:Vue.ref('idle'),error:Vue.ref(''),message:Vue.ref(''),catalogStale:Vue.ref(false),resultStale:Vue.ref(false),detail:Vue.ref(null),keys:Vue.ref(['sheet:12']) }
  state.busy=Vue.computed(() => ['loading','running'].includes(state.phase.value))
  const file=parsed('components/EngineeringCalculationBatchPanel.vue')
  const functions=file.compiled.scriptSetupAst.filter(node => node.type === 'FunctionDeclaration' && !['handleExportCurrent','showGroup'].includes(node.id.name)).map(node => node.id.name)
  const watchNode=file.compiled.scriptSetupAst.find(node => node.type === 'ExpressionStatement' && file.descriptor.scriptSetup.content.slice(node.start,node.end).startsWith('watch(() => props.workbookSourceRecordId'))
  const code=behavior('components/EngineeringCalculationBatchPanel.vue',functions)
  const methods=vm.runInNewContext(`let readSequence=0;${code};${file.descriptor.scriptSetup.content.slice(watchNode.start,watchNode.end)};({load,execute})`,{
    ...Vue,...state,clearFilters:() => calls.push(['clear']),pdeApi:{ async calculationBatchCatalog(params) { calls.push(['catalog',plain(params)]);return options.catalog ? options.catalog(params) : catalogResponse(params.workbookSourceRecordId) },async calculateSourceBatch(keys,params) { calls.push(['calculate',plain(keys),plain(params)]);return options.result ? options.result(params) : resultResponse(params.workbookSourceRecordId) } },
  })
  return { ...state,methods,calls }
}
const catalogResponse=id => ({ success:true,data:{ workbookSourceRecordId:id,version:'VERSION',sources:[{ key:'sheet:12',sheet:'sheet',row:12,businessInputs:[],inputs:{} }],capabilities:[],families:[],gaps:[],history:{ components:[],veneer:{ rows:[] },board:{ rows:[] },edges:[],roomDoor:[],roomDoorSummary:{ physicalEdgeCount:0 } } } })
const resultResponse=id => ({ success:true,data:{ workbookSourceRecordId:id,sourceCount:1,completedAt:'2026-10-19T00:00:00Z',rows:[],totals:[],segments:[],counts:{} } })
test('original batch catalog and calculation use the selected source and reject a wrong-source response', async () => {
  const f=batchHarness();await f.methods.load();await f.methods.execute()
  assert.equal(f.catalog.value.workbookSourceRecordId,12);assert.equal(f.result.value.workbookSourceRecordId,12)
  assert.deepEqual(f.calls.slice(0,2),[['catalog',{ workbookSourceRecordId:12 }],['calculate',['sheet:12'],{ workbookSourceRecordId:12 }]])
  const wrong=batchHarness({ catalog:() => catalogResponse(99) });await wrong.methods.load()
  assert.equal(wrong.catalog.value,null);assert.equal(wrong.phase.value,'catalog_failed');assert.match(wrong.error.value,/workbookSourceRecordId/)
})
test('changing source during a batch read keeps the new catalog and discards the old late response', async () => {
  const pending=deferred(),f=batchHarness({ catalog:params => params.workbookSourceRecordId === 12 ? pending.promise : catalogResponse(params.workbookSourceRecordId) })
  const reading=f.methods.load();f.props.workbookSourceRecordId='13';await Vue.nextTick();await new Promise(setImmediate)
  assert.ok(f.catalog.value,JSON.stringify({ calls:f.calls,phase:f.phase.value,error:f.error.value }))
  assert.equal(f.catalog.value.workbookSourceRecordId,13)
  pending.resolve(catalogResponse(12));await reading
  assert.equal(f.catalog.value.workbookSourceRecordId,13);assert.equal(f.phase.value,'ready')
})
test('wrong-source calculation cannot replace the last good batch, and a late old calculation is discarded', async () => {
  const wrong=batchHarness({ result:() => resultResponse(99) });await wrong.methods.load()
  const previous=resultResponse(11).data;wrong.result.value=previous
  await wrong.methods.execute()
  assert.equal(wrong.result.value.workbookSourceRecordId,11);assert.equal(wrong.resultStale.value,true)
  assert.equal(wrong.phase.value,'batch_failed');assert.match(wrong.error.value,/workbookSourceRecordId/)
  const pending=deferred(),f=batchHarness({ result:() => pending.promise });await f.methods.load()
  const calculating=f.methods.execute();f.props.workbookSourceRecordId='13';await Vue.nextTick();await new Promise(setImmediate)
  pending.resolve(resultResponse(12));await calculating
  assert.equal(f.result.value,null);assert.equal(f.catalog.value.workbookSourceRecordId,13)
  assert.equal(f.calls.filter(row => row[0] === 'calculate').length,1)
})

function continuationHarness(options = {}) {
  const actions=[{ actionCode:'preview',allowed:true },{ actionCode:'execute',allowed:true }],calls=[],messages=[]
  const selectedSource={ id:12,contentHash:'d'.repeat(64),sourceVersion:'SOURCE-V2',formatRule:{ ruleId:51,ruleVersion:'V2',specificationHash:'c'.repeat(64) } }
  const record={ id:201,newCalculationId:501,predecessorCalculationId:301,orderEngineeringBaselineId:403,workbookSourceRecordId:12,stateMachineConsistent:true,requestStatus:'COMMITTED',statusLabel:'原生接续已提交' }
  const proof={ sourceRecordId:12,contentHash:selectedSource.contentHash,workbookSha256:selectedSource.contentHash,sourceVersion:selectedSource.sourceVersion,mappingRuleId:51,mappingRuleVersion:'V2',mappingSpecificationHash:'c'.repeat(64) }
  const detail={ id:501,companyId:1,salesOrderItemId:103,orderEngineeringInstanceId:202,status:'completed',trace:{ baselineReference:{ id:403 },workbookSource:proof } }
  const state={ selectedOrder:Vue.ref({ salesOrderItemId:103,orderNo:'ORDER-A',sourceRecordId:41,isSourceTrial:false }),formalContinuationLine:Vue.ref({ orderEngineeringInstanceId:202,calculationContinuation:{ predecessorCalculations:[{ id:301 }],availableActions:actions,records:[] } }),formalBaselines:Vue.ref([{ id:403 }]),selectedBaselineId:Vue.ref(403),selectedPredecessorCalculationId:Vue.ref(301),selectedWorkbookSourceRecordId:Vue.ref('12'),workbookSources:Vue.ref([selectedSource]),permissionProfile:Vue.ref({ companyId:1,userId:7 }),formalContinuation:Vue.ref({ formalRulePackages:[{ id:71 }] }),formalBusy:Vue.ref(false),mainContinuationPreview:Vue.ref(null),mainContinuationError:Vue.ref(''),mainContinuationReadback:Vue.ref(null),writeCount:Vue.ref(0) }
  const functions=['formalRuleIds','mainContinuationPayload','mainContinuationScopeKey','resetMainContinuationPreview','previewMainContinuation','executeMainContinuation','unwrap','explain']
  const variables=['mainContinuationFacts','mainContinuationActions','mainContinuationCanExecute']
  let methods
  const dependencies={ ...Vue,...state,pdeApi:{
    async previewEngineeringCalculationVersionContinuation(payload) { calls.push(['preview',plain(payload)]);return options.preview ? options.preview(payload) : { ready:true,workbookSourceRecordId:12,expectedContextHash:'native-context',continuationBasisHash:'native-basis',availableActions:actions } },
    async executeEngineeringCalculationVersionContinuation(payload) { calls.push(['execute',plain(payload)]);return { continuation:{ id:201 },calculation:{ id:501,companyId:1 },idempotent:false } },
    async engineeringCalculation(id) { calls.push(['read',id]);return { calculation:options.detail ? options.detail(plain(detail)) : detail } },
  },ElMessageBox:{ async confirm() {} },ElMessage:{ success:value => messages.push(value) },async loadFormalContinuation() { state.formalContinuationLine.value.calculationContinuation.records=[options.record ? options.record(plain(record)) : record];methods.resetMainContinuationPreview() },async loadCalculations() {} }
  methods=vm.runInNewContext(`let mainContinuationRequestSequence=0, mainContinuationPreviewScope='';${behavior('pages/PdeOrderEngineeringCalculationPage.vue',functions,variables)};({ ${[...functions,...variables].join(',')} })`,dependencies)
  return { ...state,methods,calls,messages }
}
test('main continuation binds the explicitly selected source through native preview, execute and exact proof readback', async () => {
  const f=continuationHarness();await f.methods.previewMainContinuation();await f.methods.executeMainContinuation()
  assert.equal(f.calls[0][1].workbookSourceRecordId,12)
  assert.equal(f.calls.find(row => row[0] === 'execute')[1].workbookSourceRecordId,12)
  assert.equal(f.mainContinuationReadback.value.workbookSourceRecordId,12)
  assert.equal(f.writeCount.value,1);assert.deepEqual(f.messages,['原生接续已提交'])
})
test('a ready response from another workbook never enables native execution', async () => {
  const f=continuationHarness({ preview:() => ({ ready:true,workbookSourceRecordId:99,expectedContextHash:'wrong',continuationBasisHash:'wrong' }) })
  await f.methods.previewMainContinuation();await f.methods.executeMainContinuation()
  assert.deepEqual(f.calls.map(row => row[0]),['preview']);assert.equal(f.mainContinuationPreview.value,null)
  assert.match(f.mainContinuationError.value,/工作簿来源版本/)
})
test('zero and malformed source references remain invalid instead of becoming the empty historical selection', async () => {
  for (const value of ['0',0,'null','-1','1.5']) {
    const f=continuationHarness();f.selectedWorkbookSourceRecordId.value=value
    assert.equal(f.methods.mainContinuationPayload(),null)
    await f.methods.previewMainContinuation();assert.equal(f.calls.length,0)
    assert.equal(f.selectedWorkbookSourceRecordId.value,value)
  }
})
test('fresh readback with wrong source, file or mapping proof is not reported as saved for this selection', async () => {
  const cases=[{ record:value => ({ ...value,workbookSourceRecordId:99 }) },{ detail:value => { value.trace.workbookSource.workbookSha256='e'.repeat(64);return value } },{ detail:value => { value.trace.workbookSource.mappingSpecificationHash='f'.repeat(64);return value } }]
  for (const options of cases) {
    const f=continuationHarness(options);await f.methods.previewMainContinuation();await f.methods.executeMainContinuation()
    assert.equal(f.calls.filter(row => row[0] === 'execute').length,1)
    assert.equal(f.mainContinuationReadback.value,null);assert.equal(f.messages.length,0)
    assert.match(f.mainContinuationError.value,/工作簿、映射版本及文件指纹/)
  }
})
test('changing the selected workbook invalidates a pending main preview even when all business IDs stay the same', async () => {
  const pending=deferred(),f=continuationHarness({ preview:() => pending.promise })
  const before=f.methods.mainContinuationScopeKey(),reading=f.methods.previewMainContinuation()
  f.selectedWorkbookSourceRecordId.value='13';f.methods.resetMainContinuationPreview()
  assert.notEqual(f.methods.mainContinuationScopeKey(),before)
  pending.resolve({ ready:true,workbookSourceRecordId:12,expectedContextHash:'old',continuationBasisHash:'old' });await reading
  assert.equal(f.mainContinuationPreview.value,null);assert.equal(f.methods.mainContinuationCanExecute.value,false)
})
test('method-only source cannot invoke either original engineering-object write handler', async () => {
  const warnings=[],writes=[]
  const code=behavior('pages/PdeOrderEngineeringCalculationPage.vue',['saveDraft','saveRegisteredSource'],['workbookObjectWriteAllowed'])
  const selectedWorkbookSourceRecordId=Vue.ref('12'),workbookSourceIntake=Vue.ref({ sourceIntakeAllowed:false,sourceIntakeStatusLabel:'仅承接核算方法来源，原对象关联保持' })
  const methods=vm.runInNewContext(`${code};({saveDraft,saveRegisteredSource,workbookObjectWriteAllowed})`,{ ...Vue,selectedWorkbookSourceRecordId,workbookSourceIntake,ElMessage:{ warning:value => warnings.push(value) },pdeApi:new Proxy({}, { get:() => () => writes.push('write') }) })
  await methods.saveDraft();await methods.saveRegisteredSource()
  assert.equal(writes.length,0);assert.deepEqual(warnings,Array(2).fill(workbookSourceIntake.value.sourceIntakeStatusLabel))
  selectedWorkbookSourceRecordId.value='';assert.equal(methods.workbookObjectWriteAllowed.value,true)
})

function preflightHarness(options = {}) {
  const calls=[],messages=[]
  const state={ selectedOrder:Vue.ref({ orderNo:'ORDER-CURRENT',sourceRecordId:41 }),selectedWorkbookSourceRecordId:Vue.ref('12'),busy:Vue.ref(false),conditionPreflight:Vue.ref({ blockers:[] }),conditionPreflightOperation:Vue.reactive({ attempt:0,state:'idle',message:'' }) }
  const functions=['loadConditionPreflight','unwrap','explain','failureKind']
  const methods=vm.runInNewContext(`let conditionPreflightSequence=0;${behavior('pages/PdeOrderEngineeringCalculationPage.vue',functions)};({loadConditionPreflight})`,{ ...Vue,...state,pdeApi:{ async preflightOrderEngineeringCalculation(params) { calls.push(plain(params));return options.read ? options.read(params) : { workbookSourceRecordId:params.workbookSourceRecordId ?? null,readyForFullValidation:true,blockers:[],businessWriteSideEffectCount:0 } } },ElMessage:{ success:value => messages.push(['success',value]),warning:value => messages.push(['warning',value]),error:value => messages.push(['error',value]) } })
  return { ...state,methods,calls,messages }
}
test('actual condition-preflight API preserves the selected workbook on the existing read-only endpoint', () => {
  const requests=[],source=fs.readFileSync(new URL('../../src/api/pde.js',import.meta.url),'utf8')
  const api=vm.runInNewContext(`${source.replace(/^import .*$/m,'').replace('export const pdeApi','const pdeApi')};pdeApi`,{ request:value => { requests.push(plain(value));return value } })
  api.preflightOrderEngineeringCalculation({ orderNo:'ORDER-CURRENT',sourceRecordId:41,workbookSourceRecordId:12 })
  assert.deepEqual(requests.map(row => [row.method,row.url]),[['GET','/api/pde/a1-engineering/order-calculation/condition-preflight/']])
  assert.deepEqual(requests[0].params,{ orderNo:'ORDER-CURRENT',sourceRecordId:41,workbookSourceRecordId:12 })
})
test('actual condition-preflight caller sends the exact selected source and accepts only its current native response', async () => {
  const f=preflightHarness();await f.methods.loadConditionPreflight({ announce:true })
  assert.deepEqual(f.calls,[{ orderNo:'ORDER-CURRENT',sourceRecordId:41,workbookSourceRecordId:12 }])
  assert.equal(f.conditionPreflight.value.workbookSourceRecordId,12)
  assert.equal(f.conditionPreflightOperation.state,'completed');assert.equal(f.busy.value,false)
  const empty=preflightHarness();empty.selectedWorkbookSourceRecordId.value='';await empty.methods.loadConditionPreflight()
  assert.deepEqual(empty.calls,[{ orderNo:'ORDER-CURRENT',sourceRecordId:41 }])
  assert.equal(Object.hasOwn(empty.calls[0],'workbookSourceRecordId'),false)
})
test('late condition-preflight success from the previous workbook cannot overwrite the new scope', async () => {
  const pending=deferred(),f=preflightHarness({ read:() => pending.promise })
  const reading=f.methods.loadConditionPreflight();f.selectedWorkbookSourceRecordId.value='13'
  f.conditionPreflight.value={ marker:'new-source' };f.conditionPreflightOperation.message='new-source-loading'
  pending.resolve({ workbookSourceRecordId:12,readyForFullValidation:true,blockers:[] });await reading
  assert.deepEqual(plain(f.conditionPreflight.value),{ marker:'new-source' })
  assert.equal(f.conditionPreflightOperation.message,'new-source-loading');assert.equal(f.messages.length,0)
})
test('late old physical-file failure cannot poison the current workbook preflight state', async () => {
  const pending=deferred(),f=preflightHarness({ read:() => pending.promise })
  const reading=f.methods.loadConditionPreflight();f.selectedWorkbookSourceRecordId.value='13'
  f.conditionPreflightOperation.state='running';f.conditionPreflightOperation.message='current-workbook'
  pending.reject(Object.assign(new Error('old physical file missing'),{ response:{ status:500,data:{ code:'OLD_SOURCE_MISSING',message:'old physical file missing' } } }));await reading
  assert.equal(f.conditionPreflightOperation.state,'running');assert.equal(f.conditionPreflightOperation.message,'current-workbook')
  assert.equal(f.messages.length,0)
})
test('wrong-source condition preflight fails closed without enabling validation or retrying', async () => {
  const f=preflightHarness({ read:() => ({ workbookSourceRecordId:99,readyForFullValidation:true,blockers:[] }) })
  await f.methods.loadConditionPreflight({ announce:true })
  assert.equal(f.conditionPreflight.value.readyForFullValidation,undefined)
  assert.equal(f.conditionPreflightOperation.state,'failed');assert.match(f.conditionPreflightOperation.message,/工作簿来源版本/)
  assert.equal(f.calls.length,1);assert.equal(f.busy.value,false)
})
test('current-scope permission failure remains visible and existing request sequencing rejects an older success', async () => {
  const denied=preflightHarness({ read:() => { throw Object.assign(new Error('denied'),{ response:{ status:403,data:{ code:'READ_DENIED',message:'当前账号不能查看此范围' } } }) } })
  await denied.methods.loadConditionPreflight({ announce:true })
  assert.equal(denied.conditionPreflightOperation.state,'failed');assert.equal(denied.conditionPreflightOperation.title,'无权查看预检事实')
  assert.match(denied.conditionPreflightOperation.message,/当前账号无查看权限/);assert.equal(denied.calls.length,1)
  const pending=deferred();let calls=0
  const f=preflightHarness({ read:() => ++calls===1 ? pending.promise : { workbookSourceRecordId:12,readyForFullValidation:false,blockers:[{ reason:'current native blocker' }] } })
  const old=f.methods.loadConditionPreflight();await f.methods.loadConditionPreflight()
  pending.resolve({ workbookSourceRecordId:12,readyForFullValidation:true,blockers:[] });await old
  assert.equal(f.conditionPreflight.value.readyForFullValidation,false);assert.equal(f.conditionPreflightOperation.state,'blocked')
  assert.equal(f.conditionPreflight.value.blockers[0].reason,'current native blocker')
})

function ssrFunction(template) {
  const output=compileTemplate({ source:template,filename:'actual-component-template.vue',id:'workbook-template',ssr:true,ssrCssVars:[] })
  assert.deepEqual(output.errors,[])
  const code=output.code.replace(/import \{([^}]+)\} from ["']([^"']+)["']/g,(_,names,module) => `const {${names.replace(/ as /g,':')}}=${module === 'vue' ? 'Vue' : 'SSR'};`).replace('export function ssrRender','function ssrRender')
  return vm.runInNewContext(`${code};ssrRender`,{ Vue,SSR })
}
async function renderActual(template,state) {
  return SSR.renderToString(Vue.createSSRApp({ setup:() => state,ssrRender:ssrFunction(template),components:{ RouterLink:{ render() { return Vue.h('a',this.$slots.default?.()) } } } }))
}
test('actual source template renders formal scope, zero versus unknown and slot beside current coordinate', async () => {
  const f=inputHarness();f.methods.updateDraft();await f.methods.preview()
  const html=await renderActual(parsed('components/EngineeringSourceFormatInput.vue').descriptor.template.content,{ ...f,availableRules:f.methods.availableRules.value,selectedRule:f.methods.selectedRule.value,isWorkbook:true,workbookContexts:f.props.workbookContexts,selectedContextKey:f.selectedContextKey.value,workbookContextsError:'',rulesError:'',readonly:false,modelValue:'{}',currentPreview:f.methods.currentPreview.value,workbookContextKey:forms.workbookContextKey,updateDraft:() => {},uploadWorkbook:() => {},changeMode:() => {},preview:() => {},editTechnical:() => {} })
  for (const expected of ['正式范围一致','0 m','未知（空值）','计算槽位：LENGTH','正式工作表!BC12','BC9 · 当前长度','尚未登记或确认正式来源']) assert.ok(html.includes(expected),expected)
})
test('actual original-page source selector keeps empty historical mode and renders the server object-write boundary', async () => {
  const template=parsed('pages/PdeOrderEngineeringCalculationPage.vue').descriptor.template.content
  const start=template.indexOf('    <section v-if="permissionAllowed(CALCULATION_VIEW_PERMISSION) && !configurationSubview"')
  const fragment=template.slice(start,template.indexOf('</section>',start)+10)
  const base={ permissionAllowed:() => true,CALCULATION_VIEW_PERMISSION:'read',configurationSubview:false,selectedWorkbookSourceRecordId:'',selectedWorkbookSource:null,workbookSources:[{ id:12,label:'正式来源 · V2',statusLabel:'已确认',contentHash:'d'.repeat(64) }],loading:false,formalBusy:false,busy:false,workbookSourcesLoading:false,workbookSourcesError:'',workbookSourceIntake:{ sourceIntakeAllowed:false,sourceIntakeStatusLabel:'仅承接核算方法来源；工程对象与基线保持原关联' },selectWorkbookSource:() => {} }
  const empty=await renderActual(fragment,base)
  assert.ok(empty.includes('历史登记来源（只读）'));assert.ok(!/value="12" selected/.test(empty))
  const selected=await renderActual(fragment,{ ...base,selectedWorkbookSourceRecordId:'12',selectedWorkbookSource:base.workbookSources[0] })
  assert.ok(selected.includes(base.workbookSourceIntake.sourceIntakeStatusLabel))
  assert.ok(selected.includes(base.workbookSources[0].contentHash))
})
test('all affected SFCs compile, and original page keeps selectors, formal actions and source boundaries', async () => {
  for (const name of ['components/SourceFormatMappingEditor.vue','components/EngineeringSourceFormatInput.vue','components/ProductionFoundationMaintenance.vue','components/EngineeringCalculationBatchPanel.vue','pages/PdeOrderEngineeringCalculationPage.vue']) {
    const file=parsed(name)
    assert.deepEqual(compileTemplate({ source:file.descriptor.template.content,filename:name,id:name,compilerOptions:{ bindingMetadata:file.compiled.bindings } }).errors,[],name)
  }
  const page=parsed('pages/PdeOrderEngineeringCalculationPage.vue').source
  assert.ok(page.indexOf('data-section="workbook-source-selection"') < page.indexOf('data-section="shared-order-context"'))
  for (const action of ['createFormalInstance','confirmFormalInstanceSource','validateFormalContinuation','executeFormalContinuation']) assert.ok(page.includes(`@click="${action}"`))
  assert.match(page,/:disabled="savingRegisteredSource \|\| !workbookObjectWriteAllowed"/)
  assert.match(page,/sourceIntakeStatusLabel/)
  assert.match(page,/watch\(selectedWorkbookSourceRecordId, resetMainContinuationPreview/)
})
