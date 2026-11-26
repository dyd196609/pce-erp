<template><component :is="compactViewport ? 'details' : 'section'" v-if="facts" class="mes-execution-context" aria-label="当前工单与流程节点"><summary v-if="compactViewport">本单流程与来源说明</summary><h2 v-else>当前工单与流程节点</h2><p>当前工单：{{ context?.workOrderNo || '请选择有权工单或任务' }}；当前任务：{{ context?.taskNo || '本单任务目录／待选择任务' }}；当前节点：{{ node?.nodeName }}</p><p>查看路径：业务流程中心 → MES → 生产执行与成品交接 → {{ node?.nodeName }}。</p><p>六节点表示查看与办理入口；不把导航箭头当成工艺前置。分批产出、分支、条件未触发节点及实际前置以本单冻结来源与接收证明为准。</p></component></template>
<script setup>
import {computed} from 'vue'
import {useRoute} from 'vue-router'
import {mesReadContext,mesNodeIndex,MES_TEST_NODES} from '@/meta/runtime/mesTestProcessNavigation.js'
import {useCompactViewport} from '@/meta/runtime/useCompactViewport.js'
const compactViewport=useCompactViewport()
const props=defineProps({facts:{type:Object,default:null}}),route=useRoute()
const context=computed(()=>mesReadContext(props.facts)),node=computed(()=>MES_TEST_NODES[mesNodeIndex(route)])
</script>
<style scoped>
@media(max-width:900px){.mes-execution-context{padding:4px 10px;border:1px solid #dbe3ef;border-radius:8px;background:#fff;font-size:.8125rem;line-height:1.5}.mes-execution-context summary{min-height:44px;cursor:pointer;font-weight:600;line-height:44px}.mes-execution-context p{overflow-wrap:anywhere}}
</style>
