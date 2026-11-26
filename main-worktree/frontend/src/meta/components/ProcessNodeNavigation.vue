<template>
  <article
    class="process-node-navigation"
    :class="{ bound: navigable, selected }"
    data-process-node-visual="card"
    :data-process-node="node.nodeCode"
    :data-process-node-sequence="node.sequence"
    :data-process-node-status="node.acceptanceStatus"
    :data-process-node-version="node.pageVersion || undefined"
    :data-page-code="node.pageCode || undefined"
    :data-page-url="node.pageUrl || undefined"
    :data-allow-new-tab="node.allowNewTab === true"
  >
    <button
      type="button"
      class="process-node-summary"
      :disabled="!node.pageUrl"
      :aria-label="`查看${node.nodeName}节点信息`"
      @click="openCurrentPage"
    >
      <span class="node-sequence">{{ node.sequence }}</span>
      <strong>{{ node.nodeName }}</strong>
      <small v-if="node.pageUrl">{{ node.pageVersion || '页面已登记' }}</small>
      <small v-else>流程节点</small>
      <em v-if="node.pageUrl">页面已挂接 · {{ node.acceptanceStatus }}</em>
      <small v-if="node.statusDescription" class="status-description">{{ node.statusDescription }}</small>
    </button>
    <div class="process-node-actions" aria-label="流程节点操作">
      <button
        type="button"
        data-process-node-action="view-page"
        :disabled="!node.pageUrl"
        @click="openCurrentPage"
      >查看页面</button>
      <button
        type="button"
        data-process-node-action="new-tab"
        :disabled="!navigable"
        @click="openNewTab"
      >新标签打开</button>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  isProcessNodeNavigable,
  openProcessNodeInCurrentPage,
  openProcessNodeInNewTab,
} from '../process/processNodeNavigation.js'

const props = defineProps({
  node: { type: Object, required: true },
  selected: { type: Boolean, default: false },
})

const emit = defineEmits(['inspect', 'opened'])
const router = useRouter()
const navigable = computed(() => isProcessNodeNavigable(props.node))

function inspect() {
  if (!props.node.pageUrl) return
  emit('inspect', props.node)
}

async function openNewTab() {
  const pending = openProcessNodeInNewTab(props.node, router)
  const result = pending.handoffPromise ? await pending.handoffPromise : pending
  emit('opened', { node: props.node, ...result })
}

async function openCurrentPage() {
  inspect()
  const result = await openProcessNodeInCurrentPage(props.node, router)
  emit('opened', { node: props.node, ...result })
}
</script>

<style scoped>
.process-node-navigation {
  box-sizing: border-box;
  display: grid;
  flex: 0 0 200px;
  gap: 8px;
  width: 200px;
  min-width: 200px;
  max-width: 200px;
  min-height: 154px;
  padding: 9px;
  border: 1px solid #d7dee9;
  border-radius: 9px;
  background: #f8fafc;
}

.process-node-navigation.bound {
  border-color: #60a5fa;
  background: #eff6ff;
}

.process-node-navigation.selected {
  box-shadow: inset 0 0 0 2px #2563eb;
}

.process-node-summary {
  box-sizing: border-box;
  display: grid;
  gap: 5px;
  min-width: 0;
  width: 100%;
  padding: 2px;
  border: 0;
  background: transparent;
  color: #475569;
  text-align: left;
}

.process-node-summary strong {
  color: #0f172a;
  font-size: 15px;
  overflow-wrap: anywhere;
}

.process-node-summary small,
.process-node-summary em {
  color: #64748b;
  font-size: 11px;
  font-style: normal;
}

.process-node-summary .status-description {
  color: #334155;
  line-height: 1.4;
}

.process-node-summary em {
  color: #15803d;
  font-weight: 700;
}

.node-sequence {
  display: inline-grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border-radius: 50%;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.process-node-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.process-node-actions button {
  min-width: 0;
  min-height: 34px;
  padding: 5px 7px;
  font-size: 11px;
  white-space: normal;
}

.process-node-actions button[data-process-node-action="new-tab"] {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}
</style>
