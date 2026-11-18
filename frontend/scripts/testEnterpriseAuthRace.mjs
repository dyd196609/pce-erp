import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
test('late previous identity permission response cannot replace new identity cache',async()=>{
 let epoch=1;const pending=[]
 globalThis.__homeAuthEpoch=()=>epoch
 globalThis.__homeProfile=()=>new Promise(resolve=>pending.push(resolve))
 let source=fs.readFileSync(new URL('../src/meta/runtime/permissionProfileRuntime.js',import.meta.url),'utf8')
 source=source.replace("import {getTabAuthEpoch} from './tabAuthenticationContext.js'",'const getTabAuthEpoch=()=>globalThis.__homeAuthEpoch()')
 source=source.replace("import { accessControlApi } from '@/api/accessControl.js'",'const accessControlApi={profile:()=>globalThis.__homeProfile()}')
 const m=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
 const old=m.loadPermissionProfile({force:true});const denied=assert.rejects(old,/认证身份已变化/)
 epoch=2;const current=m.loadPermissionProfile({force:true})
 pending[1]({success:true,data:{authenticated:true,userId:2,permissionCodes:[]}});await current
 pending[0]({success:true,data:{authenticated:true,userId:1,permissionCodes:['*']}});await denied
 assert.equal((await m.loadPermissionProfile()).userId,2)
 delete globalThis.__homeAuthEpoch;delete globalThis.__homeProfile
})
