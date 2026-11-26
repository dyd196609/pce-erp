import {onBeforeUnmount,ref} from 'vue'

// Presentation only: never a source of permissions, quantities or business state.
export function useCompactViewport() {
 const media=typeof window==='undefined'?null:window.matchMedia('(max-width: 900px)')
 const compact=ref(Boolean(media?.matches))
 const changed=event=>{compact.value=event.matches}
 media?.addEventListener('change',changed)
 onBeforeUnmount(()=>media?.removeEventListener('change',changed))
 return compact
}
