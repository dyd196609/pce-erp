<template>
  <el-dialog v-model="visible" :title="title" width="600px">
    <!-- 自动表单 -->
    <component :is="formComponent" :model="formData" />

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { generateForm } from './formGenerator'

const props = defineProps({
  meta: Object,
  modelValue: Boolean,
  row: Object,
})

const emit = defineEmits(['update:modelValue', 'submit'])

const visible = ref(false)
const formData = ref({})

const formComponent = generateForm(props.meta)

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

watch(
  () => props.row,
  (row) => {
    formData.value = row ? { ...row } : {}
  }
)

const title = '编辑数据'

const handleSubmit = () => {
  emit('submit', formData.value)
  visible.value = false
}
</script>
