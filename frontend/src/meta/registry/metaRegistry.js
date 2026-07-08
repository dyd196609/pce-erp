/**
 * Meta Registry（V24统一入口）
 * ===========================
 */

export const loadMeta = async (name) => {
  try {
    const module = await import(`../pages/${name}.meta.js`)
    return module.default
  } catch (e) {
    console.error('[MetaRegistry] loadMeta failed:', name, e)
    return {}
  }
}

/**
 * 未来扩展：
 * - remote meta
 * - backend meta
 * - version meta
 */
