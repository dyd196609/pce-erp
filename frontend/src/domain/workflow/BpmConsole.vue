<template>
  <div class="bpm-console">
    <!-- =========================
         顶部统计面板
    ========================== -->
    <el-row :gutter="12">
      <el-col :span="6">
        <el-card>
          <div class="stat">运行中</div>
          <div class="num">{{ running.length }}</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <div class="stat">已完成</div>
          <div class="num">{{ finished.length }}</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <div class="stat">异常</div>
          <div class="num">{{ error.length }}</div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <div class="stat">总实例</div>
          <div class="num">{{ instances.length }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- =========================
         实例列表
    ========================== -->
    <el-card class="mt">
      <el-table :data="instances" border>
        <el-table-column prop="id" label="实例ID" width="160" />

        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="statusType(scope.row.status)">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="currentNode" label="当前节点" />

        <el-table-column label="操作" width="260">
          <template #default="scope">
            <el-button size="small" @click="viewTrace(scope.row)"> 追踪 </el-button>

            <el-button size="small" type="primary" @click="step(scope.row)"> 推进 </el-button>

            <el-button size="small" type="danger" @click="forceFail(scope.row)"> 中断 </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- =========================
         流程追踪
    ========================== -->
    <el-drawer v-model="traceVisible" title="流程追踪" size="40%">
      <pre>{{ currentTrace }}</pre>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { stepExecute } from '@/domain/workflow/bpmRuntime'

const instances = ref([])

const traceVisible = ref(false)
const currentTrace = ref({})

// =========================
// 分类统计
// =========================
const running = computed(() => instances.value.filter((i) => i.status === 'RUNNING'))

const finished = computed(() => instances.value.filter((i) => i.status === 'FINISHED'))

const error = computed(() => instances.value.filter((i) => i.status === 'ERROR'))

// =========================
// 状态颜色
// =========================
const statusType = (status) => {
  if (status === 'RUNNING') return 'primary'
  if (status === 'FINISHED') return 'success'
  if (status === 'ERROR') return 'danger'
  return 'info'
}

// =========================
// 查看轨迹
// =========================
const viewTrace = (row) => {
  currentTrace.value = row.history || []
  traceVisible.value = true
}

// =========================
// 单步推进（核心能力）
// =========================
const step = (row) => {
  const updated = stepExecute(row)

  const index = instances.value.findIndex((i) => i.id === row.id)
  if (index !== -1) {
    instances.value[index] = updated
  }
}

// =========================
// 强制失败（运维能力）
// =========================
const forceFail = (row) => {
  row.status = 'ERROR'
}
</script>

<style scoped>
.bpm-console {
  padding: 12px;
}

.stat {
  font-size: 14px;
  color: #666;
}

.num {
  font-size: 26px;
  font-weight: bold;
  margin-top: 8px;
}

.mt {
  margin-top: 16px;
}
</style>
