<template>
  <PceListPageShell :module-id="OPERATION_START_PAGE.moduleId" :governance="OPERATION_START_GOVERNANCE"
    :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
    <OperationStartContent ref="content" @refresh-status="refreshStatus = $event" />
  </PceListPageShell>
</template>
<script setup>
import { ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import OperationStartContent from '@/meta/components/OperationStartContent.vue'
import { OPERATION_START_PAGE, OPERATION_START_GOVERNANCE } from '@/meta/runtime/operationStartContract.js'
const content = ref(null), refreshStatus = ref('idle')
const refresh = () => content.value?.refresh()
</script>
