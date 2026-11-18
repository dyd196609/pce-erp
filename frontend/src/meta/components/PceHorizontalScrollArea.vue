<template>
  <div class="pce-horizontal-scroll-area" :data-acceptance-id="acceptanceId">
    <div
      ref="viewportRef"
      class="pce-horizontal-scroll-viewport"
      :class="{ 'is-dragging': contentDragging }"
      :data-acceptance-id="`${acceptanceId}-viewport`"
      tabindex="0"
      @scroll="syncFromViewport"
      @wheel="handleWheel"
      @pointerdown.capture="startContentDrag"
      @mousedown.capture="startContentMouseDrag"
    >
      <div ref="contentRef" class="pce-horizontal-scroll-content" :style="contentStyle">
        <slot />
      </div>
    </div>

    <div
      v-if="scrollable"
      class="pce-horizontal-scroll-controls"
      :data-acceptance-id="`${acceptanceId}-controls`"
      aria-label="横向滚动控制"
    >
      <button
        type="button"
        class="pce-horizontal-scroll-button"
        :data-acceptance-id="`${acceptanceId}-left-button`"
        :disabled="atLeft"
        @click="scrollByAmount(-scrollStep)"
      >
        {{ scrollCopy.left }}
      </button>
      <div
        ref="trackRef"
        class="pce-horizontal-scroll-track"
        :data-acceptance-id="`${acceptanceId}-track`"
        @pointerdown="startTrackJump"
      >
        <div
          ref="thumbRef"
          class="pce-horizontal-scroll-thumb"
          :data-acceptance-id="`${acceptanceId}-thumb`"
          :style="thumbStyle"
          role="slider"
          tabindex="0"
          :aria-label="scrollCopy.instruction"
          :aria-valuemin="0"
          :aria-valuemax="maxScrollLeft"
          :aria-valuenow="scrollLeft"
          @pointerdown.stop="startThumbDrag"
          @mousedown.stop="startThumbMouseDrag"
          @keydown.left.prevent="scrollByAmount(-scrollStep)"
          @keydown.right.prevent="scrollByAmount(scrollStep)"
        />
      </div>
      <span class="pce-horizontal-scroll-instruction">{{ scrollCopy.instruction }}</span>
      <button
        type="button"
        class="pce-horizontal-scroll-button"
        :data-acceptance-id="`${acceptanceId}-right-button`"
        :disabled="atRight"
        @click="scrollByAmount(scrollStep)"
      >
        {{ scrollCopy.right }}
      </button>
    </div>
    <div
      v-else
      class="pce-horizontal-scroll-noop"
      :data-acceptance-id="`${acceptanceId}-not-needed`"
    >
      {{ scrollCopy.noScrollNeeded }}
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'
import { businessAcceptanceScrollCopy } from '../runtime/businessAcceptanceCopy.js'

const props = defineProps({
  acceptanceId: {
    type: String,
    required: true,
  },
  minWidth: {
    type: [String, Number],
    default: '1180px',
  },
  scrollStep: {
    type: Number,
    default: 360,
  },
})

const viewportRef = ref(null)
const contentRef = ref(null)
const trackRef = ref(null)
const thumbRef = ref(null)
const scrollLeft = ref(0)
const clientWidth = ref(0)
const scrollWidth = ref(0)
const trackWidth = ref(0)
const contentDragging = ref(false)
const thumbDragging = ref(false)
let dragStartX = 0
let dragStartScrollLeft = 0
let resizeObserver = null

const scrollCopy = businessAcceptanceScrollCopy

const contentStyle = computed(() => ({
  minWidth: typeof props.minWidth === 'number' ? `${props.minWidth}px` : props.minWidth,
}))

const maxScrollLeft = computed(() => Math.max(0, scrollWidth.value - clientWidth.value))
const scrollable = computed(() => maxScrollLeft.value > 2)
const atLeft = computed(() => scrollLeft.value <= 1)
const atRight = computed(() => scrollLeft.value >= maxScrollLeft.value - 1)

