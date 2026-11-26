import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'

const [distRootArg, portArg, backendOriginArg, identityFileArg] = process.argv.slice(2)
const distRoot = path.resolve(distRootArg || '')
const port = Number(portArg || 5183)
const backendOrigin = new URL(backendOriginArg || 'http://127.0.0.1:8001')
const identityFile = path.resolve(identityFileArg || '')

if (!fs.existsSync(path.join(distRoot, 'index.html'))) throw new Error(`built index missing: ${distRoot}`)
if (!fs.existsSync(identityFile)) throw new Error(`identity file missing: ${identityFile}`)

const mime = new Map([
  ['.html', 'text/html; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'], ['.json', 'application/json; charset=utf-8'],
  ['.svg', 'image/svg+xml'], ['.png', 'image/png'], ['.ico', 'image/x-icon'],
  ['.woff', 'font/woff'], ['.woff2', 'font/woff2'],
])

function proxy(request, response) {
  const upstream = http.request({
    protocol: backendOrigin.protocol,
    hostname: backendOrigin.hostname,
    port: backendOrigin.port,
    method: request.method,
    path: request.url,
    headers: { ...request.headers, host: backendOrigin.host },
  }, upstreamResponse => {
    response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers)
    upstreamResponse.pipe(response)
  })
  upstream.on('error', error => {
    response.writeHead(502, { 'content-type': 'application/json; charset=utf-8' })
    response.end(JSON.stringify({ factLoadStatus: 'read_failed', errorCode: 'REHEARSAL_BACKEND_UNREACHABLE', errorMessage: error.message }))
  })
  request.pipe(upstream)
}

http.createServer((request, response) => {
  const requestPath = new URL(request.url || '/', 'http://127.0.0.1').pathname
  if (requestPath.startsWith('/api/')) return proxy(request, response)
  if (requestPath === '/__pce_frontend_identity') {
    response.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
    return response.end(fs.readFileSync(identityFile))
  }
  const relative = decodeURIComponent(requestPath).replace(/^\/+/, '')
  const candidate = path.resolve(distRoot, relative || 'index.html')
  const safeCandidate = candidate.startsWith(`${distRoot}${path.sep}`) || candidate === path.join(distRoot, 'index.html')
  const file = safeCandidate && fs.existsSync(candidate) && fs.statSync(candidate).isFile()
    ? candidate : path.join(distRoot, 'index.html')
  response.writeHead(200, { 'content-type': mime.get(path.extname(file).toLowerCase()) || 'application/octet-stream' })
  fs.createReadStream(file).pipe(response)
}).listen(port, '127.0.0.1', () => {
  console.log(`PCE rehearsal frontend ready at http://127.0.0.1:${port}`)
})
