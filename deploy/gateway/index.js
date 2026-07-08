import http from 'node:http'
import { handleRequest } from '../../frontend/src/meta/api/profitOSApi.js'
import { listRegisteredModules } from '../../frontend/src/meta/registry/moduleRegistry.js'
import { handleAgent } from '../agent-service/index.js'
import { handleBusiness } from '../business-service/index.js'
import { handleKernel } from '../kernel-service/index.js'

export async function route(req) {
  const { type, path } = req

  if (path === '/api/core/modules') {
    return {
      success: true,
      data: listRegisteredModules(),
    }
  }

  if (path?.startsWith('/api/core')) {
    return handleKernel(req)
  }

  if (path?.startsWith('/api/profit')) {
    return handleRequest(req)
  }

  if (path?.startsWith('/api/execution')) {
    return handleAgent(req)
  }

  switch (type) {
    case 'kernel':
      return handleKernel(req)

    case 'agent':
      return handleAgent(req)

    case 'business':
      return handleBusiness(req)

    case 'profitos':
    default:
      return handleRequest(req)
  }
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    let body = ''

    request.on('data', (chunk) => {
      body += chunk
    })

    request.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {})
      } catch (error) {
        reject(error)
      }
    })
  })
}

const server = http.createServer(async (request, response) => {
  const allowedPaths = [
    '/api/profitos/run',
    '/api/core/run',
    '/api/core/modules',
    '/api/profit/run',
    '/api/execution/run',
  ]

  if (request.method !== 'POST' || !allowedPaths.includes(request.url)) {
    response.writeHead(404, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify({ success: false, error: 'NOT_FOUND' }))
    return
  }

  try {
    const payload = await readBody(request)
    const result = await route({
      type: 'profitos',
      path: request.url,
      ...payload,
    })

    response.writeHead(result.success === false ? 403 : 200, {
      'Content-Type': 'application/json',
    })
    response.end(JSON.stringify(result))
  } catch (error) {
    response.writeHead(500, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify({ success: false, error: error.message }))
  }
})

if (process.env.NODE_ENV !== 'test') {
  server.listen(Number(process.env.PORT || 8080), '0.0.0.0')
}
