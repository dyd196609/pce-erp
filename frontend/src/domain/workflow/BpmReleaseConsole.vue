<template>
  <div>
    <el-card>
      <h3>BPM流程版本管理</h3>

      <el-table :data="versions">
        <el-table-column prop="version" label="版本" />
        <el-table-column prop="status" label="状态" />

        <el-table-column label="操作">
          <template #default="scope">
            <el-button type="primary" size="small" @click="publish(scope.row.version)">
              发布
            </el-button>

            <el-button type="warning" size="small" @click="rollback(scope.row.version)">
              回滚
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  getVersions,
  publishVersion,
  rollbackVersion,
} from '@/domain/workflow/workflowVersionManager'

const moduleName = 'purchaseOrder'

const versions = ref(getVersions(moduleName))

const publish = (v) => {
  publishVersion(moduleName, v)
  versions.value = getVersions(moduleName)
}

const rollback = (v) => {
  rollbackVersion(moduleName, v)
  versions.value = getVersions(moduleName)
}
</script>
