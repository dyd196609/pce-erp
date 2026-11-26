import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import locale from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'
import './styles/appExperience.css'
import './styles/pceAdvancedFilterLayout.css'
import {
  MATERIAL_RUNTIME_STATUS,
  initializeMaterialMasterRuntimeLifecycle,
} from './meta/providers/materialMasterRuntimeProvider'

function normalizeHashHistoryUrl() {
  if (typeof window === 'undefined') return false

  const { origin, pathname, search, hash } = window.location
  const normalizedPath = pathname.replace(/\/$/, '') || '/'
  const isRootPath = normalizedPath === '/' || normalizedPath === '/index.html'

  if (hash.startsWith('#/') && !isRootPath) {
    window.location.replace(`${origin}/${hash}`)
    return true
  }

  const enterprisePaths = new Set([
    '/dashboard',
    '/process-center',
    '/work-center',
    '/organization',
    '/analytics',
    '/admin',
  ])

  if (!hash && enterprisePaths.has(normalizedPath)) {
    window.location.replace(`${origin}/#${normalizedPath}${search || ''}`)
    return true
  }

  return false
}

async function bootstrap() {
  if (import.meta.env.DEV) {
    console.info(`Current Frontend Origin: ${window.location.origin}`)
  }

  const materialRuntime = initializeMaterialMasterRuntimeLifecycle({
    onError(error) {
      if (![MATERIAL_RUNTIME_STATUS.AUTH_REQUIRED, MATERIAL_RUNTIME_STATUS.PERMISSION_DENIED].includes(error?.code)) {
        console.error('MaterialMaster runtime preload failed', error)
      }
    },
  })

  // An unauthenticated start is a valid lifecycle state. Authenticated sessions
  // still preload before mount; login and identity changes trigger a fresh load.
  try {
    await materialRuntime.preload()
  } catch (error) {
    if (![MATERIAL_RUNTIME_STATUS.AUTH_REQUIRED, MATERIAL_RUNTIME_STATUS.PERMISSION_DENIED].includes(error?.code)) {
      console.error('MaterialMaster runtime preload failed', error)
    }
  }

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus, { locale })
  app.mount('#app')
}

if (!normalizeHashHistoryUrl()) bootstrap()
