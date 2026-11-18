<template><PceListPageShell compact-employee-view show-compact-page-actions :module-id="FINISHED_GOODS_PAGE.moduleId" :governance="governance" separate-compact-navigation :page-refresh-handler="refresh" :page-refresh-status="refreshStatus"><FinishedGoodsContent ref="content" @refresh-status="refreshStatus=$event" /></PceListPageShell></template>
<script setup>
import {computed} from 'vue'
import {useRoute} from 'vue-router'
import {mesPageGovernance} from '@/meta/runtime/mesTestProcessNavigation.js'
import { ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import FinishedGoodsContent from '@/meta/components/FinishedGoodsContent.vue'
import { FINISHED_GOODS_PAGE,FINISHED_GOODS_GOVERNANCE } from '@/meta/runtime/finishedGoodsContract.js'
const content=ref(null),refreshStatus=ref('idle');const refresh=()=>content.value?.refresh()
const route=useRoute();const governance=computed(()=>mesPageGovernance(FINISHED_GOODS_GOVERNANCE,route,content.value?.navigationContext))
</script>
