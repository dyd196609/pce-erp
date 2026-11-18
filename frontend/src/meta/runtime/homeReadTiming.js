let bootstrapStart=null
export function isHomeBootstrap(){return typeof window!=='undefined' && ['','#','#/'].includes(window.location.hash)||typeof window!=='undefined' && window.location.hash.startsWith('#/home')}
export function markHomeBootstrap(){if(isHomeBootstrap())bootstrapStart=0}
export function consumeHomeBootstrap(){const value=bootstrapStart;bootstrapStart=null;return value}
export function clearHomeBootstrap(){bootstrapStart=null}
