<template>
  <section class="bpm-designer">
    <aside class="designer-panel">
      <h3>BPM 状态节点</h3>
      <div class="add-row">
        <input v-model="newState" placeholder="STATE_ID" @keyup.enter="handleAddState">
        <button type="button" @click="handleAddState">添加状态</button>
      </div>

      <button
        v-for="node in graph.nodes"
        :key="node.id"
        type="button"
        class="state-item"
        draggable="true"
        @dragstart="dragging = node.id"
        @click="selectedNode = node.id"
      >
        <span>{{ translate(node.id) }}</span>
        <small>{{ node.id }}</small>
      </button>

      <button
        type="button"
        class="danger"
        :disabled="!selectedNode || disabled"
        @click="handleDeleteState"
      >
        删除状态
      </button>
    </aside>

    <main
      class="graph-panel"
      @dragover.prevent
      @drop="handleDrop"
    >
      <header>
        <strong>Workflow Graph</strong>
        <span>{{ graph.nodes.length }} 个状态 / {{ graph.edges.length }} 条流转</span>
      </header>

      <div class="graph-canvas">
        <button
          v-for="node in graph.nodes"
          :key="node.id"
          type="button"
          class="graph-node"
          :class="{ selected: selectedNode === node.id }"
          :style="{ left: `${node.x}px`, top: `${node.y}px` }"
          draggable="true"
          @dragstart="dragging = node.id"
          @click="selectedNode = node.id"
        >
          {{ translate(node.id) }}
        </button>

        <button
          v-for="edge in graph.edges"
          :key="edge.id"
          type="button"
          class="graph-edge"
          :class="{ selected: selectedEdge?.id === edge.id }"
          @click="selectedEdge = edge"
        >
          {{ edge.from }} → {{ edge.to }}
        </button>
      </div>
    </main>

    <aside class="designer-panel">
      <h3>Action / Transition 编辑</h3>

      <label>
        From
        <select v-model="transitionFrom">
          <option v-for="node in graph.nodes" :key="node.id" :value="node.id">
            {{ node.id }}
          </option>
        </select>
      </label>

      <label>
        To
        <select v-model="transitionTo">
          <option v-for="node in graph.nodes" :key="node.id" :value="node.id">
            {{ node.id }}
          </option>
        </select>
      </label>

      <button type="button" :disabled="disabled" @click="handleAddTransition">
        添加连线
      </button>

      <button
        type="button"
        class="danger"
        :disabled="!selectedEdge || disabled"
        @click="handleDeleteTransition"
      >
        删除选中连线
      </button>

      <button type="button" class="primary" :disabled="disabled" @click="handleSave">
        保存 Schema
      </button>

      <p v-if="disabled" class="blocked-note">
        当前模块已被审查控制阻断，禁止编辑。
      </p>
    </aside>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  addState,
  addTransition,
  applyGraphToSchema,
  buildDesignerGraph,
  deleteState,
  deleteTransition,
  moveState,
} from './bpmDesignerEngine.js'
import { translate } from '../runtime/i18nEngine.js'

const props = defineProps({
  schema: {
    type: Object,
    required: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['save', 'update'])

const graph = ref(buildDesignerGraph(props.schema))
const newState = ref('')
const selectedNode = ref('')
const selectedEdge = ref(null)
const dragging = ref('')

const transitionFrom = ref(graph.value.nodes[0]?.id || '')
const transitionTo = ref(graph.value.nodes[1]?.id || graph.value.nodes[0]?.id || '')

const schemaPatch = computed(() => applyGraphToSchema(graph.value))

watch(
  () => props.schema,
  (schema) => {
    graph.value = buildDesignerGraph(schema)
  }
)

watch(schemaPatch, () => {
  emit('update', buildSchema())
})

function buildSchema() {
  return {
    ...props.schema,
    workflow: {
      ...(props.schema.workflow || {}),
      ...schemaPatch.value,
    },
  }
}

function handleAddState() {
  if (props.disabled) return
  graph.value = addState(graph.value, newState.value)
  newState.value = ''
}

function handleDeleteState() {
  if (props.disabled || !selectedNode.value) return
  graph.value = deleteState(graph.value, selectedNode.value)
  selectedNode.value = ''
}

function handleDrop(event) {
  if (props.disabled || !dragging.value) return

  const rect = event.currentTarget.getBoundingClientRect()
  graph.value = moveState(graph.value, dragging.value, {
    x: Math.max(12, event.clientX - rect.left - 40),
    y: Math.max(54, event.clientY - rect.top - 18),
  })
  dragging.value = ''
}

function handleAddTransition() {
  if (props.disabled) return
  graph.value = addTransition(graph.value, transitionFrom.value, transitionTo.value)
}

function handleDeleteTransition() {
  if (props.disabled || !selectedEdge.value) return
  graph.value = deleteTransition(graph.value, selectedEdge.value.id)
  selectedEdge.value = null
}

function handleSave() {
  if (props.disabled) return
  emit('save', buildSchema())
}
</script>

<style scoped>
.bpm-designer {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  gap: 12px;
  min-height: 520px;
}

.designer-panel,
.graph-panel {
  min-width: 0;
  padding: 14px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.designer-panel h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.add-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  margin-bottom: 12px;
}

input,
select {
  width: 100%;
  min-height: 34px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 8px;
}

button {
  min-height: 34px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  border-radius: 6px;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.primary {
  background: #1d4ed8;
  color: #fff;
  border-color: #1d4ed8;
}

.danger {
  color: #991b1b;
  border-color: #fecaca;
  background: #fff7f7;
}

.state-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 0 10px;
}

.state-item small {
  color: #64748b;
}

.graph-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.graph-canvas {
  position: relative;
  min-height: 440px;
  overflow: hidden;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
}

.graph-node {
  position: absolute;
  min-width: 86px;
  border-color: #93c5fd;
  background: #e0f2fe;
  color: #075985;
}

.graph-node.selected {
  background: #1d4ed8;
  color: #fff;
}

.graph-edge {
  display: inline-flex;
  margin: 10px 8px 0 10px;
  padding: 0 10px;
}

.graph-edge.selected {
  background: #dcfce7;
  border-color: #22c55e;
}

label {
  display: block;
  margin-bottom: 12px;
  color: #475569;
}

.blocked-note {
  color: #991b1b;
}

@media (max-width: 980px) {
  .bpm-designer {
    grid-template-columns: 1fr;
  }
}
</style>

