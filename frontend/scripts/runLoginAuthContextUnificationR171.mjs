import { spawn, spawnSync } from 'node:child_process'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backend = path.resolve(frontend, '..', 'backend')
const python = process.env.PCE_PYTHON || 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const sitePackages = path.join(backend, 'venv', 'Lib', 'site-packages')
const manageBootstrap = `import sys; sys.path.append(r'${sitePackages}'); exec(open('manage.py',encoding='utf-8').read())`

function waitForHttp(url, timeoutMs = 60_000) {
  const startedAt = Date.now()
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const request = http.get(url, (response) => {
        response.resume()
        resolve()
      })
      request.on('error', () => {
        if (Date.now() - startedAt >= timeoutMs) reject(new Error(`Timed out waiting for ${url}`))
        else setTimeout(attempt, 300)
      })
      request.setTimeout(2_000, () => request.destroy())
    }
    attempt()
  })
}

async function isAvailable(url) {
  try {
    await waitForHttp(url, 1_000)
    return true
  } catch {
    return false
  }
}

const backendServer = await isAvailable('http://127.0.0.1:8000/api/auth/login/')
  ? null
  : spawn(
      python,
      ['-c', manageBootstrap, 'runserver', '127.0.0.1:8000', '--noreload'],
      { cwd: backend, windowsHide: true, stdio: ['ignore', 'inherit', 'inherit'] },
    )
const viteServer = await isAvailable('http://localhost:5173')
  ? null
  : spawn(
      'cmd.exe',
      ['/d', '/s', '/c', 'npm.cmd run dev'],
      { cwd: frontend, windowsHide: true, stdio: ['ignore', 'inherit', 'inherit'] },
    )

try {
  await Promise.all([
    waitForHttp('http://127.0.0.1:8000/api/auth/login/'),
    waitForHttp('http://localhost:5173'),
  ])
  const test = spawnSync(
    process.execPath,
    [
      'node_modules/@playwright/test/cli.js',
      'test',
      'tests/auth/loginAuthContextUnificationR171.spec.js',
      '--config=playwright.r171.config.js',
    ],
    { cwd: frontend, env: process.env, windowsHide: true, stdio: 'inherit' },
  )
  if (test.status !== 0) process.exitCode = test.status || 1
} finally {
  for (const child of [viteServer, backendServer]) {
    if (!child?.pid) continue
    spawnSync('taskkill.exe', ['/pid', String(child.pid), '/t', '/f'], {
      windowsHide: true,
      stdio: 'ignore',
    })
  }
}
