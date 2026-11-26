<template>
  <span
    class="latest-base-data-import-toolbar-extension"
    data-latest-base-data-import-extension="PCE-LATEST-BASE-DATA-TEMPLATE-V1.0"
  >
    <span v-if="provider === 'organization'" class="target-company">导入公司：{{ targetContext?.targetCompany ? `${targetContext.targetCompany.name}（${targetContext.targetCompany.code}）` : '点击操作时核对合法目标公司' }}</span>
    <el-button
      plain
      data-acceptance-id="list-download-import-template-button"
      :disabled="templateDisabled"
      @click="downloadTemplate"
    >下载导入模板</el-button>
    <el-button
      type="success"
      plain
      data-acceptance-id="list-import-data-button"
      :disabled="importDisabled"
      :loading="importing"
      @click="chooseFile"
    >{{ importing ? '导入处理中…' : '导入数据' }}</el-button>
    <input ref="fileInput" class="file-input" type="file" :accept="xlsxOnly ? '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : '.xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv'" @change="previewFile" />
    <el-dialog v-model="dialogVisible" :title="`${entityName} · 导入预览`" width="980px" append-to-body data-acceptance-id="formal-import-preview-dialog">
      <el-steps :active="step" finish-status="success" simple class="import-steps">
        <el-step title="选择文件" /><el-step title="系统校验" /><el-step title="确认导入" /><el-step title="结果读回" />
      </el-steps>
      <p class="import-boundary">预览不会写入正式数据。请先核对“新建、匹配已有、需复核、已阻断”的行数和具体原因，再决定是否确认导入。</p>
      <el-alert v-if="busy && !preview" title="正在校验并生成导入预览，请稍候…" type="info" :closable="false" show-icon />
      <div v-if="selectedFile" class="file-summary"><strong>文件：</strong>{{ selectedFile.name }}</div>
      <div v-if="preview?.worksheetName" class="file-summary"><strong>工作表：</strong>{{ preview.worksheetName }}</div>
      <div v-if="preview && provider === 'organization'" class="summary" data-acceptance-id="formal-import-preview-summary">
        <span>总行数 {{ preview.counts.total }}</span><span>可提交 {{ preview.counts.ready }}</span>
        <span>需复核 {{ preview.counts.review }}</span><span>已阻断 {{ preview.counts.blocked }}</span>
        <span>拟新增 {{ preview.counts.create }}</span><span>匹配已有 {{ preview.counts.match }}</span>
        <span v-if="preview.counts.reference">引用已有不修改 {{ preview.counts.reference }}</span><span v-if="preview.counts.excluded">不作为部门导入 {{ preview.counts.excluded }}</span>
        <span>错误行数 {{ preview.counts.errorRows }}</span><span>错误项数 {{ preview.counts.validationErrors }}</span>
      </div>
      <div v-else-if="preview" class="summary" data-acceptance-id="formal-import-preview-summary">
        <span>总行数 {{ preview.counts.total }}</span><span>可导入（READY）{{ preview.counts.ready }}</span>
        <span>需复核（REVIEW）{{ preview.counts.review }}</span><span>已阻断（BLOCKED）{{ preview.counts.blocked }}</span>
        <span class="create">新建（CREATE）{{ preview.counts.create }}</span><span class="match">匹配已有（MATCH）{{ preview.counts.match }}</span>
        <span v-if="preview.counts.reference">引用已有不修改 {{ preview.counts.reference }}</span><span v-if="preview.counts.excluded">排除导入 {{ preview.counts.excluded }}</span>
        <span>错误 {{ preview.counts.validationErrors }}</span><span>警告 {{ preview.warnings?.length || 0 }}</span>
      </div>
      <el-alert v-if="preview" class="replay-tip" title="重放验证：重复导入同一份已成功文件时，已存在且完全一致的记录会显示为“匹配已有”，不会重复创建。" type="info" :closable="false" />
      <el-table v-if="preview" :data="preview.rows" max-height="330" border>
        <el-table-column prop="rowNumber" label="源行号" width="80" />
        <el-table-column prop="identity" label="业务编码" min-width="150" />
        <el-table-column label="校验结果" width="150"><template #default="{ row }">{{ row.stateLabel }}<span v-if="provider !== 'organization'">（{{ row.state }}）</span></template></el-table-column>
        <el-table-column label="目标动作" width="150"><template #default="{ row }">{{ row.decisionLabel }}<span v-if="provider !== 'organization'">（{{ row.decision }}）</span></template></el-table-column>
        <el-table-column label="关键字段" min-width="220"><template #default="{ row }">{{ displayFields(row) }}</template></el-table-column>
        <el-table-column label="错误/建议" min-width="340">
          <template #default="{ row }">
            <template v-if="provider === 'organization'">
              <p v-for="(item,index) in row.errors" :key="`error-${index}`">{{ item.fieldLabel }}：填写“{{ item.rawValue ?? '' }}”；解析或已有值“{{ item.resolvedValue ?? '' }}”。{{ item.message }} {{ item.suggestedAction }}</p>
              <p v-for="(item,index) in row.normalizations" :key="`note-${index}`">{{ item.fieldLabel }}：{{ item.rawValue }} → {{ item.resolvedValue }}。{{ item.message }}</p>
              <details v-if="row.errors.length"><summary>技术明细</summary>{{ row.errors.map(item => `${item.field}: ${item.errorType}`).join('；') }}</details>
            </template>
            <template v-else>{{ row.errors.map(item => `${item.message} ${item.suggestedAction}`).join('；') || '-' }}</template>
          </template>
        </el-table-column>
      </el-table>
      <el-alert v-if="commitResult" class="commit-result" type="success" :closable="false" show-icon
        :title="`导入完成：新增 ${commitResult.created}，匹配 ${commitResult.matched}；正式页面已刷新读回。`" />
      <template #footer>
        <el-button v-if="preview?.errors?.length" @click="downloadErrors">下载错误报告</el-button>
        <el-button @click="dialogVisible = false">{{ commitResult ? '完成' : '取消 / 返回' }}</el-button>
        <el-button v-if="!commitResult" type="primary" data-acceptance-id="formal-import-confirm-button"
          :disabled="!preview?.canCommit || busy" :loading="busy" @click="commit">确认导入</el-button>
      </template>
    </el-dialog>
  </span>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pdeApi } from '@/api/pde.js'
