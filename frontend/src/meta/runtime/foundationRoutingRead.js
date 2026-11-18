export function isScopedRoutingView(entity, mode, subview) {
  return entity === 'routings' && mode === 'view' && !subview
}

export function assertFoundationRequestIdentity(displayed, actual) {
  if (!displayed?.username || !actual?.username || displayed.username !== actual.username
      || (displayed.userId != null && String(displayed.userId) !== String(actual.userId))
      || (displayed.companyId != null && String(displayed.companyId) !== String(actual.companyId))) {
    throw new Error('当前标签账户与服务端请求身份不一致，已停止展示；请核对本标签的原登录身份，不代表没有路线数据。')
  }
}

export function isScopedFoundationView(entity,mode,subview){
  return Boolean(entity) && entity!=='operations' && entity!=='engineering-rule-definitions' && ['view','maintain'].includes(mode) && !subview
}
