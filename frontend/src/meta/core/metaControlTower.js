// V3 CONTROL TOWER - schema execution tracer

export const MetaControlTower = {
  logs: [],

  enable: true,

  record(event, payload = {}) {
    if (!this.enable) return

    const log = {
      time: new Date().toISOString(),
      event,
      payload,
    }

    this.logs.push(log)

    // 控制台输出（关键）
    console.log(`[CONTROL TOWER] ${event}`, payload)
  },

  clear() {
    this.logs = []
  },

  dump() {
    return this.logs
  },
}
