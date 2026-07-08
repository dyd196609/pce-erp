<template>
  <div v-if="isDesign">
    <h3>Meta Designer V8</h3>

    <el-button @click="addColumn">+ 列</el-button>
    <el-button @click="addField">+ 表单字段</el-button>
    <el-button @click="addAction">+ 按钮</el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { isDesignMode, addField, addAction } from './metaDesignerEngine'

const isDesign = ref(isDesignMode())

const addColumn = () => {
  console.log('TODO: column design')
}

const addField = () => {
  console.log('add field')
}

const addAction = () => {
  console.log('add action')
}
</script>
