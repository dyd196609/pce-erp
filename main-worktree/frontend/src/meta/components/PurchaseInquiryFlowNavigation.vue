<template>
  <section class="flow-navigation" data-acceptance-id="purchase-inquiry-flow-navigation">
    <article><span>当前节点</span><strong>{{ state.currentNode }}</strong></article>
    <article><span>业务状态</span><strong>{{ state.businessStatusLabel }}</strong></article>
    <article><span>流程状态</span><strong>{{ state.processStatusLabel }}</strong></article>
    <article><span>下一步业务动作</span><strong>{{ state.nextAction }}</strong></article>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { resolvePurchaseInquiryBusinessState } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'

const props = defineProps({ inquiry: { type: Object, default: () => ({}) } })
const state = computed(() => resolvePurchaseInquiryBusinessState(props.inquiry))
</script>

<style scoped>
.flow-navigation{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.flow-navigation article{display:grid;gap:6px;padding:14px;border:1px solid #dce4ed;border-radius:10px;background:#f8fafc}.flow-navigation span,.flow-navigation small{color:#64748b}@media(max-width:900px){.flow-navigation{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