const thumbWidth = computed(() => {
  if (!scrollable.value || !scrollWidth.value) return 0
  if (!trackWidth.value) return 44
  return Math.max(44, Math.floor((clientWidth.value / scrollWidth.value) * trackWidth.value))
})

const thumbLeft = computed(() => {
  if (!scrollable.value || !trackWidth.value) return 0
  const movable = Math.max(0, trackWidth.value - thumbWidth.value)
  return maxScrollLeft.value ? (scrollLeft.value / maxScrollLeft.value) * movable : 0
})

const thumbStyle = computed(() => ({
  width: `${thumbWidth.value}px`,
  transform: `translateX(${thumbLeft.value}px)`,
}))

function refreshMetrics() {
  const viewport = viewportRef.value
  const track = trackRef.value
  if (!viewport) return
  clientWidth.value = viewport.clientWidth
  scrollWidth.value = viewport.scrollWidth
  scrollLeft.value = viewport.scrollLeft
  trackWidth.value = track?.clientWidth || 0
  if (track && resizeObserver) resizeObserver.observe(track)
}

function syncFromViewport() {
  if (!viewportRef.value) return
  scrollLeft.value = viewportRef.value.scrollLeft
}

function setScrollLeft(value) {
  const viewport = viewportRef.value
  if (!viewport) return
  viewport.scrollLeft = Math.max(0, Math.min(maxScrollLeft.value, value))
  syncFromViewport()
}

function scrollByAmount(amount) {
  setScrollLeft(scrollLeft.value + amount)
}

function handleWheel(event) {
  if (!event.shiftKey || !scrollable.value) return
  event.preventDefault()
  setScrollLeft(scrollLeft.value + event.deltaY)
}

function isInteractiveElement(target) {
  return Boolean(target?.closest?.('button,a,input,textarea,select,.el-button,[role="button"]'))
}

function beginContentDrag(event) {
  if (contentDragging.value || thumbDragging.value || !scrollable.value || event.button !== 0 || isInteractiveElement(event.target)) return
  contentDragging.value = true
  dragStartX = event.clientX
  dragStartScrollLeft = scrollLeft.value
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', moveContentDrag)
  window.addEventListener('mousemove', moveContentDrag)
  window.addEventListener('pointerup', stopDrag, { once: true })
  window.addEventListener('mouseup', stopDrag, { once: true })
}

function isInsideViewport(event) {
  const rect = viewportRef.value?.getBoundingClientRect()
  if (!rect) return false
  return event.clientX >= rect.left
    && event.clientX <= rect.right
    && event.clientY >= rect.top
    && event.clientY <= rect.bottom
}

function startContentDrag(event) {
  beginContentDrag(event)
}

function startContentMouseDrag(event) {
  beginContentDrag(event)
}

function maybeStartContentDragFromWindow(event) {
  if (!isInsideViewport(event)) return
  beginContentDrag(event)
}

function moveContentDrag(event) {
  if (!contentDragging.value) return
  const delta = event.clientX - dragStartX
  if (Math.abs(delta) < 3) return
  event.preventDefault()
  setScrollLeft(dragStartScrollLeft - delta)
}

function startThumbDrag(event) {
  if (contentDragging.value || thumbDragging.value || !scrollable.value || event.button !== 0) return
  thumbDragging.value = true
  dragStartX = event.clientX
  dragStartScrollLeft = scrollLeft.value
  event.currentTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', moveThumbDrag)
  window.addEventListener('mousemove', moveThumbDrag)
  window.addEventListener('pointerup', stopDrag, { once: true })
  window.addEventListener('mouseup', stopDrag, { once: true })
}

function startThumbMouseDrag(event) {
  if (contentDragging.value || thumbDragging.value || !scrollable.value || event.button !== 0) return
  thumbDragging.value = true
  dragStartX = event.clientX
  dragStartScrollLeft = scrollLeft.value
  window.addEventListener('mousemove', moveThumbDrag)
  window.addEventListener('mouseup', stopDrag, { once: true })
}

