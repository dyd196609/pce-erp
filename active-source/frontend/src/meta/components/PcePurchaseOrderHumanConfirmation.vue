<template>
  <div class="human-confirmation-card" :data-acceptance-id="acceptanceId">
    <strong>人工确认</strong>
    <p>Gate 准入检查通过后，请人工核对以下正式采购信息。</p>
    <el-checkbox :model-value="modelValue" :disabled="disabled" :data-acceptance-id="checkboxAcceptanceId"
      @change="$emit('update:modelValue', $event === true); $emit('change', $event === true)">
      {{ confirmationText }}
    </el-checkbox>
    <small>{{ modelValue ? '人工确认完成，可以创建正式采购订单。' : '勾选后才允许创建正式采购订单。' }}</small>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  acceptanceId: { type: String, required: true },
  checkboxAcceptanceId: { type: String, required: true },
  confirmationText: { type: String, required: true },
})
defineEmits(['update:modelValue', 'change'])
</script>

<style scoped>
.human-confirmation-card{box-sizing:border-box;display:grid;gap:8px;width:100%;max-width:600px;justify-self:center;padding:16px;border:1px solid #93c5fd;border-radius:12px;background:#eff6ff;color:#1e293b}.human-confirmation-card>strong{font-size:16px}.human-confirmation-card p{margin:0;font-size:14px}.human-confirmation-card small{color:#64748b}.human-confirmation-card :deep(.el-checkbox){height:auto;white-space:normal}.human-confirmation-card :deep(.el-checkbox__label){font-size:14px;font-weight:600;line-height:1.5;white-space:normal}.human-confirmation-card :deep(.el-checkbox__inner){width:18px;height:18px}
</style>
