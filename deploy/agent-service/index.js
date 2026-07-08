import http from 'node:http'
import { runAgentCore } from '../../frontend/src/meta/agent-core/index.js'

export async function handleAgent(req = {}) {
  return {
    success: true,
    data: runAgentCore(req.input?.goal || req.input, {
      ...(req.context || {}),
      tenantId: req.tenantId,
    }),
  }
}

function createService() {
  return http.createServer(async (request, response) => {
    if (request.method !== 'POST') {
      response.writeHead(404, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify({ success: false, error: 'NOT_FOUND' }))
      return
    }

    let body = ''
    request.on('data', (chunk) => {
      body += chunk
    })
    request.on('end', async () => {
      const result = await handleAgent(body ? JSON.parse(body) : {})
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify(result))
    })
  })
}

if (process.env.NODE_ENV !== 'test' && process.env.SERVICE === 'agent') {
  createService().listen(8082, '0.0.0.0')
}
