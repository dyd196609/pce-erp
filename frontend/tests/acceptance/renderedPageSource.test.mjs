import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import {readRenderedPageSource,hasDirectListPageShell} from '../../scripts/pceRenderedPageSource.mjs'
const root=path.resolve('test-virtual-frontend')
function readVirtual(files) {return file=>{const key=path.relative(root,file).replaceAll('\\','/');assert.ok(Object.hasOwn(files,key),'Unexpected dependency '+key);return files[key]}}
test('rendered business content supplies list controls; unused imports and generic shells cannot',()=>{
 const files={'src/Page.vue':`import RealContent from './RealContent.vue'; import UnusedContent from './UnusedContent.vue'; import GenericShell from './GenericShell.vue'; <template><GenericShell><RealContent /></GenericShell></template>`,
 'src/RealContent.vue':'<template><PceEnterpriseListTable /></template>'}
 const result=readRenderedPageSource(root,'src/Page.vue',readVirtual(files))
 assert.deepEqual(result.files,['src/Page.vue','src/RealContent.vue'])
 assert.match(result.source,/<PceEnterpriseListTable/)
})
test('dependency cycles stop and rendered imports cannot escape frontend',()=>{
 const files={'src/AContent.vue':`import BContent from './BContent.vue'; <BContent />`,'src/BContent.vue':`import AContent from './AContent.vue'; <AContent />`}
 assert.equal(readRenderedPageSource(root,'src/AContent.vue',readVirtual(files)).files.length,2)
 assert.throws(()=>readRenderedPageSource(root,'src/Page.vue',()=>`import OutsideContent from '../../outside.vue'; <OutsideContent />`),/outside frontend/)
})
test('a direct page shell requires its exact shared import and module binding',()=>{
 const valid=`import PceListPageShell from '@/meta/components/PceListPageShell.vue'; <PceListPageShell :module-id="moduleId">`
 assert.equal(hasDirectListPageShell(valid),true)
 assert.equal(hasDirectListPageShell(valid.replace(':module-id','module-id')),false)
 assert.equal(hasDirectListPageShell(valid.replace("@/meta/components/",'./fake/')),false)
})
