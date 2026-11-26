/** Serialize writes and reconcile committed actions through a fresh, read-only request. */
export function createReviewOperation({write, read, validate, onBusy, onReadback, onError, onPending}) {
  let busy=false, pending=null, generation=0
  const setBusy=value=>{busy=value;onBusy(value)}
  const current=epoch=>epoch===generation
  async function reconcile(entry, epoch) {
    try {
      const response=await read(entry.payload)
      if(!current(epoch))return false
      if(!response?.success)throw new Error(response?.error?.message||'服务端状态读取失败')
      const error=validate(response.data,entry.payload)
      if(error)throw new Error(error)
      pending=null;onPending(null);onReadback(response.data,entry.payload)
      return true
    } catch(error) {
      if(current(epoch)) {
        pending=entry;onPending(entry)
        const prefix=entry.acknowledged?(entry.payload.action==='signItems'?'已签认，状态回读失败':'已保存，状态回读失败'):'操作结果尚未确认'
        onError(`${prefix}：${error.message}。输入已保留，请只读重试。`)
      }
      return false
    }
  }
  return {
    async run(payload) {
      if(busy||pending)return false
      const epoch=++generation;setBusy(true)
      try {
        let response
        try {response=await write(payload)} catch(error) {
          if(current(epoch)){pending={payload,acknowledged:false};onPending(pending);onError(`操作结果尚未确认：${error.message}。输入已保留，请只读重试。`)}
          return false
        }
        if(!current(epoch))return false
        if(!response?.success){onError(`${response?.error?.message||'操作失败'}${response?.error?.code?`（${response.error.code}）`:''}；输入已保留。`);return false}
        return await reconcile({payload,acknowledged:true},epoch)
      } finally {if(current(epoch))setBusy(false)}
    },
    async retryReadback() {
      if(busy||!pending)return false
      const epoch=++generation;setBusy(true)
      try{return await reconcile(pending,epoch)}finally{if(current(epoch))setBusy(false)}
    },
    invalidate(){generation++;pending=null;onPending(null);setBusy(false)},
  }
}
