export const ARCH_RULES = {
  domain: {
    desc: '只定义数据结构，不允许请求API、不允许UI逻辑',
    allow: [],
    forbid: ['api', 'runtime', 'vue', 'axios'],
  },

  runtime: {
    desc: '执行层，可以调用api和workflow',
    allow: ['api', 'workflow', 'domain'],
    forbid: ['ui'],
  },

  workflow: {
    desc: '流程控制层，只能调用runtime',
    allow: ['runtime'],
    forbid: ['ui', 'api'],
  },

  api: {
    desc: '唯一请求层',
    allow: [],
    forbid: ['domain', 'ui', 'workflow'],
  },

  view: {
    desc: 'UI层，只能调用runtime',
    allow: ['runtime'],
    forbid: ['api'],
  },
}
