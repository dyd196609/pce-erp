<template>
  <div>
    <el-button type="success" @click="publish"> 发布Meta </el-button>

    <el-select v-model="version">
      <el-option
        v-for="v in versions"
        :key="v.version"
        :label="'v' + v.version"
        :value="v.version"
      />
    </el-select>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { publishMeta, getLatestVersion } from './metaVersionManager'

const version = ref(1)
const versions = ref([])

const publish = () => {
  publishMeta('purchaseOrder', version.value)
  console.log('发布成功')
}
</script>
