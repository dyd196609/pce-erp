<template>
  <main class="approval-flow-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.11.10 审批流配置</p>
        <h1>审批关卡配置</h1>
        <p>本轮只配置 1 关、2 关、3 关，不做复杂条件审批。</p>
      </section>
      <nav class="page-tabs">
        <router-link to="/admin">系统配置</router-link>
        <router-link to="/admin/approval-flow-config">审批流配置</router-link>
        <router-link to="/scm">SCM采购管理</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" type="success" show-icon :closable="false" />

    <section class="operation-shell">
      <el-card shadow="never">
        <template #header><h2>模块审批关卡</h2></template>
        <el-table :data="configs" border stripe>
          <el-table-column prop="moduleLabel" label="模块" />
          <el-table-column label="启用">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="save(row)" />
            </template>
          </el-table-column>
          <el-table-column label="关卡数量" min-width="240">
            <template #default="{ row }">
              <el-segmented
                v-model="row.stepCount"
                :options="stepOptions"
                @change="save(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="当前关卡">
            <template #default="{ row }">
              {{ row.steps.map((step) => step.stepLabel).join(' / ') }}
            </template>
          </el-table-column>
          <el-table-column label="状态流转说明" min-width="260">
            <template #default="{ row }">
              {{ flowText(row.stepCount) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import {
  listApprovalFlowConfigs,
  saveApprovalFlowConfig,
} from '../workflow/approvalFlowConfigStore.js'

const stepOptions = [
  { label: '1关', value: 1 },
  { label: '2关', value: 2 },
  { label: '3关', value: 3 },
]
const message = ref('')
const configs = ref(loadRows())

function loadRows() {
  return listApprovalFlowConfigs().map((item) => ({
    ...item,
    stepCount: item.steps?.length || 1,
  }))
}

function flowText(count) {
  if (Number(count) === 1) return '草稿 → 提交 → 审批通过'
  if (Number(count) === 2) return '草稿 → 提交 → 审核 → 审批通过'
  return '草稿 → 提交 → 审核 → 复核 → 审批通过'
}

function save(row) {
  saveApprovalFlowConfig(row.moduleName, {
    enabled: row.enabled,
    stepCount: row.stepCount,
  })
  configs.value = loadRows()
  message.value = `${row.moduleLabel}审批配置已保存`
  window.clearTimeout(save.timer)
  save.timer = window.setTimeout(() => {
    message.value = ''
  }, 1800)
}
</script>

<style scoped>
.approval-flow-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

.page-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-tabs a {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
}
</style>
