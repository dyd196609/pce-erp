<template>
  <div class="bpm-designer">
    <div class="toolbar">
      <el-button type="primary" @click="addNode('start')">开始</el-button>
      <el-button type="success" @click="addNode('approve')">审批节点</el-button>
      <el-button type="warning" @click="addNode('end')">结束</el-button>

      <el-button type="primary" @click="exportFlow">导出流程</el-button>
      <el-button type="primary" @click="step"> 执行一步 </el-button>
    </div>

    <div class="canvas">
      <div
        v-for="node in nodes"
        :key="node.id"
        class="bpmn-node"
        :class="node.type"
        :style="{ left: node.x + 'px', top: node.y + 'px' }"
        @mousedown="startDrag(node, $event)"
      >
        <div class="node-title">
          {{ node.label }}
        </div>

        <div class="node-type">
          {{ node.type }}
        </div>
      </div>

      <!-- 连线层（V2新增） -->
      <svg class="lines">
        <line
          v-for="(edge, i) in edges"
          :key="i"
          :x1="getNode(edge.from).x + 60"
          :y1="getNode(edge.from).y + 30"
          :x2="getNode(edge.to).x + 60"
          :y2="getNode(edge.to).y + 30"
          stroke="#409eff"
          stroke-width="2"
        />
      </svg>
    </div>

    <pre class="output"
      >{{ flowJson }}
    </pre>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { v4 as uuidv4 } from 'uuid'

const nodes = ref([])

const flowJson = ref({})

const addNode = (type) => {
  const map = {
    start: '开始',
    approve: '审批节点',
    service: '自动任务',
    gateway: '条件分支',
    end: '结束',
  }

  nodes.value.push({
    id: uuidv4(),
    type,
    label: map[type],
    x: 100 + nodes.value.length * 120,
    y: 120,
  })
}

const dragState = ref(null)

const startDrag = (node, e) => {
  dragState.value = {
    node,
    offsetX: e.clientX - node.x,
    offsetY: e.clientY - node.y,
  }

  document.onmousemove = onDrag
  document.onmouseup = stopDrag
}

const onDrag = (e) => {
  if (!dragState.value) return

  dragState.value.node.x = e.clientX - dragState.value.offsetX
  dragState.value.node.y = e.clientY - dragState.value.offsetY
}

const stopDrag = () => {
  dragState.value = null
  document.onmousemove = null
  document.onmouseup = null
}

const exportFlow = () => {
  flowJson.value = {
    version: '2.0',
    nodes: nodes.value,
    flows: edges.value,
  }
}

const buildEdges = () => {
  const edges = []

  for (let i = 0; i < nodes.value.length - 1; i++) {
    edges.push({
      from: nodes.value[i].id,
      to: nodes.value[i + 1].id,
    })
  }

  return edges
}
</script>

<style scoped>
.bpm-designer {
  display: flex;
  flex-direction: column;
}

.toolbar {
  padding: 10px;
  border-bottom: 1px solid #ddd;
}

.canvas {
  position: relative;
  height: 500px;
  border: 1px solid #eee;
  margin: 10px;
  overflow: hidden;
  background: #fafafa;
}

.node {
  position: absolute;
  padding: 10px 16px;
  border-radius: 6px;
  cursor: move;
  user-select: none;
}

.start {
  background: #409eff;
  color: white;
}

.approve {
  background: #67c23a;
  color: white;
}

.end {
  background: #f56c6c;
  color: white;
}

.output {
  margin: 10px;
  background: #000;
  color: #0f0;
  padding: 10px;
  font-size: 12px;
}

const edges = ref([])

const getNode = (id) => {
  return nodes.value.find(n => n.id === id) || { x: 0, y: 0 }
}

.bpmn-node {
  position: absolute;
  width: 120px;
  height: 60px;
  border-radius: 8px;
  text-align: center;
  padding: 8px;
  cursor: move;
  user-select: none;
  border: 2px solid #ddd;
  background: white;
}

.start { border-color: #409eff; }
.approve { border-color: #67c23a; }
.service { border-color: #e6a23c; }
.gateway { border-color: #909399; }
.end { border-color: #f56c6c; }

.node-title {
  font-weight: bold;
}

.node-type {
  font-size: 12px;
  color: #999;
}

.lines {
  position: absolute;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

import { createRuntimeInstance, stepExecute } from '@/domain/workflow/bpmRuntime'

const runtime = ref(null)

const runFlow = () => {
  runtime.value = createRuntimeInstance({
    nodes: nodes.value,
    edges: edges.value
  }, {
    risk_score: 75
  })
}

const step = () => {
  runtime.value = stepExecute(runtime.value)
}
</style>
