<template>
  <section class="format-mapping-editor" data-section="source-format-mapping-editor">
    <h5>原始格式与字段映射</h5>
    <p>逐列声明正式字段及原值含义；空白与0分别维护，预览及保存由服务端校验。</p>
    <fieldset :disabled="readonly">
      <div class="mapping-grid">
        <label><span>原始格式</span><select :value="modelValue.format" @change="changeFormat($event.target.value)"><option value="CSV">CSV列数据</option><option value="JSON_ROWS">JSON对象行</option><option value="XLSX_ADAPTER">工作簿字段映射</option></select></label>
        <label v-if="modelValue.format === 'CSV'"><span>列分隔符</span><input :value="modelValue.delimiter" maxlength="1" @input="update('delimiter', $event.target.value)" /></label>
        <label v-if="!isWorkbook"><span>小数分隔符</span><input :value="modelValue.decimalSeparator" maxlength="1" @input="update('decimalSeparator', $event.target.value)" /></label>
        <label v-if="!isWorkbook"><span>千分位分隔符（无则留空）</span><input :value="modelValue.thousandsSeparator" maxlength="1" @input="update('thousandsSeparator', $event.target.value)" /></label>
        <label v-if="isWorkbook"><span>已批准核算适配合同版本</span><input :value="modelValue.adapterContract" required @input="update('adapterContract', $event.target.value)" /></label>
      </div>
      <template v-if="isWorkbook">
        <p>按真实工作表、列及表头维护映射；稳定计算槽位仅引用既有核算方法。对象与基线一致性由服务端校验。</p>
        <article v-for="(sheet, sheetIndex) in modelValue.sheets || []" :key="sheetIndex" class="mapping-field">
          <div class="mapping-grid"><label><span>工作表名称</span><input :value="sheet.sheetName" required @input="updateSheet(sheetIndex, 'sheetName', $event.target.value)" /></label><label><span>实际来源行号（逗号分隔）</span><input :value="(sheet.sourceRows || []).join(',')" required @input="updateSheetRows(sheetIndex, $event.target.value)" /></label></div>
          <button type="button" class="secondary" @click="addField(sheetIndex)">为本工作表新增列映射</button>
          <button type="button" class="secondary" @click="removeSheet(sheetIndex)">移除本工作表</button>
        </article>
        <button type="button" class="secondary" @click="addSheet">新增工作表映射</button>
      </template>
      <article v-for="({ field, sheetIndex }, index) in editorFields" :key="index" class="mapping-field">
        <h6>{{ isWorkbook ? `${modelValue.sheets[sheetIndex].sheetName || '待填工作表'} · ` : '' }}第{{ index + 1 }}列映射</h6>
        <div class="mapping-grid">
          <label><span>{{ isWorkbook ? '实际工作簿列' : '原始列名' }}</span><input :value="field.rawField" required @input="updateField(index, 'rawField', $event.target.value)" /></label>
          <label><span>{{ isWorkbook ? '稳定计算槽位' : '规范字段' }}</span><input :value="field.canonicalName" required @input="updateField(index, 'canonicalName', $event.target.value)" /></label>
          <template v-if="isWorkbook">
            <label><span>实际表头单元格</span><input :value="field.headerCell" required @input="updateField(index, 'headerCell', $event.target.value)" /></label>
            <label><span>实际表头原文</span><input :value="field.headerValue" required @input="updateField(index, 'headerValue', $event.target.value)" /></label>
            <label><span>已确认对象快照字段路径</span><input :value="field.baselinePath" @input="updateField(index, 'baselinePath', $event.target.value)" /></label>
            <label><span>当前设计输入字段（适用时）</span><input :value="field.designOverrideField" @input="updateField(index, 'designOverrideField', $event.target.value)" /></label>
            <label class="checkbox-label"><input type="checkbox" :checked="field.identity === true" @change="updateField(index, 'identity', $event.target.checked)" />对象身份核对字段</label>
            <label class="checkbox-label"><input type="checkbox" :checked="field.methodReference === true" @change="updateField(index, 'methodReference', $event.target.checked)" />已批准方法的来源输入核对</label>
          </template>
          <label><span>字段来源类型</span><select :value="field.sourceType" @change="updateField(index, 'sourceType', $event.target.value)"><option v-for="[value, label] in engineeringSourceTypes" :key="value" :value="value">{{ label }}</option></select></label>
          <label><span>字段类型</span><select :value="field.valueType" @change="updateField(index, 'valueType', $event.target.value)"><option value="decimal">十进制数</option><option value="integer">整数</option><option value="text">文本</option></select></label>
          <label><span>正式单位编码（无量纲可留空）</span><input :value="field.unit" @input="updateField(index, 'unit', $event.target.value)" /></label>
          <label><span>单位维度</span><input :value="field.unitDimension" required @input="updateField(index, 'unitDimension', $event.target.value)" /></label>
          <label><span>表示0的原始文本（每行一个）</span><textarea :value="tokenText(field.zeroTokens)" @input="updateTokens(index, 'zeroTokens', $event.target.value, false)" /></label>
          <label><span>表示空白的原始文本（每行一个）</span><textarea :value="tokenText(field.blankTokens)" @input="updateTokens(index, 'blankTokens', $event.target.value, (field.blankTokens || []).includes(''))" /><span class="checkbox-label"><input type="checkbox" :checked="(field.blankTokens || []).includes('')" @change="updateTokens(index, 'blankTokens', tokenText(field.blankTokens), $event.target.checked)" />空字符串明确表示空白</span></label>
          <label><span>空白处理</span><select :value="field.blankPolicy" @change="updateField(index, 'blankPolicy', $event.target.value)"><option value="ERROR">阻断并要求补充</option><option value="NULL">保留未知值</option></select></label>
        </div>
        <button type="button" class="secondary" @click="removeField(index)">移除本列</button>
      </article>
      <button v-if="!isWorkbook" type="button" class="secondary" @click="addField()">新增列映射</button>
    </fieldset>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { engineeringSourceTypes, newMappingField, newWorkbookMappingSheet, tokensFromText } from '@/meta/runtime/sourceFormatMaintenanceForm.js'
