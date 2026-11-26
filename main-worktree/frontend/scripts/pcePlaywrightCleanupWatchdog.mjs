import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import {
  cleanupRuntimeIsolation,
  isProcessAlive,
  windowsListeningPids,
} from './pcePlaywrightRunner.mjs'

const markerName = '.pce-playwright-run-owner.json'
const [runRoot, runId] = process.argv.slice(2)
const markerPath = path.join(runRoot || '', markerName)

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function readMarker() {
  try {
    return JSON.parse(fs.readFileSync(markerPath, 'utf8'))
  } catch {
    return null
  }
}

async function stopOwnedTree(pid) {
  if (!Number.isInteger(pid) || pid <= 0 || !isProcessAlive(pid)) return
  try {
    process.kill(pid, 'SIGTERM')
  } catch {}
  for (let attempt = 0; attempt < 20 && isProcessAlive(pid); attempt += 1) await delay(50)
  if (isProcessAlive(pid)) {
    spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], {
      stdio: 'ignore',
      windowsHide: true,
    })
  }
}

function listeningPids() {
  const result = spawnSync('netstat', ['-ano', '-p', 'tcp'], { encoding: 'utf8', windowsHide: true })
  if (result.error || result.status !== 0) return null
  return windowsListeningPids(result.stdout)
}

if (!runRoot || !runId || process.platform !== 'win32') process.exitCode = 2
else {
  let marker = readMarker()
  while (marker && marker.runId === runId && isProcessAlive(marker.ownerPid)) {
    await delay(250)
    marker = readMarker()
  }

  if (marker?.runId === runId && marker.runRoot === path.resolve(runRoot)) {
    await stopOwnedTree(marker.browserPid)
    await stopOwnedTree(marker.vitePid)
    await delay(150)
    const listeners = listeningPids()
    const knownPids = new Set([marker.browserPid, marker.vitePid].filter(Number.isInteger))
    const unknownListener = listeners === null || listeners.some((pid) => !knownPids.has(pid))
    if (!unknownListener && !isProcessAlive(marker.browserPid) && !isProcessAlive(marker.vitePid)) {
      try {
        cleanupRuntimeIsolation({ runId, tempRoot: runRoot, profileRoot: runRoot })
      } catch {
        process.exitCode = 3
      }
    } else {
      process.exitCode = 4
    }
  }
}