import { accessControlApi } from '@/api/accessControl.js'

const props = defineProps({
  entity: { type: String, required: true },
  entityName: { type: String, default: '基础数据' },
  templateDisabled: { type: Boolean, default: false },
  importDisabled: { type: Boolean, default: false },
  importing: { type: Boolean, default: false },
  provider: { type: String, default: 'pde' },
  xlsxOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['download-import-template', 'import', 'import-committed'])
const fileInput = ref(null)
const selectedFile = ref(null)
const preview = ref(null)
const commitResult = ref(null)
const dialogVisible = ref(false)
const busy = ref(false)
const step = ref(0)
const targetContext = ref(null)
async function checkTarget() {
  if (props.provider !== 'organization') return
  const context=payload(await accessControlApi.organizationImportContext(props.entity))
  if (!context?.targetCompany) throw new Error('导入目标公司读取失败，请重试本操作。')
  targetContext.value=context
  if (!context.allowed) throw new Error(context.reason || '当前身份没有该公司的导入维护资格。')
}
onMounted(() => { if (props.provider === 'organization') checkTarget().catch(() => {}) })

function payload(response) {
  if (response?.success === false) throw new Error(response.error?.message || '正式导入服务失败')
  return response?.data ?? response
}
function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = filename; link.click()
  URL.revokeObjectURL(url)
}
async function downloadTemplate() {
  emit('download-import-template')
  try {
    await checkTarget()
    const result = payload(await (props.provider === 'organization' ? accessControlApi.organizationImportTemplate(props.entity) : pdeApi.formalImportTemplate(props.entity)))
    saveBlob(result instanceof Blob ? result : new Blob([result], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), `${props.entityName}-正式导入模板.xlsx`)
  } catch (error) { ElMessage.error(error.message) }
}
async function chooseFile() {
  try { await checkTarget(); emit('import'); fileInput.value?.click() }
  catch (error) { ElMessage.error(error.message) }
}
async function previewFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  selectedFile.value = file
  preview.value = null
  commitResult.value = null
  step.value = 1
  dialogVisible.value = true
  busy.value = true
  try {
    preview.value = payload(await (props.provider === 'organization' ? accessControlApi.previewOrganizationImport(props.entity, file) : pdeApi.previewFormalImport(props.entity, file)))
    step.value = 2
  } catch (error) { ElMessage.error(error.message) }
  finally { busy.value = false }
}
function displayFields(row) {
  return (row.displayData || []).slice(0, 4).map(item => `${item.label}：${item.value}`).join('；') || '-'
}
async function downloadErrors() {
  if (props.provider === 'organization') {
    try { const result=payload(await accessControlApi.organizationImportErrorReport(props.entity,selectedFile.value)); saveBlob(result,`${props.entityName}-导入校验报告.xlsx`) }
    catch (error) { ElMessage.error(error.message) }
    return
  }
  const rows = [['源行号', '字段', '错误类型', '中文说明', '建议动作'], ...preview.value.errors.map(item => [item.rowNumber, item.fieldLabel || item.field, item.errorType, item.message, item.suggestedAction])]
  const csv = rows.map(row => row.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
  saveBlob(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }), `${props.entityName}-导入错误报告.csv`)
}
async function commit() {
  try {
    await ElMessageBox.confirm(`即将新建 ${preview.value.counts.create} 条，匹配 ${preview.value.counts.match} 条，引用已有不修改 ${preview.value.counts.reference || 0} 条，排除导入 ${preview.value.counts.excluded || 0} 条，待复核 ${preview.value.counts.review} 条，阻断 ${preview.value.counts.blocked} 条。完全匹配和引用行不会重复新增。`, '确认导入', { type: 'warning', confirmButtonText: '确认导入', cancelButtonText: '取消 / 返回' })
  } catch { return }
  busy.value = true
  try {
    const key = globalThis.crypto?.randomUUID?.() || `formal-import-${Date.now()}`
    const result = payload(await (props.provider === 'organization' ? accessControlApi.commitOrganizationImport : pdeApi.commitFormalImport)(
      props.entity, selectedFile.value, preview.value.previewFingerprint, key,
      preview.value.previewActorBinding,
    ))
    ElMessage.success(`正式导入完成：新增 ${result.created}，匹配 ${result.matched}`)
    commitResult.value = result
    step.value = 4
    emit('import-committed', result)
  } catch (error) { ElMessage.error(error.message) }
  finally { busy.value = false }
}
</script>

<style scoped>
.latest-base-data-import-toolbar-extension { display: inline-flex; gap: 8px; }
.target-company { align-self:center; font-size:13px; color:#334155; }
.file-input { display:none; }
.import-boundary { margin:0 0 12px; color:#7c4a03; }
.summary { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
.summary span { padding:6px 9px; border-radius:6px; background:#eef3f8; font-weight:700; }
.summary .create { background:#dcfce7; color:#166534; }
.summary .match { background:#dbeafe; color:#1d4ed8; }
.import-steps { margin-bottom:14px; }
.file-summary { margin:10px 0; color:#334155; }
.replay-tip, .commit-result { margin:10px 0; }
</style>
