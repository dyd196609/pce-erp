import http from 'node:http'
import { runBusinessCore } from '../../frontend/src/meta/business-core/index.js'

export async function handleBusiness(req = {}) {
  return {
    success: true,
    data: runBusinessCore(req.context?.data || req.context?.order || req.input || {}),
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
      const result = await handleBusiness(body ? JSON.parse(body) : {})
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify(result))
    })
  })
}

if (process.env.NODE_ENV !== 'test' && process.env.SERVICE === 'business') {
  createService().listen(8083, '0.0.0.0')
}
