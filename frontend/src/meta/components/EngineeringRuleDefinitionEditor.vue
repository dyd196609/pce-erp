<template>
  <section class="structured-rule-editor" data-section="structured-rule-definition">
    <label class="editor-switch"><input v-model="structured" type="checkbox" :disabled="readonly || !supported" @change="changeMode" />使用结构化安全表达式定义</label>
    <p v-if="!supported">该定义包含专用或多输入合同，继续使用原技术定义与原生校验；不会自动简化已有规则。</p>
    <template v-if="structured && supported">
      <p>维护一个正式输入及一个结果。这里只编制定义，数量求值与发布校验均由原生服务执行。</p>
      <fieldset :disabled="readonly" @input="publish" @change="publish">
        <div class="rule-grid">
          <label><span>输入规范字段</span><input v-model.trim="draft.inputName" required /></label>
          <label><span>来源类型</span><select v-model="draft.sourceType"><option v-for="[value, label] in engineeringSourceTypes" :key="value" :value="value">{{ label }}</option></select></label>
          <label><span>来源派生字段（需要时填写）</span><input v-model.trim="draft.sourceField" /></label>
          <label><span>输入值类型</span><select v-model="draft.inputType"><option value="decimal">十进制数</option><option value="integer">整数</option></select></label>
          <label><span>输入正式单位编码</span><input v-model.trim="draft.inputUnit" /></label>
          <label><span>输入单位维度</span><input v-model.trim="draft.inputDimension" required /></label>
          <label class="wide"><span>安全表达式</span><input v-model.trim="draft.expression" required /><small>使用输入字段、十进制常量及 + − × ÷ 和括号；不执行脚本。</small></label>
          <label><span>输出规范字段</span><input v-model.trim="draft.outputName" required /></label>
          <label><span>结果用途</span><select v-model="draft.resultDomain"><option v-for="[value, label] in outputDomains" :key="value" :value="value">{{ label }}</option></select></label>
          <label><span>输出值类型</span><select v-model="draft.outputType"><option value="decimal">十进制数</option><option value="integer">整数</option></select></label>
          <label><span>输出正式单位编码</span><input v-model.trim="draft.outputUnit" /></label>
          <label><span>输出单位维度</span><input v-model.trim="draft.outputDimension" required /></label>
          <label><span>运算精度</span><input v-model="draft.precision" type="number" min="1" max="50" required /></label>
          <label><span>结果小数位</span><input v-model="draft.scale" type="number" min="0" max="50" required /></label>
          <label><span>舍入方式</span><select v-model="draft.rounding"><option v-for="[value,label] in roundingOptions" :key="value" :value="value">{{ label }}</option></select></label>
          <label><span>适用范围</span><input v-model.trim="draft.scope" required /></label>
          <label class="wide"><span>正式来源依据</span><textarea v-model.trim="draft.evidence" required /></label>
        </div>
        <label class="editor-switch"><input :checked="Boolean(mapping)" type="checkbox" @change="toggleMapping($event.target.checked)" />维护原始格式及字段映射</label>
        <SourceFormatMappingEditor v-if="mapping" :model-value="mapping" :readonly="readonly" @update:model-value="setMapping" />
      </fieldset>
    </template>
    <p v-if="error" role="alert" class="editor-error">{{ error }}</p>
    <details class="technical-definition"><summary>技术定义与兼容维护（默认收起）</summary>
      <p>专用规则及已有复杂合同保留技术定义；手动编辑会退出结构化维护。</p>
      <textarea :value="modelValue" :readonly="readonly" aria-label="规则规范技术原文" @input="editTechnical($event.target.value)" />
    </details>
  </section>
</template>
<script setup>
import { reactive, ref, watch } from 'vue'
import SourceFormatMappingEditor from './SourceFormatMappingEditor.vue'
import { engineeringSourceTypes, outputDomains, newFormatMapping, parseObject, supportsStructuredRule,
  ruleDraftFromSpecification, specificationFromRuleDraft } from '@/meta/runtime/sourceFormatMaintenanceForm.js'
const props = defineProps({ modelValue: { type: String, default: '' }, ruleCode: { type: String, default: '' },
  ruleVersion: { type: String, default: 'V1.0' }, readonly: Boolean })
const emit = defineEmits(['update:modelValue', 'validity'])
const draft = reactive(ruleDraftFromSpecification({})), mapping = ref(null), structured = ref(true), supported = ref(true), error = ref('')
let base = {}, emitted = null
const roundingOptions = [['ROUND_HALF_UP','四舍五入'],['ROUND_HALF_EVEN','五留双'],['ROUND_DOWN','向零舍入'],
  ['ROUND_UP','远离零舍入'],['ROUND_CEILING','向正无穷舍入'],['ROUND_FLOOR','向负无穷舍入'],['ROUND_HALF_DOWN','五舍入']]
function hydrate(value) {
  if (value === emitted) return
  try {
    base = parseObject(value)
    supported.value = supportsStructuredRule(base)
    structured.value = supported.value
    Object.assign(draft, ruleDraftFromSpecification(base))
    mapping.value = base.sourceFormatMapping || null
    error.value = ''
    emit('validity', true)
  } catch (failure) { supported.value = false; structured.value = false; error.value = failure.message; emit('validity', false) }
}
function publish() {
  if (props.readonly || !structured.value || !supported.value) return
  try {
    const spec = specificationFromRuleDraft(draft, { code: props.ruleCode, version: props.ruleVersion || 'V1.0' }, base)
    if (mapping.value) spec.sourceFormatMapping = mapping.value
    else delete spec.sourceFormatMapping
    emitted = JSON.stringify(spec, null, 2)
    emit('update:modelValue', emitted)
    emit('validity', true)
    error.value = ''
  } catch (failure) { error.value = failure.message; emit('validity', false) }
}
function toggleMapping(enabled) { mapping.value = enabled ? newFormatMapping({ canonicalName:draft.inputName,sourceType:draft.sourceType,
  valueType:draft.inputType,unit:draft.inputUnit,unitDimension:draft.inputDimension }) : null; publish() }
function setMapping(value) { mapping.value = value; publish() }
function changeMode() {
  if (structured.value) { Object.assign(draft, ruleDraftFromSpecification(base)); mapping.value = base.sourceFormatMapping || mapping.value; publish() }
}
function editTechnical(value) { structured.value = false; emitted = value; emit('update:modelValue', value)
  try { base = parseObject(value); supported.value = supportsStructuredRule(base); error.value = ''; emit('validity', true) }
  catch (failure) { error.value = failure.message; emit('validity', false) } }
watch(() => props.modelValue, hydrate, { immediate: true })
watch(() => [props.ruleCode, props.ruleVersion], publish)
</script>
<style scoped>
.structured-rule-editor{margin:16px 0;padding:14px;border:1px solid #cbd5e1;border-radius:8px}.rule-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.rule-grid label{min-width:0}.wide{grid-column:span 3}.rule-grid span{display:block;margin-bottom:5px}.editor-switch{display:block;margin:10px 0}.editor-switch input{width:auto;margin-right:7px}fieldset{border:0;padding:0}input,select,textarea{box-sizing:border-box;width:100%;padding:8px;border:1px solid #b9c5d4;border-radius:5px}textarea{min-height:70px}.technical-definition{margin-top:14px}.technical-definition textarea{min-height:230px;font-family:monospace}.editor-error{color:#a32020}@media(max-width:900px){.rule-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.wide{grid-column:span 2}}@media(max-width:600px){.rule-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
