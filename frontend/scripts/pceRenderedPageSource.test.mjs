import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import {readRenderedPageSource,hasDirectListPageShell} from './pceRenderedPageSource.mjs'
const root=process.cwd()
for(const name of ['OperationReport','OperationCompletion','OperationHandover','FinishedGoods'])test(name+' original page composes real business Content list',()=>{const r=readRenderedPageSource(root,'src/meta/pages/'+name+'Page.vue');assert.equal(r.files.length,2);assert.ok(r.source.includes('<PceEnterpriseListTable'));assert.ok(hasDirectListPageShell(r.source))})
test('unused imported Content cannot satisfy list checks',()=>{const r=readRenderedPageSource(root,'src/Unused.vue',()=>`<template><p>none</p></template><script>import FakeContent from './Fake.vue'</script>`);assert.equal(r.files.length,1);assert.ok(!r.source.includes('<PceEnterpriseListTable'))})
test('rendered content without list remains without controls',()=>{const sources=new Map([[path.resolve(root,'src/Empty.vue'),`<template><EmptyContent/></template><script>import EmptyContent from './EmptyContent.vue'</script>`],[path.resolve(root,'src/EmptyContent.vue'),'<template><p>no list</p></template>']]);const r=readRenderedPageSource(root,'src/Empty.vue',file=>sources.get(file));assert.equal(r.files.length,2);assert.ok(!r.source.includes('<PceEnterpriseListTable'))})
test('source outside frontend rejected',()=>assert.throws(()=>readRenderedPageSource(root,'../outside.vue',()=>''),/outside frontend/))
test('shell token without original import cannot pass',()=>assert.equal(hasDirectListPageShell('<PceListPageShell :module-id="x"/>'),false))
