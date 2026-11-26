<template>
  <component
    :is="tag"
    data-pce-name-consumer="BusinessNameRegistry"
    :data-page-code="consumption.pageCode || pageCode"
    :data-name-field="field"
  >{{ displayedName }}</component>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { resolvePageNameConsumption } from '../governance/pageNameConsumer.js'

const props = defineProps({
  pageCode: { type: String, default: '' },
  nodeCode: { type: String, default: '' },
  routePath: { type: String, default: '' },
  field: { type: String, default: 'pageTitle' },
  tag: { type: String, default: 'span' },
})
const route = useRoute()
const consumption = computed(() => resolvePageNameConsumption({
  pageCode: props.pageCode,
  nodeCode: props.nodeCode,
  route: props.routePath || route.path,
}))
const displayedName = computed(() => consumption.value[props.field] || consumption.value.pageTitle)
</script>