function moveThumbDrag(event) {
  if (!thumbDragging.value) return
  event.preventDefault()
  const movable = Math.max(1, trackWidth.value - thumbWidth.value)
  const delta = event.clientX - dragStartX
  setScrollLeft(dragStartScrollLeft + (delta / movable) * maxScrollLeft.value)
}

function startTrackJump(event) {
  if (!scrollable.value || event.target === thumbRef.value) return
  const rect = trackRef.value?.getBoundingClientRect()
  if (!rect) return
  const targetLeft = event.clientX - rect.left - thumbWidth.value / 2
  const movable = Math.max(1, trackWidth.value - thumbWidth.value)
  setScrollLeft((targetLeft / movable) * maxScrollLeft.value)
}

function stopDrag() {
  contentDragging.value = false
  thumbDragging.value = false
  window.removeEventListener('pointermove', moveContentDrag)
  window.removeEventListener('pointermove', moveThumbDrag)
  window.removeEventListener('mousemove', moveContentDrag)
  window.removeEventListener('mousemove', moveThumbDrag)
}

onMounted(() => {
  nextTick(() => {
    refreshMetrics()
    nextTick(refreshMetrics)
  })
  resizeObserver = new ResizeObserver(refreshMetrics)
  if (viewportRef.value) resizeObserver.observe(viewportRef.value)
  if (contentRef.value) resizeObserver.observe(contentRef.value)
  if (trackRef.value) resizeObserver.observe(trackRef.value)
  window.addEventListener('resize', refreshMetrics)
  window.addEventListener('pointerdown', maybeStartContentDragFromWindow, true)
  window.addEventListener('mousedown', maybeStartContentDragFromWindow, true)
})

onUpdated(() => {
  nextTick(refreshMetrics)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', refreshMetrics)
  window.removeEventListener('pointerdown', maybeStartContentDragFromWindow, true)
  window.removeEventListener('mousedown', maybeStartContentDragFromWindow, true)
  stopDrag()
})

defineExpose({
  refreshMetrics,
  scrollByAmount,
  setScrollLeft,
})
</script>

<style scoped>
.pce-horizontal-scroll-area {
  display: grid;
  gap: 8px;
  width: 100%;
  max-width: 100%;
}

.pce-horizontal-scroll-viewport {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: visible;
  cursor: grab;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}

.pce-horizontal-scroll-viewport.is-dragging {
  cursor: grabbing;
  user-select: none;
}

.pce-horizontal-scroll-content {
  width: max-content;
  min-width: 100%;
}

.pce-horizontal-scroll-controls {
  position: sticky;
  bottom: 0;
  z-index: 4;
  display: grid;
  grid-template-columns: auto minmax(160px, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid #bfd7ff;
  border-radius: 8px;
  background: #f8fbff;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.pce-horizontal-scroll-button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #ffffff;
  color: #1d4ed8;
  font-weight: 800;
}

.pce-horizontal-scroll-button:disabled {
  border-color: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
}

.pce-horizontal-scroll-track {
  position: relative;
  height: 18px;
  border-radius: 999px;
  background: #dbeafe;
  cursor: pointer;
}

.pce-horizontal-scroll-thumb {
  position: absolute;
  top: 2px;
  left: 0;
  min-width: 44px;
  height: 14px;
  border-radius: 999px;
  background: #2563eb;
  cursor: grab;
  touch-action: none;
  pointer-events: auto;
}

.pce-horizontal-scroll-thumb:active {
  cursor: grabbing;
}

.pce-horizontal-scroll-instruction,
.pce-horizontal-scroll-noop {
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.pce-horizontal-scroll-noop {
  padding: 6px 8px;
  border-radius: 6px;
  background: #f8fafc;
}
</style>
