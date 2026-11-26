<template>
  <section class="source-format-input" data-section="engineering-source-format-input">
    <h5>原始来源录入</h5>
    <label class="editor-switch"><input v-model="mapped" type="checkbox" :disabled="readonly" @change="changeMode" />使用已发布格式与字段映射规则</label>
    <template v-if="mapped">
      <p>规则引用及指纹来自当前公司服务端目录；规范数量仅展示原生预览结果。</p>
      <p v-if="rulesError" class="source-error" role="alert">{{ rulesError }}，当前不能选择或保存新的格式引用。</p>
      <p v-else-if="availableRules.length === 0" class="source-notice">当前公司尚无可选的已发布格式映射规则。请先从产品工程的<router-link :to="{ name:'FoundationEngineeringRuleDefinitions' }">工程规则定义</router-link>维护并按原流程发布。</p>
      <fieldset :disabled="readonly || busy">
        <div class="source-grid">
          <label><span>已发布来源格式规则</span><select v-model="selectedRuleId" required @change="updateDraft"><option value="">请选择正式格式规则</option><option v-for="rule in availableRules" :key="rule.id" :value="String(rule.id)">{{ rule.rule_name }} · {{ rule.version }} · {{ rule.specification.sourceFormatMapping.format }}</option></select></label>
          <label><span>{{ isWorkbook ? '预览行索引（从0开始，留空使用服务端默认）' : '选取行索引（从0开始，单行可留空）' }}</span><input v-model="rowIndex" inputmode="numeric" @input="updateDraft" /></label>
          <label v-if="isWorkbook"><span>已确认对象及基线范围</span><select v-model="selectedContextKey" required @change="updateDraft"><option value="">请选择正式范围</option><option v-for="context in workbookContexts" :key="workbookContextKey(context)" :value="workbookContextKey(context)">{{ context.label }}</option></select></label>
        </div>
        <p v-if="selectedRule">正式版本：{{ selectedRule.version }}；生效期：{{ selectedRule.effective_from || '未限定' }}至{{ selectedRule.effective_to || '长期有效' }}</p>
        <template v-if="isWorkbook">
          <p v-if="workbookContextsError" class="source-error" role="alert">{{ workbookContextsError }}；当前不能选取或保存工作簿对象范围。</p>
          <label><span>上传本版本原始工作簿</span><input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" @change="uploadWorkbook" /></label>
          <p v-if="workbookBlob">已存储文件：{{ workbookBlob.originalName }}；{{ workbookBlob.bytes }} 字节；SHA-256：{{ workbookBlob.sha256 }}。尚未登记或确认正式来源。</p>
          <p>文件只由服务端读取和校验。保存来源版本后，仍须使用原“确认来源”动作完成正式确认。</p>
        </template>
        <label v-else><span>{{ selectedRule?.specification.sourceFormatMapping.format === 'JSON_ROWS' ? '原始对象行（JSON数组）' : '原始CSV内容（含列名）' }}</span><textarea v-model="rawText" required class="raw-content" @input="updateDraft" /></label>
        <button type="button" class="secondary" :disabled="!draftValid || busy" @click="preview">{{ busy ? '正在原生预览…' : '只读预览格式映射' }}</button>
      </fieldset>
      <p v-if="error" class="source-error" role="alert">{{ error }}</p>
      <p v-if="!currentPreview" class="source-notice">当前草稿尚未取得原生规范化预览；保存前须完成本草稿预览。</p>
      <section v-else class="source-preview" data-section="source-format-native-preview" data-fact-source="server">
        <h6>原生规范化预览（未保存）</h6>
        <p>来源行数：{{ currentPreview.normalization.rowCount }}；选取行索引：{{ currentPreview.normalization.selectedRow }}</p>
        <p v-if="currentPreview.normalization.sourceScope">{{ currentPreview.normalization.sourceScope.statusLabel }}；对象数：{{ currentPreview.normalization.sourceScope.objectCount }}；基线：{{ currentPreview.normalization.sourceScope.baselineId }}</p>
        <dl><div v-for="(input, name) in currentPreview.canonicalInputs" :key="name"><dt>{{ name }}</dt><dd>{{ input.value === null ? '未知（空值）' : String(input.value) }} {{ input.unit || '' }} · {{ input.valueType }}<small v-if="input.adapterSlot">计算槽位：{{ input.adapterSlot }}；实际来源：{{ input.sourceSheet }}!{{ input.sourceCell }}；表头：{{ input.headerCell }} · {{ input.headerValue }}</small></dd></div></dl>
        <p>业务写入0；审计写入0。原始内容和规范化快照随来源版本保存，并由服务端重新校验。</p>
      </section>
    </template>
    <details class="technical-definition"><summary>技术快照与原有格式兼容维护</summary>
      <p>旧来源保留原格式。编辑原快照时退出结构化录入；已确认来源仍由原生命周期保护。</p>
      <textarea :value="modelValue" :readonly="readonly" aria-label="工程来源技术快照" @input="editTechnical($event.target.value)" />
    </details>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { pdeApi } from '@/api/pde.js'
