const plugins = {}

export function registerPlugin(name, plugin) {
  plugins[name] = plugin
}

export function runPlugin(name, input) {
  if (!plugins[name]) {
    return { error: 'PLUGIN_NOT_FOUND' }
  }

  return plugins[name](input)
}

export function listPlugins() {
  return Object.keys(plugins)
}
