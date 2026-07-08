// ===============================
// SCHEMA RESOLVER V3.8 FIXED
// ===============================

import { schemaRegistry } from './schemaRegistry'
import { normalizeSchema } from './schemaNormalizer'

export async function resolveSchema(route) {
  const path = route.path

  console.log('[SCHEMA RESOLVER] path:', path)

  const loader = schemaRegistry?.[path]

  if (!loader) {
    throw new Error('[V3.8] route not mapped to schema')
  }

  const raw = await loader()

  return {
    default: normalizeSchema(raw),
  }
}