const props = defineProps({ modelValue: { type: Object, required: true }, readonly: Boolean })
const emit = defineEmits(['update:modelValue'])
const isWorkbook = computed(() => props.modelValue.format === 'XLSX_ADAPTER')
const editorFields = computed(() => isWorkbook.value
  ? (props.modelValue.sheets || []).flatMap((sheet, sheetIndex) => (sheet.fields || []).map((field, fieldIndex) => ({ field, sheetIndex, fieldIndex })))
  : (props.modelValue.fields || []).map((field, fieldIndex) => ({ field, fieldIndex })))
function update(key, value) { emit('update:modelValue', { ...props.modelValue, [key]: value }) }
function changeFormat(format) {
  if (format === props.modelValue.format) return
  if (format === 'XLSX_ADAPTER') emit('update:modelValue', { contractVersion:props.modelValue.contractVersion,format,adapterContract:'',sheets:[newWorkbookMappingSheet()] })
  else emit('update:modelValue', { contractVersion:props.modelValue.contractVersion,format,delimiter:props.modelValue.delimiter || ',',decimalSeparator:props.modelValue.decimalSeparator || '.',thousandsSeparator:props.modelValue.thousandsSeparator || '',fields:props.modelValue.fields || [newMappingField()] })
}
function updateSheet(index, key, value) { update('sheets', props.modelValue.sheets.map((sheet, position) => position === index ? { ...sheet, [key]:value } : sheet)) }
function updateSheetRows(index, value) { updateSheet(index, 'sourceRows', value.split(/[,\s]+/).filter(Boolean).map(token => /^\d+$/.test(token) && Number.isSafeInteger(Number(token)) ? Number(token) : token)) }
function addSheet() { update('sheets', [...(props.modelValue.sheets || []),newWorkbookMappingSheet()]) }
function removeSheet(index) { update('sheets', props.modelValue.sheets.filter((_, position) => position !== index)) }
function updateField(index, key, value) {
  if (key === 'unit' && value === '') value = null
  const entry = editorFields.value[index]
  if (isWorkbook.value) updateSheet(entry.sheetIndex, 'fields', props.modelValue.sheets[entry.sheetIndex].fields.map((field, position) => position === entry.fieldIndex ? { ...field,[key]:value } : field))
  else update('fields', props.modelValue.fields.map((field, position) => position === index ? { ...field, [key]: value } : field))
}
function tokenText(values) { return (values || []).filter(value => value !== '').join('\n') }
function updateTokens(index, key, value, includeEmpty) { updateField(index, key, tokensFromText(value, includeEmpty)) }
function addField(sheetIndex) {
  if (isWorkbook.value) updateSheet(sheetIndex, 'fields', [...(props.modelValue.sheets[sheetIndex].fields || []),newMappingField()])
  else update('fields', [...props.modelValue.fields, newMappingField()])
}
function removeField(index) {
  const entry = editorFields.value[index]
  if (isWorkbook.value) updateSheet(entry.sheetIndex, 'fields', props.modelValue.sheets[entry.sheetIndex].fields.filter((_, position) => position !== entry.fieldIndex))
  else update('fields', props.modelValue.fields.filter((_, position) => position !== index))
}
</script>
<style scoped>
.format-mapping-editor{margin:16px 0;padding:14px;border:1px solid #cbd5e1;border-radius:8px}.mapping-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.mapping-grid label{min-width:0}.mapping-grid span{display:block;margin-bottom:5px}.mapping-field{margin:14px 0;padding-top:10px;border-top:1px solid #dbe3ed}fieldset{padding:0;border:0}input,select,textarea{box-sizing:border-box;width:100%;padding:8px;border:1px solid #b9c5d4;border-radius:5px}textarea{min-height:62px}.checkbox-label{font-size:12px;margin-top:5px}.checkbox-label input{width:auto}button{margin-top:9px}@media(max-width:900px){.mapping-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.mapping-grid{grid-template-columns:1fr}}
</style>
