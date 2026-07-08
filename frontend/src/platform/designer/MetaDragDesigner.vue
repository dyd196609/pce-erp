<template>
  <div class="designer">
    <div class="panel">
      <h3>Meta Designer V9</h3>

      <el-button @click="addField">+ 字段</el-button>
      <el-button @click="addColumn">+ 列</el-button>
      <el-button @click="addAction">+ 按钮</el-button>

      <hr />

      <el-button type="success" @click="exportMeta"> 生成Meta JSON </el-button>
    </div>

    <pre class="preview"
      >{{ meta }}
    </pre>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import {
  dragAddField,
  dragAddColumn,
  dragAddAction,
  buildMeta,
  initDesigner,
} from './dragMetaDesigner'

const meta = ref({})

initDesigner({})

const addField = () => {
  meta.value = dragAddField({
    label: '新字段',
    prop: 'field_' + Date.now(),
    type: 'input',
  })
}

const addColumn = () => {
  meta.value = dragAddColumn({
    label: '新列',
    prop: 'col_' + Date.now(),
  })
}

const addAction = () => {
  meta.value = dragAddAction({
    label: '按钮',
    action: 'view',
    type: 'primary',
  })
}

const exportMeta = () => {
  meta.value = buildMeta()
  console.log('Meta JSON:', meta.value)
}
</script>

<style>
.designer {
  display: flex;
  gap: 20px;
}
.panel {
  width: 300px;
}
.preview {
  flex: 1;
  background: #111;
  color: #0f0;
  padding: 10px;
}
</style>
