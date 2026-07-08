<template>
  <div>
    <h2>AI ERP Generator</h2>

    <el-input v-model="prompt" placeholder="输入：比如 创建一个工厂采购系统" />

    <el-button type="primary" @click="generate"> 生成ERP </el-button>

    <pre>{{ result }}</pre>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { generateERP } from './aiErpGenerator'

const prompt = ref('')
const result = ref({})

const generate = async () => {
  result.value = await generateERP(prompt.value)
}
</script>
