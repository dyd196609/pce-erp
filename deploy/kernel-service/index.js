import http from 'node:http'
import { runKernel } from '../../frontend/src/meta/kernel-core/index.js'

export async function handleKernel(req = {}) {
  return {
    success: true,
    data: runKernel(req.input, {
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
      const result = await handleKernel(body ? JSON.parse(body) : {})
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify(result))
    })
  })
}

if (process.env.NODE_ENV !== 'test' && process.env.SERVICE === 'kernel') {
  createService().listen(8081, '0.0.0.0')
}
