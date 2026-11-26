import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { UI_BRAND } from './src/meta/runtime/uiBranding.js'
import path from 'path'
import { fileURLToPath } from 'url'
import { createHash } from 'crypto'
import { readFileSync } from 'fs'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const identityFiles = Object.freeze({
  router: path.resolve(__dirname, 'src/router/index.js'),
  moduleRegistry: path.resolve(__dirname, 'src/meta/master-data/foundationEntryUnificationRegistry.js'),
  pageComponent: path.resolve(__dirname, 'src/meta/components/ProductionFoundationMaintenance.vue'),
})
const fileHash = file => createHash('sha256').update(readFileSync(file)).digest('hex')
const identityHashes = Object.freeze({
  routerRegistryHash: fileHash(identityFiles.router),
  moduleRegistryHash: fileHash(identityFiles.moduleRegistry),
  pageComponentHash: fileHash(identityFiles.pageComponent),
})
const sourceTreeId = `working-tree:${createHash('sha256').update(Object.values(identityHashes).join(':')).digest('hex')}`
const bundleTimestamp = new Date().toISOString()
const buildRuntimeId = `pce-foundation-${sourceTreeId.slice(-16)}`
const UNIFIED_PROXY_TARGET = 'http://127.0.0.1:8075'

function frontendRuntimeIdentityPlugin(runtimeIdentity) {
  const payload = Object.freeze({ contract: 'PCE-FRONTEND-RUNTIME-IDENTITY-V1', buildRuntimeId, sourceTreeId, bundleTimestamp, ...identityHashes, unifiedBaselineId:String(process.env.PCE_UNIFIED_BASELINE_ID || 'UNBOUND'),sourceRoot:path.resolve(__dirname,'..'),handoverComponentHash:fileHash(path.resolve(__dirname,'src/meta/components/OperationHandoverContent.vue')),reviewComponentHash:fileHash(path.resolve(__dirname,'src/meta/components/OperationCompletionContent.vue')),tableComponentHash:fileHash(path.resolve(__dirname,'src/meta/components/PceEnterpriseListTable.vue')),logoSHA256:fileHash(path.resolve(__dirname,'public/brand/palmcloud-original.png')),uiVersion:UI_BRAND.version, uiBrand:UI_BRAND.name, loginComponentHash:fileHash(path.resolve(__dirname,'src/views/Login.vue')), reportComponentHash:fileHash(path.resolve(__dirname,'src/meta/components/OperationReportContent.vue')), ...runtimeIdentity })
  return {
    name: 'pce-frontend-runtime-identity',
    handleHotUpdate({ file, server }) {
      if (Object.values(identityFiles).includes(path.resolve(file))) {
        setTimeout(() => server.restart(), 0)
        return []
      }
      return undefined
    },
    configureServer(server) {
      server.middlewares.use('/__pce_frontend_identity', (_request, response) => {
        response.setHeader('Content-Type', 'application/json; charset=utf-8')
        response.setHeader('Cache-Control', 'no-store')
        response.end(JSON.stringify(payload))
      })
    },
  }
}

function productionFoundationA0CompatibilityPlugin() {
  return {
    name: 'pce-production-foundation-a0-compatibility',
    enforce: 'pre',
    transform(source, id) {
      if (!id.replaceAll('\\\\', '/').endsWith('/src/meta/pages/ManufacturingFoundationPage.vue')) return null
      return source
        .replace("return 'manufacturingFoundationStore'", "return 'ProductionFoundationServerCompatibilityProvider'")
        .replace(": 'manufacturing-foundation-state-v1'", ": 'server-required-localStorage-rejected'")
        .replace(
          'return { rows: [...(latest[collection] || [])], localProvider: true }',
          "return { rows: [...(latest[collection] || [])], localProvider: false, factLoadStatus: 'read_failed', errorCode: 'PRODUCTION_SERVER_FACT_NOT_CONNECTED' }",
        )
    },
  }
}

export default defineConfig(({ command, mode }) => {
  const configuredProxyTarget = String(process.env.PCE_API_PROXY_TARGET || '').trim()
  const unifiedServe = command === 'serve' && mode === 'unified-acceptance'
  if (unifiedServe && configuredProxyTarget !== UNIFIED_PROXY_TARGET) {
    throw new Error(`统一验收前端必须显式代理到 ${UNIFIED_PROXY_TARGET}；请使用 tools/Start-PceUnifiedDevelopment.ps1。`)
  }
  if (unifiedServe && process.env.PCE_RUNTIME_PROFILE !== 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE') {
    throw new Error('统一验收前端缺少 PCE_RUNTIME_PROFILE；拒绝以未声明运行身份启动。')
  }
  if (unifiedServe && process.env.PCE_RUNTIME_LAUNCHER_VERIFIED !== '1') {
    throw new Error('统一验收前端未通过启动器只读预检；拒绝直接启动。')
  }
  const proxy = configuredProxyTarget
    ? { '/api': { target: configuredProxyTarget, changeOrigin: true } }
    : {}
  // node_modules can be a shared dependency junction. Optimizer caches must
  // belong to this source tree and must not race its live development server.
  const cacheDir = path.resolve(__dirname, '.pce-vite-cache', process.env.PCE_PLAYWRIGHT_RUN_ID ? 'acceptance' : 'development')
  return {
  cacheDir,
  plugins: [frontendRuntimeIdentityPlugin({ mode, apiProxyTarget: configuredProxyTarget || null, cacheDir }), productionFoundationA0CompatibilityPlugin(), vue()],

  define: {
    __PCE_BUILD_RUNTIME_ID__: JSON.stringify(buildRuntimeId),
    __PCE_SOURCE_TREE_ID__: JSON.stringify(sourceTreeId),
    __PCE_BUNDLE_TIMESTAMP__: JSON.stringify(bundleTimestamp),
    __PCE_ROUTER_HASH__: JSON.stringify(identityHashes.routerRegistryHash),
    __PCE_MODULE_REGISTRY_HASH__: JSON.stringify(identityHashes.moduleRegistryHash),
    __PCE_PAGE_COMPONENT_HASH__: JSON.stringify(identityHashes.pageComponentHash),
  },

  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, 'src') },
      {
        find: /^.*\/manufacturing\/manufacturingFoundationStore\.js$/,
        replacement: path.resolve(__dirname, 'src/meta/productionFoundationStore.js'),
      },
      {
        find: /^.*\/manufacturing\/manufacturingReferenceService\.js$/,
        replacement: path.resolve(__dirname, 'src/meta/productionFoundationReferenceService.js'),
      },
      {
        find: /^.*\/manufacturing\/manufacturingFoundationChecker\.js$/,
        replacement: path.resolve(__dirname, 'src/meta/productionFoundationChecker.js'),
      },
    ],
  },

  server: {
    port: 5173,
    strictPort: true,

    proxy,
  },
  }
})
