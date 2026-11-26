<template>
  <main class="workflow-page" data-acceptance-id="process-designer-page" data-process-source="server">
    <header class="page-header">
      <div>
        <p>ProfitOS 驾驶舱 / 流程治理</p>
        <h1>正式流程定义与节点</h1>
        <p>维护服务端正式流程定义、顺序节点和真实业务动作绑定。</p>
      </div>
    </header>

    <section class="workflow-actions" data-acceptance-id="process-designer-actions" aria-label="流程设计操作">
      <div class="workflow-action-context">
        <strong>流程设计操作</strong>
        <span v-if="catalogAccess === 'allowed'">正式维护授权已通过</span>
        <span v-else-if="catalogAccess === 'checking'">正在核验正式维护权限…</span>
        <span v-else>{{ catalogAccessReason }}</span>
      </div>
      <div class="button-row">
        <el-tooltip :disabled="catalogAccess === 'allowed'" :content="catalogAccessReason" placement="bottom">
          <span class="create-definition-control">
            <el-button
              data-acceptance-id="create-workflow-definition-button"
              type="primary"
              :disabled="catalogAccess !== 'allowed'"
              @click="openDefinition()"
            >新建流程定义</el-button>
          </span>
        </el-tooltip>
        <el-button v-if="selected" type="primary" plain :disabled="catalogAccess !== 'allowed'" @click="openNode()">新增流程节点</el-button>
        <el-button @click="refresh">刷新</el-button>
        <el-button @click="copyDiagnostic">复制诊断信息</el-button>
        <el-button @click="router.push('/process-center')">返回业务流程中心</el-button>
      </div>
    </section>

    <section class="boundary-card">
      <strong>正式事实源：workflow_runtime.ProcessDefinition / WorkflowNodeDefinition</strong>
      <span>新建最小Template通过一次请求原子保存Definition、唯一初始Node、幂等账本与审计；既有对象维护保持原入口。</span>
      <span class="system-catalog-note">工艺路线版本正式评审等已有系统合同的标准流程由系统目录自动生成，不应在本页手工填写技术编码。</span>
      <span>本页不执行采购、付款或审批业务，也不维护岗位流程责任。</span>
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <section class="panel" data-acceptance-id="process-design-list">
      <header>
        <div><h2>正式流程定义</h2><p>共 {{ definitions.length }} 条服务端记录。</p></div>
      </header>
      <el-table v-loading="loading" :data="definitions" row-key="id" highlight-current-row
        @current-change="selectDefinition">
        <el-table-column prop="definitionCode" label="流程编码" min-width="220" />
        <el-table-column prop="definitionName" label="流程名称" min-width="200" />
        <el-table-column prop="businessDomain" label="业务域" width="110" />
        <el-table-column prop="documentType" label="单据类型" min-width="160" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="nodeCount" label="节点数" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="scope"><el-tag :type="scope.row.active ? 'success' : 'info'">{{ scope.row.active ? '启用' : '停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="scope"><el-button link type="primary" @click.stop="openDefinition(scope.row)">维护</el-button></template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="selected" class="panel" data-acceptance-id="process-designer-node-list">
      <header>
        <div><h2>{{ selected.definitionName }}</h2><p>{{ selected.definitionCode }} · {{ selected.description || '无说明' }}</p></div>
        <el-button type="primary" @click="openNode()">新增节点</el-button>
      </header>
      <el-table v-loading="detailLoading" :data="selected.nodes || []" row-key="id">
        <el-table-column prop="sequence" label="顺序" width="80" />
        <el-table-column prop="nodeCode" label="节点编码" min-width="180" />
        <el-table-column prop="nodeName" label="节点名称" min-width="160" />
        <el-table-column prop="businessActionCode" label="正式业务动作" min-width="260" />
        <el-table-column prop="description" label="说明" min-width="220" />
        <el-table-column label="状态" width="90">
          <template #default="scope"><el-tag :type="scope.row.active ? 'success' : 'info'">{{ scope.row.active ? '启用' : '停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="scope"><el-button link type="primary" @click="openNode(scope.row)">维护</el-button></template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="selected" class="panel" data-acceptance-id="workflow-execution-resolution">
      <header>
        <div><h2>流程执行责任解析</h2><p>服务端按 Permission → Role → Responsibility → Position → Employee → Account 实时解析。</p></div>
        <el-tag :type="executionResolution?.metrics?.executableNodeCount === executionResolution?.metrics?.formalNodeCount ? 'success' : 'warning'">
          可执行 {{ executionResolution?.metrics?.executableNodeCount || 0 }}/{{ executionResolution?.metrics?.formalNodeCount || 0 }} 节点
        </el-tag>
      </header>
      <el-table v-loading="detailLoading" :data="executionResolution?.nodes || []" row-key="nodeId">
        <el-table-column prop="sequence" label="顺序" width="70" />
        <el-table-column prop="nodeName" label="流程节点" min-width="150" />
        <el-table-column prop="businessActionCode" label="业务动作 / 权限" min-width="250" />
        <el-table-column label="角色" min-width="170"><template #default="scope">{{ joinNames(scope.row.roles, 'name') }}</template></el-table-column>
        <el-table-column label="岗位 / 职责" min-width="250"><template #default="scope">{{ assignmentText(scope.row) }}</template></el-table-column>
        <el-table-column label="员工 / 账户" min-width="240"><template #default="scope">{{ employeeText(scope.row) }}</template></el-table-column>
        <el-table-column label="解析结果" width="150"><template #default="scope"><el-tag :type="scope.row.executable ? 'success' : 'danger'">{{ scope.row.executable ? '可执行' : '待补齐' }}</el-tag><div class="resolution-reason">{{ scope.row.reason }}</div></template></el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="definitionDialog" :title="definitionForm.id ? '维护流程定义' : '新建流程定义'" width="680px">
      <el-form label-width="110px">
        <el-form-item label="流程编码"><el-input v-model="definitionForm.definitionCode" :disabled="Boolean(definitionForm.id)" /></el-form-item>
        <el-form-item label="流程名称"><el-input v-model="definitionForm.definitionName" /></el-form-item>
        <el-form-item label="业务域"><el-input v-model="definitionForm.businessDomain" placeholder="例如 SCM" /></el-form-item>
        <el-form-item label="单据类型"><el-input v-model="definitionForm.documentType" /></el-form-item>
        <el-form-item label="版本"><el-input-number v-model="definitionForm.version" :min="1" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="definitionForm.active" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="definitionForm.description" type="textarea" /></el-form-item>
        <template v-if="!definitionForm.id">
          <el-divider content-position="left">唯一初始节点（原子保存）</el-divider>
          <el-form-item label="节点编码"><el-input v-model="atomicNodeForm.nodeCode" /></el-form-item>
          <el-form-item label="节点名称"><el-input v-model="atomicNodeForm.nodeName" /></el-form-item>
          <el-form-item label="节点顺序"><el-input-number v-model="atomicNodeForm.sequence" :min="1" /></el-form-item>
          <el-form-item label="正式业务动作"><el-input v-model="atomicNodeForm.businessActionCode" placeholder="必须是已登记 Permission.code" /></el-form-item>
          <el-form-item label="节点启用"><el-switch v-model="atomicNodeForm.active" /></el-form-item>
          <el-form-item label="节点说明"><el-input v-model="atomicNodeForm.description" type="textarea" /></el-form-item>
        </template>
        <el-form-item label="修改原因"><el-input v-model="definitionForm.reason" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="definitionDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submitDefinition">{{ definitionForm.id ? '保存' : '原子创建Template' }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="nodeDialog" :title="nodeForm.id ? '维护流程节点' : '新增流程节点'" width="680px">
      <el-form label-width="120px">
        <el-form-item label="节点编码"><el-input v-model="nodeForm.nodeCode" :disabled="Boolean(nodeForm.id)" /></el-form-item>
        <el-form-item label="节点名称"><el-input v-model="nodeForm.nodeName" /></el-form-item>
        <el-form-item label="节点顺序"><el-input-number v-model="nodeForm.sequence" :min="1" /></el-form-item>
        <el-form-item label="正式业务动作"><el-input v-model="nodeForm.businessActionCode" placeholder="必须是已登记 Permission.code" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="nodeForm.active" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="nodeForm.description" type="textarea" /></el-form-item>
        <el-form-item label="修改原因"><el-input v-model="nodeForm.reason" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="nodeDialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="submitNode">保存</el-button></template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { createAtomicMinimalWorkflowTemplate, getWorkflowDefinition, getWorkflowExecutionResolution, listWorkflowDefinitions, saveWorkflowDefinition, saveWorkflowNode } from '@/api/workflowDefinitions.js'

const route = useRoute()
const router = useRouter()
const definitions = ref([])
const selected = ref(null)
const executionResolution = ref(null)
const loading = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const catalogAccess = ref('checking')
const catalogAccessFailureReason = ref('')
const definitionDialog = ref(false)
const nodeDialog = ref(false)
const definitionForm = reactive({})
const atomicNodeForm = reactive({})
const nodeForm = reactive({})
const atomicRequestIdentity = ref('')
const catalogAccessReason = computed(() => {
  if (catalogAccess.value === 'checking') return '正在核验正式维护权限，请稍候。'
  if (catalogAccess.value === 'allowed') return '正式维护授权已通过。'
  return catalogAccessFailureReason.value
    || '当前账号不能维护流程定义；需要权限 system.organization.workflow_responsibility.manage。'
})

function assign(target, value) {
  Object.keys(target).forEach(key => delete target[key])
  Object.assign(target, value)
}

function createRequestIdentity() {
  const randomPart = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `workflow-catalog-${randomPart}`
}

async function refresh() {
  loading.value = true
  errorMessage.value = ''
  catalogAccess.value = 'checking'
  catalogAccessFailureReason.value = ''
  const response = await listWorkflowDefinitions()
  loading.value = false
  if (!response.success) {
    errorMessage.value = response.error?.message || '流程定义读取失败'
    catalogAccess.value = response.meta?.status === 403 ? 'denied' : 'unavailable'
    catalogAccessFailureReason.value = response.meta?.status === 403
      ? `${errorMessage.value}；需要权限 system.organization.workflow_responsibility.manage。`
      : `${errorMessage.value}；服务端事实恢复前禁止维护。`
    return
  }
  catalogAccess.value = 'allowed'
  definitions.value = response.data?.definitions || []
  if (selected.value) {
    const current = definitions.value.find(item => item.id === selected.value.id)
    if (current) await selectDefinition(current)
  } else if (route.params.id) {
    const current = definitions.value.find(item => String(item.id) === String(route.params.id)
      || item.definitionCode === route.params.id)
    if (current) await selectDefinition(current)
  } else if (definitions.value.length) await selectDefinition(definitions.value[0])
}

async function selectDefinition(row) {
  if (!row?.id) return
  detailLoading.value = true
  const [response, resolutionResponse] = await Promise.all([
    getWorkflowDefinition(row.id), getWorkflowExecutionResolution(row.id),
  ])
  detailLoading.value = false
  if (!response.success) { errorMessage.value = response.error?.message || '流程详情读取失败'; return }
  selected.value = response.data?.definition || null
  executionResolution.value = resolutionResponse.success ? resolutionResponse.data : null
  if (!resolutionResponse.success) errorMessage.value = resolutionResponse.error?.message || '流程执行责任解析失败'
}

function joinNames(rows, field) { return (rows || []).map(row => row[field]).filter(Boolean).join('、') || '待维护' }
function assignmentText(row) { return (row.assignments || []).map(item => `${item.position.code} ${item.position.name} / ${item.responsibility.code} ${item.responsibility.name} / ${item.ownershipType}`).join('；') || '待维护' }
function employeeText(row) { return (row.employees || []).map(item => `${item.fullName} / ${item.username || '无账户'}${item.executable ? '（可执行）' : ''}`).join('；') || '待维护' }

function openDefinition(row = null) {
  assign(definitionForm, row ? { ...row, reason: '维护正式流程定义' } : {
    definitionCode: '', definitionName: '', businessDomain: 'SCM', documentType: '',
    version: 1, active: true, description: '', reason: '建立正式流程定义',
  })
  if (row) {
    assign(atomicNodeForm, {})
    atomicRequestIdentity.value = ''
  } else {
    assign(atomicNodeForm, {
      nodeCode: '', nodeName: '', sequence: 1, businessActionCode: '',
      active: true, description: '',
    })
    // Keep this identity for every retry while the same create dialog remains open.
    atomicRequestIdentity.value = createRequestIdentity()
  }
  definitionDialog.value = true
}

function openNode(row = null) {
  if (!selected.value) return
  assign(nodeForm, row ? { ...row, reason: '维护正式流程节点' } : {
    processDefinitionId: selected.value.id, nodeCode: '', nodeName: '',
    sequence: (selected.value.nodes?.length || 0) + 1, businessActionCode: '',
    active: true, description: '', reason: '建立正式流程节点',
  })
  nodeForm.processDefinitionId = selected.value.id
  nodeDialog.value = true
}

async function submitDefinition() {
  saving.value = true
  const editing = Boolean(definitionForm.id)
  let response
  if (editing) {
    response = await saveWorkflowDefinition({ ...definitionForm })
  } else {
    const { reason, ...definition } = { ...definitionForm }
    response = await createAtomicMinimalWorkflowTemplate({
      definition,
      node: { ...atomicNodeForm },
      reason,
    }, atomicRequestIdentity.value)
  }
  saving.value = false
  if (!response.success) {
    const prefix = response.meta?.status === 409 ? '配置冲突：' : '保存失败：'
    return ElMessage.error(`${prefix}${response.error?.message || '未知错误'}`)
  }
  definitionDialog.value = false
  ElMessage.success(editing ? '流程定义已保存并形成审计记录' : '流程定义与唯一初始节点已原子提交')
  atomicRequestIdentity.value = ''
  await refresh()
  await selectDefinition(response.data.definition)
}

async function submitNode() {
  saving.value = true
  const response = await saveWorkflowNode({ ...nodeForm })
  saving.value = false
  if (!response.success) return ElMessage.error(response.error?.message || '保存失败')
  nodeDialog.value = false
  ElMessage.success('流程节点已保存并形成审计记录')
  await refresh()
}

async function copyDiagnostic() {
  const facts = { page: location.href, api: '/api/workflow/definitions/',
    loadedDefinitions: definitions.value.length, selectedDefinition: selected.value?.definitionCode || null,
    selectedNodeCount: selected.value?.nodes?.length || 0,
    executionMetrics: executionResolution.value?.metrics || null, error: errorMessage.value || null,
    capturedAt: new Date().toISOString() }
  await navigator.clipboard.writeText(JSON.stringify(facts, null, 2))
  ElMessage.success('诊断信息已复制')
}

onMounted(async () => {
  await refresh()
  if (route.name === 'ProcessDesignerCreate' && catalogAccess.value === 'allowed') openDefinition()
})
</script>

<style scoped>
.workflow-page { display:grid; gap:18px; padding:24px; color:#172033; }
.page-header,.panel>header { display:flex; justify-content:space-between; align-items:flex-start; gap:20px; }
.page-header h1,.panel h2 { margin:4px 0 8px; }
.page-header p,.panel p { margin:0; color:#64748b; }
.boundary-card,.panel { padding:20px; border:1px solid #dbe4ee; border-radius:14px; background:#fff; }
.boundary-card { display:grid; gap:8px; background:#f8fbff; }
.workflow-actions { position:relative; z-index:1; display:grid; gap:12px; padding:14px 16px; border:1px solid #cbd9e8; border-radius:12px; background:#fff; box-shadow:0 4px 12px rgba(15,23,42,.04); }
.workflow-action-context { display:grid; gap:4px; min-width:220px; }
.workflow-action-context span { color:#64748b; font-size:13px; line-height:1.5; }
.button-row { display:flex; min-width:0; flex-wrap:wrap; justify-content:flex-start; gap:8px; }
.create-definition-control { display:inline-flex; }
.button-row .el-button { margin-left:0; }
.panel>header { margin-bottom:16px; }
.resolution-reason { margin-top:6px; color:#64748b; font-size:12px; line-height:1.4; }
@media (max-width:760px) { .page-header,.panel>header { display:grid; grid-template-columns:1fr; } }
</style>
