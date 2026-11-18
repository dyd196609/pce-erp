<template>
  <PceListPageShell compact-employee-view show-compact-page-actions separate-compact-navigation :module-id="OPERATION_HANDOVER_PAGE.moduleId" :governance="governance" :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
    <OperationHandoverContent ref="content" @refresh-status="refreshStatus = $event" />
  </PceListPageShell>
</template>
<script setup>
import {computed} from 'vue'
import {useRoute} from 'vue-router'
import {mesPageGovernance} from '@/meta/runtime/mesTestProcessNavigation.js'
import { ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import OperationHandoverContent from '@/meta/components/OperationHandoverContent.vue'
import { OPERATION_HANDOVER_PAGE, OPERATION_HANDOVER_GOVERNANCE } from '@/meta/runtime/operationHandoverContract.js'
const content = ref(null), refreshStatus = ref('idle')
const refresh = () => content.value?.refresh()
const route=useRoute();const governance=computed(()=>mesPageGovernance(OPERATION_HANDOVER_GOVERNANCE,route,content.value?.navigationContext))
</script>

