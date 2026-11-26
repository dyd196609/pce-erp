<template>
  <PceListPageShell :module-id="WORKSHOP_TASK_PAGE.moduleId" :governance="WORKSHOP_TASK_GOVERNANCE"
    :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
    <WorkshopTaskDispatchContent ref="content" @refresh-status="refreshStatus = $event" />
  </PceListPageShell>
</template>
<script setup>
import { ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import WorkshopTaskDispatchContent from '@/meta/components/WorkshopTaskDispatchContent.vue'
import { WORKSHOP_TASK_PAGE, WORKSHOP_TASK_GOVERNANCE } from '@/meta/runtime/workshopTaskDispatchContract.js'
const content = ref(null), refreshStatus = ref('idle')
const refresh = () => content.value?.refresh()
</script>
