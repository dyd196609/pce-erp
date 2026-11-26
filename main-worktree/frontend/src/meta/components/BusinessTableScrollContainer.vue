<template>
  <div
    ref="scrollContainer"
    class="business-table-scroll-container"
    :data-acceptance-id="acceptanceId"
    :data-pce-page-id="pageId || undefined"
    :data-pce-table-id="resolvedTableId"
    :data-pce-scroll-for="resolvedTableId"
    :data-pce-min-width="resolvedMinWidth"
    :data-pce-width-policy="widthPolicy"
    :data-pce-scroll-width="scrollFacts.scrollWidth"
    :data-pce-client-width="scrollFacts.clientWidth"
    :data-pce-horizontal-scroll-visible="scrollFacts.horizontalScrollVisible"
    :data-pce-scroll-target="scrollFacts.scrollTarget"
    :data-pce-scrollbar-height="scrollFacts.scrollbarHeight"
    :data-pce-no-page-overflow="scrollFacts.noPageOverflow"
    :style="containerStyle"
    data-pce-fixed-column-contract-version="V1.14.2.8.4.7"
    data-pce-horizontal-scroll-owner="element-plus-native"
    data-pce-table-container-contract="TABLE-SCROLL-RUNTIME-001"
  >
    <div class="business-table-scroll-content">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { createPceTableScrollRuntime, measureHorizontalScroll } from '@/meta/runtime/pceTableScrollRuntime.js'
import { createListContainerRuntime } from '@/meta/runtime/listContainerRuntime.js'

const props = defineProps({
  acceptanceId: {
    type: String,
    required: true,
  },
  minWidth: {
    type: [String, Number],
    default: '1180px',
  },
  pageId: {
    type: String,
    default: '',
  },
  tableId: {
    type: String,
    default: '',
  },
  widthPolicy: { type: String, default: 'wide' },
})

const resolvedTableId = computed(() => {
  if (props.tableId) return props.tableId
  return String(props.acceptanceId || '').replace(/^business-table-scroll-/, '')
})
const tableScrollRuntime = computed(() => createPceTableScrollRuntime({ widthPolicy: props.widthPolicy,
  requestedMinWidth: props.minWidth }))
const resolvedMinWidth = computed(() => tableScrollRuntime.value.width.cssMinWidth)
const listContainerRuntime = computed(() => createListContainerRuntime({ tableMinWidth: resolvedMinWidth.value }))
const containerStyle = computed(() => ({ ...listContainerRuntime.value.tableStyle, overflowX: 'hidden',
  '--pce-table-min-width': resolvedMinWidth.value }))
const scrollContainer = ref(null)
const scrollFacts = ref({ scrollWidth: 0, clientWidth: 0, scrollbarHeight: 0,
  scrollTarget: 'pending', horizontalScrollVisible: false, noPageOverflow: true })
let resizeObserver = null

function syncScrollFacts() {
  if (scrollContainer.value) scrollFacts.value = measureHorizontalScroll(scrollContainer.value)
}

onMounted(async () => {
  await nextTick()
  syncScrollFacts()
  if (globalThis.ResizeObserver && scrollContainer.value) {
    resizeObserver = new ResizeObserver(syncScrollFacts)
    resizeObserver.observe(scrollContainer.value)
    if (scrollContainer.value?.firstElementChild) resizeObserver.observe(scrollContainer.value.firstElementChild)
    const viewport = scrollContainer.value?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    if (viewport) resizeObserver.observe(viewport)
  }
  globalThis.addEventListener?.('resize', syncScrollFacts)
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  globalThis.removeEventListener?.('resize', syncScrollFacts)
})

</script>

<style scoped>
.business-table-scroll-container {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  overflow-y: hidden;
  box-sizing: border-box;
}

.business-table-scroll-content {
  width: 100%;
  min-width: 0;
  max-width: 100%;
}

:deep(.el-table__header),
:deep(.el-table__body) {
  min-width: var(--pce-table-min-width);
}

.business-table-scroll-container.pce-baseline-table-shell {
  overflow-x: hidden;
  overflow-y: hidden;
}

.business-table-scroll-container.pce-baseline-table-shell .business-table-scroll-content {
  width: 100%;
  min-width: 100%;
}

:deep(.el-table) {
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
}

:deep(.el-table__inner-wrapper) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
}

:deep(.el-scrollbar__bar.is-horizontal) {
  display: block !important;
  height: 12px !important;
  bottom: 0 !important;
  opacity: 1 !important;
}

:deep(.payment-fixed-action-column) {
  background: #fff !important;
  box-shadow: -8px 0 12px -12px rgba(15, 23, 42, 0.45);
  z-index: 3;
}

:deep(th.payment-fixed-action-column) {
  background: #f8fafc !important;
}

:deep(.business-table-selection-column),
:deep(.payment-fixed-selection-column),
:deep(.el-table-column--selection) {
  background: #fff !important;
  z-index: 3;
}

:deep(th.business-table-selection-column),
:deep(th.payment-fixed-selection-column),
:deep(th.el-table-column--selection) {
  background: #f8fafc !important;
}

:deep(.pce-fixed-index-column),
:deep(.payment-fixed-index-column) {
  background: #fff !important;
  z-index: 3;
}

:deep(th.pce-fixed-index-column),
:deep(th.payment-fixed-index-column) {
  background: #f8fafc !important;
}

:deep(.pce-fixed-primary-no-column),
:deep(.payment-fixed-no-column) {
  background: #fff !important;
  box-shadow: 8px 0 12px -12px rgba(15, 23, 42, 0.45);
  z-index: 3;
}

:deep(th.pce-fixed-primary-no-column),
:deep(th.payment-fixed-no-column) {
  background: #f8fafc !important;
  box-shadow: 8px 0 12px -12px rgba(15, 23, 42, 0.45);
}

:deep(.app-action-cell) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  justify-content: flex-start;
  max-width: 100%;
}
</style>
