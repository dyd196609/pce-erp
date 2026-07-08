<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  runtime: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['change', 'action'])

// ======================
// 表单状态（核心新增）
// ======================
const formState = reactive({})

// ======================
// runtime
// ======================
const fields = props.runtime?.fields || []
const visibleActions = props.runtime?.visibleActions || []

// ======================
// 监听表单变化
// ======================
const updateField = (key, value) => {
  formState[key] = value
  emit('change', { ...formState })
}
</script>

<template>
  <div v-if="fields && fields.length">
    <!-- 表单 -->
    <div class="form">
      <div v-for="field in fields" :key="field.prop">
        <label>{{ field.label }}</label>

        <input
          v-if="field.type !== 'date'"
          :value="formState[field.prop]"
          @input="updateField(field.prop, $event.target.value)"
        />

        <input
          v-else
          type="date"
          :value="formState[field.prop]"
          @input="updateField(field.prop, $event.target.value)"
        />
      </div>
    </div>

    <!-- actions -->
    <div class="actions">
      <button v-for="a in visibleActions" :key="a" @click="$emit('action', a)">
        {{ a }}
      </button>
    </div>
  </div>
</template>
