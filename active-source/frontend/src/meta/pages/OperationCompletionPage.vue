<template>
  <PceListPageShell compact-employee-view show-compact-page-actions separate-compact-navigation :module-id="OPERATION_COMPLETION_PAGE.moduleId" :governance="governance"
    :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
    <OperationCompletionContent ref="content" @refresh-status="refreshStatus = $event" />
  </PceListPageShell>
</template>
<script setup>
import {computed} from 'vue'
import {useCompactViewport} from '@/meta/runtime/useCompactViewport.js'
const compactViewport=useCompactViewport()
import {useRoute} from 'vue-router'
import {mesPageGovernance} from '@/meta/runtime/mesTestProcessNavigation.js'
import { ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import OperationCompletionContent from '@/meta/components/OperationCompletionContent.vue'
import { OPERATION_COMPLETION_PAGE, OPERATION_COMPLETION_GOVERNANCE } from '@/meta/runtime/operationCompletionContract.js'
const content = ref(null), refreshStatus = ref('idle')
const refresh = () => content.value?.refresh()
const route=useRoute();const governance=computed(()=>mesPageGovernance(OPERATION_COMPLETION_GOVERNANCE,route,content.value?.navigationContext))
</script>