import { eligibleFormatRules, parseObject, sourcePayloadFromDraft, validateSourceFormatPreview, validateWorkbookUpload, workbookContextKey, sourceFormatResponse } from '@/meta/runtime/sourceFormatMaintenanceForm.js'
const props = defineProps({ modelValue: { type: String, default: '' }, rules: { type: Array, default: () => [] },
  companyId: { type: [String, Number], default: null }, rulesError: { type: String, default: '' },
  workbookContexts: { type:Array,default:() => [] },workbookContextsError: { type:String,default:'' },readonly: Boolean })
const emit = defineEmits(['update:modelValue', 'validity', 'previewed'])
const mapped = ref(true), selectedRuleId = ref(''), rawText = ref(''), rowIndex = ref(''), error = ref(''), busy = ref(false)
const previewResult = ref(null), draftValid = ref(false)
const workbookBlob = ref(null), selectedContextKey = ref('')
const availableRules = computed(() => eligibleFormatRules(props.rules, props.companyId))
const selectedRule = computed(() => availableRules.value.find(rule => String(rule.id) === selectedRuleId.value))
const isWorkbook = computed(() => selectedRule.value?.specification.sourceFormatMapping.format === 'XLSX_ADAPTER')
const selectedContext = computed(() => props.workbookContexts.find(context => workbookContextKey(context) === selectedContextKey.value))
const identity = computed(() => JSON.stringify([props.companyId,selectedRuleId.value,selectedRule.value?.version,selectedRule.value?.specificationHash,rawText.value,rowIndex.value,workbookBlob.value,selectedContextKey.value]))
const currentPreview = computed(() => previewResult.value?.identity === identity.value ? previewResult.value.value : null)
let base = {}, emitted = null, requestId = 0
function hydrate(value) {
  if (value === emitted) return
  try {
    base = parseObject(value)
    mapped.value = !Object.keys(base).length || Boolean(base.sourceFormatReference)
    selectedRuleId.value = base.sourceFormatReference ? String(base.sourceFormatReference.ruleId) : ''
    rawText.value = typeof base.rawContent === 'string' ? base.rawContent : base.rawContent ? JSON.stringify(base.rawContent, null, 2) : ''
    workbookBlob.value = base.rawContent?.contractVersion === 'PCE-ENGINEERING-WORKBOOK-BLOB-V1' ? base.rawContent : null
    selectedContextKey.value = workbookContextKey(base.sourceContext)
    rowIndex.value = base.sourceFormatRow ?? ''
    previewResult.value = null
    draftValid.value = false
    error.value = ''
    emit('validity', !mapped.value)
  } catch (failure) { mapped.value = false; error.value = failure.message; emit('validity', false) }
}
function payload() { return sourcePayloadFromDraft({ rule:selectedRule.value,rawText:rawText.value,rowIndex:rowIndex.value,workbookBlob:workbookBlob.value,sourceContext:selectedContext.value }, base) }
function updateDraft() {
  requestId += 1
  previewResult.value = null
  emit('validity', false)
  try {
    const value = payload()
    if (!isWorkbook.value && !rawText.value) throw new Error('请填写本次真实原始内容。')
    if (isWorkbook.value && props.workbookContextsError) throw new Error(props.workbookContextsError)
    emitted = JSON.stringify(value, null, 2)
    emit('update:modelValue', emitted)
    draftValid.value = true
    error.value = ''
  } catch (failure) { error.value = failure.message; draftValid.value = false }
}
async function uploadWorkbook(event) {
  const file = event.target.files?.[0]; event.target.value = ''
  if (!file || props.readonly || busy.value || !isWorkbook.value) return
  workbookBlob.value = null; previewResult.value = null; draftValid.value = false; emit('validity', false)
  const request = ++requestId, submittedIdentity = identity.value
  busy.value = true; error.value = ''
  try {
    const response = await pdeApi.uploadSourceWorkbook(file)
    if (request !== requestId || submittedIdentity !== identity.value) return
    workbookBlob.value = validateWorkbookUpload(sourceFormatResponse(response), props.companyId)
    updateDraft()
  } catch (failure) {
    if (request !== requestId || submittedIdentity !== identity.value) return
    error.value = failure?.response?.data?.message || failure.message || '工作簿上传失败；未登记来源。'
  } finally { busy.value = false }
}
function changeMode() {
  previewResult.value = null
  requestId += 1
  if (mapped.value) updateDraft()
  else {
    try { emit('validity', !parseObject(props.modelValue).sourceFormatReference) }
    catch { emit('validity', false) }
  }
}
function editTechnical(value) {
  mapped.value = false; requestId += 1; previewResult.value = null; emitted = value; emit('update:modelValue', value)
  try { base = parseObject(value); error.value = ''; emit('validity', !base.sourceFormatReference) }
  catch (failure) { error.value = failure.message; emit('validity', false) }
}
async function preview() {
  if (!draftValid.value || props.readonly || busy.value) return
  const request = ++requestId, submittedIdentity = identity.value
  busy.value = true; error.value = ''
  try {
    const submitted = payload()
    const response = await pdeApi.previewSourceFormat(submitted)
    const result = sourceFormatResponse(response)
    if (request !== requestId || submittedIdentity !== identity.value) return
    validateSourceFormatPreview(result, submitted)
    previewResult.value = { identity:submittedIdentity,value:result }
    emitted = JSON.stringify(result.normalizedPayload, null, 2)
    emit('update:modelValue', emitted)
    emit('previewed', result)
    emit('validity', true)
  } catch (failure) {
    if (request !== requestId || submittedIdentity !== identity.value) return
    previewResult.value = null; emit('validity', false)
    error.value = failure?.response?.data?.message || failure.message || '原生格式预览读取失败。'
  } finally { busy.value = false }
}
watch(() => props.modelValue, hydrate, { immediate:true })
watch(() => [selectedRule.value?.specificationHash,props.rulesError,props.workbookContextsError,selectedContext.value?.baselineSnapshotHash,props.companyId], () => { if (mapped.value && !props.readonly) updateDraft() })
</script>
<style scoped>
.source-format-input{overflow-wrap:anywhere;margin:16px 0;padding:14px;border:1px solid #cbd5e1;border-radius:8px}.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}label span{display:block;margin:5px 0}.editor-switch input{width:auto;margin-right:7px}fieldset{border:0;padding:0}input,select,textarea{box-sizing:border-box;width:100%;padding:8px;border:1px solid #b9c5d4;border-radius:5px}.raw-content{min-height:140px}.technical-definition{margin-top:14px}.technical-definition textarea{min-height:220px;font-family:monospace}.source-error{color:#a32020}.source-notice{color:#5b6473}.source-preview{margin-top:14px;padding:10px;background:#edf5ff}dl>div{display:flex;gap:12px}dd{margin:0}dd small{display:block;margin-top:4px}button{margin-top:10px}@media(max-width:650px){.source-grid{grid-template-columns:1fr}}
</style>
