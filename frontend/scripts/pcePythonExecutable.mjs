import fs from 'node:fs'
import path from 'node:path'

export function resolvePcePython(repositoryRoot, env = process.env) {
  if (env.PCE_PYTHON) return env.PCE_PYTHON
  const projectPython = path.join(repositoryRoot, 'backend', 'venv', 'Scripts', 'python.exe')
  return fs.existsSync(projectPython) ? projectPython : 'python'
}

export function resolvePcePythonRuntime(repositoryRoot, env = process.env) {
  if (env.PCE_PYTHON) return { executable: env.PCE_PYTHON, env }
  const backendRoot = path.join(repositoryRoot, 'backend')
  const venvRoot = path.join(backendRoot, 'venv')
  const configPath = path.join(venvRoot, 'pyvenv.cfg')
  if (fs.existsSync(configPath)) {
    const config = fs.readFileSync(configPath, 'utf8')
    const configured = config.match(/(?:^|[\r\n])executable\s*=\s*([^\r\n]+)/)?.[1]?.trim()
    if (configured) {
      const sitePackages = path.join(venvRoot, 'Lib', 'site-packages')
      return {
        executable: configured,
        env: { ...env, PYTHONPATH: [sitePackages, env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
      }
    }
  }
  return { executable: resolvePcePython(repositoryRoot, env), env }
}
