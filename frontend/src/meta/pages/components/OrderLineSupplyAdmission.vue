<template>
  <el-dialog :model-value="modelValue" title="订单行供应承接确认" width="640px" @update:model-value="emit('update:modelValue', $event)">
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="busy">正在读取供应承接事实</p>
    <template v-if="facts">
      <p>{{ facts.status === 'CONFIRMED' ? '供应承接已确认' : '供应承接待确认' }}</p>
      <template v-if="facts.status === 'CONFIRMED'">
        <p>承接方式 {{ modeLabel(facts.supplyType) }}</p>
        <p style="white-space: pre-wrap">业务依据 {{ facts.reason }}</p>
        <p>确认人 {{ facts.responsibility.name }}（{{ facts.responsibility.username }}）</p>
        <p>确认时间 {{ facts.confirmedAt }}</p>
        <p>已有确认事实按服务端规则保留。</p>
      </template>
      <template v-else-if="facts.status === 'UNRESOLVED'">
        <p>尚不能确定自制或外购，工程准备及计划需求准入受阻。</p>
        <el-form label-width="110px">
          <el-form-item label="承接方式"><el-select v-model="mode"><el-option label="自制（MAKE）" value="MAKE"/><el-option label="外购（BUY）" value="BUY"/></el-select></el-form-item>
          <el-form-item label="业务依据"><el-input v-model="reason" type="textarea" :rows="4" maxlength="300" show-word-limit placeholder="请填写2—300字业务依据"/></el-form-item>
        </el-form>
        <p v-if="mode === 'MAKE'">本入口仅确认自制承接。生产执行责任可按既有流程另行指定。</p>
        <el-button type="primary" :loading="saving" :disabled="!mode || reason.trim().length < 2" @click="save">确认供应承接</el-button>
      </template>
      <p v-else role="alert">{{ facts.resolutionReason || '历史确认事实校验未通过，请核对后办理。' }}</p>
    </template>
    <template #footer><el-button @click="emit('update:modelValue', false)">关闭</el-button><el-button :loading="busy" @click="load">刷新回执</el-button></template>
  </el-dialog>
</template>
<script setup>
import { ref, watch } from 'vue'
import { salesApi } from '@/api/sales'
const props = defineProps({ modelValue: Boolean, orderId: Number, itemId: Number })
const emit = defineEmits(['update:modelValue', 'saved'])
const facts = ref(null), error = ref(''), busy = ref(false), saving = ref(false)
const mode = ref(''), reason = ref(''), key = ref('')
const modeLabel = value => ({ MAKE: '自制（MAKE）', BUY: '外购（BUY）' })[value] || '未确认'
async function load() {
  const id = props.itemId
  if (!id) return
  busy.value = true
  error.value = ''
  facts.value = null
  try {
    const result = await salesApi.supplyAdmission(props.orderId, id)
    if (id !== props.itemId) return
    if (!result.success) throw new Error(result.error?.message)
    facts.value = result.data.confirmation
  } catch (cause) { error.value = cause.message || '供应承接读取失败' }
  finally { busy.value = false }
}
watch(() => [props.modelValue, props.itemId], () => {
  if (!props.modelValue) return
  mode.value = ''
  reason.value = ''
  key.value = crypto.randomUUID()
  load()
})
async function save() {
  saving.value = true
  error.value = ''
  try {
    const result = await salesApi.confirmSupplyAdmission(props.orderId, props.itemId, {
      supplyType: mode.value, reason: reason.value.trim(), idempotencyKey: key.value,
    })
    if (!result.success) throw new Error(result.error?.message)
    await load()
    emit('saved')
  } catch (cause) { error.value = cause.message || '供应承接确认失败' }
  finally { saving.value = false }
}
</script>
