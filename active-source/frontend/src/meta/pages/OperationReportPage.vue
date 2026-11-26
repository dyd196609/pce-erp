<template>
  <PceListPageShell compact-employee-view show-compact-page-actions separate-compact-navigation :module-id="OPERATION_REPORT_PAGE.moduleId" :governance="governance"
    :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
    <OperationReportContent ref="content" @refresh-status="refreshStatus = $event" />
  </PceListPageShell>
</template>
<script setup>
import {computed} from 'vue'
import {useRoute} from 'vue-router'
import {mesPageGovernance} from '@/meta/runtime/mesTestProcessNavigation.js'
import { ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import OperationReportContent from '@/meta/components/OperationReportContent.vue'
import { OPERATION_REPORT_PAGE, OPERATION_REPORT_GOVERNANCE } from '@/meta/runtime/operationReportContract.js'
const content = ref(null), refreshStatus = ref('idle')
const refresh = () => content.value?.refresh()
const route=useRoute();const governance=computed(()=>mesPageGovernance(OPERATION_REPORT_GOVERNANCE,route,content.value?.navigationContext))
</script>

<style scoped>
:deep(.pce-page-action-bar button){min-height:44px}:deep(.pce-page-action-bar :focus-visible){outline:3px solid #2563eb;outline-offset:2px}
</style>
