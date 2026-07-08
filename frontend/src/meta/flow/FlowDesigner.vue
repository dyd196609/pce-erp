<template>
  <div class="flow-designer">
    <h3>V27 条件分支流程图</h3>

    <div class="toolbar">
      <button @click="addNode('start')">开始</button>
      <button @click="addNode('approval')">审批</button>
      <button @click="addNode('end')">结束</button>
      <button @click="setLinkMode">连线模式</button>
      <button @click="exportFlow">导出JSON</button>
    </div>

    <!-- 画布 -->
    <div class="canvas">
      <!-- 连线 -->
      <svg class="lines">
        <g v-for="(e, i) in flowSchema.edges" :key="i">
          <line
            :x1="getNode(e.from)?.x + 60"
            :y1="getNode(e.from)?.y + 30"
            :x2="getNode(e.to)?.x + 60"
            :y2="getNode(e.to)?.y + 30"
            stroke="black"
            stroke-width="2"
          />

          <!-- 条件标签 -->
          <text
            :x="(getNode(e.from)?.x + getNode(e.to)?.x) / 2"
            :y="(getNode(e.from)?.y + getNode(e.to)?.y) / 2"
            fill="red"
          >
            {{ formatCondition(e.condition) }}
          </text>
        </g>
      </svg>

      <!-- 节点 -->
      <div
        v-for="node in flowSchema.nodes"
        :key="node.id"
        class="node"
        :style="{ left: node.x + 'px', top: node.y + 'px' }"
        @click="handleNodeClick(node)"
      >
        {{ node.name }}
      </div>
    </div>

    <!-- 条件编辑器 -->
    <div v-if="showConditionPanel" class="panel">
      <h4>设置条件</h4>

      <select v-model="condition.field">
        <option value="amount">金额</option>
        <option value="level">等级</option>
      </select>

      <select v-model="condition.op">
        <option value=">">&gt;</option>
        <option value="<">&lt;</option>
        <option value=">=">&gt;=</option>
        <option value="<=">&lt;=</option>
        <option value="==">==</option>
      </select>

      <input v-model="condition.value" placeholder="值" />

      <button @click="confirmEdge">确认连线</button>
    </div>

    <pre>{{ flowSchema }}</pre>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'

let id = 1

const flowSchema = reactive({
  nodes: [],
  edges: [],
  statusField: 'status',
})

const linkMode = ref(false)
const fromNode = ref(null)

const showConditionPanel = ref(false)

const condition = reactive({
  field: 'amount',
  op: '>',
  value: 0,
})

// --------------------
// 节点
// --------------------
function addNode(type) {
  flowSchema.nodes.push({
    id: 'n_' + id++,
    name: type,
    type,
    x: 100 + id * 30,
    y: 100 + id * 30,
  })
}

// --------------------
// 点击节点
// --------------------
function handleNodeClick(node) {
  if (!linkMode.value) return

  if (!fromNode.value) {
    fromNode.value = node
  } else {
    // 打开条件面板
    pendingEdge.from = fromNode.value
    pendingEdge.to = node
    showConditionPanel.value = true
  }
}

// --------------------
// 临时边
// --------------------
const pendingEdge = reactive({
  from: null,
  to: null,
})

// --------------------
// 确认边
// --------------------
function confirmEdge() {
  flowSchema.edges.push({
    from: pendingEdge.from.id,
    to: pendingEdge.to.id,
    condition: { ...condition },
  })

  showConditionPanel.value = false
  fromNode.value = null
}

// --------------------
// 找节点
// --------------------
function getNode(id) {
  return flowSchema.nodes.find((n) => n.id === id)
}

// --------------------
// 连线模式
// --------------------
function setLinkMode() {
  linkMode.value = true
  fromNode.value = null
}

// --------------------
// 格式化条件
// --------------------
function formatCondition(c) {
  if (!c) return '无条件'
  return `${c.field} ${c.op} ${c.value}`
}

// --------------------
// 导出
// --------------------
function exportFlow() {
  console.log(JSON.stringify(flowSchema, null, 2))
}
</script>

<style>
.flow-designer {
  padding: 20px;
}
.canvas {
  position: relative;
  height: 500px;
  border: 1px solid #ccc;
}
.node {
  position: absolute;
  width: 100px;
  background: #409eff;
  color: #fff;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}
.lines {
  position: absolute;
  width: 100%;
  height: 100%;
}
.panel {
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #aaa;
}
</style>
