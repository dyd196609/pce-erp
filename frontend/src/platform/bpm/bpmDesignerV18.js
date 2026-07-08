/**
 * ============================
 * Meta Runtime V18 - BPM Designer
 * 可视化流程设计器
 * ============================
 */

const nodes = []
const edges = []

// 添加节点
export const addNode = (node) => {
  nodes.push({
    id: generateId(),
    ...node,
  })
}

// 添加连线
export const addEdge = (from, to) => {
  edges.push({ from, to })
}

// 生成流程定义（核心）
export const buildProcess = () => {
  return {
    nodes,
    edges,
  }
}

// 清空设计器
export const resetDesigner = () => {
  nodes.length = 0
  edges.length = 0
}

function generateId() {
  return 'node_' + Math.random().toString(36).slice(2, 8)
}
