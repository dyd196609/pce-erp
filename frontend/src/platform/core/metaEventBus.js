// ======================================
// Meta Runtime V17 - Event Bus
// 全系统通信核心
// ======================================

const listeners = {}

// 注册事件
export const onEvent = (event, handler) => {
  if (!listeners[event]) listeners[event] = []
  listeners[event].push(handler)
}

// 触发事件
export const emitEvent = (event, payload) => {
  const handlers = listeners[event] || []
  handlers.forEach((fn) => fn(payload))
}

// 清除事件
export const clearEvent = (event) => {
  delete listeners[event]
}
